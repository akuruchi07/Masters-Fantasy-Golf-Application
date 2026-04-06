const WS_URL = `ws://${window.location.hostname}:8000/ws`;

export function connectWS(userId, onMessage) {
  const ws = new WebSocket(`${WS_URL}?userId=${encodeURIComponent(userId)}`);

  ws.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data);
      onMessage?.(msg);
    } catch (err) {
      console.error("Failed to parse websocket message:", err);
    }
  };

  ws.onopen = () => {
    console.log("WebSocket connected");
  };

  ws.onclose = () => {
    console.log("WebSocket disconnected");
  };

  ws.onerror = (err) => {
    console.error("WebSocket error:", err);
  };

  return ws;
}