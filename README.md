# Masters Draft Tracker (Draft + Live Scoring)

## Prereqs
- Node 20+ (important)
- Python 3.10+

## Run backend (8080)
cd backend
pip install -r requirements.txt
uvicorn app:app --reload --port 8000

## Run backend (5173)
cd frontend
npm install
npm run dev

## API
GET /api/field?limit=50
GET /api/teams
POST /api/draft
GET /api/draft/scoreboard
GET /api/player/{athlete_id}/holes

## NOTES
The scoring endpoint is currently stubbed (returns 0 points) until you wire a reliable hole-by-hole source.

Once hole-by-hole is connected, the UI will show live totals without changes