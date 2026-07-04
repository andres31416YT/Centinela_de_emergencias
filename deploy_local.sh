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

if [ -n "$NGROK_AUTHTOKEN" ] && [ "$NGROK_AUTHTOKEN" != "tu_token_aqui" ] && command -v ngrok &> /dev/null; then
    echo ""
    echo "=== Iniciando tunel ngrok ==="
    echo "Region: ${NGROK_REGION:-us}"
    ngrok config add-authtoken "$NGROK_AUTHTOKEN" >/dev/null 2>&1 || true
    nohup ngrok http "$NGROK_CONTAINER_PORT" --region="${NGROK_REGION:-us}" > ngrok.log 2>&1 &
    echo "ngrok iniciado. URL publica en unos segundos..."
    echo "Ver URL: tail -f ngrok.log"
elif [ -z "$NGROK_AUTHTOKEN" ] || [ "$NGROK_AUTHTOKEN" = "tu_token_aqui" ]; then
    echo ""
    echo "=== Para exponer a internet con ngrok ==="
    echo "Edita .env y coloca tu NGROK_AUTHTOKEN"
    echo "O ejecuta manualmente:"
    echo "    ngrok http 8000"
else
    echo ""
    echo "=== Para exponer a internet con ngrok ==="
    echo "Instala ngrok y ejecuta:"
    echo "    ngrok http 8000"
fi

echo ""
echo "Para detener: docker compose down"
