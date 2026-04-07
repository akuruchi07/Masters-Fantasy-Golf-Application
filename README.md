# Masters Draft Room

A live fantasy draft and scoring app for the Masters Tournament.

This project lets a group of users join a shared draft room, draft golfers into category-based roster slots, track team standings, and follow live fantasy scoring throughout the tournament.

---

## Overview

This app has two main modes:

### 1. Draft Room
Used only during the live draft.

In this mode, users can:
- join the room
- see whose turn it is
- see the draft timer
- draft golfers from the player pool
- view their own current team
- view every other team’s draft progress live
- filter the player pool by roster category

### 2. Standings Dashboard
Used before and after the draft, and during tournament play.

In this mode, users can:
- view league standings
- view the live tournament leaderboard
- view their own full roster
- view all team rosters
- inspect hole-by-hole fantasy scoring for drafted players

---

## Core Features

### Live multiplayer draft
- Users join the same room from separate devices
- The host starts the draft
- Draft order is randomized
- Snake draft logic is supported
- Draft state updates live through WebSockets
- Pick timer can be updated by the host during the draft

### Category-based roster drafting
Each team drafts **7 players** into these slots:

#### Required starter slots
- Past Masters Champion
- International
- American
- Non-PGA Tour
- Wildcard

#### Backup slots
- Backup 1
- Backup 2

### Slot eligibility rules
A player may qualify for multiple categories.

For example:
- a player can be both a **Past Champion** and **International**
- a LIV player may be **Non-PGA** and also **American** or **International**

When a player qualifies for multiple valid roster slots, the app prompts the user to choose which slot to use.

### Draft enforcement
The app enforces these rules:
- the first 5 picks must fill the 5 required starter categories
- backup slots cannot be drafted until all required starter slots are filled
- each golfer can only be drafted once across the room
- each team can only have a golfer once

### Live scoring
The app pulls live tournament data and computes fantasy scoring for drafted players.

Users can:
- view league standings
- view per-team totals
- view individual player fantasy points
- open hole-by-hole scoring details for drafted players

### Backup substitution logic
Backup players only count under specific conditions.

#### Scoring rules:
- starter players score normally during Thursday and Friday
- after the cut:
  - if 1 starter misses the cut, Backup 1 becomes eligible
  - if 2 starters miss the cut, Backup 1 and Backup 2 become eligible
- backups only contribute points from **Saturday and Sunday**
- backups only score if they themselves made the cut

### Player filtering
During the draft, users can filter the player pool by:
- All
- Past Champion
- International
- American
- Non-PGA

Wildcard is not included as a filter because every golfer is effectively wildcard-eligible.

---

## Tech Stack

### Backend
- FastAPI
- WebSockets
- Python

### Frontend
- React
- Vite
- CSS

### Data / scoring
- CSV-based player pool
- live tournament leaderboard / scorecard scraping
- fantasy scoring engine for hole-by-hole point calculation

---

## Application Flow

## Joining the app
When a user opens the app:
1. they enter their name
2. they join the shared room
3. the first user becomes the host

## Before the draft
Before the draft starts:
- users can see the lobby
- the host can start the draft
- the app defaults to the standings/dashboard view unless the draft is active

## During the draft
Once the host starts the draft:
- teams are randomized
- the draft timer begins
- the app automatically switches to Draft Room view
- users draft players into valid category slots
- all connected clients receive live updates

## After the draft
Once all rosters are full:
- the draft is complete
- the app defaults back to the standings/dashboard
- users can continue tracking the tournament and fantasy scores

---

## Draft Room Layout

The draft room is intentionally focused and minimal.

It shows:
- the available player list
- category filters
- your current team
- the live draft board showing all teams’ current rosters

It does **not** prioritize league standings or tournament leaderboard during the draft.

### Draft room visual cues
- the current team on the clock is highlighted
- unfilled required categories on your team are shown in red
- players display category tags so users can quickly understand eligibility
- if a golfer qualifies for multiple categories, a slot selection modal appears

---

## Dashboard Layout

The standings/dashboard is the main tournament view.

It shows:
- league standings
- your team
- tournament leaderboard
- all team rosters

This is the primary screen outside of the active draft.

---

## Roster Categories

### Past Masters Champion
A golfer who has previously won the Masters.

### International
A non-American player.

### American
An American player.

### Non-PGA Tour
A player who is not currently classified as a PGA Tour player in this app’s category mapping.

### Wildcard
Any golfer.

### Backup 1 / Backup 2
Bench players used only when starters miss the cut.

---

## Fantasy Scoring Behavior

The scoring model uses live hole-by-hole tournament results.

### Starters
Starter slots can earn points all tournament long, but:
- if a starter misses the cut, they only retain their scored points from completed rounds
- they do not earn weekend points

### Backups
Backups:
- do not score on Thursday or Friday
- only activate when starters miss the cut
- only earn Saturday and Sunday points
- must have made the cut themselves to contribute

---

## Important Files

### Backend
- `backend/app.py`
  - FastAPI app
  - REST endpoints
  - WebSocket broadcasting
  - room state
  - draft flow
  - timer updates
- `backend/draft.py`
  - draft state model
  - roster slot logic
  - pick validation
  - snake draft behavior
- `backend/leaderboard.py`
  - live scorecard ingestion
  - team fantasy scoring
  - backup activation logic

### Frontend
- `frontend/src/App.jsx`
  - main UI
  - draft room
  - standings dashboard
  - filters
  - modals
- `frontend/src/api.js`
  - frontend API helpers
- `frontend/src/ws.js`
  - WebSocket connection logic
- `frontend/src/styles.css`
  - app styling

---

## API Summary

### General
- `GET /api/health`
- `GET /api/state`
- `GET /api/field`
- `GET /api/scoreboard`
- `GET /api/tournament-leaderboard`

### User / room
- `POST /api/join`

### Draft control
- `POST /api/draft/start`
- `POST /api/draft/reset`
- `POST /api/draft/timer`

### Draft actions
- `GET /api/draft/eligible-slots/{athlete_id}`
- `POST /api/draft/pick`

### Player detail
- `GET /api/player/{athlete_id}/holes`

### WebSocket
- `/ws`

---

## Running Locally


## Run backend (8080)
cd backend
pip install -r requirements.txt
uvicorn app:app --reload --port 8000

To host locally, python -m uvicorn app:app --host 0.0.0.0 --port 8000

## Run frontend (5173)
cd frontend
npm install
npm run dev

To host locally, npm run dev -- --host 0.0.0.0 --port 5173