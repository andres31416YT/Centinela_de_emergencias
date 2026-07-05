from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

import os
import time
import uuid
import json
import asyncio
import cv2
import numpy as np
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer

from app.model import load_model, predict_frame

app = FastAPI(title="Centinela de Emergencias - Fire Detection API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "kafka:9092")
KAFKA_FRAMES_TOPIC = os.getenv("KAFKA_FRAMES_TOPIC", "fire-frames")
KAFKA_RESULTS_TOPIC = os.getenv("KAFKA_RESULTS_TOPIC", "fire-results")
CONSUMER_GROUP_ID = os.getenv("CONSUMER_GROUP_ID", "fire-detector")

_model = None
_producer = None
_active_websockets = {}
_consumer_task = None

async def ensure_kafka():
    global _producer
    if _producer is None:
        _producer = AIOKafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP,
            max_request_size=10485760,
        )
        await _producer.start()
    return _producer

async def kafka_consumer_loop():
    global _model
    backoff = 1
    consumer = None
    while consumer is None:
        try:
            consumer = AIOKafkaConsumer(
                KAFKA_RESULTS_TOPIC,
                bootstrap_servers=KAFKA_BOOTSTRAP,
                auto_offset_reset="latest",
            )
            await consumer.start()
            print(f"[KAFKA] consumer started topic={KAFKA_RESULTS_TOPIC}")
            backoff = 1
        except Exception as e:
            print(f"[KAFKA] consumer not ready yet: {e}; retrying in {backoff}s")
            if consumer is not None:
                try:
                    await consumer.stop()
                except Exception:
                    pass
                consumer = None
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30)

    try:
        async for msg in consumer:
            try:
                payload = json.loads(msg.value)
                session_id = payload.get("session_id")
                ws = _active_websockets.get(session_id)
                if ws and ws.client_state.name == "OPEN":
                    await ws.send_json(payload)
            except Exception:
                pass
    finally:
        if consumer is not None:
            await consumer.stop()

@app.on_event("startup")
def startup_event():
    global _model, _consumer_task
    t0 = time.time()
    _model = load_model()
    print(f"[API] Modelo ResNet50 cargado en {time.time() - t0:.2f}s")

    async def start_background_tasks():
        await ensure_kafka()
        global _consumer_task
        if _consumer_task is None:
            _consumer_task = asyncio.create_task(kafka_consumer_loop())

    loop = asyncio.get_event_loop()
    loop.create_task(start_background_tasks())

@app.on_event("shutdown")
async def shutdown_event():
    global _consumer_task
    if _consumer_task:
        _consumer_task.cancel()
        try:
            await _consumer_task
        except Exception:
            pass
    if _producer:
        await _producer.stop()

@app.get("/health")
def health():
    return {"status": "ok", "model_loaded": _model is not None}

@app.post("/predict")
async def predict(request: Request):
    global _model
    if _model is None:
        return JSONResponse(status_code=503, content={"error": "Model not loaded"})

    content_type = request.headers.get("content-type", "")
    try:
        if "multipart/form-data" in content_type:
            form = await request.form()
            file = form.get("file")
            if file is None:
                return JSONResponse(status_code=400, content={"error": "No file provided"})
            contents = await file.read()
        else:
            contents = await request.body()

        nparr = np.frombuffer(contents, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if frame is None:
            return JSONResponse(status_code=400, content={"error": "Invalid image"})

        result = predict_frame(_model, frame)
        return JSONResponse(content=result)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.websocket("/ws/stream")
async def websocket_stream(websocket: WebSocket):
    global _model
    await websocket.accept()
    session_id = str(uuid.uuid4())
    print(f"[WS] accepted session={session_id}")
    _active_websockets[session_id] = websocket

    producer = await ensure_kafka()
    print(f"[KAFKA] producer ready bootstrap={KAFKA_BOOTSTRAP}")

    try:
        while True:
            print(f"[WS] waiting for bytes session={session_id} state={websocket.client_state.name}")
            try:
                data = await websocket.receive_bytes()
            except Exception as e:
                print(f"[WS] receive_bytes error session={session_id} error={e}")
                raise

            print(f"[WS] received bytes={len(data)} session={session_id}")
            if not data:
                break

            nparr = np.frombuffer(data, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if frame is None:
                print(f"[WS] invalid frame session={session_id}")
                await websocket.send_json({"error": "Invalid frame"})
                continue

            result = predict_frame(_model, frame)
            print(f"[WS] result={result} session={session_id}")
            try:
                await producer.send_and_wait(
                    KAFKA_RESULTS_TOPIC,
                    value=json.dumps({
                        "session_id": session_id,
                        "class": result["class"],
                        "confidence": result["confidence"],
                        "all": result["all"],
                    }).encode("utf-8"),
                )
                print(f"[KAFKA] sent topic={KAFKA_RESULTS_TOPIC} payload={result['class']} {result['confidence']} session={session_id}")
            except Exception as e:
                print(f"[KAFKA] send error session={session_id}: {e}")

            try:
                await websocket.send_json(result)
            except Exception as e:
                print(f"[WS] send_json error session={session_id}: {e}")
                raise
    except WebSocketDisconnect:
        print(f"[WS] disconnected session={session_id}")
    except Exception as e:
        print(f"[WS] error session={session_id}: {e}")
        try:
            await websocket.send_json({"error": str(e)})
        except Exception:
            pass
    finally:
        _active_websockets.pop(session_id, None)

app.mount("/static", StaticFiles(directory="/app/frontend"), name="static")

@app.get("/")
async def serve_frontend():
    with open("/app/frontend/index.html", "r") as f:
        return HTMLResponse(content=f.read())
