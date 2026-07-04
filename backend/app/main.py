from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

import os
import time
import cv2
import numpy as np

from app.model import load_model, predict_frame

app = FastAPI(title="Centinela de Emergencias - Fire Detection API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_model = None

@app.on_event("startup")
def startup_event():
    global _model
    t0 = time.time()
    _model = load_model()
    print(f"[API] Modelo ResNet50 cargado en {time.time() - t0:.2f}s")

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
    try:
        while True:
            data = await websocket.receive_bytes()
            if not data:
                break

            nparr = np.frombuffer(data, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if frame is None:
                await websocket.send_json({"error": "Invalid frame"})
                continue

            result = predict_frame(_model, frame)
            await websocket.send_json(result)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({"error": str(e)})
        except Exception:
            pass

app.mount("/static", StaticFiles(directory="/app/frontend"), name="static")

@app.get("/")
async def serve_frontend():
    with open("/app/frontend/index.html", "r") as f:
        return HTMLResponse(content=f.read())
