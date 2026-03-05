const API = "http://localhost:8000/api";

async function jget(path) {
  const res = await fetch(`${API}${path}`);
  if (!res.ok) {
    let err = {};
    try { err = await res.json(); } catch {}
    throw new Error(err.detail || `GET ${path} failed`);
  }
  return res.json();
}

async function jpost(path, body) {
  const res = await fetch(`${API}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    let err = {};
    try { err = await res.json(); } catch {}
    throw new Error(err.detail || `POST ${path} failed`);
  }
  return res.json();
}

export const api = {
  health: () => jget("/health"),
  field: (limit = 50) => jget(`/field?limit=${limit}`),
  teams: () => jget("/teams"),
  draft: (team, athleteId, playerName) =>
    jpost("/draft", { team, athlete_id: athleteId, player_name: playerName }),
  scoreboard: () => jget("/draft/scoreboard"),
  playerHoles: (athleteId) => jget(`/player/${athleteId}/holes`),
};