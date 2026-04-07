const API =
  import.meta.env.VITE_API_BASE_URL ||
  `http://${window.location.hostname}:8000/api`;

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
  field: (limit = 0) => jget(`/field?limit=${limit}`),
  join: (userId, name) => jpost("/join", { userId, name }),
  state: () => jget("/state"),
  scoreboard: () => jget("/scoreboard"),
  startDraft: (userId, cfg) => jpost("/draft/start", { userId, ...cfg }),
  resetDraft: (userId) => jpost("/draft/reset", { userId }),
  updateTimer: (userId, secondsPerPick) =>
    jpost("/draft/timer", { userId, seconds_per_pick: secondsPerPick }),
  autoPick: (userId) => jpost("/draft/auto-pick", { userId }),
  pick: (userId, athleteId, name, slot = null) =>
    jpost("/draft/pick", { userId, athlete_id: athleteId, name, slot }),
  eligibleSlots: (userId, athleteId) =>
    jget(`/draft/eligible-slots/${athleteId}?userId=${encodeURIComponent(userId)}`),
  playerHoles: (athleteId) => jget(`/player/${athleteId}/holes`),
  tournamentLeaderboard: () => jget("/tournament-leaderboard"),
};