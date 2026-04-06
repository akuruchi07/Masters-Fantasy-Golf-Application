const API = `http://${window.location.hostname}:8000/api`;

async function jget(path) {
  const res = await fetch(`${API}${path}`);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `GET ${path} failed`);
  return data;
}

async function jpost(path, body) {
  const res = await fetch(`${API}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `POST ${path} failed`);
  return data;
}

export const api = {
  field: (limit = 50) => jget(`/field?limit=${limit}`),
  join: (userId, name) => jpost("/join", { userId, name }),
  state: () => jget("/state"),
  startDraft: (userId, cfg) => jpost("/draft/start", { userId, ...cfg }),
  resetDraft: (userId) => jpost("/draft/reset", { userId }),
  pick: (userId, athleteId, name) =>
    jpost("/draft/pick", { userId, athlete_id: athleteId, name }),
  playerHoles: (athleteId) => jget(`/player/${athleteId}/holes`),
  tournamentLeaderboard: () => jget("/tournament-leaderboard"),
};