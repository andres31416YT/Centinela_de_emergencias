#!/bin/bash
set -e

cd "$(dirname "$0")"

echo "=== Centinela de Emergencias - Deploy Local ==="
echo ""

if ! command -v docker &> /dev/null; then
    echo "ERROR: Docker no está instalado."
    exit 1
fi

if ! command -v docker compose &> /dev/null; then
    echo "ERROR: Docker Compose no está instalado."
    exit 1
fi

if [ -f ".env" ]; then
    set -a
    source .env
    set +a
fi

echo "[0/3] Verificando GPU NVIDIA..."
if ! command -v nvidia-smi &> /dev/null || ! nvidia-smi -L > /dev/null 2>&1; then
    echo "ADVERTENCIA: No se detectó GPU NVIDIA. El modelo correrá en CPU (más lento)."
else
    echo "GPU detectada:"
    nvidia-smi -L | sed 's/^/  /'
fi

echo ""
echo "[1/3] Building Docker image..."
docker compose build

echo ""
echo "[2/3] Starting containers..."
docker compose up -d

echo ""
echo "[3/3] Esperando API..."
for i in {1..30}; do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo "API lista en http://localhost:8000"
        break
    fi
    sleep 1
done

echo ""
echo "=== Estado ==="
docker compose ps

echo ""
echo "=== Acceso ==="
echo "Frontend local: http://localhost:8000"
echo "API docs:       http://localhost:8000/docs"
echo "Health check:   http://localhost:8000/health"

if [ -n "$NGROK_AUTHTOKEN" ] && [ "$NGROK_AUTHTOKEN" != "tu_token_aqui" ]; then
    echo ""
    echo "=== Tunel ngrok (Docker) ==="
    PUBLIC_URL=$(curl -s http://localhost:4040/api/tunnels | grep -oE 'https://[a-zA-Z0-9-]+\.ngrok(-free)?\.app' | head -1)
    if [ -n "$PUBLIC_URL" ]; then
        echo "URL publica: $PUBLIC_URL"
    else
        echo "Revisa los logs: docker compose logs ngrok"
    fi
else
    echo ""
    echo "=== Para exponer a internet con ngrok ==="
    echo "Edita .env y coloca tu NGROK_AUTHTOKEN"
fi

echo ""
echo "Para detener: docker compose down"
