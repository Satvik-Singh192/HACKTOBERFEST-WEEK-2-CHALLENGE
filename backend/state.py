"""State management and JSON persistence for the BGMI Live Scoreboard.

Stores and manages:
- Roster (Teams, Players, OCR Aliases, Colors)
- Tournament Settings & Points System (BGIS rules)
- Current Active Match (Status: LIVE / PAUSED / FINISHED, scores, player frags)
- Match History (Completed matches, cumulative standings)
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from backend.teamManager import TeamManager
    from backend.teams import Team, Player, PlayerStatus
    from backend.events import Event, Icon
except ImportError:
    from teamManager import TeamManager
    from teams import Team, Player, PlayerStatus
    from events import Event, Icon

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
ROSTER_FILE = DATA_DIR / "roster.json"
SETTINGS_FILE = DATA_DIR / "settings.json"
MATCH_FILE = DATA_DIR / "current_match.json"
HISTORY_FILE = DATA_DIR / "history.json"
ROI_CONFIG_FILE = DATA_DIR / "roi_config.json"

DEFAULT_SETTINGS: Dict[str, Any] = {
    "tournament_title": "BGMI Invitational Scrims Season 4",
    "active_map": "Erangel (Classic)",
    "current_match_number": 1,
    "total_matches": 6,
    "points_per_kill": 1,
    "placement_points": {
        "1": 10,
        "2": 6,
        "3": 5,
        "4": 4,
        "5": 3,
        "6": 2,
        "7": 1,
        "8": 1,
    },
    "overlay_config": {
        "scoreboard_visible": True,
        "fraggers_visible": True,
        "fraggers_mode": "top5",  # "top5" or "mvp"
    },
}

DEFAULT_ROSTER: List[Dict[str, Any]] = [
    {
        "team": "FLx",
        "color": "#38BDF8",
        "players": [
            {"name": "FLx_ELNoiX", "aliases": []},
            {"name": "OGxKRISH", "aliases": []},
            {"name": "LSxGBplayzYT", "aliases": []},
            {"name": "AyushShivam", "aliases": []},
        ],
    },
    {
        "team": "SANDHU",
        "color": "#F59E0B",
        "players": [
            {"name": "SANDHU", "aliases": []},
            {"name": "KISHANKINGE", "aliases": []},
            {"name": "beastjokerrr", "aliases": []},
            {"name": "AyushRaj5513", "aliases": []},
        ],
    },
    {
        "team": "TEAM 3",
        "color": "#10B981",
        "players": [
            {"name": "IMxVAISHNAV", "aliases": []},
            {"name": "KALASHI", "aliases": []},
            {"name": "DarthPotato", "aliases": []},
            {"name": "JAYKISHAN", "aliases": []},
        ],
    },
    {
        "team": "NEMESIS",
        "color": "#EF4444",
        "players": [
            {"name": "NEMESIS", "aliases": []},
            {"name": "YADAV", "aliases": []},
            {"name": "ALPHA_BEAST", "aliases": []},
            {"name": "UNKN0WN", "aliases": []},
        ],
    },
    {
        "team": "DEVILS",
        "color": "#8B5CF6",
        "players": [
            {"name": "Devils_Empero", "aliases": []},
            {"name": "JyotishmoyNar", "aliases": []},
            {"name": "tmkoc", "aliases": []},
            {"name": "abHishekSingha", "aliases": []},
        ],
    },
    {
        "team": "TTx",
        "color": "#F97316",
        "players": [
            {"name": "SOHAMtheGR8", "aliases": []},
            {"name": "TTXAYUSH45", "aliases": []},
            {"name": "TTxRex8", "aliases": []},
            {"name": "Suryawannshi", "aliases": []},
        ],
    },
    {
        "team": "CODESTROYER",
        "color": "#06B6D4",
        "players": [
            {"name": "codestroyer", "aliases": []},
            {"name": "kl0ishere", "aliases": []},
            {"name": "vapouriser2918", "aliases": []},
        ],
    },
    {
        "team": "REAPER",
        "color": "#EC4899",
        "players": [
            {"name": "AmanXY", "aliases": []},
            {"name": "Satlaw933", "aliases": []},
            {"name": "barbadaadmi69", "aliases": []},
            {"name": "REAPERislive", "aliases": []},
        ],
    },
    {
        "team": "TS",
        "color": "#EAB308",
        "players": [
            {"name": "TS_PRESENCE", "aliases": []},
            {"name": "TS_FRAGGER", "aliases": []},
            {"name": "TS_HARSH", "aliases": []},
            {"name": "SNIDE", "aliases": []},
        ],
    },
    {
        "team": "4DM",
        "color": "#14B8A6",
        "players": [
            {"name": "4DMxRevdiiiii", "aliases": []},
            {"name": "TMPxKiNGOP", "aliases": []},
            {"name": "KGF_TONY", "aliases": []},
            {"name": "realnikk", "aliases": []},
        ],
    },
    {
        "team": "EQX",
        "color": "#6366F1",
        "players": [
            {"name": "EQX_SHUBH", "aliases": []},
            {"name": "AR_DYNAMIC", "aliases": []},
            {"name": "rathouranurag", "aliases": []},
            {"name": "EQX_SAHIL", "aliases": []},
        ],
    },
    {
        "team": "IIIT",
        "color": "#84CC16",
        "players": [
            {"name": "saxena_ji", "aliases": []},
            {"name": "IIITianAman", "aliases": []},
            {"name": "uv_is_Live", "aliases": []},
            {"name": "alphadevil", "aliases": []},
        ],
    },
    {
        "team": "ANURAG",
        "color": "#A855F7",
        "players": [
            {"name": "ANURAG", "aliases": []},
        ],
    },
]

# Testing Roster matching the video and TeamManager definitions
TESTING_VIDEO_ROSTER: List[Dict[str, Any]] = DEFAULT_ROSTER

# Official BMSD Pro Testing Roster (16 teams, 76 players)
BMSD_TEAMS: Dict[str, List[str]] = {
    "NINZ": [
        "NINZ Fierce",
        "NINZ Apollo",
        "NINZ Auxin",
        "NINZ Shadow7",
        "NINZ javin",
    ],
    "IQOO 8BIT": [
        "IQOO 8BIT Sarang",
        "IQOO 8BIT Juicy",
        "IQOO 8BIT Shubh",
        "IQOO 8BIT skipzz",
        "IQOO 8BIT Shorty",
    ],
    "IQOO RNTX": [
        "IQOO RNTX Tracegod",
        "IQOO RNTX Pain",
        "IQOO RNTX NinjaJod",
        "IQOO RNTX ProToN",
        "IQOO RNTX Sukuna",
    ],
    "BLEG": [
        "BLEG Areeb",
        "BLEG EGGY",
        "BLEG Lobster",
        "BLEG Ralphie",
        "BLEG FanOP",
    ],
    "TAG": [
        "TAG Jelly",
        "TAG KioLmao",
        "TAG JONATHAN",
        "TAG Hydro",
        "TAG Harsh",
    ],
    "NBE": [
        "NBE Aadi",
        "NBE Arjun",
        "NBE KRATOS",
        "NBE Phoenix",
        "NBE KnowMe",
    ],
    "IQOO SOUL": [
        "IQOO SOUL Goblin",
        "IQOO SOUL NakuL",
        "IQOO SOUL LEGIT",
        "IQOO SOUL Thunder",
        "IQOO SOUL Jokerr",
    ],
    "K9": [
        "K9 Saumraj",
        "K9 SnowJOD",
        "K9 Smoker46",
        "K9 Taurus",
        "K9 Stranger",
    ],
    "V1BA": [
        "V1BA Punkk",
        "V1BA Omega",
        "V1BA Termi",
        "V1BA Shayaan",
        "V1BA Achuk",
    ],
    "GODL": [
        "GODL Manya",
        "GODL ADMINO",
        "GODL Spower",
        "GODL Godz",
        "GODL Saumay",
    ],
    "OR": [
        "OR Omega",
        "OR NinjaBoi",
        "OR Slug",
        "OR Knight",
    ],
    "GDR": [
        "GDR Neyo",
        "GDR AquaNox",
        "GDR DeltaPG",
        "GDR Justin",
    ],
    "MYTH": [
        "MYTH Lucifer",
        "MYTH Daddy",
        "MYTH Detrox",
        "MYTH Harshil",
        "MYTH Aryton",
    ],
    "WELT": [
        "WELT DragonOP",
        "WELT PokoWNL",
        "WELT Rico",
        "WELT SHYAM",
        "WELT GokulWNL",
    ],
    "GEN": [
        "GEN HunterZ",
        "GEN Zap",
        "GEN GravityJOD",
        "GEN FurY",
        "GEN VipeR",
    ],
    "WF": [
        "WF Kanha",
        "WF SENSEI",
        "WF Goten",
        "WF SPRAYGOD",
        "WF Sam999",
    ],
}

BMSD_COLORS = [
    "#E11D48", "#F59E0B", "#10B981", "#3B82F6",
    "#8B5CF6", "#EC4899", "#06B6D4", "#14B8A6",
    "#F97316", "#EAB308", "#6366F1", "#84CC16",
    "#A855F7", "#D97706", "#0284C7", "#DC2626",
]

BMSD_TEST_ROSTER: List[Dict[str, Any]] = [
    {
        "team": tname,
        "color": BMSD_COLORS[idx % len(BMSD_COLORS)],
        "players": [{"name": p, "aliases": []} for p in players],
    }
    for idx, (tname, players) in enumerate(BMSD_TEAMS.items())
]


def _ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _load_json(file_path: Path, default_val: Any) -> Any:
    _ensure_data_dir()
    if not file_path.is_file():
        _save_json(file_path, default_val)
        return deepcopy(default_val)
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return deepcopy(default_val)


def _save_json(file_path: Path, data: Any) -> None:
    _ensure_data_dir()
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


class StateStore:
    def __init__(self) -> None:
        self.settings: Dict[str, Any] = _load_json(SETTINGS_FILE, DEFAULT_SETTINGS)
        self.roster: List[Dict[str, Any]] = _load_json(ROSTER_FILE, DEFAULT_ROSTER)
        self.history: List[Dict[str, Any]] = _load_json(HISTORY_FILE, [])

        self.team_manager = TeamManager()
        self._init_team_manager_from_roster()

        # Initialize or load current match
        current = _load_json(MATCH_FILE, None)
        if current and "team_manager_state" in current:
            try:
                self.team_manager.load_from_dict(current["team_manager_state"])
                self.current_match = current
                self.current_match["teams"] = self._build_teams_list()
            except Exception as e:
                print(f"[StateStore] Warning loading team_manager_state: {e}")
                self.current_match = self._create_initial_match(
                    match_number=self.settings.get("current_match_number", 1),
                    map_name=self.settings.get("active_map", "Erangel (Classic)")
                )
                self._save_match()
        else:
            self.current_match = self._create_initial_match(
                match_number=self.settings.get("current_match_number", 1),
                map_name=self.settings.get("active_map", "Erangel (Classic)")
            )
            self._save_match()

        self._last_match_mtime: float = MATCH_FILE.stat().st_mtime if MATCH_FILE.is_file() else 0.0

    def reload_if_updated_externally(self) -> None:
        """Reload from MATCH_FILE if updated on disk by an external process."""
        if not MATCH_FILE.is_file():
            return
        try:
            mtime = MATCH_FILE.stat().st_mtime
            if mtime > getattr(self, "_last_match_mtime", 0.0) + 0.005:
                current = _load_json(MATCH_FILE, None)
                if current and "team_manager_state" in current:
                    self.team_manager.load_from_dict(current["team_manager_state"])
                    self.current_match = current
                    self.current_match["teams"] = self._build_teams_list()
                    self._last_match_mtime = mtime
        except Exception:
            pass

    def _init_team_manager_from_roster(self) -> None:
        self.team_manager.teams.clear()
        self.team_manager.player_team_map.clear()
        self.team_manager.alias_to_canonical.clear()
        self.team_manager.last_knocked_by.clear()
        self.team_manager.eliminatedTeams = 0

        for entry in self.roster:
            team_name = entry.get("team", "").strip()
            if not team_name:
                continue
            players = []
            for p in entry.get("players", []):
                p_name = p.get("name", "").strip()
                if p_name:
                    aliases = p.get("aliases", [])
                    players.append(Player(name=p_name, aliases=aliases))
            if players and team_name not in self.team_manager.teams:
                self.team_manager.add_team(Team(name=team_name, players=players))

        self.team_manager.initialize_player_matcher()

    def _build_teams_list(self) -> List[Dict[str, Any]]:
        teams_list: List[Dict[str, Any]] = []
        for team in self.team_manager.teams.values():
            color = self.get_team_color(team.name)
            kills = sum(p.kills for p in team.players)
            knocks = sum(1 for p in team.players if p.status == PlayerStatus.KNOCKED)
            place = team.placement_points
            total = kills + place
            eliminated = bool(
                team.placement is not None
                or (team.players and all(p.status == PlayerStatus.ELIMINATED for p in team.players))
            )
            alive_count = sum(1 for p in team.players if p.status != PlayerStatus.ELIMINATED)
            players_info = [
                {
                    "name": p.name,
                    "kills": p.kills,
                    "status": p.status.value,
                }
                for p in team.players
            ]
            teams_list.append({
                "team": team.name,
                "color": color,
                "kills": kills,
                "knocks": knocks,
                "place": place,
                "placement": team.placement,
                "total": total,
                "eliminated": eliminated,
                "alive_count": alive_count,
                "total_players": len(team.players),
                "players": players_info,
            })

        teams_list.sort(key=lambda t: (t["total"], t["kills"]), reverse=True)
        for idx, t in enumerate(teams_list):
            t["rank"] = idx + 1
        return teams_list

    def _create_initial_match(self, match_number: int, map_name: str) -> Dict[str, Any]:
        self._init_team_manager_from_roster()
        return {
            "status": "LIVE",  # "LIVE", "PAUSED", "FINISHED"
            "match_number": match_number,
            "map": map_name,
            "teams": self._build_teams_list(),
            "team_manager_state": self.team_manager.to_dict(),
            "events_log": [],
        }

    def _save_match(self) -> None:
        self.current_match["team_manager_state"] = self.team_manager.to_dict()
        self.current_match["teams"] = self._build_teams_list()
        _save_json(MATCH_FILE, self.current_match)
        if MATCH_FILE.is_file():
            try:
                self._last_match_mtime = MATCH_FILE.stat().st_mtime
            except Exception:
                pass

    def _save_roster(self) -> None:
        _save_json(ROSTER_FILE, self.roster)

    def _save_settings(self) -> None:
        _save_json(SETTINGS_FILE, self.settings)

    def _save_history(self) -> None:
        _save_json(HISTORY_FILE, self.history)

    # ------------------ Match Lifecycle ------------------
    def get_status(self) -> str:
        return self.current_match.get("status", "LIVE")

    def set_status(self, status: str) -> Dict[str, Any]:
        valid = ["LIVE", "PAUSED", "FINISHED"]
        if status.upper() in valid:
            self.current_match["status"] = status.upper()
            self._save_match()
        return self.get_match_snapshot()

    def start_new_match(self, map_name: Optional[str] = None) -> Dict[str, Any]:
        cur_num = self.current_match.get("match_number", 1) + 1
        self.settings["current_match_number"] = cur_num
        active_map = map_name or self.settings.get("active_map", "Erangel (Classic)")
        self.settings["active_map"] = active_map
        self._save_settings()

        self.current_match = self._create_initial_match(cur_num, active_map)
        self._save_match()
        return self.get_match_snapshot()

    def reset_current_match(self) -> Dict[str, Any]:
        cur_num = self.current_match.get("match_number", 1)
        cur_map = self.current_match.get("map", "Erangel")
        self.current_match = self._create_initial_match(cur_num, cur_map)
        self._save_match()
        return self.get_match_snapshot()

    def end_match(self) -> Dict[str, Any]:
        """Finalize scores, assign placement points according to BGIS matrix, and save to history."""
        # Find remaining alive teams
        alive_teams = [
            t for t in self.team_manager.teams.values()
            if t.placement is None and any(p.status != PlayerStatus.ELIMINATED for p in t.players)
        ]
        if len(alive_teams) == 1:
            winner = alive_teams[0]
            winner.placement = 1
            winner.placement_points += 4
        elif len(alive_teams) > 1:
            alive_teams.sort(key=lambda t: sum(p.kills for p in t.players), reverse=True)
            placement_matrix = self.settings.get("placement_points", DEFAULT_SETTINGS["placement_points"])
            for rank_idx, t in enumerate(alive_teams, start=1):
                t.placement = rank_idx
                t.placement_points = int(placement_matrix.get(str(rank_idx), 0))

        self.current_match["status"] = "FINISHED"
        self._save_match()

        teams_list = self._build_teams_list()
        winner_name = teams_list[0]["team"] if teams_list else "None"

        # Archive to tournament history
        history_entry = {
            "match_number": self.current_match.get("match_number", 1),
            "map": self.current_match.get("map", "Erangel"),
            "timestamp": self.current_match.get("finished_at", None),
            "winner": winner_name,
            "teams": deepcopy(teams_list),
            "player_kills": {
                p.name: p.kills
                for t in self.team_manager.teams.values()
                for p in t.players
            },
        }
        self.history.append(history_entry)
        self._save_history()

        return self.get_match_snapshot()

    # ------------------ Model Ingestion & Actions ------------------
    def process_event(self, event: Event) -> Dict[str, Any]:
        """Process authoritative kill-feed Event through TeamManager."""
        if self.get_status() in ["PAUSED", "FINISHED"]:
            return self.get_match_snapshot()

        self.team_manager.process_events(event)
        self.current_match.setdefault("events_log", []).append({
            "type": "event",
            "attacker": event.attacker,
            "icons": [i.value if hasattr(i, "value") else str(i) for i in event.icons],
            "victim": event.victim,
        })
        self._save_match()
        return self.get_match_snapshot()

    def add_kill(self, team_name: str, player_name: Optional[str] = None, delta: int = 1) -> Optional[Dict[str, Any]]:
        if self.get_status() in ["PAUSED", "FINISHED"]:
            return None

        matched_player = None
        # 1. Try finding player by player_name
        if player_name:
            try:
                matched_player = self.team_manager.get_player(player_name)
            except KeyError:
                pass

        # 2. If no player found, check if team_name itself is a player name
        if not matched_player:
            try:
                matched_player = self.team_manager.get_player(team_name)
            except KeyError:
                pass

        # 3. If still not found, check if team_name is a team
        if not matched_player:
            for t in self.team_manager.teams.values():
                if t.name.upper() == team_name.strip().upper():
                    if t.players:
                        matched_player = t.players[0]
                    break

        if matched_player:
            matched_player.kills = max(0, matched_player.kills + delta)
            self.current_match.setdefault("events_log", []).append({
                "type": "kill",
                "team": team_name,
                "player": matched_player.name,
                "delta": delta,
            })
            self._save_match()
        else:
            print(f"[Notice] add_kill could not match entity: '{team_name}' / '{player_name}'")

        return self.get_match_snapshot()

    def add_knock(self, team_name: str, player_name: Optional[str] = None, delta: int = 1) -> Optional[Dict[str, Any]]:
        if self.get_status() in ["PAUSED", "FINISHED"]:
            return None

        target = player_name or team_name
        try:
            player = self.team_manager.get_player(target)
            player.status = PlayerStatus.KNOCKED
            self.current_match.setdefault("events_log", []).append({
                "type": "knock",
                "team": team_name,
                "player": player.name,
                "delta": delta,
            })
            self._save_match()
        except KeyError:
            pass

        return self.get_match_snapshot()

    def eliminate_team(self, team_name: str) -> Dict[str, Any]:
        target_team = None
        for t in self.team_manager.teams.values():
            if t.name.upper() == team_name.strip().upper():
                target_team = t
                break

        if not target_team:
            try:
                target_team = self.team_manager.get_team(team_name)
            except KeyError:
                pass

        if target_team and target_team.placement is None:
            for p in target_team.players:
                p.status = PlayerStatus.ELIMINATED
            self.team_manager.awardPlacementPoints(target_team)
            self.current_match.setdefault("events_log", []).append({
                "type": "eliminate",
                "team": target_team.name,
            })
            self._save_match()

        return self.get_match_snapshot()

    def undo_last_action(self) -> Optional[Dict[str, Any]]:
        events = self.current_match.get("events_log", [])
        if not events:
            return None
        last = events.pop()
        if last.get("type") == "kill":
            pname = last.get("player")
            delta = last.get("delta", 1)
            if pname:
                try:
                    p = self.team_manager.get_player(pname)
                    p.kills = max(0, p.kills - delta)
                except KeyError:
                    pass
            self._save_match()
            return self.get_match_snapshot()
        return None

    # ------------------ Roster Management ------------------
    def get_team_color(self, team_name: str) -> str:
        for r in self.roster:
            if r.get("team", "").upper() == team_name.upper():
                return r.get("color", "#94A3B8")
        return "#94A3B8"

    def update_team(self, team_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        name = team_data.get("team", "").strip().upper()
        if not name:
            return self.roster

        found = False
        for idx, item in enumerate(self.roster):
            if item.get("team", "").upper() == name:
                self.roster[idx] = {
                    "team": name,
                    "color": team_data.get("color", item.get("color", "#94A3B8")),
                    "players": team_data.get("players", item.get("players", [])),
                }
                found = True
                break

        if not found:
            self.roster.append({
                "team": name,
                "color": team_data.get("color", "#94A3B8"),
                "players": team_data.get("players", []),
            })

        self._save_roster()
        self._sync_match_with_roster()
        return self.roster

    def delete_team(self, team_name: str) -> List[Dict[str, Any]]:
        name = team_name.strip().upper()
        self.roster = [r for r in self.roster if r.get("team", "").upper() != name]
        self._save_roster()
        self._sync_match_with_roster()
        return self.roster

    def reset_roster_defaults(self) -> List[Dict[str, Any]]:
        self.roster = deepcopy(DEFAULT_ROSTER)
        self._save_roster()
        self._sync_match_with_roster()
        return self.roster

    def load_testing_roster(self) -> List[Dict[str, Any]]:
        """Switch to video testing roster (TS, NEMESIS, FLx, TEAM 9)."""
        self.roster = deepcopy(TESTING_VIDEO_ROSTER)
        self._save_roster()
        self._sync_match_with_roster()
        return self.roster

    def load_default_roster(self) -> List[Dict[str, Any]]:
        """Switch to standard tournament roster (KRAIT, NOVA, ZENITH, etc.)."""
        self.roster = deepcopy(DEFAULT_ROSTER)
        self._save_roster()
        self._sync_match_with_roster()
        return self.roster

    def load_bmsd_roster(self) -> List[Dict[str, Any]]:
        """Switch to official BMSD 16-team testing roster."""
        self.roster = deepcopy(BMSD_TEST_ROSTER)
        self._save_roster()
        self._sync_match_with_roster()
        return self.roster

    def sync_from_team_manager(self, team_manager: Any = None) -> List[Dict[str, Any]]:
        """Extract teams and players directly from a TeamManager instance."""
        if team_manager is None:
            try:
                from backend.teamManager import TeamManager
                team_manager = TeamManager()
                team_manager.load_video_testing_teams()
            except Exception:
                return self.roster

        new_roster = []
        default_colors = ["#38BDF8", "#F43F5E", "#A855F7", "#EAB308", "#FF7A45", "#4DA3FF", "#A78BFA", "#2DD4BF"]
        for idx, (tname, team_obj) in enumerate(team_manager.teams.items()):
            color = default_colors[idx % len(default_colors)]
            players = []
            for p in getattr(team_obj, "players", []):
                players.append({
                    "name": p.name,
                    "aliases": getattr(p, "aliases", [])
                })
            new_roster.append({
                "team": tname.upper(),
                "color": color,
                "players": players
            })

        if new_roster:
            self.roster = new_roster
            self._save_roster()
            self._sync_match_with_roster()
        return self.roster

    def _sync_match_with_roster(self) -> None:
        """Keep TeamManager and current match in sync with updated roster."""
        existing_players: Dict[str, Any] = {}
        for team in self.team_manager.teams.values():
            for p in team.players:
                existing_players[p.name] = (p.kills, p.status)

        self._init_team_manager_from_roster()

        for team in self.team_manager.teams.values():
            for p in team.players:
                if p.name in existing_players:
                    p.kills, p.status = existing_players[p.name]

        self._save_match()

    def get_ocr_roster_lookup(self) -> Dict[str, List[str]]:
        """Format team roster into { TeamName: [Player, Aliases...] } for SingleRowKillfeedOCR."""
        lookup: Dict[str, List[str]] = {}
        for r in self.roster:
            tname = r.get("team", "")
            players = []
            for p in r.get("players", []):
                pname = p.get("name", "")
                if pname:
                    players.append(pname)
                for a in p.get("aliases", []):
                    if a:
                        players.append(a)
            lookup[tname] = players
        return lookup

    # ------------------ Settings Management ------------------
    def update_settings(self, new_settings: Dict[str, Any]) -> Dict[str, Any]:
        self.settings.update(new_settings)
        self._save_settings()
        self.current_match["map"] = self.settings.get("active_map", "Erangel")
        self._save_match()
        return self.settings

    def get_overlay_config(self) -> Dict[str, Any]:
        default_cfg = {
            "scoreboard_visible": True,
            "fraggers_visible": True,
            "fraggers_mode": "top5",
        }
        cfg = self.settings.get("overlay_config", {})
        merged = deepcopy(default_cfg)
        merged.update(cfg)
        return merged

    def update_overlay_config(self, patch: Dict[str, Any]) -> Dict[str, Any]:
        cfg = self.get_overlay_config()
        cfg.update(patch)
        self.settings["overlay_config"] = cfg
        self._save_settings()
        return cfg

    # ------------------ Snapshots & Queries ------------------
    def get_match_snapshot(self) -> Dict[str, Any]:
        """Full data snapshot broadcast to WebSockets and returned by /scoreboard."""
        self.reload_if_updated_externally()
        teams = self._build_teams_list()
        top_fraggers = self.get_top_fraggers(limit=5)
        top_player = (
            top_fraggers[0]
            if top_fraggers and top_fraggers[0]["kills"] > 0
            else None
        )

        return {
            "version": self.current_match.get("version", 1),
            "status": self.get_status(),  # LIVE, PAUSED, FINISHED
            "match_number": self.current_match.get("match_number", 1),
            "total_matches": self.settings.get("total_matches", 6),
            "map": self.current_match.get("map", "Erangel"),
            "tournament_title": self.settings.get("tournament_title", "BGMI Tournament"),
            "teams": teams,
            "top_fraggers": top_fraggers,
            "mvp": top_player,
            "overlay_config": self.get_overlay_config(),
        }

    def get_top_fraggers(self, limit: int = 5) -> List[Dict[str, Any]]:
        fraggers = []
        for team in self.team_manager.teams.values():
            color = self.get_team_color(team.name)
            for p in team.players:
                fraggers.append({
                    "player": p.name,
                    "team": team.name,
                    "color": color,
                    "kills": p.kills,
                    "knocks": 1 if p.status == PlayerStatus.KNOCKED else 0,
                    "status": p.status.value,
                    "gun": "M416",
                })

        fraggers.sort(key=lambda x: (x["kills"], 1 if x["status"] != "eliminated" else 0), reverse=True)
        for idx, f in enumerate(fraggers[:limit]):
            f["rank"] = idx + 1
        return fraggers[:limit]

    def get_accumulated_history(self) -> Dict[str, Any]:
        """Aggregate stats across all archived matches."""
        team_totals: Dict[str, Dict[str, Any]] = {}
        for r in self.roster:
            tname = r.get("team", "")
            team_totals[tname] = {
                "team": tname,
                "color": r.get("color", "#94A3B8"),
                "matches_played": 0,
                "wwcd": 0,
                "kills": 0,
                "place": 0,
                "total": 0,
            }

        for match in self.history:
            winner = match.get("winner")
            for t in match.get("teams", []):
                tname = t.get("team", "")
                if tname not in team_totals:
                    team_totals[tname] = {
                        "team": tname,
                        "color": t.get("color", "#94A3B8"),
                        "matches_played": 0,
                        "wwcd": 0,
                        "kills": 0,
                        "place": 0,
                        "total": 0,
                    }
                rec = team_totals[tname]
                rec["matches_played"] += 1
                rec["kills"] += t.get("kills", 0)
                rec["place"] += t.get("place", 0)
                rec["total"] += t.get("total", 0)
                if tname == winner:
                    rec["wwcd"] += 1

        standings = list(team_totals.values())
        standings.sort(key=lambda x: x["total"], reverse=True)
        for idx, s in enumerate(standings):
            s["rank"] = idx + 1

        return {
            "total_matches": len(self.history),
            "matches": self.history,
            "overall_standings": standings,
        }


# Singleton instance
store = StateStore()
