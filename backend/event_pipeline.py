
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

            self.team_manager.teams.clear()
            self.team_manager.player_team_map.clear()
            self.team_manager.alias_to_canonical.clear()

            for entry in store.roster:
                team_name = entry.get("team", "")
                players = [
                    Player(name=p["name"], aliases=p.get("aliases", []))
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

        self.processed_events += 1

        # Sync with authoritative Scoreboard store and WebSocket broadcast
        if self.sync_scoreboard:
            self._sync_event_to_scoreboard(event)
        else:
            try:
                resolved_event = self.team_manager.resolve_event(event)
                self.team_manager.process_events(resolved_event)
            except Exception as e:
                print(f"[EventPipeline] TeamManager: {e}")

    def _sync_event_to_scoreboard(self, event: Event) -> None:
        try:
            import json
            import urllib.request
            import urllib.error

            payload = json.dumps({
                "attacker": event.attacker,
                "icons": [i.value if hasattr(i, "value") else str(i) for i in event.icons],
                "victim": event.victim,
            }).encode("utf-8")
            url = "http://127.0.0.1:8000/api/event"
            req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=1.0) as resp:
                    pass
            except Exception:
                from backend.state import store
                store.process_event(event)
        except Exception as e:
            print(f"[EventPipeline] Scoreboard sync notice: {e}")
