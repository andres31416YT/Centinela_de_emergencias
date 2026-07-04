(function () {
    const video = document.getElementById('video');
    const canvas = document.getElementById('overlay');
    const ctx = canvas.getContext('2d');
    const statusEl = document.getElementById('status');
    const alertsEl = document.getElementById('alerts');
    const alertCountEl = document.getElementById('alertCount');
    const fpsEl = document.getElementById('fps');
    const lastPredictionEl = document.getElementById('lastPrediction');

    const WS_URL = `ws://${location.host}/ws/stream`;
    let ws = null;
    let streaming = false;
    let alertCount = 0;
    let lastFrameTime = performance.now();
    let frameCount = 0;

    function connectWebSocket() {
        ws = new WebSocket(WS_URL);
        ws.binaryType = 'arraybuffer';

        ws.onopen = () => {
            statusEl.textContent = 'Conectado';
            statusEl.classList.add('connected');
            streaming = true;
            sendFrame();
        };

        ws.onclose = () => {
            statusEl.textContent = 'Desconectado';
            statusEl.classList.remove('connected');
            streaming = false;
            setTimeout(connectWebSocket, 2000);
        };

        ws.onerror = () => {
            statusEl.textContent = 'Error de conexión';
        };

        ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                if (data.error) return;
                drawPrediction(data);
                updateStats(data);
                if (data.class === 'Fire' || data.class === 'Smoke') {
                    addAlert(data);
                }
            } catch (e) {
                console.error('Error parsing message:', e);
            }
        };
    }

    function sendFrame() {
        if (!streaming || !ws || ws.readyState !== WebSocket.OPEN) return;

        if (video.readyState >= 2) {
            canvas.width = video.videoWidth || 640;
            canvas.height = video.videoHeight || 480;
            ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

            try {
                canvas.toBlob((blob) => {
                    if (blob && ws.readyState === WebSocket.OPEN) {
                        blob.arrayBuffer().then((buf) => ws.send(buf));
                    }
                }, 'image/jpeg', 0.8);
            } catch (e) {
                // Canvas tainted or not ready
            }
        }

        setTimeout(sendFrame, 100);
    }

    function drawPrediction(data) {
        ctx.fillStyle = 'transparent';
        ctx.fillRect(0, 0, canvas.width, canvas.height);

        ctx.font = 'bold 24px sans-serif';
        ctx.fillStyle = data.class === 'Fire' ? '#dc2626' : data.class === 'Smoke' ? '#f59e0b' : '#22c55e';
        ctx.fillText(`${data.class}: ${(data.confidence * 100).toFixed(1)}%`, 20, 40);

        if (data.class === 'Fire') {
            statusEl.classList.add('alert');
            setTimeout(() => statusEl.classList.remove('alert'), 1000);
        }
    }

    function updateStats(data) {
        frameCount++;
        const now = performance.now();
        if (now - lastFrameTime >= 1000) {
            fpsEl.textContent = `FPS: ${frameCount}`;
            frameCount = 0;
            lastFrameTime = now;
        }
        lastPredictionEl.textContent = `Última predicción: ${data.class} (${(data.confidence * 100).toFixed(1)}%)`;
    }

    function addAlert(data) {
        const div = document.createElement('div');
        div.className = `alert-item ${data.class.toLowerCase()}`;
        const time = new Date().toLocaleTimeString();
        div.innerHTML = `<span>${data.class} detectado - Confianza: ${(data.confidence * 100).toFixed(1)}%</span><span class="timestamp">${time}</span>`;
        alertsEl.prepend(div);
        alertCount++;
        alertCountEl.textContent = alertCount;

        while (alertsEl.children.length > 50) {
            alertsEl.removeChild(alertsEl.lastChild);
        }
    }

    document.getElementById('btnCamera').addEventListener('click', async () => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 } });
            video.srcObject = stream;
            if (!ws || ws.readyState === WebSocket.CLOSED) {
                connectWebSocket();
            }
        } catch (e) {
            alert('No se pudo acceder a la cámara local: ' + e.message);
        }
    });

    document.getElementById('btnStop').addEventListener('click', () => {
        if (ws) ws.close();
        if (video.srcObject) {
            video.srcObject.getTracks().forEach(t => t.stop());
            video.srcObject = null;
        }
        streaming = false;
        statusEl.textContent = 'Detenido';
        statusEl.classList.remove('connected');
        ctx.fillStyle = '#000';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
    });

    ctx.fillStyle = '#000';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    connectWebSocket();
})();
