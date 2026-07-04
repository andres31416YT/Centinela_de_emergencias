# PROYECTO - CENTINELA DE EMERGENCIAS

---

## Descripción del Proyecto
**Centinela de Emergencias** es un sistema de detección automática de incendios forestales basado en técnicas de aprendizaje profundo y visión por computadora. El proyecto aborda el problema crítico de la detección temprana de incendios en zonas boscosas, donde los minutos de respuesta marcan la diferencia entre un conato controlable y una catástrofe ambiental.

> *Centinela de Emergencias busca minimizar el tiempo de respuesta ante desastres forestales para salvar los ecosistemas.*

---

### Equipo de Trabajo

| Integrantes |
| :--- |
| **Arroyo Terán**, Peter Álvaro |
| **Pagan Roncall**, Andres Antonio |
| **Tandaypan Segura**, Matthew Alexander |
| **Baldeon Julca**, Rodrigo |
| **Yon Alva**, Carlos |

---

## Despliegue Local con Docker

### Requisitos previos
- Docker Engine >= 24.0
- Docker Compose v2
- (Opcional) ngrok para exponer el servicio a internet
- (Opcional) GPU NVIDIA con CUDA para inferencia acelerada

### Estructura del proyecto
```
Centinela_de_emergencias/
├── ML/
│   ├── Dataset/               # Dataset de entrenamiento
│   ├── metrics/               # Métricas y curvas de entrenamiento
│   └── models/
│       └── resnet50/optimal/  # Modelo ResNet50 fine-tuneado (best_model.pt)
├── backend/
│   ├── app/
│   │   ├── main.py           # API FastAPI + WebSocket
│   │   └── model.py          # Carga y preprocesamiento del modelo
│   └── requirements.txt
├── frontend/
│   ├── index.html
│   ├── app.js
│   └── style.css
├── Dockerfile.api
├── docker-compose.yml
└── deploy_local.sh
```

### 1. Levantar el servicio

```bash
# Clonar el repositorio
git clone <repo-url>
cd Centinela_de_emergencias

# Hacer ejecutable el script de deploy (si es necesario)
chmod +x deploy_local.sh

# Levantar con Docker
./deploy_local.sh
```

O manualmente:
```bash
docker compose build
docker compose up -d
```

### 2. Verificar funcionamiento

```bash
curl http://localhost:8000/health
```

Deberías ver:
```json
{"status":"ok","model_loaded":true}
```

### 3. Acceder al frontend

Abre tu navegador en:
```
http://localhost:8000
```

Allí puedes:
- Visualizar el stream de video (usa la cámara local para probar)
- Ver predicciones en tiempo real sobre el video
- Revisar alertas de detección de fuego y humo

### 4. Configurar ngrok

Crea un archivo `.env` a partir del ejemplo:

```bash
cp .env.example .env
```

Edita `.env` y coloca tu token de ngrok:

```
NGROK_AUTHTOKEN=tu_token_aqui
```

Para obtener tu token:
1. Crea una cuenta en https://dashboard.ngrok.com/signup
2. Ve a https://dashboard.ngrok.com/get-started/your-authtoken
3. Copia el token y pégalo en `.env`

### 5. Exponer a internet con ngrok (para dron)

Ejecuta:

```bash
ngrok http 8000
```

Esto te dará una URL pública tipo `https://xxxx.ngrok-free.app`.

#### Configuración del dron/gateway

El dron debe enviar frames JPEG por POST o por WebSocket a la URL pública:

**Opción A: POST HTTP** (recomendado para integración simple)
```
POST https://xxxx.ngrok-free.app/predict
Content-Type: multipart/form-data
<file: frame_jpeg>
```

Respuesta:
```json
{
  "class": "Fire",
  "confidence": 0.9856,
  "all": {
    "Fire": 0.9856,
    "Normal": 0.0102,
    "Smoke": 0.0042
  }
}
```

**Opción B: WebSocket** (para stream continuo)
```
ws://xxxx.ngrok-free.app/ws/stream
```

El dron envía frames JPEG como mensajes binarios por el WebSocket y recibe JSON por cada frame procesado.

### 6. Detener el servicio

```bash
docker compose down
```

---

## Arquitectura

```
┌─────────────┐      HTTPS/WS      ┌──────────────────┐     ResNet50     ┌───────────┐
│   Dron      │ ─────────────────► │  ngrok Tunnel    │ ───────────────► │ Backend   │
│ (frames     │                    │  (tu máquina)    │                 │ (Docker)  │
│  JPEG)      │ ◄───────────────── │  localhost:8000  │ ◄────────────── │           │
└─────────────┘    JSON predicción └──────────────────┘    alerta/log  └─────┬─────┘
                                                                              │
                                                                        http://localhost:8000
                                                                              │
                                                                       ┌──────▼──────┐
                                                                       │ Frontend    │
                                                                       │ (monitoreo) │
                                                                       └─────────────┘
```

---

## Modelo Utilizado

**ResNet50** fine-tuneado con 3 clases:
- `Fire` (Fuego)
- `Normal` (Normal)
- `Smoke` (Humo)

Precisión en test: **99.47%** (F1-weighted: 0.9947)

---

## Troubleshooting

### El modelo no carga
Verifica que `ML/models/resnet50/optimal/best_model.pt` exista. El volumen en docker-compose lo monta como read-only.

### Bajo FPS en CPU
ResNet50 sin GPU puede procesar ~1-2 FPS en CPU. Si necesitas más:
1. Usa GPU NVIDIA (el compose incluye soporte CUDA)
2. Cuantiza el modelo a INT8
3. Cambia a MobileNetV3 (más liviano, ~98.5% accuracy)

### ngrok se desconecta
ngrok free puede cambiar la URL al reiniciar. Considera usar un plan pago o un dominio propio.

---

## Repositorio

`feature` - Rama actual con modelos entrenados y pipeline de despliegue
