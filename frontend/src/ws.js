export function connectWS(userId, onMsg) {
  const WS_URL = `ws://${window.location.hostname}:8000/ws?userId=${encodeURIComponent(userId)}`;
  const ws = new WebSocket(WS_URL);

  ws.onopen = () => {
    const t = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) ws.send("ping");
    }, 10000);
    ws._pingTimer = t;
  };

  ws.onmessage = (evt) => {
    try { onMsg(JSON.parse(evt.data)); } catch {}
  };

export const api = {
  field: (limit = 50) => jget(`/field?limit=${limit}`),
  join: (userId, name) => jpost("/join", { userId, name }),
  state: () => jget("/state"),
  startDraft: (userId, cfg) => jpost("/draft/start", { userId, ...cfg }),
  resetDraft: (userId) => jpost("/draft/reset", { userId }),
  pick: (userId, athleteId, name) => jpost("/draft/pick", { userId, athlete_id: athleteId, name }),
  playerHoles: (athleteId) => jget(`/player/${athleteId}/holes`),
};

export function connectWS(userId, onMessage) {
  const ws = new WebSocket(`ws://127.0.0.1:8000/ws?userId=${encodeURIComponent(userId)}`);

  ws.onopen = () => {
    console.log("WebSocket connected");
  };

  ws.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    if (onMessage) onMessage(msg);
  };

  ws.onclose = () => {
    console.log("WebSocket disconnected");
  };

  ws.onerror = (err) => {
    console.error("WebSocket error:", err);
  };

  return ws;
}