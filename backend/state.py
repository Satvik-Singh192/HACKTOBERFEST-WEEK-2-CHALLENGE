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

        # Initialize or load current match
        current = _load_json(MATCH_FILE, None)
        if not current or "teams" not in current or not current["teams"]:
            self.current_match = self._create_initial_match(
                match_number=self.settings.get("current_match_number", 1),
                map_name=self.settings.get("active_map", "Erangel (Classic)")
            )
            self._save_match()
        else:
            self.current_match = current

    def _create_initial_match(self, match_number: int, map_name: str) -> Dict[str, Any]:
        teams: List[Dict[str, Any]] = []
        for idx, entry in enumerate(self.roster):
            teams.append({
                "rank": idx + 1,
                "team": entry["team"],
                "color": entry.get("color", "#94A3B8"),
                "kills": 0,
                "place": 0,
                "total": 0,
                "knocks": 0,
                "eliminated": False,
            })

        return {
            "status": "LIVE",  # "LIVE", "PAUSED", "FINISHED"
            "match_number": match_number,
            "map": map_name,
            "teams": teams,
            "player_kills": {},
            "player_knocks": {},
            "events_log": [],
        }

    def _save_match(self) -> None:
        _save_json(MATCH_FILE, self.current_match)

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

    def end_match(self) -> Dict[str, Any]:
        """Finalize scores, assign placement points according to BGIS matrix, and save to history."""
        teams = self.current_match.get("teams", [])
        alive = [t for t in teams if not t.get("eliminated")]

        # Winner gets WWCD (1st place)
        placement_matrix = self.settings.get("placement_points", DEFAULT_SETTINGS["placement_points"])

        # Sort remaining alive teams by kills as tiebreaker, assign top spots
        alive.sort(key=lambda t: t.get("kills", 0), reverse=True)
        assigned_rank = 1
        for t in alive:
            t["place"] = int(placement_matrix.get(str(assigned_rank), 0))
            t["total"] = t["kills"] + t["place"]
            assigned_rank += 1

        # Re-sort all teams by total points
        teams.sort(key=lambda t: t.get("total", 0), reverse=True)
        for idx, t in enumerate(teams):
            t["rank"] = idx + 1

        self.current_match["status"] = "FINISHED"
        self._save_match()

        # Archive to tournament history
        history_entry = {
            "match_number": self.current_match.get("match_number", 1),
            "map": self.current_match.get("map", "Erangel"),
            "timestamp": self.current_match.get("finished_at", None),
            "winner": teams[0]["team"] if teams else "None",
            "teams": deepcopy(teams),
            "player_kills": deepcopy(self.current_match.get("player_kills", {})),
        }
        self.history.append(history_entry)
        self._save_history()

        return self.get_match_snapshot()

    # ------------------ Kill & Knock Actions ------------------
    def add_kill(self, team_name: str, player_name: Optional[str] = None, delta: int = 1) -> Optional[Dict[str, Any]]:
        # If match is stopped or paused, refuse new kills!
        if self.get_status() in ["PAUSED", "FINISHED"]:
            return None

        teams = self.current_match.get("teams", [])
        normalized_team = team_name.strip().upper()
        team_names_set = {t.get("team", "").upper(): t for t in teams}
        target_team = team_names_set.get(normalized_team)

        # If team_name not found, check if it's a player name or alias in roster
        if not target_team:
            for r in self.roster:
                r_team = r.get("team", "").upper()
                for p in r.get("players", []):
                    p_name = p.get("name", "").upper()
                    aliases = [a.upper() for a in p.get("aliases", [])]
                    if normalized_team == p_name or normalized_team in aliases:
                        if not player_name:
                            player_name = p.get("name")
                        target_team = team_names_set.get(r_team)
                        normalized_team = r_team
                        break
                if target_team:
                    break

        # If still not found, check if it's a team in roster not yet in current_match
        if not target_team:
            for r in self.roster:
                if r.get("team", "").upper() == normalized_team:
                    color = r.get("color", "#94A3B8")
                    target_team = {
                        "rank": len(teams) + 1,
                        "team": normalized_team,
                        "color": color,
                        "kills": 0,
                        "place": 0,
                        "total": 0,
                        "knocks": 0,
                        "eliminated": False,
                    }
                    teams.append(target_team)
                    break

        # Ignore completely unknown entities so fake teams never pollute the scoreboard
        if not target_team:
            print(f"[Notice] Scoreboard ignored unregistered entity: '{team_name}'")
            return self.get_match_snapshot()

        target_team["kills"] = max(0, target_team.get("kills", 0) + delta)
        target_team["total"] = target_team["kills"] + target_team.get("place", 0)

        # Update player kill counter
        if player_name:
            p_kills = self.current_match.setdefault("player_kills", {})
            p_kills[player_name] = max(0, p_kills.get(player_name, 0) + delta)

        # Log event
        self.current_match.setdefault("events_log", []).append({
            "type": "kill",
            "team": normalized_team,
            "player": player_name,
            "delta": delta,
        })

        # Re-sort teams by total points descending
        teams.sort(key=lambda t: t.get("total", 0), reverse=True)
        for idx, t in enumerate(teams):
            t["rank"] = idx + 1

        self._save_match()
        return self.get_match_snapshot()

    def add_knock(self, team_name: str, player_name: Optional[str] = None, delta: int = 1) -> Optional[Dict[str, Any]]:
        if self.get_status() in ["PAUSED", "FINISHED"]:
            return None

        teams = self.current_match.get("teams", [])
        normalized_team = team_name.strip().upper()
        team_names_set = {t.get("team", "").upper(): t for t in teams}
        target_team = team_names_set.get(normalized_team)

        if not target_team:
            for r in self.roster:
                r_team = r.get("team", "").upper()
                for p in r.get("players", []):
                    p_name = p.get("name", "").upper()
                    aliases = [a.upper() for a in p.get("aliases", [])]
                    if normalized_team == p_name or normalized_team in aliases:
                        target_team = team_names_set.get(r_team)
                        break
                if target_team:
                    break

        if target_team:
            target_team["knocks"] = max(0, target_team.get("knocks", 0) + delta)

        if player_name:
            p_knocks = self.current_match.setdefault("player_knocks", {})
            p_knocks[player_name] = max(0, p_knocks.get(player_name, 0) + delta)

        self._save_match()
        return self.get_match_snapshot()

    def eliminate_team(self, team_name: str) -> Dict[str, Any]:
        teams = self.current_match.get("teams", [])
        placement_matrix = self.settings.get("placement_points", DEFAULT_SETTINGS["placement_points"])

        alive = [t for t in teams if not t.get("eliminated")]
        finish_rank = len(alive)  # e.g., if 8 alive, first out gets 8th place

        for t in teams:
            if t.get("team", "").upper() == team_name.upper() and not t.get("eliminated"):
                t["eliminated"] = True
                t["place"] = int(placement_matrix.get(str(finish_rank), 1))
                t["total"] = t["kills"] + t["place"]
                break

        teams.sort(key=lambda t: t.get("total", 0), reverse=True)
        for idx, t in enumerate(teams):
            t["rank"] = idx + 1

        self._save_match()
        return self.get_match_snapshot()

    def undo_last_action(self) -> Optional[Dict[str, Any]]:
        events = self.current_match.get("events_log", [])
        if not events:
            return None
        last = events.pop()
        if last.get("type") == "kill":
            team = last.get("team", "")
            player = last.get("player")
            delta = last.get("delta", 1)
            # Reverse delta
            teams = self.current_match.get("teams", [])
            for t in teams:
                if t.get("team", "").upper() == team.upper():
                    t["kills"] = max(0, t.get("kills", 0) - delta)
                    t["total"] = t["kills"] + t.get("place", 0)
                    break
            if player:
                p_kills = self.current_match.setdefault("player_kills", {})
                p_kills[player] = max(0, p_kills.get(player, 0) - delta)

            teams.sort(key=lambda t: t.get("total", 0), reverse=True)
            for idx, t in enumerate(teams):
                t["rank"] = idx + 1

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
        """Keep current match team list in sync with updated roster."""
        match_teams = self.current_match.setdefault("teams", [])
        existing_names = {t.get("team", "").upper(): t for t in match_teams}

        new_teams = []
        for r in self.roster:
            name = r.get("team", "").upper()
            if name in existing_names:
                t = existing_names[name]
                t["color"] = r.get("color", "#94A3B8")
                new_teams.append(t)
            else:
                new_teams.append({
                    "rank": len(new_teams) + 1,
                    "team": name,
                    "color": r.get("color", "#94A3B8"),
                    "kills": 0,
                    "place": 0,
                    "total": 0,
                    "knocks": 0,
                    "eliminated": False,
                })

        new_teams.sort(key=lambda t: t.get("total", 0), reverse=True)
        for idx, t in enumerate(new_teams):
            t["rank"] = idx + 1

        self.current_match["teams"] = new_teams
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

    # ------------------ Snapshots & Queries ------------------
    def get_match_snapshot(self) -> Dict[str, Any]:
        """Full data snapshot broadcast to WebSockets and returned by /scoreboard."""
        top_fraggers = self.get_top_fraggers(limit=5)
        top_player = top_fraggers[0] if top_fraggers else {"player": "None", "team": "None", "kills": 0, "knocks": 0}

        return {
            "version": self.current_match.get("version", 1),
            "status": self.get_status(),  # LIVE, PAUSED, FINISHED
            "match_number": self.current_match.get("match_number", 1),
            "total_matches": self.settings.get("total_matches", 6),
            "map": self.current_match.get("map", "Erangel"),
            "tournament_title": self.settings.get("tournament_title", "BGMI Tournament"),
            "teams": deepcopy(self.current_match.get("teams", [])),
            "top_fraggers": top_fraggers,
            "mvp": top_player,
        }

    def get_top_fraggers(self, limit: int = 5) -> List[Dict[str, Any]]:
        p_kills = self.current_match.get("player_kills", {})
        p_knocks = self.current_match.get("player_knocks", {})

        # Find team for each player
        player_to_team = {}
        for r in self.roster:
            tname = r.get("team", "")
            for p in r.get("players", []):
                player_to_team[p.get("name", "")] = tname

        fraggers = []
        # If no player kills logged yet, pull player names from roster with 0 kills
        all_players = set(p_kills.keys()).union(player_to_team.keys())
        for pname in all_players:
            if not pname:
                continue
            kills = p_kills.get(pname, 0)
            knocks = p_knocks.get(pname, 0)
            team = player_to_team.get(pname, "Unknown")
            fraggers.append({
                "player": pname,
                "team": team,
                "kills": kills,
                "knocks": knocks,
                "gun": "M416",
            })

        fraggers.sort(key=lambda x: (x["kills"], x["knocks"]), reverse=True)
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
