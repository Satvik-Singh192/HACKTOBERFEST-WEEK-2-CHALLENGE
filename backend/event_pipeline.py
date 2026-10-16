
from __future__ import annotations

from typing import Optional
from backend.events import Event, Icon
from backend.teamManager import TeamManager


class EventPipeline:
    """Pass recognized kill-feed events to the scoring backend."""

    def __init__(self, team_manager: TeamManager | None = None, sync_scoreboard: bool = True):
        self.team_manager = team_manager or TeamManager()
        self.processed_events = 0
        self.sync_scoreboard = sync_scoreboard

        # Automatically load roster if no teams registered
        if not self.team_manager.teams:
            self._load_roster_into_team_manager()

    def _load_roster_into_team_manager(self) -> None:
        try:
            from backend.state import store
            from backend.teams import Team, Player

            for entry in store.roster:
                team_name = entry.get("team", "")
                players = [
                    Player(name=p["name"])
                    for p in entry.get("players", [])
                    if p.get("name")
                ]
                if team_name and players and team_name not in self.team_manager.teams:
                    self.team_manager.add_team(Team(name=team_name, players=players))

            self.team_manager.initialize_player_matcher()
        except Exception as e:
            print(f"Notice: Could not auto-populate TeamManager roster: {e}")

    def process_event(self, event: Event) -> None:
        """Process one recognized event and update match state."""
        if not isinstance(event, Event):
            raise TypeError(
                f"Expected Event, received {type(event).__name__}"
            )

        # Let TeamManager own all scoring and player-state transitions.
        try:
            self.team_manager.process_events(event)
        except Exception as e:
            print(f"[EventPipeline] TeamManager: {e}")

        self.processed_events += 1

        # Sync with Scoreboard store and WebSocket broadcast
        if self.sync_scoreboard:
            self._sync_event_to_scoreboard(event)

    def _sync_event_to_scoreboard(self, event: Event) -> None:
        try:
            import json
            import urllib.request
            import urllib.error

            is_knock = Icon.KNOCK in event.icons
            is_kill = Icon.OBJECT in event.icons or (not is_knock and event.attacker and event.attacker != "Playzone")

            attacker_name = event.attacker
            victim_name = event.victim

            attacker_team = None
            if attacker_name and attacker_name != "Playzone":
                try:
                    attacker_team = self.team_manager.get_team(attacker_name).name
                except Exception:
                    attacker_team = attacker_name

            if is_kill and attacker_team:
                payload = json.dumps({
                    "team": attacker_team,
                    "player": attacker_name,
                    "delta": 1,
                }).encode("utf-8")
                url = "http://127.0.0.1:8000/api/kill"
                req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
                try:
                    with urllib.request.urlopen(req, timeout=0.8) as resp:
                        pass
                except Exception:
                    from backend.state import store
                    store.add_kill(team_name=attacker_team, player_name=attacker_name, delta=1)

            elif is_knock and attacker_team:
                payload = json.dumps({
                    "team": attacker_team,
                    "player": attacker_name,
                    "delta": 1,
                }).encode("utf-8")
                url = "http://127.0.0.1:8000/api/knock"
                req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
                try:
                    with urllib.request.urlopen(req, timeout=0.8) as resp:
                        pass
                except Exception:
                    from backend.state import store
                    store.add_knock(team_name=attacker_team, player_name=attacker_name, delta=1)
        except Exception as e:
            print(f"[EventPipeline] Scoreboard sync notice: {e}")
