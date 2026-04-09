from __future__ import annotations

import asyncio
import csv
import os
import random
import time
import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from draft import ALL_SLOTS, BACKUP_SLOTS, DraftConfig, DraftState, SLOT_LABELS, STARTER_SLOTS
from leaderboard import LivePlayerScorecard, build_team_scoreboard, fetch_live_scorecards, get_leaderboard

APP_ROOT = os.path.dirname(os.path.abspath(__file__))
PLAYERS_CSV = os.path.join(APP_ROOT, "players.csv")

app = FastAPI(title="Masters Draft Room API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def slugify(s: str) -> str:
    return (
        s.strip()
        .lower()
        .replace("’", "")
        .replace("'", "")
        .replace(".", "")
        .replace(",", "")
        .replace("å", "a")
        .replace("ö", "o")
        .replace("ä", "a")
        .replace("ü", "u")
        .replace("é", "e")
        .replace("è", "e")
        .replace("ê", "e")
        .replace("á", "a")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ú", "u")
        .replace("ñ", "n")
        .replace("ø", "o")
        .replace(" ", "-")
    )


PAST_CHAMPIONS = {
    "angel-cabrera",
    "fred-couples",
    "sergio-garcia",
    "dustin-johnson",
    "zach-johnson",
    "hideki-matsuyama",
    "rory-mcilroy",
    "jose-maria-olazabal",
    "jon-rahm",
    "patrick-reed",
    "scottie-scheffler",
    "charl-schwartzel",
    "adam-scott",
    "vijay-singh",
    "jordan-spieth",
    "bubba-watson",
    "mike-weir",
    "danny-willett",
}

AMERICANS = {
    "daniel-berger",
    "akshay-bhatia",
    "keegan-bradley",
    "michael-brennan",
    "jacob-bridgeman",
    "sam-burns",
    "brian-campbell",
    "patrick-cantlay",
    "wyndham-clark",
    "fred-couples",
    "bryson-dechambeau",
    "harris-english",
    "ethan-fang",
    "ryan-gerard",
    "chris-gotterup",
    "max-greyserman",
    "ben-griffin",
    "brian-harman",
    "russell-henley",
    "jackson-herrington",
    "brandon-holtz",
    "max-homa",
    "mason-howell",
    "dustin-johnson",
    "zach-johnson",
    "john-keefer",
    "michael-kim",
    "kurt-kitayama",
    "jake-knapp",
    "brooks-koepka",
    "matt-mccarty",
    "maverick-mcnealy",
    "collin-morikawa",
    "andrew-novak",
    "patrick-reed",
    "davis-riley",
    "xander-schauffele",
    "scottie-scheffler",
    "jj-spaun",
    "jordan-spieth",
    "samuel-stevens",
    "justin-thomas",
    "bubba-watson",
    "gary-woodland",
    "cameron-young",
}

NON_PGA_TOUR = {
    "bryson-dechambeau",
    "patrick-reed",
    "sergio-garcia",
    "tyrrell-hatton",
    "dustin-johnson",
    "tom-mckibbin",
    "carlos-ortiz",
    "jon-rahm",
    "charl-schwartzel",
    "cameron-smith",
    "bubba-watson",
    "angel-cabrera",
    "fred-couples",
    "jose-maria-olazabal",
    "vijay-singh",
    "mike-weir",
    "casey-jarvis",
    "danny-willett",
}

ODDS_LABELS = {
    "scottie-scheffler": "+500",
    "bryson-dechambeau": "10/1",
    "jon-rahm": "11/1",
    "rory-mcilroy": "11/1",
    "ludvig-aberg": "15/1",
    "xander-schauffele": "17/1",
    "cameron-young": "22/1",
    "justin-rose": "30/1",
    "brooks-koepka": "40/1",
    "jordan-spieth": "40/1",
    "viktor-hovland": "45/1",
    "patrick-reed": "45/1",
    "robert-macintyre": "35/1",
    "tommy-fleetwood": "35/1",
    "justin-thomas": "80/1",
    "akshay-bhatia": "70/1",
    "shane-lowry": "80/1",
    "patrick-cantlay": "66/1",
    "dustin-johnson": "225/1",
}

AUTO_DRAFT_PRIORITY = [
    "scottie-scheffler",
    "bryson-dechambeau",
    "jon-rahm",
    "rory-mcilroy",
    "xander-schauffele",
    "ludvig-aberg",
    "matt-fitzpatrick",    
    "cameron-young",
    "tommy-fleetwood",    
    "hideki-matsuyama",    
    "robert-macintyre",
    "min-woo-lee",        
    "justin-rose",
    "patrick-reed",    
    "collin-morikawa",  
    "si-woo-kim",      
    "jordan-spieth",
    "brooks-koepka",
    "chris-gotterup",
    "russell-henley",
    "nicolai-hojgaard",
    "viktor-hovland",
    "akshay-bhatia",
    "maverick-mcnealy",
    "jake-knapp",
    "shane-lowry",
    "patrick-cantlay",  
    "justin-thomas",
    "adam-scott",
    "jason-day",
    "sepp-straka",
    "tyrrell-hatton",
    "jj-spaun",
    "corey-conners",
    "jacob-bridgeman",
    "sam-burns",
    "rasmus-hojgaard",
    "harris-english",
    "cameron-smith",
    "marco-penge",
    "sungjae-im",
    "gary-woodland",
    "kurt-kitayama",
    "daniel-berger",
    "ben-griffin",
    "alex-noren",
    "ryan-gerard",
    "samuel-stevens",
    "keegan-bradley",
    "harry-hall",
    "aldrich-potgieter",
    "aaron-rai",
    "kristoffer-reitan",
    "max-homa",
    "ryan-fox",
    "casey-jarvis",
    "wyndham-clark",
    "brian-harman",
    "dustin-johnson",
    "sergio-garcia",
    "nicolas-echavarria",
    "carlos-ortiz",
    "michael-kim",
    "max-greyserman",
    "nick-taylor",
    "haotong-li",
    "matt-mccarty",
    "rasmus-neergaard-petersen",
    "andrew-novak",
    "tom-mckibbin",
    "michael-brennan",
    "sami-valimaki",
    "john-keefer",
    "bubba-watson",
    "charl-schwartzel",
    "zach-johnson",
    "davis-riley",
    "angel-cabrera",
    "mason-howell",
    "fifa-laopakdee",
    "ethan-fang",
    "vijay-singh",
    "brian-campbell",
    "jose-maria-olazabal",
    "naoyuki-kataoka",
    "brandon-holtz",
    "danny-willett",
    "fred-couples",
    "mike-weir",
    "mateo-pulcini",
    "jackson-herrington",
]
AUTO_DRAFT_RANK = {name: idx + 1 for idx, name in enumerate(AUTO_DRAFT_PRIORITY)}


def player_meta_from_name(name: str) -> Dict[str, Any]:
    athlete_id = slugify(name)
    is_american = athlete_id in AMERICANS
    odds_rank = AUTO_DRAFT_RANK.get(athlete_id, 10_000)
    initials = " ".join(part[0] for part in name.replace(".", "").split()[:2]).upper()
    avatar_url = f"https://ui-avatars.com/api/?name={name.replace(' ', '+')}&size=128&background=145233&color=F5E7B1&bold=true"
    return {
        "athleteId": athlete_id,
        "name": name,
        "isPastChampion": athlete_id in PAST_CHAMPIONS,
        "isAmerican": is_american,
        "isInternational": not is_american,
        "isNonPga": athlete_id in NON_PGA_TOUR,
        "oddsRank": odds_rank,
        "oddsLabel": ODDS_LABELS.get(athlete_id),
        "avatarUrl": avatar_url,
        "initials": initials,
    }


def load_players() -> List[Dict[str, Any]]:
    if not os.path.exists(PLAYERS_CSV):
        raise HTTPException(status_code=500, detail="players.csv not found in backend folder.")
    players: List[Dict[str, Any]] = []
    with open(PLAYERS_CSV, "r", encoding="utf-8") as f:
        r = csv.DictReader(f)
        if "name" not in (r.fieldnames or []):
            raise HTTPException(status_code=500, detail="players.csv must have a 'name' column.")
        for row in r:
            name = (row.get("name") or "").strip()
            if name:
                players.append(player_meta_from_name(name))
    return players


def player_priority_score(player: Dict[str, Any]) -> int:
    return int(player.get("oddsRank") or AUTO_DRAFT_RANK.get(player["athleteId"], 10_000))


DRAFT_POOL = load_players()
PLAYER_MAP = {p["athleteId"]: p for p in DRAFT_POOL}
scorecards: Dict[str, LivePlayerScorecard] = {}


@dataclass
class User(BaseModel):
    user_id: str
    name: str
    is_host: bool = False
    spectator: bool = False    


class Room:
    def __init__(self):
        self.users: Dict[str, User] = {}
        self.sockets: Dict[str, WebSocket] = {}
        self.draft = DraftState(DraftConfig(roster_size=7, seconds_per_pick=60, snake=True, auto_pick=True))
        self.draft.reset_for_teams([])

    def host_id(self) -> Optional[str]:
        for uid, u in self.users.items():
            if u.is_host:
                return uid
        return None


ROOM = Room()

def seed_room_from_saved_state():
    saved = json.loads("""
        {"users":[{"userId":"2f1ae78d-31db-46b0-8d00-d49c4e3dd0fc","name":"Abhi","isHost":true},{"userId":"3371c79b-0517-4496-8b8c-f10b928822e8","name":"Big_Red","isHost":false},{"userId":"71816e0d-d31c-4294-b1ef-eeb44b583ced","name":"Billiam","isHost":false},{"userId":"f6cf8fb6-1691-4a64-8fed-735889ad1eca","name":"Chris","isHost":false},{"userId":"2582d355-6f51-4133-a118-39aa87fe737d","name":"Jay","isHost":false},{"userId":"934dd78c-7e9c-48a2-ad2e-f1cd4fc0d0a7","name":"jububi","isHost":false},{"userId":"03a6e9af-7809-42c7-b44f-db28673f0afa","name":"McKay","isHost":false},{"userId":"9985cc62-c0b9-4650-b1a5-8af4c5b98323","name":"Pooby","isHost":false},{"userId":"7bd36b58-4173-47a2-8fc5-bfc076f95754","name":"Shwinny","isHost":false},{"userId":"102552a1-ddca-419a-98c7-276554e158b0","name":"Steemy","isHost":false},{"userId":"8f881214-2dbb-4a25-81ee-2af64862b281","name":"THill","isHost":false},{"userId":"269cd19d-e0a7-4c8a-b507-5eb5bf62bf4c","name":"Tommy (Jynxzi) Dalrymple","isHost":false},{"userId":"3212295b-4f19-44ab-bf2a-c68badbca580","name":"Zubrow","isHost":false}],"slotLabels":{"past_champion":"Past Masters Champion","international":"International","american":"American","non_pga":"Non-PGA Tour","wildcard":"Wildcard","backup_1":"Backup 1","backup_2":"Backup 2"},"draft":{"started":true,"completed":true,"teams":["Steemy","Chris","Zubrow","Jay","Billiam","Shwinny","Tommy (Jynxzi) Dalrymple","Big_Red","THill","McKay","Pooby","Abhi","jububi"],"pickNo":92,"totalPicks":91,"currentTeam":null,"secondsLeft":null,"deadlineTs":null,"rosterSize":7,"secondsPerPick":30,"snake":true,"autoPick":true,"starterSlots":["past_champion","international","american","non_pga","wildcard"],"backupSlots":["backup_1","backup_2"],"picks":[{"pickNo":1,"team":"Steemy","athleteId":"scottie-scheffler","name":"Scottie Scheffler","slot":"past_champion","slotLabel":"Past Masters Champion","ts":1775692967.0334833},{"pickNo":2,"team":"Chris","athleteId":"jon-rahm","name":"Jon Rahm","slot":"past_champion","slotLabel":"Past Masters Champion","ts":1775692987.2158713},{"pickNo":3,"team":"Zubrow","athleteId":"jordan-spieth","name":"Jordan Spieth","slot":"past_champion","slotLabel":"Past Masters Champion","ts":1775693010.914368},{"pickNo":4,"team":"Jay","athleteId":"rory-mcilroy","name":"Rory McIlroy","slot":"past_champion","slotLabel":"Past Masters Champion","ts":1775693057.8563657},{"pickNo":5,"team":"Billiam","athleteId":"bryson-dechambeau","name":"Bryson DeChambeau","slot":"non_pga","slotLabel":"Non-PGA Tour","ts":1775693075.9968538},{"pickNo":6,"team":"Shwinny","athleteId":"xander-schauffele","name":"Xander Schauffele","slot":"american","slotLabel":"American","ts":1775693118.7568889},{"pickNo":7,"team":"Tommy (Jynxzi) Dalrymple","athleteId":"ludvig-aberg","name":"Ludvig Åberg","slot":"international","slotLabel":"International","ts":1775693135.9488535},{"pickNo":8,"team":"Big_Red","athleteId":"cameron-young","name":"Cameron Young","slot":"american","slotLabel":"American","ts":1775693146.2159007},{"pickNo":9,"team":"THill","athleteId":"hideki-matsuyama","name":"Hideki Matsuyama","slot":"past_champion","slotLabel":"Past Masters Champion","ts":1775693157.9847956},{"pickNo":10,"team":"McKay","athleteId":"cameron-smith","name":"Cameron Smith","slot":"non_pga","slotLabel":"Non-PGA Tour","ts":1775693189.084078},{"pickNo":11,"team":"Pooby","athleteId":"tommy-fleetwood","name":"Tommy Fleetwood","slot":"international","slotLabel":"International","ts":1775693230.2952378},{"pickNo":12,"team":"Abhi","athleteId":"patrick-reed","name":"Patrick Reed","slot":"past_champion","slotLabel":"Past Masters Champion","ts":1775693235.9507742},{"pickNo":13,"team":"jububi","athleteId":"matt-fitzpatrick","name":"Matt Fitzpatrick","slot":"international","slotLabel":"International","ts":1775693276.694482},{"pickNo":14,"team":"jububi","athleteId":"collin-morikawa","name":"Collin Morikawa","slot":"american","slotLabel":"American","ts":1775693322.9940393},{"pickNo":15,"team":"Abhi","athleteId":"tyrrell-hatton","name":"Tyrrell Hatton","slot":"non_pga","slotLabel":"Non-PGA Tour","ts":1775693331.031603},{"pickNo":16,"team":"Pooby","athleteId":"min-woo-lee","name":"Min Woo Lee","slot":"wildcard","slotLabel":"Wildcard","ts":1775693359.0843868},{"pickNo":17,"team":"McKay","athleteId":"viktor-hovland","name":"Viktor Hovland","slot":"international","slotLabel":"International","ts":1775693389.666652},{"pickNo":18,"team":"THill","athleteId":"brooks-koepka","name":"Brooks Koepka","slot":"american","slotLabel":"American","ts":1775693429.9479482},{"pickNo":19,"team":"Big_Red","athleteId":"adam-scott","name":"Adam Scott","slot":"past_champion","slotLabel":"Past Masters Champion","ts":1775693442.667095},{"pickNo":20,"team":"Tommy (Jynxzi) Dalrymple","athleteId":"akshay-bhatia","name":"Akshay Bhatia","slot":"american","slotLabel":"American","ts":1775693472.1241846},{"pickNo":21,"team":"Shwinny","athleteId":"dustin-johnson","name":"Dustin Johnson","slot":"past_champion","slotLabel":"Past Masters Champion","ts":1775693514.3034053},{"pickNo":22,"team":"Billiam","athleteId":"justin-rose","name":"Justin Rose","slot":"international","slotLabel":"International","ts":1775693562.7964797},{"pickNo":23,"team":"Jay","athleteId":"corey-conners","name":"Corey Conners","slot":"international","slotLabel":"International","ts":1775693619.306027},{"pickNo":24,"team":"Zubrow","athleteId":"robert-macintyre","name":"Robert MacIntyre","slot":"international","slotLabel":"International","ts":1775693678.7970119},{"pickNo":25,"team":"Chris","athleteId":"si-woo-kim","name":"Si Woo Kim","slot":"international","slotLabel":"International","ts":1775693738.6057913},{"pickNo":26,"team":"Steemy","athleteId":"nicolai-hojgaard","name":"Nicolai Højgaard","slot":"international","slotLabel":"International","ts":1775693786.308149},{"pickNo":27,"team":"Steemy","athleteId":"carlos-ortiz","name":"Carlos Ortiz","slot":"non_pga","slotLabel":"Non-PGA Tour","ts":1775693814.4359124},{"pickNo":28,"team":"Chris","athleteId":"chris-gotterup","name":"Chris Gotterup","slot":"american","slotLabel":"American","ts":1775693874.206413},{"pickNo":29,"team":"Zubrow","athleteId":"shane-lowry","name":"Shane Lowry","slot":"wildcard","slotLabel":"Wildcard","ts":1775693903.7064579},{"pickNo":30,"team":"Jay","athleteId":"jacob-bridgeman","name":"Jacob Bridgeman","slot":"american","slotLabel":"American","ts":1775693936.151686},{"pickNo":31,"team":"Billiam","athleteId":"russell-henley","name":"Russell Henley","slot":"american","slotLabel":"American","ts":1775693989.2610388},{"pickNo":32,"team":"Shwinny","athleteId":"jason-day","name":"Jason Day","slot":"international","slotLabel":"International","ts":1775694048.8021472},{"pickNo":33,"team":"Tommy (Jynxzi) Dalrymple","athleteId":"sergio-garcia","name":"Sergio Garcia","slot":"past_champion","slotLabel":"Past Masters Champion","ts":1775694079.5265553},{"pickNo":34,"team":"Big_Red","athleteId":"sepp-straka","name":"Sepp Straka","slot":"international","slotLabel":"International","ts":1775694082.6587458},{"pickNo":35,"team":"THill","athleteId":"rasmus-hojgaard","name":"Rasmus Højgaard","slot":"international","slotLabel":"International","ts":1775694117.1467652},{"pickNo":36,"team":"McKay","athleteId":"maverick-mcnealy","name":"Maverick McNealy","slot":"american","slotLabel":"American","ts":1775694148.145356},{"pickNo":37,"team":"Pooby","athleteId":"jj-spaun","name":"J.J. Spaun","slot":"american","slotLabel":"American","ts":1775694170.4730954},{"pickNo":38,"team":"Abhi","athleteId":"patrick-cantlay","name":"Patrick Cantlay","slot":"american","slotLabel":"American","ts":1775694179.6713915},{"pickNo":39,"team":"jububi","athleteId":"zach-johnson","name":"Zach Johnson","slot":"past_champion","slotLabel":"Past Masters Champion","ts":1775694199.7564871},{"pickNo":40,"team":"jububi","athleteId":"casey-jarvis","name":"Casey Jarvis","slot":"non_pga","slotLabel":"Non-PGA Tour","ts":1775694245.3983285},{"pickNo":41,"team":"Abhi","athleteId":"jake-knapp","name":"Jake Knapp","slot":"wildcard","slotLabel":"Wildcard","ts":1775694248.870355},{"pickNo":42,"team":"Pooby","athleteId":"vijay-singh","name":"Vijay Singh","slot":"non_pga","slotLabel":"Non-PGA Tour","ts":1775694275.6505072},{"pickNo":43,"team":"McKay","athleteId":"justin-thomas","name":"Justin Thomas","slot":"wildcard","slotLabel":"Wildcard","ts":1775694314.201247},{"pickNo":44,"team":"THill","athleteId":"sam-burns","name":"Sam Burns","slot":"wildcard","slotLabel":"Wildcard","ts":1775694321.2757006},{"pickNo":45,"team":"Big_Red","athleteId":"daniel-berger","name":"Daniel Berger","slot":"wildcard","slotLabel":"Wildcard","ts":1775694336.827426},{"pickNo":46,"team":"Tommy (Jynxzi) Dalrymple","athleteId":"tom-mckibbin","name":"Tom McKibbin","slot":"non_pga","slotLabel":"Non-PGA Tour","ts":1775694383.0396025},{"pickNo":47,"team":"Shwinny","athleteId":"bubba-watson","name":"Bubba Watson","slot":"non_pga","slotLabel":"Non-PGA Tour","ts":1775694401.81725},{"pickNo":48,"team":"Billiam","athleteId":"harris-english","name":"Harris English","slot":"wildcard","slotLabel":"Wildcard","ts":1775694449.1530843},{"pickNo":49,"team":"Jay","athleteId":"charl-schwartzel","name":"Charl Schwartzel","slot":"non_pga","slotLabel":"Non-PGA Tour","ts":1775694493.656164},{"pickNo":50,"team":"Zubrow","athleteId":"ben-griffin","name":"Ben Griffin","slot":"american","slotLabel":"American","ts":1775694507.7690353},{"pickNo":51,"team":"Chris","athleteId":"angel-cabrera","name":"Angel Cabrera","slot":"non_pga","slotLabel":"Non-PGA Tour","ts":1775694567.4028668},{"pickNo":52,"team":"Steemy","athleteId":"kurt-kitayama","name":"Kurt Kitayama","slot":"american","slotLabel":"American","ts":1775694612.4515054},{"pickNo":53,"team":"Steemy","athleteId":"sungjae-im","name":"Sungjae Im","slot":"wildcard","slotLabel":"Wildcard","ts":1775694632.8875082},{"pickNo":54,"team":"Chris","athleteId":"keegan-bradley","name":"Keegan Bradley","slot":"wildcard","slotLabel":"Wildcard","ts":1775694656.2213068},{"pickNo":55,"team":"Zubrow","athleteId":"fred-couples","name":"Fred Couples","slot":"non_pga","slotLabel":"Non-PGA Tour","ts":1775694664.045963},{"pickNo":56,"team":"Jay","athleteId":"max-homa","name":"Max Homa","slot":"wildcard","slotLabel":"Wildcard","ts":1775694692.3000703},{"pickNo":57,"team":"Billiam","athleteId":"jose-maria-olazabal","name":"Jose Maria Olazabal","slot":"past_champion","slotLabel":"Past Masters Champion","ts":1775694721.595674},{"pickNo":58,"team":"Shwinny","athleteId":"marco-penge","name":"Marco Penge","slot":"wildcard","slotLabel":"Wildcard","ts":1775694730.164586},{"pickNo":59,"team":"Tommy (Jynxzi) Dalrymple","athleteId":"gary-woodland","name":"Gary Woodland","slot":"wildcard","slotLabel":"Wildcard","ts":1775694759.9069066},{"pickNo":60,"team":"Big_Red","athleteId":"danny-willett","name":"Danny Willett","slot":"non_pga","slotLabel":"Non-PGA Tour","ts":1775694771.2973857},{"pickNo":61,"team":"THill","athleteId":"mike-weir","name":"Mike Weir","slot":"non_pga","slotLabel":"Non-PGA Tour","ts":1775694784.857023},{"pickNo":64,"team":"Abhi","athleteId":"aldrich-potgieter","name":"Aldrich Potgieter","slot":"international","slotLabel":"International","ts":1775694853.6775331},{"pickNo":65,"team":"jububi","athleteId":"samuel-stevens","name":"Samuel Stevens","slot":"wildcard","slotLabel":"Wildcard","ts":1775694878.620812},{"pickNo":66,"team":"jububi","athleteId":"alex-noren","name":"Alex Noren","slot":"backup_1","slotLabel":"Backup 1","ts":1775694908.4046075},{"pickNo":67,"team":"Abhi","athleteId":"ryan-gerard","name":"Ryan Gerard","slot":"backup_1","slotLabel":"Backup 1","ts":1775694918.1973667},{"pickNo":70,"team":"THill","athleteId":"harry-hall","name":"Harry Hall","slot":"backup_1","slotLabel":"Backup 1","ts":1775695006.798338},{"pickNo":71,"team":"Big_Red","athleteId":"aaron-rai","name":"Aaron Rai","slot":"backup_1","slotLabel":"Backup 1","ts":1775695035.8109314},{"pickNo":72,"team":"Tommy (Jynxzi) Dalrymple","athleteId":"wyndham-clark","name":"Wyndham Clark","slot":"backup_1","slotLabel":"Backup 1","ts":1775695050.2928734},{"pickNo":73,"team":"Shwinny","athleteId":"kristoffer-reitan","name":"Kristoffer Reitan","slot":"backup_1","slotLabel":"Backup 1","ts":1775695079.401122},{"pickNo":74,"team":"Billiam","athleteId":"brian-harman","name":"Brian Harman","slot":"backup_1","slotLabel":"Backup 1","ts":1775695097.8887444},{"pickNo":75,"team":"Jay","athleteId":"ryan-fox","name":"Ryan Fox","slot":"backup_1","slotLabel":"Backup 1","ts":1775695112.1840947},{"pickNo":76,"team":"Zubrow","athleteId":"nicolas-echavarria","name":"Nicolas Echavarria","slot":"backup_1","slotLabel":"Backup 1","ts":1775695142.1099172},{"pickNo":77,"team":"Chris","athleteId":"michael-kim","name":"Michael Kim","slot":"backup_1","slotLabel":"Backup 1","ts":1775695171.599033},{"pickNo":78,"team":"Steemy","athleteId":"rasmus-neergaard-petersen","name":"Rasmus Neergaard-Petersen","slot":"backup_1","slotLabel":"Backup 1","ts":1775695190.7465553},{"pickNo":79,"team":"Steemy","athleteId":"max-greyserman","name":"Max Greyserman","slot":"backup_2","slotLabel":"Backup 2","ts":1775695213.2104144},{"pickNo":80,"team":"Chris","athleteId":"nick-taylor","name":"Nick Taylor","slot":"backup_2","slotLabel":"Backup 2","ts":1775695242.2998729},{"pickNo":81,"team":"Zubrow","athleteId":"haotong-li","name":"Haotong Li","slot":"backup_2","slotLabel":"Backup 2","ts":1775695272.106382},{"pickNo":82,"team":"Jay","athleteId":"matt-mccarty","name":"Matt McCarty","slot":"backup_2","slotLabel":"Backup 2","ts":1775695301.801839},{"pickNo":83,"team":"Billiam","athleteId":"andrew-novak","name":"Andrew Novak","slot":"backup_2","slotLabel":"Backup 2","ts":1775695315.9486284},{"pickNo":84,"team":"Shwinny","athleteId":"michael-brennan","name":"Michael Brennan","slot":"backup_2","slotLabel":"Backup 2","ts":1775695345.7960708},{"pickNo":85,"team":"Tommy (Jynxzi) Dalrymple","athleteId":"sami-valimaki","name":"Sami Valimaki","slot":"backup_2","slotLabel":"Backup 2","ts":1775695355.018975},{"pickNo":86,"team":"Big_Red","athleteId":"ethan-fang","name":"Ethan Fang","slot":"backup_2","slotLabel":"Backup 2","ts":1775695380.3964362},{"pickNo":87,"team":"THill","athleteId":"john-keefer","name":"John Keefer","slot":"backup_2","slotLabel":"Backup 2","ts":1775695409.8050444},{"pickNo":90,"team":"Abhi","athleteId":"davis-riley","name":"Davis Riley","slot":"backup_2","slotLabel":"Backup 2","ts":1775695498.2053592},{"pickNo":91,"team":"jububi","athleteId":"mason-howell","name":"Mason Howell","slot":"backup_2","slotLabel":"Backup 2","ts":1775695515.5701945}],"rosters":{"Steemy":{"slots":{"past_champion":{"athleteId":"scottie-scheffler","name":"Scottie Scheffler","slot":"past_champion","slotLabel":"Past Masters Champion"},"international":{"athleteId":"nicolai-hojgaard","name":"Nicolai Højgaard","slot":"international","slotLabel":"International"},"american":{"athleteId":"kurt-kitayama","name":"Kurt Kitayama","slot":"american","slotLabel":"American"},"non_pga":{"athleteId":"carlos-ortiz","name":"Carlos Ortiz","slot":"non_pga","slotLabel":"Non-PGA Tour"},"wildcard":{"athleteId":"sungjae-im","name":"Sungjae Im","slot":"wildcard","slotLabel":"Wildcard"},"backup_1":{"athleteId":"rasmus-neergaard-petersen","name":"Rasmus Neergaard-Petersen","slot":"backup_1","slotLabel":"Backup 1"},"backup_2":{"athleteId":"max-greyserman","name":"Max Greyserman","slot":"backup_2","slotLabel":"Backup 2"}},"filledCount":7,"requiredFilled":true},"Chris":{"slots":{"past_champion":{"athleteId":"jon-rahm","name":"Jon Rahm","slot":"past_champion","slotLabel":"Past Masters Champion"},"international":{"athleteId":"si-woo-kim","name":"Si Woo Kim","slot":"international","slotLabel":"International"},"american":{"athleteId":"chris-gotterup","name":"Chris Gotterup","slot":"american","slotLabel":"American"},"non_pga":{"athleteId":"angel-cabrera","name":"Angel Cabrera","slot":"non_pga","slotLabel":"Non-PGA Tour"},"wildcard":{"athleteId":"keegan-bradley","name":"Keegan Bradley","slot":"wildcard","slotLabel":"Wildcard"},"backup_1":{"athleteId":"michael-kim","name":"Michael Kim","slot":"backup_1","slotLabel":"Backup 1"},"backup_2":{"athleteId":"nick-taylor","name":"Nick Taylor","slot":"backup_2","slotLabel":"Backup 2"}},"filledCount":7,"requiredFilled":true},"Zubrow":{"slots":{"past_champion":{"athleteId":"jordan-spieth","name":"Jordan Spieth","slot":"past_champion","slotLabel":"Past Masters Champion"},"international":{"athleteId":"robert-macintyre","name":"Robert MacIntyre","slot":"international","slotLabel":"International"},"american":{"athleteId":"ben-griffin","name":"Ben Griffin","slot":"american","slotLabel":"American"},"non_pga":{"athleteId":"fred-couples","name":"Fred Couples","slot":"non_pga","slotLabel":"Non-PGA Tour"},"wildcard":{"athleteId":"shane-lowry","name":"Shane Lowry","slot":"wildcard","slotLabel":"Wildcard"},"backup_1":{"athleteId":"nicolas-echavarria","name":"Nicolas Echavarria","slot":"backup_1","slotLabel":"Backup 1"},"backup_2":{"athleteId":"haotong-li","name":"Haotong Li","slot":"backup_2","slotLabel":"Backup 2"}},"filledCount":7,"requiredFilled":true},"Jay":{"slots":{"past_champion":{"athleteId":"rory-mcilroy","name":"Rory McIlroy","slot":"past_champion","slotLabel":"Past Masters Champion"},"international":{"athleteId":"corey-conners","name":"Corey Conners","slot":"international","slotLabel":"International"},"american":{"athleteId":"jacob-bridgeman","name":"Jacob Bridgeman","slot":"american","slotLabel":"American"},"non_pga":{"athleteId":"charl-schwartzel","name":"Charl Schwartzel","slot":"non_pga","slotLabel":"Non-PGA Tour"},"wildcard":{"athleteId":"max-homa","name":"Max Homa","slot":"wildcard","slotLabel":"Wildcard"},"backup_1":{"athleteId":"ryan-fox","name":"Ryan Fox","slot":"backup_1","slotLabel":"Backup 1"},"backup_2":{"athleteId":"matt-mccarty","name":"Matt McCarty","slot":"backup_2","slotLabel":"Backup 2"}},"filledCount":7,"requiredFilled":true},"Billiam":{"slots":{"past_champion":{"athleteId":"jose-maria-olazabal","name":"Jose Maria Olazabal","slot":"past_champion","slotLabel":"Past Masters Champion"},"international":{"athleteId":"justin-rose","name":"Justin Rose","slot":"international","slotLabel":"International"},"american":{"athleteId":"russell-henley","name":"Russell Henley","slot":"american","slotLabel":"American"},"non_pga":{"athleteId":"bryson-dechambeau","name":"Bryson DeChambeau","slot":"non_pga","slotLabel":"Non-PGA Tour"},"wildcard":{"athleteId":"harris-english","name":"Harris English","slot":"wildcard","slotLabel":"Wildcard"},"backup_1":{"athleteId":"brian-harman","name":"Brian Harman","slot":"backup_1","slotLabel":"Backup 1"},"backup_2":{"athleteId":"andrew-novak","name":"Andrew Novak","slot":"backup_2","slotLabel":"Backup 2"}},"filledCount":7,"requiredFilled":true},"Shwinny":{"slots":{"past_champion":{"athleteId":"dustin-johnson","name":"Dustin Johnson","slot":"past_champion","slotLabel":"Past Masters Champion"},"international":{"athleteId":"jason-day","name":"Jason Day","slot":"international","slotLabel":"International"},"american":{"athleteId":"xander-schauffele","name":"Xander Schauffele","slot":"american","slotLabel":"American"},"non_pga":{"athleteId":"bubba-watson","name":"Bubba Watson","slot":"non_pga","slotLabel":"Non-PGA Tour"},"wildcard":{"athleteId":"marco-penge","name":"Marco Penge","slot":"wildcard","slotLabel":"Wildcard"},"backup_1":{"athleteId":"kristoffer-reitan","name":"Kristoffer Reitan","slot":"backup_1","slotLabel":"Backup 1"},"backup_2":{"athleteId":"michael-brennan","name":"Michael Brennan","slot":"backup_2","slotLabel":"Backup 2"}},"filledCount":7,"requiredFilled":true},"Tommy (Jynxzi) Dalrymple":{"slots":{"past_champion":{"athleteId":"sergio-garcia","name":"Sergio Garcia","slot":"past_champion","slotLabel":"Past Masters Champion"},"international":{"athleteId":"ludvig-aberg","name":"Ludvig Åberg","slot":"international","slotLabel":"International"},"american":{"athleteId":"akshay-bhatia","name":"Akshay Bhatia","slot":"american","slotLabel":"American"},"non_pga":{"athleteId":"tom-mckibbin","name":"Tom McKibbin","slot":"non_pga","slotLabel":"Non-PGA Tour"},"wildcard":{"athleteId":"gary-woodland","name":"Gary Woodland","slot":"wildcard","slotLabel":"Wildcard"},"backup_1":{"athleteId":"wyndham-clark","name":"Wyndham Clark","slot":"backup_1","slotLabel":"Backup 1"},"backup_2":{"athleteId":"sami-valimaki","name":"Sami Valimaki","slot":"backup_2","slotLabel":"Backup 2"}},"filledCount":7,"requiredFilled":true},"Big_Red":{"slots":{"past_champion":{"athleteId":"adam-scott","name":"Adam Scott","slot":"past_champion","slotLabel":"Past Masters Champion"},"international":{"athleteId":"sepp-straka","name":"Sepp Straka","slot":"international","slotLabel":"International"},"american":{"athleteId":"cameron-young","name":"Cameron Young","slot":"american","slotLabel":"American"},"non_pga":{"athleteId":"danny-willett","name":"Danny Willett","slot":"non_pga","slotLabel":"Non-PGA Tour"},"wildcard":{"athleteId":"daniel-berger","name":"Daniel Berger","slot":"wildcard","slotLabel":"Wildcard"},"backup_1":{"athleteId":"aaron-rai","name":"Aaron Rai","slot":"backup_1","slotLabel":"Backup 1"},"backup_2":{"athleteId":"ethan-fang","name":"Ethan Fang","slot":"backup_2","slotLabel":"Backup 2"}},"filledCount":7,"requiredFilled":true},"THill":{"slots":{"past_champion":{"athleteId":"hideki-matsuyama","name":"Hideki Matsuyama","slot":"past_champion","slotLabel":"Past Masters Champion"},"international":{"athleteId":"rasmus-hojgaard","name":"Rasmus Højgaard","slot":"international","slotLabel":"International"},"american":{"athleteId":"brooks-koepka","name":"Brooks Koepka","slot":"american","slotLabel":"American"},"non_pga":{"athleteId":"mike-weir","name":"Mike Weir","slot":"non_pga","slotLabel":"Non-PGA Tour"},"wildcard":{"athleteId":"sam-burns","name":"Sam Burns","slot":"wildcard","slotLabel":"Wildcard"},"backup_1":{"athleteId":"harry-hall","name":"Harry Hall","slot":"backup_1","slotLabel":"Backup 1"},"backup_2":{"athleteId":"john-keefer","name":"John Keefer","slot":"backup_2","slotLabel":"Backup 2"}},"filledCount":7,"requiredFilled":true},"McKay":{"slots":{"past_champion":null,"international":{"athleteId":"viktor-hovland","name":"Viktor Hovland","slot":"international","slotLabel":"International"},"american":{"athleteId":"maverick-mcnealy","name":"Maverick McNealy","slot":"american","slotLabel":"American"},"non_pga":{"athleteId":"cameron-smith","name":"Cameron Smith","slot":"non_pga","slotLabel":"Non-PGA Tour"},"wildcard":{"athleteId":"justin-thomas","name":"Justin Thomas","slot":"wildcard","slotLabel":"Wildcard"},"backup_1":null,"backup_2":null},"filledCount":4,"requiredFilled":false},"Pooby":{"slots":{"past_champion":null,"international":{"athleteId":"tommy-fleetwood","name":"Tommy Fleetwood","slot":"international","slotLabel":"International"},"american":{"athleteId":"jj-spaun","name":"J.J. Spaun","slot":"american","slotLabel":"American"},"non_pga":{"athleteId":"vijay-singh","name":"Vijay Singh","slot":"non_pga","slotLabel":"Non-PGA Tour"},"wildcard":{"athleteId":"min-woo-lee","name":"Min Woo Lee","slot":"wildcard","slotLabel":"Wildcard"},"backup_1":null,"backup_2":null},"filledCount":4,"requiredFilled":false},"Abhi":{"slots":{"past_champion":{"athleteId":"patrick-reed","name":"Patrick Reed","slot":"past_champion","slotLabel":"Past Masters Champion"},"international":{"athleteId":"aldrich-potgieter","name":"Aldrich Potgieter","slot":"international","slotLabel":"International"},"american":{"athleteId":"patrick-cantlay","name":"Patrick Cantlay","slot":"american","slotLabel":"American"},"non_pga":{"athleteId":"tyrrell-hatton","name":"Tyrrell Hatton","slot":"non_pga","slotLabel":"Non-PGA Tour"},"wildcard":{"athleteId":"jake-knapp","name":"Jake Knapp","slot":"wildcard","slotLabel":"Wildcard"},"backup_1":{"athleteId":"ryan-gerard","name":"Ryan Gerard","slot":"backup_1","slotLabel":"Backup 1"},"backup_2":{"athleteId":"davis-riley","name":"Davis Riley","slot":"backup_2","slotLabel":"Backup 2"}},"filledCount":7,"requiredFilled":true},"jububi":{"slots":{"past_champion":{"athleteId":"zach-johnson","name":"Zach Johnson","slot":"past_champion","slotLabel":"Past Masters Champion"},"international":{"athleteId":"matt-fitzpatrick","name":"Matt Fitzpatrick","slot":"international","slotLabel":"International"},"american":{"athleteId":"collin-morikawa","name":"Collin Morikawa","slot":"american","slotLabel":"American"},"non_pga":{"athleteId":"casey-jarvis","name":"Casey Jarvis","slot":"non_pga","slotLabel":"Non-PGA Tour"},"wildcard":{"athleteId":"samuel-stevens","name":"Samuel Stevens","slot":"wildcard","slotLabel":"Wildcard"},"backup_1":{"athleteId":"alex-noren","name":"Alex Noren","slot":"backup_1","slotLabel":"Backup 1"},"backup_2":{"athleteId":"mason-howell","name":"Mason Howell","slot":"backup_2","slotLabel":"Backup 2"}},"filledCount":7,"requiredFilled":true}},"picked":["ryan-gerard","daniel-berger","xander-schauffele","ben-griffin","max-greyserman","sungjae-im","sami-valimaki","nicolas-echavarria","rasmus-hojgaard","mason-howell","robert-macintyre","ludvig-aberg","angel-cabrera","akshay-bhatia","dustin-johnson","patrick-cantlay","nicolai-hojgaard","aldrich-potgieter","harry-hall","jason-day","tom-mckibbin","harris-english","fred-couples","viktor-hovland","wyndham-clark","corey-conners","samuel-stevens","carlos-ortiz","marco-penge","sam-burns","matt-mccarty","zach-johnson","jose-maria-olazabal","jake-knapp","shane-lowry","bryson-dechambeau","charl-schwartzel","michael-kim","ryan-fox","jj-spaun","sepp-straka","john-keefer","mike-weir","alex-noren","chris-gotterup","matt-fitzpatrick","tyrrell-hatton","brian-harman","tommy-fleetwood","michael-brennan","haotong-li","jordan-spieth","rasmus-neergaard-petersen","cameron-smith","danny-willett","nick-taylor","casey-jarvis","jon-rahm","adam-scott","davis-riley","si-woo-kim","keegan-bradley","brooks-koepka","justin-rose","russell-henley","max-homa","jacob-bridgeman","kristoffer-reitan","gary-woodland","ethan-fang","collin-morikawa","sergio-garcia","maverick-mcnealy","cameron-young","justin-thomas","vijay-singh","patrick-reed","rory-mcilroy","kurt-kitayama","aaron-rai","hideki-matsuyama","andrew-novak","scottie-scheffler","min-woo-lee","bubba-watson"]}}
    """)

    draft_state = saved.get("draft", {})
    d = ROOM.draft

    d.teams = list(draft_state.get("teams", []))
    d.started = bool(draft_state.get("started", False))
    d.completed = bool(draft_state.get("completed", False))
    d.pick_no = int(draft_state.get("pickNo", 0) or 0)
    d.total_picks = int(draft_state.get("totalPicks", 0) or 0)
    d.team_index = int(draft_state.get("teamIndex", 0) or 0)
    d.direction = int(draft_state.get("direction", 1) or 1)
    d.deadline_ts = draft_state.get("deadlineTs")
    d.current_team_name = draft_state.get("currentTeam")

    # restore rosters exactly as saved
    d.rosters = {}
    for team_name, roster_info in draft_state.get("rosters", {}).items():
        saved_slots = roster_info.get("slots", {}) if isinstance(roster_info, dict) else {}
        base = d.empty_roster()
        for slot_name, player in saved_slots.items():
            if slot_name in base:
                base[slot_name] = player
        d.rosters[team_name] = base

    # restore pick history if present
    d.picks = list(draft_state.get("picks", []))

    # restore picked ids from the saved state if present, otherwise rebuild them
    saved_picked = draft_state.get("picked")
    if isinstance(saved_picked, list):
        d.picked_ids = set(saved_picked)
    else:
        rebuilt = set()
        for roster in d.rosters.values():
            for player in roster.values():
                if player and player.get("athleteId"):
                    rebuilt.add(player["athleteId"])
        d.picked_ids = rebuilt

    # ---- MANUAL FIXES FOR THE 6 UNDRAFTED PLAYERS ----
    # McKay gets Campbell, Fifa, Herrington
    if "McKay" in d.rosters:
        d.rosters["McKay"]["past_champion"] = player_meta_from_name("Brian Campbell") | {
            "slot": "past_champion",
            "slotLabel": SLOT_LABELS["past_champion"],
        }
        d.rosters["McKay"]["backup_1"] = player_meta_from_name("Fifa Laopakdee") | {
            "slot": "backup_1",
            "slotLabel": SLOT_LABELS["backup_1"],
        }
        d.rosters["McKay"]["backup_2"] = player_meta_from_name("Jackson Herrington") | {
            "slot": "backup_2",
            "slotLabel": SLOT_LABELS["backup_2"],
        }

    # Pooby gets Holtz, Kataoka, Pulcini
    if "Pooby" in d.rosters:
        d.rosters["Pooby"]["past_champion"] = player_meta_from_name("Naoyuki Kataoka") | {
            "slot": "past_champion",
            "slotLabel": SLOT_LABELS["past_champion"],
        }
        d.rosters["Pooby"]["backup_1"] = player_meta_from_name("Brandon Holtz") | {
            "slot": "backup_1",
            "slotLabel": SLOT_LABELS["backup_1"],
        }
        d.rosters["Pooby"]["backup_2"] = player_meta_from_name("Mateo Pulcini") | {
            "slot": "backup_2",
            "slotLabel": SLOT_LABELS["backup_2"],
        }

    # rebuild picked ids so the 6 manually-added players are marked unavailable
    rebuilt = set()
    for roster in d.rosters.values():
        for player in roster.values():
            if player and player.get("athleteId"):
                rebuilt.add(player["athleteId"])
    d.picked_ids = rebuilt

seed_room_from_saved_state()


async def broadcast(msg: Dict[str, Any]):
    dead: List[str] = []
    for uid, ws in list(ROOM.sockets.items()):
        try:
            await ws.send_json(msg)
        except Exception:
            dead.append(uid)
    for uid in dead:
        ROOM.sockets.pop(uid, None)


def serialize_room_state() -> Dict[str, Any]:
    users = [{"userId": u.user_id, "name": u.name, "isHost": u.is_host, "spectator": getattr(u, "spectator", False),} for u in ROOM.users.values()]
    users.sort(key=lambda x: (not x["isHost"], x["name"].lower()))

    d = ROOM.draft
    rosters_out: Dict[str, Dict[str, Any]] = {}
    for team in d.teams:
        roster = d.rosters.get(team, {})
        rosters_out[team] = {
            "slots": {slot: roster.get(slot) for slot in ALL_SLOTS},
            "filledCount": sum(1 for slot in ALL_SLOTS if roster.get(slot) is not None),
            "requiredFilled": all(roster.get(slot) is not None for slot in STARTER_SLOTS),
        }

    return {
        "users": users,
        "slotLabels": SLOT_LABELS,
        "draft": {
            "started": d.started,
            "completed": d.completed,
            "teams": d.teams,
            "pickNo": d.pick_no,
            "totalPicks": d.total_picks,
            "currentTeam": d.current_team(),
            "secondsLeft": d.remaining_seconds(),
            "deadlineTs": d.deadline_ts,
            "rosterSize": d.config.roster_size,
            "secondsPerPick": d.config.seconds_per_pick,
            "snake": d.config.snake,
            "autoPick": d.config.auto_pick,
            "starterSlots": STARTER_SLOTS,
            "backupSlots": BACKUP_SLOTS,
            "picks": [
                {
                    "pickNo": p.pick_no,
                    "team": p.team,
                    "athleteId": p.athlete_id,
                    "name": p.name,
                    "slot": p.slot,
                    "slotLabel": p.slot_label,
                    "ts": p.ts,
                }
                for p in d.picks
            ],
            "rosters": rosters_out,
            "picked": list(d.picked_ids),
        },
    }


def serialize_scoreboard() -> Dict[str, Any]:
    teams_out = build_team_scoreboard(ROOM.draft.rosters, scorecards)
    return {"teams": teams_out, "updatedTs": time.time()}


def next_open_slot_for_team(team_name: str) -> Optional[str]:
    roster = ROOM.draft.rosters.get(team_name, {})
    slot_order = [
        "past_champion",
        "international",
        "american",
        "non_pga",
        "wildcard",
        "backup_1",
        "backup_2",
    ]
    for slot in slot_order:
        if roster.get(slot) is None:
            return slot
    return None


def best_available_for_slot(team_name: str, slot: str) -> Optional[Dict[str, Any]]:
    d = ROOM.draft
    candidates = []

    for player in DRAFT_POOL:
        if player["athleteId"] in d.picked_ids:
            continue
        eligible = d.eligible_slots(team_name, player)
        if slot in eligible:
            candidates.append(player)

    if not candidates:
        return None

    candidates.sort(key=player_priority_score)
    return candidates[0]


def do_auto_pick_for_team(team_name: str) -> bool:
    d = ROOM.draft
    next_slot = next_open_slot_for_team(team_name)
    if not next_slot:
        return False

    player = best_available_for_slot(team_name, next_slot)
    if not player:
        return False

    d.make_pick(player["athleteId"], player["name"], next_slot, player)
    return True


async def draft_clock_loop():
    while True:
        await asyncio.sleep(1)
        d = ROOM.draft
        if not d.started or d.completed:
            continue
        if d.remaining_seconds() != 0:
            continue

        if not d.config.auto_pick:
            d.advance_turn()
            await broadcast({"type": "room_state", "data": serialize_room_state()})
            continue

        team = d.current_team()
        if not team:
            continue

        try:
            picked = do_auto_pick_for_team(team)
            if not picked:
                d.advance_turn()
        except Exception:
            d.advance_turn()

        await broadcast({"type": "room_state", "data": serialize_room_state()})


async def scoring_loop():
    while True:
        await asyncio.sleep(15)
        drafted_ids = list(ROOM.draft.picked_ids)
        if not drafted_ids:
            continue
        try:
            fetched = fetch_live_scorecards()
            filtered = {aid: sc for aid, sc in fetched.items() if aid in drafted_ids}
            scorecards.clear()
            scorecards.update(filtered)
            await broadcast({"type": "scoreboard", "data": serialize_scoreboard()})
        except Exception as e:
            await broadcast({"type": "error", "data": {"message": f"scoring_loop: {e}"}})


@app.on_event("startup")
async def _startup():
    asyncio.create_task(draft_clock_loop())
    asyncio.create_task(scoring_loop())


class JoinReq(BaseModel):
    userId: str
    name: str


class StartDraftReq(BaseModel):
    userId: str
    seconds_per_pick: Optional[int] = None
    roster_size: Optional[int] = None
    snake: Optional[bool] = None
    auto_pick: Optional[bool] = None


class MakePickReq(BaseModel):
    userId: str
    athlete_id: str
    name: str
    slot: Optional[str] = None


class UpdateTimerReq(BaseModel):
    userId: str
    seconds_per_pick: int


class AutoPickReq(BaseModel):
    userId: str


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/field")
def field(limit: int = 0):
    if limit and limit > 0:
        return {"players": DRAFT_POOL[:limit], "slotLabels": SLOT_LABELS}
    return {"players": DRAFT_POOL, "slotLabels": SLOT_LABELS}


@app.get("/api/state")
def state():
    return serialize_room_state()


@app.post("/api/join")
async def join(req: JoinReq):
    requested_name = (req.name or "").strip()[:30]
    existing = ROOM.users.get(req.userId)

    if existing:
        if requested_name:
            existing.name = requested_name
    else:
        if ROOM.draft.started or ROOM.draft.completed:
            ROOM.users[req.userId] = User(
                user_id=req.userId,
                name=requested_name or "Spectator",
                is_host=False,
                spectator=True,
            )
        else:
            ROOM.users[req.userId] = User(
                user_id=req.userId,
                name=requested_name or "Player",
                is_host=False,
                spectator=False,
            )

    if ROOM.host_id() is None and not ROOM.users[req.userId].spectator:
        ROOM.users[req.userId].is_host = True

    await broadcast({"type": "room_state", "data": serialize_room_state()})
    return serialize_room_state()


@app.post("/api/draft/start")
async def start_draft(req: StartDraftReq):
    u = ROOM.users.get(req.userId)
    if not u:
        raise HTTPException(status_code=401, detail="Join first.")
    if not u.is_host:
        raise HTTPException(status_code=403, detail="Only host can start the draft.")
    if len(ROOM.users) < 2:
        raise HTTPException(status_code=400, detail="Need at least 2 players to start.")

    if req.seconds_per_pick is not None:
        ROOM.draft.config.seconds_per_pick = int(req.seconds_per_pick)
    ROOM.draft.config.roster_size = 7
    if req.snake is not None:
        ROOM.draft.config.snake = bool(req.snake)
    if req.auto_pick is not None:
        ROOM.draft.config.auto_pick = bool(req.auto_pick)

    names = [usr.name for usr in ROOM.users.values()]
    random.shuffle(names)
    ROOM.draft.reset_for_teams(names)
    ROOM.draft.start()

    await broadcast({"type": "room_state", "data": serialize_room_state()})
    return serialize_room_state()


@app.post("/api/draft/reset")
async def reset_draft(req: StartDraftReq):
    u = ROOM.users.get(req.userId)
    if not u or not u.is_host:
        raise HTTPException(status_code=403, detail="Only host can reset.")
    ROOM.draft.reset_for_teams([])
    scorecards.clear()
    await broadcast({"type": "room_state", "data": serialize_room_state()})
    await broadcast({"type": "scoreboard", "data": serialize_scoreboard()})
    return serialize_room_state()


@app.post("/api/draft/timer")
async def update_timer(req: UpdateTimerReq):
    u = ROOM.users.get(req.userId)
    if not u or not u.is_host:
        raise HTTPException(status_code=403, detail="Only host can change the timer.")

    new_seconds = int(req.seconds_per_pick)
    if new_seconds < 5 or new_seconds > 300:
        raise HTTPException(status_code=400, detail="Timer must be between 5 and 300 seconds.")

    ROOM.draft.config.seconds_per_pick = new_seconds

    if ROOM.draft.started and not ROOM.draft.completed:
        ROOM.draft.deadline_ts = time.time() + new_seconds

    state_out = serialize_room_state()
    await broadcast({"type": "room_state", "data": state_out})
    return state_out


@app.post("/api/draft/auto-pick")
async def auto_pick(req: AutoPickReq):
    u = ROOM.users.get(req.userId)
    if not u:
        raise HTTPException(status_code=401, detail="Join first.")

    d = ROOM.draft
    if not d.started or d.completed:
        raise HTTPException(status_code=400, detail="Draft not active.")
    if d.current_team() != u.name:
        raise HTTPException(status_code=403, detail=f"Not your turn. On the clock: {d.current_team()}")

    picked = do_auto_pick_for_team(u.name)
    if not picked:
        raise HTTPException(status_code=400, detail="No valid auto-pick available.")

    state_out = serialize_room_state()
    await broadcast({"type": "room_state", "data": state_out})
    await broadcast({"type": "scoreboard", "data": serialize_scoreboard()})
    return state_out


@app.get("/api/draft/eligible-slots/{athlete_id}")
def eligible_slots(athlete_id: str, userId: str):
    u = ROOM.users.get(userId)
    if not u:
        raise HTTPException(status_code=401, detail="Join first.")
    d = ROOM.draft
    if not d.started or d.completed:
        raise HTTPException(status_code=400, detail="Draft not active.")
    player = PLAYER_MAP.get(athlete_id)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found.")
    return {"slots": d.eligible_slots(u.name, player)}


@app.post("/api/draft/pick")
async def make_pick(req: MakePickReq):
    u = ROOM.users.get(req.userId)
    if not u:
        raise HTTPException(status_code=401, detail="Join first.")

    d = ROOM.draft
    if not d.started or d.completed:
        raise HTTPException(status_code=400, detail="Draft not active.")
    if d.current_team() != u.name:
        raise HTTPException(status_code=403, detail=f"Not your turn. On the clock: {d.current_team()}")

    player = PLAYER_MAP.get(req.athlete_id)
    if not player:
        raise HTTPException(status_code=400, detail="Player not in draft pool.")
    if req.athlete_id in d.picked_ids:
        raise HTTPException(status_code=409, detail="Already drafted.")

    valid_slots = d.eligible_slots(u.name, player)
    if not valid_slots:
        raise HTTPException(status_code=400, detail="Player does not fit any available slot.")

    slot = req.slot
    if slot is None:
        if len(valid_slots) != 1:
            return {
                "needsSlotSelection": True,
                "slots": valid_slots,
                "slotLabels": {s: SLOT_LABELS[s] for s in valid_slots},
                "player": player,
            }
        slot = valid_slots[0]

    try:
        d.make_pick(req.athlete_id, req.name, slot, player)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    state_out = serialize_room_state()
    await broadcast({"type": "room_state", "data": state_out})
    await broadcast({"type": "scoreboard", "data": serialize_scoreboard()})
    return state_out


@app.get("/api/scoreboard")
def scoreboard():
    return serialize_scoreboard()


@app.get("/api/tournament-leaderboard")
def tournament_leaderboard():
    return {"leaderboard": get_leaderboard()}


@app.get("/api/player/{athlete_id}/holes")
def player_holes(athlete_id: str):
    sc = scorecards.get(athlete_id)
    if not sc:
        return {
            "athleteId": athlete_id,
            "name": athlete_id.replace("-", " ").title(),
            "holes": [],
            "fantasyPoints": 0,
            "basePoints": 0,
            "bonusPoints": 0,
            "placementBonus": 0,
            "scoringHighlights": [],
            "baseBreakdown": {},
            "bonusBreakdown": {},
            "placementBreakdown": {},
            "roundPoints": {},
            "madeCut": None,
        }

    return {
        "athleteId": sc.athlete_id,
        "name": sc.name,
        "fantasyPoints": sc.fantasy_points,
        "basePoints": sc.hole_points,
        "bonusPoints": sc.bonus_points,
        "placementBonus": sc.placement_bonus,
        "madeCut": sc.made_cut,
        "scoringHighlights": sc.scoring_highlights,
        "baseBreakdown": sc.round_base_breakdown,
        "bonusBreakdown": sc.round_bonus_breakdown,
        "placementBreakdown": sc.placement_breakdown,
        "roundPoints": sc.round_points,
        "holes": [
            {
                "round": h.round,
                "hole": h.hole,
                "par": h.par,
                "strokes": h.strokes,
                "result": h.result,
                "points": h.points,
                "bonusPoints": h.bonus_points,
                "totalPoints": round(h.points + h.bonus_points, 2),
            }
            for h in sc.holes
        ],
        "updatedTs": sc.updated_ts,
    }


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    user_id = ws.query_params.get("userId")
    if not user_id:
        await ws.close(code=1008)
        return

    await ws.accept()
    ROOM.sockets[user_id] = ws

    await ws.send_json({"type": "room_state", "data": serialize_room_state()})
    await ws.send_json({"type": "scoreboard", "data": serialize_scoreboard()})

    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        ROOM.sockets.pop(user_id, None)
    except Exception:
        ROOM.sockets.pop(user_id, None)