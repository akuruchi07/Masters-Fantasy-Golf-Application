import { useEffect, useMemo, useState } from "react";
import { api } from "./api";

export default function App() {
  const [field, setField] = useState([]);
  const [teams, setTeams] = useState([]);
  const [draft, setDraft] = useState({});
  const [picked, setPicked] = useState(new Set());
  const [scoreboard, setScoreboard] = useState(null);
  const [query, setQuery] = useState("");

  async function refreshDraftState() {
    const t = await api.teams();
    setTeams(t.teams || []);
    setDraft(t.draft || {});
    setPicked(new Set(t.picked || []));
  }

  async function refreshScoreboard() {
    const sb = await api.scoreboard();
    setScoreboard(sb);
  }

  useEffect(() => {
    (async () => {
      const f = await api.field(50);
      setField(f.players || []);
      await refreshDraftState();
      await refreshScoreboard();
    })();

    const interval = setInterval(refreshScoreboard, 15000);
    return () => clearInterval(interval);
  }, []);

  const available = useMemo(() => {
    const q = query.trim().toLowerCase();
    return field
      .filter((p) => !picked.has(p.athleteId))
      .filter((p) => (q ? p.name.toLowerCase().includes(q) : true));
  }, [field, picked, query]);

  async function onDraft(team, player) {
    try {
      await api.draft(team, player.athleteId, player.name);
      await refreshDraftState();
      await refreshScoreboard();
    } catch (e) {
      alert(e.message);
    }
  }

  return (
    <div className="page">
      <header className="header">
        <div>
          <h1>Masters Draft Board</h1>
          <p className="sub">
            Draft your top 50, then track fantasy scoring. (Scoring endpoint is stubbed until you wire hole-by-hole.)
          </p>
        </div>
        <button className="btn" onClick={async () => { await refreshDraftState(); await refreshScoreboard(); }}>
          Refresh
        </button>
      </header>

      <div className="grid">
        <section className="card">
          <h2>Available Players</h2>
          <input
            className="input"
            placeholder="Search..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <div className="list">
            {available.map((p) => (
              <div className="row" key={p.athleteId}>
                <div>
                  <div className="name">{p.name}</div>
                  <div className="meta">ID: {p.athleteId}</div>
                </div>

                <select className="select" defaultValue="" onChange={(e) => {
                  const team = e.target.value;
                  if (team) onDraft(team, p);
                  e.target.value = "";
                }}>
                  <option value="" disabled>Draft →</option>
                  {teams.map((t) => <option key={t} value={t}>{t}</option>)}
                </select>
              </div>
            ))}
            {available.length === 0 && <div className="empty">No available players.</div>}
          </div>
        </section>

        <section className="teams">
          {teams.map((team) => {
            const roster = draft[team] || [];
            const live = scoreboard?.teams?.[team];
            return (
              <div className="card" key={team}>
                <div className="teamHeader">
                  <h2>{team}</h2>
                  <div className="total">Total: {live?.total ?? 0}</div>
                </div>

                <div className="list">
                  {roster.map((p) => {
                    const pts = live?.players?.find(x => x.athleteId === p.athleteId)?.fantasyPoints ?? 0;
                    return (
                      <div className="row" key={p.athleteId}>
                        <div>
                          <div className="name">{p.name}</div>
                          <div className="meta">ID: {p.athleteId}</div>
                        </div>
                        <div className="pts">{pts}</div>
                      </div>
                    );
                  })}
                  {roster.length === 0 && <div className="empty">No picks yet.</div>}
                </div>
              </div>
            );
          })}
        </section>
      </div>

      <footer className="footer">
        Tip: once hole-by-hole is wired, you can click a player to open a modal with per-hole scoring.
      </footer>
    </div>
  );
}