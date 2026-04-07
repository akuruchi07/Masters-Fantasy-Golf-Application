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
  tags.push("Wildcard");
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

function buildColumnDraftBoard(teams, picks) {
  if (!Array.isArray(teams) || teams.length === 0) return [];
  const pickCount = Array.isArray(picks) ? picks.length : 0;
  const totalRounds = Math.max(7, Math.ceil(pickCount / teams.length));
  const columns = teams.map((team) => ({
    team,
    rounds: Array.from({ length: totalRounds }, (_, idx) => ({
      round: idx + 1,
      pick: null,
    })),
  }));

  const teamIndex = Object.fromEntries(columns.map((col, idx) => [col.team, idx]));

  for (const pick of Array.isArray(picks) ? picks : []) {
    const teamIdx = teamIndex[pick.team];
    if (teamIdx == null) continue;
    const round = Math.ceil(pick.pickNo / teams.length);
    if (round >= 1 && round <= totalRounds) {
      columns[teamIdx].rounds[round - 1].pick = pick;
    }
  }

  return columns;
}

function TeamDetailModal({ team, onClose, onOpenBreakdown, onOpenHoles }) {
  if (!team) return null;

  return (
    <div className="modalBackdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modalHeader">
          <div>
            <div className="modalTitle">{team.teamName}</div>
            <div className="meta">Team total: {team.total ?? 0}</div>
            {team.teamBonuses?.starterMadeCut?.total ? (
              <div className="meta">
                {team.teamBonuses.starterMadeCut.label}: {team.teamBonuses.starterMadeCut.count} × {team.teamBonuses.starterMadeCut.pointsEach} = {team.teamBonuses.starterMadeCut.total}
              </div>
            ) : null}
          </div>
          <button className="btn" onClick={onClose}>Close</button>
        </div>

        <div className="teamRosterSlots modalTeamRosterSlots">
          {(Array.isArray(team.players) ? team.players : []).map((p) => (
            <div className="teamRosterSlot" key={`${team.teamName}-${p.slot}`}>
              <div className="teamRosterSlotTop">
                <span className="teamRosterSlotLabel">{p.slotLabel}</span>
                <span className={`teamRosterSlotPoints ${p.status === "missed_cut" ? "missedCutText" : ""}`}>
                  {p.fantasyPoints ?? 0}
                </span>
              </div>
              <div
                className={`teamRosterPlayerName ${p.status === "missed_cut" ? "missedCutName" : ""} ${p.name ? "clickableName" : ""}`}
                onClick={() => p.name && onOpenHoles?.(p.athleteId, p.name)}
              >
                {p.name || "Empty"}
              </div>
              <div className={`teamRosterPlayerMeta ${p.status === "missed_cut" ? "missedCutText" : ""}`}>
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
                      onOpenBreakdown?.({
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
    </div>
  );
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
  const [teamModal, setTeamModal] = useState(null);
  const [error, setError] = useState("");
  const [tournamentLeaderboard, setTournamentLeaderboard] = useState([]);
  const [timerInput, setTimerInput] = useState(60);
  const [viewMode, setViewMode] = useState("auto");
  const [autoPicking, setAutoPicking] = useState(false);
  const [liveSeconds, setLiveSeconds] = useState(0);

  const draft = room?.draft;

  useEffect(() => {
    if (draft?.secondsPerPick) {
      setTimerInput(draft.secondsPerPick);
    }
  }, [draft?.secondsPerPick]);

  useEffect(() => {
    if (!draft?.started || draft?.completed || !draft?.deadlineTs) {
      setLiveSeconds(draft?.secondsLeft ?? 0);
      return;
    }

    const tick = () => {
      const remaining = Math.max(0, Math.ceil(draft.deadlineTs - Date.now() / 1000));
      setLiveSeconds(remaining);
    };

    tick();
    const interval = setInterval(tick, 1000);
    return () => clearInterval(interval);
  }, [draft?.started, draft?.completed, draft?.deadlineTs, draft?.secondsLeft]);

  useEffect(() => {
    if (!joined) return;

    let intervalId;

    (async () => {
      try {
        const f = await api.field(0);
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
        teamBonuses: safeObject(data?.teamBonuses),
      }))
      .sort((a, b) => b.total - a.total);
  }, [scoreboard]);

  const draftColumns = useMemo(
    () => buildColumnDraftBoard(draft?.teams || [], draft?.picks || []),
    [draft]
  );

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

  async function triggerAutoPick() {
    setError("");
    setAutoPicking(true);
    try {
      await api.autoPick(userId);
    } catch (e) {
      setError(e.message);
    } finally {
      setAutoPicking(false);
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

  function openTeam(teamName) {
    const team = leagueStandings.find((t) => t.teamName === teamName);
    if (team) setTeamModal(team);
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
            const missedCut = scoreRow?.status === "missed_cut";

            return (
              <div className="row rosterRow" key={slot}>
                <div className="rosterMain">
                  <div className={`name ${showMissingRequired ? "missingCategoryText" : ""}`}>{label}</div>
                  {player ? (
                    <>
                      <div
                        className={`clickableName ${missedCut ? "missedCutName" : ""}`}
                        onClick={() => openHoles(player.athleteId, player.name)}
                      >
                        {player.name}
                      </div>
                      <div className={`meta ${missedCut ? "missedCutText" : ""}`}>
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
                <div className={`pts ${missedCut ? "missedCutText" : ""}`}>{scoreRow?.fantasyPoints ?? 0}</div>
              </div>
            );
          })}
        </div>
      </section>
    );
  }

  function renderColumnDraftBoard() {
    return (
      <section className="card picksCard">
        <div className="sectionHeader">
          <h2 className="h2">Draft Board</h2>
          <div className="pill">{(draft?.teams || []).length} teams</div>
        </div>

        <div className="columnDraftBoard">
          {draftColumns.map((column) => (
            <div
              key={column.team}
              className={`draftColumn ${draft?.currentTeam === column.team && !draft?.completed ? "draftColumnOnClock" : ""}`}
            >
              <div className="draftColumnHeader">{column.team}</div>
              {column.rounds.map((round) => (
                <div className="draftColumnCell" key={`${column.team}-${round.round}`}>
                  <div className="draftColumnRound">R{round.round}</div>
                  <div className="draftColumnPlayer">{round.pick?.name || "—"}</div>
                  <div className="draftColumnMeta">{round.pick?.slotLabel || ""}</div>
                </div>
              ))}
            </div>
          ))}
        </div>
      </section>
    );
  }

  function renderDashboardView() {
    const leaderboardSlice = tournamentLeaderboard.slice(0, 50);
    const firstMissedCutIndex = leaderboardSlice.findIndex((p) => p?.made_cut === false);

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
                    <div className="standingsTeamName clickableTeamName" onClick={() => openTeam(team.teamName)}>
                      {team.teamName}
                    </div>
                    <div className="standingsTeamMeta">
                      {team.players.filter((p) => p.name).length} / 7 roster spots filled
                    </div>
                  </div>
                  <div className="standingsScore">{team.total}</div>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="layout threeCol">
          {renderMyTeamCard()}

          <section className="card">
            <h2 className="h2">Tournament Leaderboard</h2>
            <div className="list">
              {leaderboardSlice.map((player, idx) => (
                <div key={`${player.golfer_name}-${idx}`}>
                  {firstMissedCutIndex !== -1 && idx === firstMissedCutIndex && (
                    <div className="cutLineRow">
                      <span className="cutLineText">Cut Line</span>
                    </div>
                  )}
                  <div className="row leaderboardRow">
                    <div className="leaderboardMain">
                      <div className={`name ${player.made_cut === false ? "missedCutName" : ""}`}>
                        #{idx + 1} {player.golfer_name}
                      </div>
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
                      {player.made_cut === false ? <div className="missedCutNote">Missed cut</div> : null}
                    </div>
                    <div className={`pts ${player.made_cut === false ? "missedCutText" : ""}`}>
                      {player.fantasy_points}
                    </div>
                  </div>
                </div>
              ))}
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
            </div>
          </section>
        </div>
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
              <div className="draftControls">
                <div className="pill">
                  {draft?.started ? (isMyTurn ? "Your turn" : `Waiting: ${onClock}`) : "Waiting for host"}
                </div>
                {isMyTurn ? (
                  <button className="btn autoPickBtn" onClick={triggerAutoPick} disabled={autoPicking}>
                    {autoPicking ? "Auto Picking..." : "Auto Pick"}
                  </button>
                ) : null}
              </div>
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
            </div>
          </section>

          {renderMyTeamCard()}
        </div>

        {renderColumnDraftBoard()}
      </>
    );
  }

  if (!joined) {
    return (
      <div className="page">
        <div className="card" style={{ maxWidth: 520, margin: "80px auto" }}>
          <h1 style={{ marginTop: 0 }} className="h2">Join the Draft</h1>
          <p className="meta">Enter your name to enter the lobby.</p>
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
          {error ? <div className="error">{error}</div> : null}
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

  const standingsActive = activeView === "dashboard";
  const draftRoomActive = activeView === "draft";

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
            You are: <b>{me?.name || "…"}</b> {me?.isHost ? <span className="pillHost">HOST</span> : null}
            {" • "}
            {draft?.started
              ? draft.completed
                ? "Draft complete"
                : `On the clock: ${draft.currentTeam} • Pick ${draft.pickNo}/${draft.totalPicks} • ${liveSeconds}s`
              : "Draft not started"}
          </div>
        </div>

        <div className="actions">
          <button className={`btn navBtn ${standingsActive ? "navBtnActive" : ""}`} onClick={() => setViewMode("dashboard")}>
            Standings
          </button>
          <button className={`btn navBtn ${draftRoomActive ? "navBtnActive" : ""}`} onClick={() => setViewMode("draft")}>
            Draft Room
          </button>
          {/* <button className="btn" onClick={() => setViewMode("auto")}>Auto View</button> */}

          {me?.isHost && !draft?.started ? (
            <button className="btn primary" onClick={startDraft}>Start Draft</button>
          ) : null}

          {me?.isHost && draft?.started && !draft?.completed ? (
            <div className="timerControls">
              <input
                className="input timerInput"
                type="number"
                min="5"
                max="300"
                value={timerInput}
                onChange={(e) => setTimerInput(e.target.value)}
              />
              <button className="btn" onClick={updateTimer}>Update Timer</button>
            </div>
          ) : null}
        </div>
      </header>

      {error ? <div className="error" style={{ marginBottom: 10 }}>{error}</div> : null}

      {activeView === "draft" ? renderDraftView() : renderDashboardView()}

      <TeamDetailModal
        team={teamModal}
        onClose={() => setTeamModal(null)}
        onOpenBreakdown={openScoreBreakdownModal}
        onOpenHoles={openHoles}
      />

      {slotModal ? (
        <div className="modalBackdrop" onClick={() => setSlotModal(null)}>
          <div className="modal smallModal" onClick={(e) => e.stopPropagation()}>
            <div className="modalHeader">
              <div>
                <div className="modalTitle">Choose a slot for {slotModal.player.name}</div>
                <div className="meta">This player qualifies for multiple categories.</div>
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
      ) : null}

      {scoreBreakdownModal ? (
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
                <div className="meta">
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
                  <div className="meta">No points of this type yet.</div>
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
      ) : null}

      {holeModal ? (
        <div className="modalBackdrop" onClick={() => setHoleModal(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modalHeader">
              <div>
                <div className={`modalTitle ${holeModal.madeCut === false ? "missedCutName" : ""}`}>{holeModal.name}</div>
                <div className="meta">Fantasy points: {holeModal.fantasyPoints ?? 0}</div>
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
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}