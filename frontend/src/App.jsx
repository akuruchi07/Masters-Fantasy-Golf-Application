import { useEffect, useMemo, useState } from "react";
import { api } from "./api";
import { connectWS } from "./ws";

function uuid() {
  // Works on modern browsers
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();

  // Works on most browsers that have getRandomValues
  if (globalThis.crypto?.getRandomValues) {
    const a = new Uint8Array(16);
    globalThis.crypto.getRandomValues(a);
    a[6] = (a[6] & 0x0f) | 0x40;
    a[8] = (a[8] & 0x3f) | 0x80;
    const hex = [...a].map(b => b.toString(16).padStart(2, "0")).join("");
    return `${hex.slice(0,8)}-${hex.slice(8,12)}-${hex.slice(12,16)}-${hex.slice(16,20)}-${hex.slice(20)}`;
  }

  // Last resort fallback
  return `uid-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function getOrCreateUserId() {
  const key = "masters_userId";
  let v = localStorage.getItem(key);
  if (!v) {
    v = uuid();
    localStorage.setItem(key, v);
  }
  return v;
}

export default function App() {
  const userId = useMemo(() => getOrCreateUserId(), []);
  const [name, setName] = useState(localStorage.getItem("masters_name") || "");
  const [joined, setJoined] = useState(false);

  const [field, setField] = useState([]);
  const [room, setRoom] = useState(null);
  const [scoreboard, setScoreboard] = useState(null);

  const [query, setQuery] = useState("");
  const [holeModal, setHoleModal] = useState(null);
  const [error, setError] = useState("");
  const [tournamentLeaderboard, setTournamentLeaderboard] = useState([]);

  useEffect(() => {
    if (!joined) return;

    let intervalId;

    (async () => {
      try {
        const f = await api.field(50);
        setField(f.players || []);
        const lb = await api.tournamentLeaderboard();
        setTournamentLeaderboard(lb.leaderboard || []);
      } catch (e) {
        console.error("initial load failed:", e);
      }
    })();

    intervalId = setInterval(async () => {
      try {
        const lb = await api.tournamentLeaderboard();
        setTournamentLeaderboard(lb.leaderboard || []);
      } catch (e) {
        console.error("leaderboard refresh failed:", e);
      }
    }, 15000);

    const ws = connectWS(userId, (msg) => {
      if (msg.type === "room_state") setRoom(msg.data);
      if (msg.type === "scoreboard") setScoreboard(msg.data);
      if (msg.type === "error") console.log("WS error:", msg.data);
    });

    return () => {
      clearInterval(intervalId);
      ws.close();
    };
  }, [joined, userId]);

  const me = useMemo(() => {
    const users = room?.users || [];
    return users.find((u) => u.userId === userId) || null;
  }, [room, userId]);

  const myTeam = useMemo(() => {
    if (!me || !scoreboard?.teams) return null;
    return scoreboard.teams[me.name] || null;
  }, [me, scoreboard]);

  const draft = room?.draft;
  const picked = useMemo(() => new Set(draft?.picked || []), [draft]);

  const available = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (field || [])
      .filter((p) => !picked.has(p.athleteId))
      .filter((p) => (q ? p.name.toLowerCase().includes(q) : true));
  }, [field, picked, query]);

  const leagueStandings = useMemo(() => {
    if (!scoreboard?.teams) return [];
    return Object.entries(scoreboard.teams)
      .map(([teamName, data]) => ({
        teamName,
        total: data.total || 0,
        players: data.players || [],
      }))
      .sort((a, b) => b.total - a.total);
  }, [scoreboard]);

  const onClock = draft?.currentTeam;
  const isMyTurn =
    !!me && draft?.started && !draft?.completed && onClock === me.name;

  async function doJoin() {
    setError("");
    const nm = name.trim();
    if (!nm) {
      setError("Enter your name to join.");
      return;
    }
    localStorage.setItem("masters_name", nm);
    try {
      await api.join(userId, nm);
      setJoined(true);
    } catch (e) {
      setError(e.message);
    }
  }

  async function startDraft() {
    setError("");
    try {
      await api.startDraft(userId, {
        seconds_per_pick: 60,
        roster_size: 6,
        snake: true,
        auto_pick: true,
      });
    } catch (e) {
      setError(e.message);
    }
  }

  async function draftPlayer(player) {
    setError("");
    if (!isMyTurn) return;
    try {
      await api.pick(userId, player.athleteId, player.name);
    } catch (e) {
      setError(e.message);
    }
  }

  async function openHoles(athleteId, playerName) {
    const data = await api.playerHoles(athleteId);
    setHoleModal({ athleteId, name: playerName, ...data });
  }

  if (!joined) {
    return (
      <div className="page">
        <div className="card" style={{ maxWidth: 520, margin: "80px auto" }}>
          <h1 style={{ marginTop: 0 }}>Join the Draft</h1>
          <p className="muted">
            Enter your name to enter the lobby. The host will start the draft.
          </p>

          <input
            className="input"
            placeholder="Your name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") doJoin();
            }}
            style={{ width: "100%" }}
          />

          {error && <div className="error">{error}</div>}

          <button
            className="btn primary"
            onClick={doJoin}
            style={{ marginTop: 12, width: "100%" }}
          >
            Continue
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="page">
      <header className="topbar">
        <div>
          <h1 className="h1">Masters Draft Room</h1>
          <div className="muted">
            You are: <b>{me?.name || "…"}</b>{" "}
            {me?.isHost ? <span className="pillHost">HOST</span> : null}
            {" • "}
            {draft?.started
              ? draft.completed
                ? "Draft complete"
                : `On the clock: ${draft.currentTeam} • Pick ${draft.pickNo}/${draft.totalPicks} • ${draft.secondsLeft}s`
              : "Lobby (draft not started)"}
          </div>
        </div>

        <div className="actions">
          {me?.isHost && !draft?.started && (
            <button className="btn primary" onClick={startDraft}>
              Start Draft (Randomize Order)
            </button>
          )}
        </div>
      </header>

      {error && (
        <div className="error" style={{ marginBottom: 10 }}>
          {error}
        </div>
      )}

      <div className="layout">
        <section className="card">
          <h2 className="h2">Players in Lobby</h2>
          <div className="list lobbyList">
            {(room?.users || []).map((u) => (
              <div className="row" key={u.userId}>
                <div className="name">
                  {u.name}{" "}
                  {u.isHost ? <span className="pillHost">HOST</span> : null}
                </div>
              </div>
            ))}
            {(room?.users || []).length === 0 && (
              <div className="empty">No one yet.</div>
            )}
          </div>

          <div
            style={{
              marginTop: 12,
              display: "flex",
              alignItems: "baseline",
              justifyContent: "space-between",
            }}
          >
            <h2>Available (Top 50)</h2>
            <div className="pill">
              {draft?.started
                ? isMyTurn
                  ? "Your turn"
                  : `Waiting: ${onClock}`
                : "Waiting for host"}
            </div>
          </div>

          <input
            className="input"
            placeholder="Search..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />

          <div className="list">
            {available.map((p) => (
              <div
                className={`row ${isMyTurn ? "clickable" : ""}`}
                key={p.athleteId}
                onClick={() => isMyTurn && draftPlayer(p)}
                title={isMyTurn ? "Click to draft" : "Not your turn"}
              >
                <div>
                  <div className="name">{p.name}</div>
                  <div className="meta">ID: {p.athleteId}</div>
                </div>
                <div className="pill">{isMyTurn ? "Draft" : "—"}</div>
              </div>
            ))}
            {available.length === 0 && (
              <div className="empty">No available players.</div>
            )}
          </div>
        </section>

        {/* Right: dashboard */}
        <section className="teams">
          {/* MY TEAM */}
          <div className="card">
            <div className="teamHeader">
              <h2>My Team</h2>
              <div className="total">Total: {myTeam?.total ?? 0}</div>
            </div>

            <div className="list">
              {(myTeam?.players || []).map((p) => (
                <div className="row" key={p.athleteId}>
                  <div
                    className="clickableName"
                    onClick={() => openHoles(p.athleteId, p.name)}
                  >
                    <div className="name">{p.name}</div>
                    <div className="meta">Click for hole-by-hole</div>
                  </div>
                  <div className="pts">{p.fantasyPoints ?? 0}</div>
                </div>
              ))}
            </div>
          </div>

          {/* LEAGUE STANDINGS */}
          <div className="card">
            <h2>League Standings</h2>
            <div className="list">
              {leagueStandings.map((team, idx) => (
                <div className="row" key={team.teamName}>
                  <div>
                    <div className="name">
                      #{idx + 1} {team.teamName}
                    </div>
                    <div className="meta">
                      {team.players.map((p) => p.name).join(", ")}
                    </div>
                  </div>
                  <div className="pts">{team.total}</div>
                </div>
              ))}
            </div>
          </div>

          {/* TOURNAMENT LEADERBOARD */}
          <div className="card">
            <h2>Tournament Leaderboard</h2>
            <div className="list">
              {tournamentLeaderboard.slice(0, 25).map((player, idx) => (
                <div className="row" key={`${player.golfer_name}-${idx}`}>
                  <div>
                    <div className="name">
                      #{idx + 1} {player.golfer_name}
                    </div>
                    <div className="meta">
                      Base: {player.base_points} • Bonus: {player.bonus_points}
                    </div>
                  </div>
                  <div className="pts">{player.fantasy_points}</div>
                </div>
              ))}
            </div>
          </div>
        </section>
      </div>

      <section className="card picksCard">
        <h2 className="h2">Pick History</h2>
        <div className="picks">
          {(draft?.picks || []).map((p) => (
            <div className="pick" key={`${p.pickNo}-${p.athleteId}`}>
              <div className="pickNo">#{p.pickNo}</div>
              <div className="pickBody">
                <div className="pickName">{p.name}</div>
                <div className="pickMeta">{p.team}</div>
              </div>
            </div>
          ))}
          {(draft?.picks || []).length === 0 && (
            <div className="empty">No picks yet.</div>
          )}
        </div>
      </section>

      {holeModal && (
        <div className="modalBackdrop" onClick={() => setHoleModal(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modalHeader">
              <div>
                <div className="modalTitle">{holeModal.name}</div>
                <div className="muted">
                  Fantasy points: {holeModal.fantasyPoints ?? 0}
                </div>
              </div>
              <button className="btn" onClick={() => setHoleModal(null)}>
                Close
              </button>
            </div>

            <div className="holes">
              {(holeModal.holes || []).map((h) => (
                <div className="holeRow" key={`${h.round}-${h.hole}`}>
                  <div>R{h.round}</div>
                  <div>Hole {h.hole}</div>
                  <div>Par {h.par ?? "-"}</div>
                  <div>Strokes {h.strokes ?? "-"}</div>
                  <div className="pill">{h.result}</div>
                  <div className="pts">{h.points}</div>
                </div>
              ))}
              {(holeModal.holes || []).length === 0 && (
                <div className="empty">
                  Hole-by-hole provider is currently stubbed.
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
