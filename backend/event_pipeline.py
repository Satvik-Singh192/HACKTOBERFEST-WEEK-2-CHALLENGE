
from backend.events import Event
from backend.teamManager import TeamManager


class EventPipeline:
    """Pass recognized kill-feed events to the scoring backend."""

    def __init__(self, team_manager: TeamManager | None = None):
        self.team_manager = team_manager or TeamManager()
        self.processed_events = 0

    def process_event(self, event: Event) -> None:
        """Process one recognized event and update match state."""
        if not isinstance(event, Event):
            raise TypeError(
                f"Expected Event, received {type(event).__name__}"
            )

        # Let TeamManager own all scoring and player-state transitions.
        self.team_manager.process_events(event)
        self.processed_events += 1
