from dataclasses import dataclass

from enum import Enum
class Icon(str,Enum):
    PLAYZONE="zone"
    KNOCK="knock"
    OBJECT= "obj"

@dataclass
class Event:
    attacker: str | None
    icons:list[str]
    victim:str