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
  if (player?.isPastChampion) tags.push("Past Champion");
  if (player?.isInternational) tags.push("International");
  if (player?.isAmerican) tags.push("American");
  if (player?.isNonPga) tags.push("Non-PGA");
  return tags;
}

function playerMatchesFilter(player, filter) {
  if (filter === "all") return true;
  if (filter === "past_champion") return !!player?.isPastChampion;
  if (filter === "international") return !!player?.isInternational;
  if (filter === "american") return !!player?.isAmerican;
  if (filter === "non_pga") return !!player?.isNonPga;
  return true;
}

function ScoreBreakdown({ basePoints = 0, bonusPoints = 0, placementBonus = 0, onOpenBreakdown }) {
  const hasPlacement = Number(placementBonus) !== 0;

  return (
    <div className="scoreBreakdown">
      <button type="button" className="scoreChipButton" onClick={() => onOpenBreakdown?.("base")}>
        Base {basePoints ?? 0}
      </button>
      <button type="button" className="scoreChipButton" onClick={() => onOpenBreakdown?.("bonus")}>
        Bonus {bonusPoints ?? 0}
      </button>
      {hasPlacement ? (
        <button type="button" className="scoreChipButton" onClick={() => onOpenBreakdown?.("placement")}>
          Place {placementBonus}
        </button>
      ) : null}
    </div>
  );
}

function HighlightsRow({ highlights = [] }) {
  if (!Array.isArray(highlights) || highlights.length === 0) return null;
  return (
    <div className="highlightRow">
      {highlights.slice(0, 4).map((item, idx) => (
        <span className="highlightTag" key={`${item}-${idx}`}>
          {item}
        </span>
      ))}
    </div>
  );
}

function safeObject(value) {
  return value && typeof value === "object" && !Array.isArray(value) ? value : {};
}

function flattenBreakdownMap(breakdown) {
  const obj = safeObject(breakdown);
  return Object.entries(obj)
    .map(([key, value]) => ({
      key,
      label: value?.label ?? key,
      count: value?.count ?? 0,
      pointsEach: value?.pointsEach ?? 0,
      total: value?.total ?? 0,
      rank: value?.rank,
    }))
    .filter((row) => row.count > 0 || row.total > 0);
}

function aggregateNestedBreakdown(nested) {
  const obj = safeObject(nested);
  const aggregated = {};

  Object.values(obj).forEach((roundBreakdown) => {
    const roundObj = safeObject(roundBreakdown);
    Object.entries(roundObj).forEach(([key, value]) => {
      if (!aggregated[key]) {
        aggregated[key] = {
          label: value?.label ?? key,
          count: 0,
          pointsEach: value?.pointsEach ?? 0,
          total: 0,
          rank: value?.rank,
        };
      }
      aggregated[key].count += value?.count ?? 0;
      aggregated[key].total = Number((aggregated[key].total + (value?.total ?? 0)).toFixed(2));
      if (value?.rank != null) aggregated[key].rank = value.rank;
    });
  });

  return aggregated;
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
  const [scoreBreakdownModal, setScoreBreakdownModal] = useState(null);
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
        setField(Array.isArray(f?.players) ? f.players : []);
        const s = await api.state();
        setRoom(s);
        const sb = await api.scoreboard();
        setScoreboard(sb);
        const lb = await api.tournamentLeaderboard();
        setTournamentLeaderboard(Array.isArray(lb?.leaderboard) ? lb.leaderboard : []);
      } catch (e) {
        console.error("initial load failed:", e);
        setError(e.message || "Failed to load app data.");
      }
    })();

    intervalId = setInterval(async () => {
      try {
        const lb = await api.tournamentLeaderboard();
        setTournamentLeaderboard(Array.isArray(lb?.leaderboard) ? lb.leaderboard : []);
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
    const users = Array.isArray(room?.users) ? room.users : [];
    return users.find((u) => u.userId === userId) || null;
  }, [room, userId]);

  const slotLabels = safeObject(room?.slotLabels);
  const picked = useMemo(() => new Set(Array.isArray(draft?.picked) ? draft.picked : []), [draft]);
  const myRoster = me ? safeObject(draft?.rosters?.[me.name]?.slots) : {};
  const myTeam = useMemo(() => {
    if (!me || !scoreboard?.teams) return null;
    return scoreboard.teams[me.name] || null;
  }, [me, scoreboard]);

  const available = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (Array.isArray(field) ? field : [])
      .filter((p) => !picked.has(p.athleteId))
      .filter((p) => playerMatchesFilter(p, categoryFilter))
      .filter((p) => (q ? (p?.name || "").toLowerCase().includes(q) : true));
  }, [field, picked, query, categoryFilter]);

  const leagueStandings = useMemo(() => {
    const teamsObj = safeObject(scoreboard?.teams);
    return Object.entries(teamsObj)
      .map(([teamName, data]) => ({
        teamName,
        total: data?.total || 0,
        players: Array.isArray(data?.players) ? data.players : [],
        missedStarterSlots: Array.isArray(data?.missedStarterSlots) ? data.missedStarterSlots : [],
      }))
      .sort((a, b) => b.total - a.total);
  }, [scoreboard]);

  const draftTeams = useMemo(() => {
    const rosters = safeObject(draft?.rosters);
    return Object.entries(rosters).map(([teamName, rosterData]) => ({
      teamName,
      slots: safeObject(rosterData?.slots),
      filledCount: rosterData?.filledCount || 0,
      requiredFilled: !!rosterData?.requiredFilled,
    }));
  }, [draft]);

  const onClock = draft?.currentTeam;
  const isMyTurn = !!me && draft?.started && !draft?.completed && onClock === me.name;

  const autoView = draft?.started && !draft?.completed ? "draft" : "dashboard";
  const activeView = viewMode === "auto" ? autoView : viewMode;

  function openScoreBreakdownModal(payload) {
    setScoreBreakdownModal(payload);
  }

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
    const starterSlots = new Set(Array.isArray(draft?.starterSlots) ? draft.starterSlots : []);

    return (
      <section className="card rosterCard">
        <div className="teamHeader">
          <h2 className="h2">My Current Team</h2>
          <div className="total">Total: {myTeam?.total ?? 0}</div>
        </div>
        <div className="list rosterList">
          {Object.entries(slotLabels).map(([slot, label]) => {
            const player = myRoster?.[slot];
            const scoreRow = (Array.isArray(myTeam?.players) ? myTeam.players : []).find((p) => p.slot === slot);
            const isStarter = starterSlots.has(slot);
            const showMissingRequired = isStarter && !player;

            return (
              <div className="row rosterRow" key={slot}>
                <div className="rosterMain">
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
                      <ScoreBreakdown
                        basePoints={scoreRow?.basePoints}
                        bonusPoints={scoreRow?.bonusPoints}
                        placementBonus={scoreRow?.placementBonus}
                        onOpenBreakdown={(kind) =>
                          openScoreBreakdownModal({
                            playerName: player.name,
                            teamName: me?.name,
                            slotLabel: label,
                            kind,
                            basePoints: scoreRow?.basePoints ?? 0,
                            bonusPoints: scoreRow?.bonusPoints ?? 0,
                            placementBonus: scoreRow?.placementBonus ?? 0,
                            roundPoints: scoreRow?.roundPoints ?? {},
                            highlights: scoreRow?.scoringHighlights ?? [],
                            totalPoints: scoreRow?.fantasyPoints ?? 0,
                            baseBreakdown: scoreRow?.baseBreakdown ?? {},
                            bonusBreakdown: scoreRow?.bonusBreakdown ?? {},
                            placementBreakdown: scoreRow?.placementBreakdown ?? {},
                          })
                        }
                      />
                      <HighlightsRow highlights={scoreRow?.scoringHighlights} />
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
              {p.name ? (
                <>
                  <ScoreBreakdown
                    basePoints={p.basePoints}
                    bonusPoints={p.bonusPoints}
                    placementBonus={p.placementBonus}
                    onOpenBreakdown={(kind) =>
                      openScoreBreakdownModal({
                        playerName: p.name,
                        teamName: team.teamName,
                        slotLabel: p.slotLabel,
                        kind,
                        basePoints: p.basePoints ?? 0,
                        bonusPoints: p.bonusPoints ?? 0,
                        placementBonus: p.placementBonus ?? 0,
                        roundPoints: p.roundPoints ?? {},
                        highlights: p.scoringHighlights ?? [],
                        totalPoints: p.fantasyPoints ?? 0,
                        baseBreakdown: p.baseBreakdown ?? {},
                        bonusBreakdown: p.bonusBreakdown ?? {},
                        placementBreakdown: p.placementBreakdown ?? {},
                      })
                    }
                  />
                  <HighlightsRow highlights={p.scoringHighlights} />
                </>
              ) : null}
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
                <div className="row leaderboardRow" key={`${player.golfer_name}-${idx}`}>
                  <div className="leaderboardMain">
                    <div className="name">#{idx + 1} {player.golfer_name}</div>
                    <ScoreBreakdown
                      basePoints={player.base_points}
                      bonusPoints={player.bonus_points}
                      placementBonus={player.placement_bonus}
                      onOpenBreakdown={(kind) =>
                        openScoreBreakdownModal({
                          playerName: player.golfer_name,
                          kind,
                          basePoints: player.base_points ?? 0,
                          bonusPoints: player.bonus_points ?? 0,
                          placementBonus: player.placement_bonus ?? 0,
                          highlights: player.highlights ?? [],
                          totalPoints: player.fantasy_points ?? 0,
                          baseBreakdown: player.base_breakdown ?? {},
                          bonusBreakdown: player.bonus_breakdown ?? {},
                          placementBreakdown: player.placement_breakdown ?? {},
                          roundPoints: player.round_points ?? {},
                        })
                      }
                    />
                    <HighlightsRow highlights={player.highlights} />
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
              {(Array.isArray(room?.users) ? room.users : []).map((u) => (
                <div className="row" key={u.userId}>
                  <div className="name">
                    {u.name} {u.isHost ? <span className="pillHost">HOST</span> : null}
                  </div>
                </div>
              ))}
              {(Array.isArray(room?.users) ? room.users : []).length === 0 && <div className="empty">No users joined.</div>}
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

            <input className="input" placeholder="Search..." value={query} onChange={(e) => setQuery(e.target.value)} />

            <div className="filterRow">
              <button className={`filterChip ${categoryFilter === "all" ? "active" : ""}`} onClick={() => setCategoryFilter("all")}>All</button>
              <button className={`filterChip ${categoryFilter === "past_champion" ? "active" : ""}`} onClick={() => setCategoryFilter("past_champion")}>Past Champion</button>
              <button className={`filterChip ${categoryFilter === "international" ? "active" : ""}`} onClick={() => setCategoryFilter("international")}>International</button>
              <button className={`filterChip ${categoryFilter === "american" ? "active" : ""}`} onClick={() => setCategoryFilter("american")}>American</button>
              <button className={`filterChip ${categoryFilter === "non_pga" ? "active" : ""}`} onClick={() => setCategoryFilter("non_pga")}>Non-PGA</button>
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
                        <span key={tag} className="categoryTag">{tag}</span>
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

  const breakdownRows = scoreBreakdownModal
    ? scoreBreakdownModal.kind === "base"
      ? flattenBreakdownMap(scoreBreakdownModal.baseBreakdown)
      : scoreBreakdownModal.kind === "bonus"
      ? flattenBreakdownMap(scoreBreakdownModal.bonusBreakdown)
      : flattenBreakdownMap(scoreBreakdownModal.placementBreakdown)
    : [];

  return (
    <div className="page">
      <header className="topbar">
        <div className="topbarLeft">
          <div className="brandRow">
            <div className="brandBadge">⛳</div>
            <div>
              <h1 className="brandTitle">Masters Weekend Pool</h1>
              <div className="brandSubtitle">Augusta National • Draft & Leaderboard</div>
            </div>
          </div>

          <div className="muted">
            You are: <b>{me?.name || "…"}</b>{" "}
            {me?.isHost ? <span className="pillHost">HOST</span> : null}
            {" • "}
            {draft?.started
              ? draft.completed
                ? "Draft complete"
                : `On the clock: ${draft.currentTeam} • Pick ${draft.pickNo}/${draft.totalPicks} • ${draft.secondsLeft}s`
              : "Draft not started"}
          </div>
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
                    <span key={tag} className="categoryTag">{tag}</span>
                  ))}
                </div>
              </div>
              <button className="btn" onClick={() => setSlotModal(null)}>Close</button>
            </div>

            <div className="slotChoices">
              {(Array.isArray(slotModal.slots) ? slotModal.slots : []).map((slot) => (
                <button key={slot} className="btn slotBtn" onClick={() => chooseSlot(slot)}>
                  {slotLabels[slot] || slot}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {scoreBreakdownModal && (
        <div className="modalBackdrop" onClick={() => setScoreBreakdownModal(null)}>
          <div className="modal smallModal" onClick={(e) => e.stopPropagation()}>
            <div className="modalHeader">
              <div>
                <div className="modalTitle">
                  {scoreBreakdownModal.playerName} — {scoreBreakdownModal.kind === "base"
                    ? "Base Score Breakdown"
                    : scoreBreakdownModal.kind === "bonus"
                    ? "Bonus Score Breakdown"
                    : "Placement Bonus Breakdown"}
                </div>
                <div className="muted">
                  {scoreBreakdownModal.teamName ? `${scoreBreakdownModal.teamName}` : "Tournament leaderboard"}
                  {scoreBreakdownModal.slotLabel ? ` • ${scoreBreakdownModal.slotLabel}` : ""}
                </div>
              </div>
              <button className="btn" onClick={() => setScoreBreakdownModal(null)}>Close</button>
            </div>

            <div className="breakdownSection">
              <div className="breakdownTotal">
                Current value:{" "}
                <strong>
                  {scoreBreakdownModal.kind === "base"
                    ? scoreBreakdownModal.basePoints
                    : scoreBreakdownModal.kind === "bonus"
                    ? scoreBreakdownModal.bonusPoints
                    : scoreBreakdownModal.placementBonus}
                </strong>
              </div>

              <div className="breakdownCard">
                <div className="breakdownCardTitle">Breakdown</div>
                {breakdownRows.length ? (
                  <div className="breakdownTableWrap">
                    <table className="breakdownTable">
                      <thead>
                        <tr>
                          <th>Type</th>
                          {scoreBreakdownModal.kind === "placement" ? <th>Rank</th> : null}
                          <th>Count</th>
                          <th>Pts Each</th>
                          <th>Total</th>
                        </tr>
                      </thead>
                      <tbody>
                        {breakdownRows.map((row) => (
                          <tr key={row.key}>
                            <td>{row.label}</td>
                            {scoreBreakdownModal.kind === "placement" ? <td>{row.rank ?? "-"}</td> : null}
                            <td>{row.count}</td>
                            <td>{row.pointsEach}</td>
                            <td>{row.total}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="muted">No points of this type yet.</div>
                )}
              </div>

              {scoreBreakdownModal.kind !== "placement" ? (
                <div className="breakdownCard">
                  <div className="breakdownCardTitle">Round-by-round points</div>
                  <div className="breakdownRounds">
                    {[1, 2, 3, 4].map((r) => (
                      <div className="breakdownRoundRow" key={r}>
                        <span>Round {r}</span>
                        <strong>{scoreBreakdownModal.roundPoints?.[r] ?? 0}</strong>
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}

              {Array.isArray(scoreBreakdownModal.highlights) && scoreBreakdownModal.highlights.length ? (
                <div className="breakdownCard">
                  <div className="breakdownCardTitle">Scoring highlights</div>
                  <HighlightsRow highlights={scoreBreakdownModal.highlights} />
                </div>
              ) : null}

              <div className="breakdownCard">
                <div className="breakdownCardTitle">Overall fantasy total</div>
                <div className="breakdownTotalValue">{scoreBreakdownModal.totalPoints ?? 0}</div>
              </div>
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
                <ScoreBreakdown
                  basePoints={holeModal.basePoints}
                  bonusPoints={holeModal.bonusPoints}
                  placementBonus={holeModal.placementBonus}
                  onOpenBreakdown={(kind) =>
                    openScoreBreakdownModal({
                      playerName: holeModal.name,
                      kind,
                      basePoints: holeModal.basePoints ?? 0,
                      bonusPoints: holeModal.bonusPoints ?? 0,
                      placementBonus: holeModal.placementBonus ?? 0,
                      highlights: holeModal.scoringHighlights ?? [],
                      totalPoints: holeModal.fantasyPoints ?? 0,
                      baseBreakdown: aggregateNestedBreakdown(holeModal.baseBreakdown ?? {}),
                      bonusBreakdown: aggregateNestedBreakdown(holeModal.bonusBreakdown ?? {}),
                      placementBreakdown: holeModal.placementBreakdown ?? {},
                      roundPoints: holeModal.roundPoints ?? {},
                    })
                  }
                />
                <HighlightsRow highlights={holeModal.scoringHighlights} />
              </div>
              <button className="btn" onClick={() => setHoleModal(null)}>Close</button>
            </div>

            <div className="holes">
              {(Array.isArray(holeModal.holes) ? holeModal.holes : []).map((h) => (
                <div className="holeRow" key={`${h.round}-${h.hole}`}>
                  <div>R{h.round}</div>
                  <div>Hole {h.hole}</div>
                  <div>Par {h.par ?? "-"}</div>
                  <div>Strokes {h.strokes ?? "-"}</div>
                  <div className="pill">{h.result}</div>
                  <div className="holePointsCell">
                    <div className="pts">{h.totalPoints}</div>
                    {h.bonusPoints > 0 ? <div className="holeBonusText">+{h.bonusPoints} bonus</div> : null}
                  </div>
                </div>
              ))}
              {(Array.isArray(holeModal.holes) ? holeModal.holes : []).length === 0 && (
                <div className="empty">Hole-by-hole provider is currently stubbed.</div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}