import { useEffect, useMemo, useState } from "react";
import { api } from "./api";
import { connectWS } from "./ws";

function uuid() {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();
  if (globalThis.crypto?.getRandomValues) {
    const a = new Uint8Array(16);
    globalThis.crypto.getRandomValues(a);
    a[6] = (a[6] & 0x0f) | 0x40;
    a[8] = (a[8] & 0x3f) | 0x80;
    const hex = [...a].map((b) => b.toString(16).padStart(2, "0")).join("");
    return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
  }
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

function getCategoryTags(player) {
  const tags = [];
  if (player.isPastChampion) tags.push("Past Champion");
  if (player.isInternational) tags.push("International");
  if (player.isAmerican) tags.push("American");
  if (player.isNonPga) tags.push("Non-PGA");
  return tags;
}

function playerMatchesFilter(player, filter) {
  if (filter === "all") return true;
  if (filter === "past_champion") return !!player.isPastChampion;
  if (filter === "international") return !!player.isInternational;
  if (filter === "american") return !!player.isAmerican;
  if (filter === "non_pga") return !!player.isNonPga;
  return true;
}

export default function App() {
  const userId = useMemo(() => getOrCreateUserId(), []);
  const [name, setName] = useState(localStorage.getItem("masters_name") || "");
  const [joined, setJoined] = useState(false);

  const [field, setField] = useState([]);
  const [room, setRoom] = useState(null);
  const [scoreboard, setScoreboard] = useState(null);

  const [query, setQuery] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [holeModal, setHoleModal] = useState(null);
  const [slotModal, setSlotModal] = useState(null);
  const [error, setError] = useState("");
  const [tournamentLeaderboard, setTournamentLeaderboard] = useState([]);
  const [timerInput, setTimerInput] = useState(60);
  const [viewMode, setViewMode] = useState("auto");

  const draft = room?.draft;

  useEffect(() => {
    if (draft?.secondsPerPick) {
      setTimerInput(draft.secondsPerPick);
    }
  }, [draft?.secondsPerPick]);

  useEffect(() => {
    if (!joined) return;

    let intervalId;

    (async () => {
      try {
        const f = await api.field(50);
        setField(f.players || []);
        const s = await api.state();
        setRoom(s);
        const sb = await api.scoreboard();
        setScoreboard(sb);
        const lb = await api.tournamentLeaderboard();
        setTournamentLeaderboard(lb.leaderboard || []);
      } catch (e) {
        console.error("initial load failed:", e);
        setError(e.message || "Failed to load app data.");
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

  const slotLabels = room?.slotLabels || {};
  const picked = useMemo(() => new Set(draft?.picked || []), [draft]);
  const myRoster = me ? draft?.rosters?.[me.name]?.slots || {} : {};
  const myTeam = useMemo(() => {
    if (!me || !scoreboard?.teams) return null;
    return scoreboard.teams[me.name] || null;
  }, [me, scoreboard]);

  const available = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (field || [])
      .filter((p) => !picked.has(p.athleteId))
      .filter((p) => playerMatchesFilter(p, categoryFilter))
      .filter((p) => (q ? p.name.toLowerCase().includes(q) : true));
  }, [field, picked, query, categoryFilter]);

  const leagueStandings = useMemo(() => {
    if (!scoreboard?.teams) return [];
    return Object.entries(scoreboard.teams)
      .map(([teamName, data]) => ({
        teamName,
        total: data.total || 0,
        players: data.players || [],
        missedStarterSlots: data.missedStarterSlots || [],
      }))
      .sort((a, b) => b.total - a.total);
  }, [scoreboard]);

  const draftTeams = useMemo(() => {
    if (!draft?.rosters) return [];
    return Object.entries(draft.rosters).map(([teamName, rosterData]) => ({
      teamName,
      slots: rosterData.slots || {},
      filledCount: rosterData.filledCount || 0,
      requiredFilled: !!rosterData.requiredFilled,
    }));
  }, [draft]);

  const onClock = draft?.currentTeam;
  const isMyTurn = !!me && draft?.started && !draft?.completed && onClock === me.name;

  const autoView = draft?.started && !draft?.completed ? "draft" : "dashboard";
  const activeView = viewMode === "auto" ? autoView : viewMode;

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
        roster_size: 7,
        snake: true,
        auto_pick: true,
      });
    } catch (e) {
      setError(e.message);
    }
  }

  async function updateTimer() {
    setError("");
    try {
      await api.updateTimer(userId, Number(timerInput));
    } catch (e) {
      setError(e.message);
    }
  }

  async function submitDraft(player, slot = null) {
    const res = await api.pick(userId, player.athleteId, player.name, slot);
    if (res?.needsSlotSelection) {
      setSlotModal({ player, slots: res.slots || [] });
      return;
    }
    setSlotModal(null);
  }

  async function draftPlayer(player) {
    setError("");
    if (!isMyTurn) return;
    try {
      const eligible = await api.eligibleSlots(userId, player.athleteId);
      const slots = eligible.slots || [];
      if (slots.length === 0) {
        setError("That player does not fit any open slot on your roster.");
        return;
      }
      if (slots.length > 1) {
        setSlotModal({ player, slots });
        return;
      }
      await submitDraft(player, slots[0]);
    } catch (e) {
      setError(e.message);
    }
  }

  async function chooseSlot(slot) {
    if (!slotModal) return;
    setError("");
    try {
      await submitDraft(slotModal.player, slot);
    } catch (e) {
      setError(e.message);
    }
  }

  async function openHoles(athleteId, playerName) {
    const data = await api.playerHoles(athleteId);
    setHoleModal({ athleteId, name: playerName, ...data });
  }

  function renderMyTeamCard() {
    const starterSlots = new Set(draft?.starterSlots || []);

    return (
      <section className="card rosterCard">
        <div className="teamHeader">
          <h2 className="h2">My Current Team</h2>
          <div className="total">Total: {myTeam?.total ?? 0}</div>
        </div>
        <div className="list rosterList">
          {Object.entries(slotLabels).map(([slot, label]) => {
            const player = myRoster?.[slot];
            const scoreRow = (myTeam?.players || []).find((p) => p.slot === slot);
            const isStarter = starterSlots.has(slot);
            const showMissingRequired = isStarter && !player;

            return (
              <div className="row rosterRow" key={slot}>
                <div>
                  <div className={`name ${showMissingRequired ? "missingCategoryText" : ""}`}>
                    {label}
                  </div>
                  {player ? (
                    <>
                      <div className="clickableName" onClick={() => openHoles(player.athleteId, player.name)}>
                        {player.name}
                      </div>
                      <div className="meta">
                        {scoreRow?.status === "missed_cut"
                          ? "Missed cut"
                          : scoreRow?.status === "active_backup"
                          ? "Active backup"
                          : isStarter
                          ? "Starter"
                          : "Backup"}
                        {typeof scoreRow?.madeCut === "boolean"
                          ? ` • ${scoreRow.madeCut ? "Made cut" : "Missed cut"}`
                          : ""}
                      </div>
                    </>
                  ) : (
                    <div className={`meta ${showMissingRequired ? "missingCategoryText" : ""}`}>
                      {isStarter ? "Required category not filled yet" : "Empty"}
                    </div>
                  )}
                </div>
                <div className="pts">{scoreRow?.fantasyPoints ?? 0}</div>
              </div>
            );
          })}
        </div>
      </section>
    );
  }

  function renderTeamRosterCard(team) {
    return (
      <div className="teamRosterCard" key={team.teamName}>
        <div className="teamRosterHeader">
          <div>
            <div className="teamRosterName">{team.teamName}</div>
            <div className="teamRosterSubtext">
              {team.missedStarterSlots.length > 0
                ? `Missed cut slots: ${team.missedStarterSlots.length}`
                : "All tracked slots active"}
            </div>
          </div>
          <div className="teamRosterTotal">{team.total}</div>
        </div>

        <div className="teamRosterSlots">
          {team.players.map((p) => (
            <div className="teamRosterSlot" key={`${team.teamName}-${p.slot}`}>
              <div className="teamRosterSlotTop">
                <span className="teamRosterSlotLabel">{p.slotLabel}</span>
                <span className="teamRosterSlotPoints">{p.fantasyPoints ?? 0}</span>
              </div>
              <div className="teamRosterPlayerName">{p.name || "Empty"}</div>
              <div className="teamRosterPlayerMeta">
                {p.name
                  ? p.status === "missed_cut"
                    ? "Missed cut"
                    : p.status === "active_backup"
                    ? "Active backup"
                    : p.status === "bench"
                    ? "Bench"
                    : "Scoring"
                  : "No player assigned"}
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  function renderDraftBoardCard() {
    return (
      <section className="card">
        <div className="sectionHeader">
          <h2 className="h2">Draft Board</h2>
          <div className="pill">{draftTeams.length} teams</div>
        </div>

        <div className="draftBoardGrid">
          {draftTeams.map((team) => (
            <div className="draftBoardCard" key={team.teamName}>
              <div className="draftBoardHeader">
                <div>
                  <div className="draftBoardName">
                    {team.teamName}
                    {draft?.currentTeam === team.teamName && !draft?.completed ? (
                      <span className="draftingNowPill">On clock</span>
                    ) : null}
                  </div>
                  <div className="draftBoardMeta">{team.filledCount}/7 drafted</div>
                </div>
              </div>

              <div className="draftBoardSlots">
                {Object.entries(slotLabels).map(([slot, label]) => {
                  const player = team.slots?.[slot];
                  return (
                    <div className="draftBoardSlotRow" key={`${team.teamName}-${slot}`}>
                      <div className="draftBoardSlotLabel">{label}</div>
                      <div className={`draftBoardSlotPlayer ${!player ? "draftBoardSlotEmpty" : ""}`}>
                        {player?.name || "—"}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
          {draftTeams.length === 0 && <div className="empty">No draft teams available.</div>}
        </div>
      </section>
    );
  }

  function renderDashboardView() {
    return (
      <>
        <div className="dashboardHero">
          <div className="card dashboardHeroCard">
            <div className="dashboardHeroHeader">
              <div>
                <div className="dashboardEyebrow">League Overview</div>
                <h2 className="dashboardTitle">League Standings</h2>
              </div>
              <div className="pill">
                {draft?.completed ? "Final rosters locked" : draft?.started ? "Draft in progress" : "Pre-draft"}
              </div>
            </div>

            <div className="standingsTable">
              {leagueStandings.map((team, idx) => (
                <div className="standingsRow" key={team.teamName}>
                  <div className="standingsRank">#{idx + 1}</div>
                  <div className="standingsTeamBlock">
                    <div className="standingsTeamName">{team.teamName}</div>
                    <div className="standingsTeamMeta">
                      {team.players.filter((p) => p.name).length} / 7 roster spots filled
                    </div>
                  </div>
                  <div className="standingsScore">{team.total}</div>
                </div>
              ))}
              {leagueStandings.length === 0 && <div className="empty">No standings yet.</div>}
            </div>
          </div>
        </div>

        <div className="layout threeCol">
          {renderMyTeamCard()}

          <section className="card">
            <h2 className="h2">Tournament Leaderboard</h2>
            <div className="list">
              {tournamentLeaderboard.slice(0, 25).map((player, idx) => (
                <div className="row" key={`${player.golfer_name}-${idx}`}>
                  <div>
                    <div className="name">#{idx + 1} {player.golfer_name}</div>
                    <div className="meta">Base: {player.base_points} • Bonus: {player.bonus_points}</div>
                  </div>
                  <div className="pts">{player.fantasy_points}</div>
                </div>
              ))}
              {tournamentLeaderboard.length === 0 && <div className="empty">Leaderboard unavailable.</div>}
            </div>
          </section>

          <section className="card">
            <h2 className="h2">Lobby / Draft Status</h2>
            <div className="list lobbyList">
              {(room?.users || []).map((u) => (
                <div className="row" key={u.userId}>
                  <div className="name">
                    {u.name} {u.isHost ? <span className="pillHost">HOST</span> : null}
                  </div>
                </div>
              ))}
              {(room?.users || []).length === 0 && <div className="empty">No users joined.</div>}
            </div>
          </section>
        </div>

        <section className="card picksCard">
          <div className="sectionHeader">
            <h2 className="h2">Team Rosters</h2>
            <div className="pill">{leagueStandings.length} teams</div>
          </div>
          <div className="teamRosterGrid">
            {leagueStandings.map((team) => renderTeamRosterCard(team))}
            {leagueStandings.length === 0 && <div className="empty">No teams yet.</div>}
          </div>
        </section>
      </>
    );
  }

  function renderDraftView() {
    return (
      <>
        <div className="draftLayout">
          <section className="card">
            <div className="sectionHeader">
              <h2 className="h2">Available Players</h2>
              <div className="pill">{draft?.started ? (isMyTurn ? "Your turn" : `Waiting: ${onClock}`) : "Waiting for host"}</div>
            </div>

            <input
              className="input"
              placeholder="Search..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />

            <div className="filterRow">
              <button
                className={`filterChip ${categoryFilter === "all" ? "active" : ""}`}
                onClick={() => setCategoryFilter("all")}
              >
                All
              </button>
              <button
                className={`filterChip ${categoryFilter === "past_champion" ? "active" : ""}`}
                onClick={() => setCategoryFilter("past_champion")}
              >
                Past Champion
              </button>
              <button
                className={`filterChip ${categoryFilter === "international" ? "active" : ""}`}
                onClick={() => setCategoryFilter("international")}
              >
                International
              </button>
              <button
                className={`filterChip ${categoryFilter === "american" ? "active" : ""}`}
                onClick={() => setCategoryFilter("american")}
              >
                American
              </button>
              <button
                className={`filterChip ${categoryFilter === "non_pga" ? "active" : ""}`}
                onClick={() => setCategoryFilter("non_pga")}
              >
                Non-PGA
              </button>
            </div>

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
                    <div className="tagRow">
                      {getCategoryTags(p).map((tag) => (
                        <span key={tag} className="categoryTag">
                          {tag}
                        </span>
                      ))}
                    </div>
                  </div>
                  <div className="pill">{isMyTurn ? "Draft" : "—"}</div>
                </div>
              ))}
              {available.length === 0 && <div className="empty">No available players.</div>}
            </div>
          </section>

          {renderMyTeamCard()}
        </div>

        {renderDraftBoardCard()}
      </>
    );
  }

  if (!joined) {
    return (
      <div className="page">
        <div className="card" style={{ maxWidth: 520, margin: "80px auto" }}>
          <h1 style={{ marginTop: 0 }}>Join the Draft</h1>
          <p className="muted">Enter your name to enter the lobby.</p>
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
          <button className="btn primary" onClick={doJoin} style={{ marginTop: 12, width: "100%" }}>
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
            You are: <b>{me?.name || "…"}</b> {me?.isHost ? <span className="pillHost">HOST</span> : null}
            {" • "}
            {draft?.started
              ? draft.completed
                ? "Draft complete"
                : `On the clock: ${draft.currentTeam} • Pick ${draft.pickNo}/${draft.totalPicks} • ${draft.secondsLeft}s`
              : "Draft not started"}
          </div>
        </div>

        <div className="actions">
          <button className="btn" onClick={() => setViewMode("dashboard")}>
            Standings
          </button>
          <button className="btn" onClick={() => setViewMode("draft")}>
            Draft Room
          </button>
          <button className="btn" onClick={() => setViewMode("auto")}>
            Auto View
          </button>

          {me?.isHost && !draft?.started && (
            <button className="btn primary" onClick={startDraft}>
              Start Draft
            </button>
          )}

          {me?.isHost && draft?.started && !draft?.completed && (
            <div className="timerControls">
              <input
                className="input timerInput"
                type="number"
                min="5"
                max="300"
                value={timerInput}
                onChange={(e) => setTimerInput(e.target.value)}
              />
              <button className="btn" onClick={updateTimer}>
                Update Timer
              </button>
            </div>
          )}
        </div>
      </header>

      {error && <div className="error" style={{ marginBottom: 10 }}>{error}</div>}

      {activeView === "draft" ? renderDraftView() : renderDashboardView()}

      {slotModal && (
        <div className="modalBackdrop" onClick={() => setSlotModal(null)}>
          <div className="modal smallModal" onClick={(e) => e.stopPropagation()}>
            <div className="modalHeader">
              <div>
                <div className="modalTitle">Choose a slot for {slotModal.player.name}</div>
                <div className="muted">This player qualifies for multiple categories.</div>
                <div className="tagRow">
                  {getCategoryTags(slotModal.player).map((tag) => (
                    <span key={tag} className="categoryTag">
                      {tag}
                    </span>
                  ))}
                </div>
              </div>
              <button className="btn" onClick={() => setSlotModal(null)}>Close</button>
            </div>

            <div className="slotChoices">
              {slotModal.slots.map((slot) => (
                <button key={slot} className="btn slotBtn" onClick={() => chooseSlot(slot)}>
                  {slotLabels[slot] || slot}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {holeModal && (
        <div className="modalBackdrop" onClick={() => setHoleModal(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modalHeader">
              <div>
                <div className="modalTitle">{holeModal.name}</div>
                <div className="muted">Fantasy points: {holeModal.fantasyPoints ?? 0}</div>
              </div>
              <button className="btn" onClick={() => setHoleModal(null)}>Close</button>
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
                <div className="empty">Hole-by-hole provider is currently stubbed.</div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}