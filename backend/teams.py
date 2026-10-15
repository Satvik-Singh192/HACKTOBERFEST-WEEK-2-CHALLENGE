
from dataclasses import dataclass, field
from enum import Enum
class PlayerStatus(str, Enum):
    ALIVE = "alive"
    KNOCKED = "knocked"
    ELIMINATED = "eliminated"



@dataclass
class Player:
    name: str
    kills: int = 0
    status: PlayerStatus=PlayerStatus.ALIVE
    placement: int | None=None
    placementPoints: int=0
    


@dataclass
class Team:
    name: str
    players: list[Player] = field(default_factory=list)
    placement: int | None = None
    placement_points: int = 0
