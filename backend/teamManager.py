import sys
from pathlib import Path

# Allow direct execution: `python teamManager.py` from inside backend/ or `python -m backend.teamManager` from root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.teams import Team, Player, PlayerStatus
from backend.events import Event, Icon
from backend.playerMatcher import PlayerMatcher

class TeamManager:
    def __init__(self):
        self.teams: dict[str, Team] = {}
        self.player_team_map: dict[str, str] = {}
        self.alias_to_canonical: dict[str, str] = {}
        self.last_knocked_by: dict[str, str] = {}
        self.eliminatedTeams = 0
        self.player_matcher = None

    def add_team(self, team: Team) -> None:
        if team.name in self.teams:
            raise ValueError(f"Team already exists: {team.name}")
        for player in team.players:
            if player.name in self.player_team_map:
                raise ValueError(
                    f"Player already registered: {player.name}"
                )
        self.teams[team.name] = team

        for player in team.players:
            self.player_team_map[player.name] = team.name
            for alias in getattr(player, "aliases", []):
                self.alias_to_canonical[alias] = player.name
                self.player_team_map[alias] = team.name

    def initialize_player_matcher(self) -> None:
        self.player_matcher = PlayerMatcher(self.player_team_map, self.alias_to_canonical)

    def get_player(self, player_name: str) -> Player:
        canonical_name = self.alias_to_canonical.get(player_name, player_name)
        team_name = self.player_team_map.get(canonical_name)

        if team_name is None:
            raise KeyError(f"Unknown player: {player_name}")

        team = self.teams[team_name]

        for player in team.players:
            if player.name == canonical_name:
                return player

        raise RuntimeError("Player-team mapping is inconsistent")

    def get_team(self, player_name: str) -> Team:
        canonical_name = self.alias_to_canonical.get(player_name, player_name)
        team_name = self.player_team_map.get(canonical_name)

        if team_name is None:
            raise KeyError(f"Unknown player: {player_name}")

        return self.teams[team_name]
    
    
    def resolve_event(self, event: Event) -> Event:
        if self.player_matcher is None:
            raise RuntimeError(
                "Call initialize_player_matcher() after registering teams"
            )

        victim = self.player_matcher.match(event.victim)

        if victim is None:
            raise ValueError(
                f"Could not confidently match victim: {event.victim}"
            )

        attacker = event.attacker

        if attacker is not None:
            if attacker.casefold() == "playzone":
                attacker = "Playzone"
            else:
                attacker = self.player_matcher.match(attacker)

                if attacker is None:
                    raise ValueError(
                        f"Could not confidently match attacker: {event.attacker}"
                    )

        from dataclasses import replace

        return replace(event, attacker=attacker, victim=victim)

    def process_events(self, event: Event) -> None:
        event = self.resolve_event(event)
        victim = self.get_player(event.victim)
        victim_team = self.get_team(event.victim)

        # knock handler
        if Icon.KNOCK in event.icons:
            if event.attacker is None:
                return

            victim.status = PlayerStatus.KNOCKED
            self.last_knocked_by[event.victim] = event.attacker
            return

        # finish handler
        if Icon.OBJECT in event.icons:
            previous_knocker = self.last_knocked_by.get(event.victim)

            # Victim is eliminated regardless of who finished them.
            victim.status = PlayerStatus.ELIMINATED
            self.check_team_elimination(victim_team)

            if event.attacker is not None and event.attacker.casefold() != "playzone":
                # A known, actual player finished the victim.
                finisher_team = self.get_team(event.attacker)
            
                if finisher_team.name != victim_team.name:
                    self.get_player(event.attacker).kills += 1

                elif (
                    previous_knocker is not None
                    and previous_knocker.casefold() != "playzone"
                ):
                    knocker_team = self.get_team(previous_knocker)
                    if knocker_team.name != victim_team.name:
                        self.get_player(previous_knocker).kills += 1

            elif previous_knocker is not None:
                if previous_knocker.casefold() != "playzone":
                    knocker_team = self.get_team(previous_knocker)
                    if knocker_team.name != victim_team.name:
                        self.get_player(previous_knocker).kills += 1

            self.last_knocked_by.pop(event.victim, None)

    
    def awardPlacementPoints(self, team: Team) -> None:
        # Prevent duplicate placement awards
        if team.placement is not None:
            return

        self.eliminatedTeams += 1

        # First eliminated team = 10th place
        team.placement = len(self.teams) - self.eliminatedTeams + 1

        # Your exact rules:
        # 10th: +0, 9th: +0, 8th: +1,
        # 7th: +0, 6th to 2nd: +1 each
        if team.placement in {8, 6, 5, 4, 3, 2}:
            for other_team in self.teams.values():

                # Skip teams already eliminated prior to this elimination
                if other_team.placement is not None and other_team is not team:
                    continue

                # Award only to teams with at least one non-eliminated player (or team itself finishing at this milestone)
                is_alive = any(
                    player.status != PlayerStatus.ELIMINATED
                    for player in other_team.players
                )

                if is_alive or other_team is team:
                    other_team.placement_points += 1
                    print(
                        f"{other_team.name}: +1 placement point "
                        f"(total: {other_team.placement_points})"
                    )

        print(
            f"\n{team.name} finished {team.placement}th"
            f"\nPlacement points: {team.placement_points}"
        )

        # Find the last surviving team
        alive_teams = [
            current_team
            for current_team in self.teams.values()
            if current_team.placement is None
            and any(
                player.status != PlayerStatus.ELIMINATED
                for player in current_team.players
            )
        ]

        # Chicken Dinner bonus
        if len(alive_teams) == 1:
            winner = alive_teams[0]
            winner.placement = 1
            winner.placement_points += 4

            print(f"\nCHICKEN DINNER: {winner.name}")
            print(
                f"Final placement points: "
                f"{winner.placement_points}"
            )

    def check_team_elimination(self, team: Team) -> None:
        if team.placement is not None:
            return

        is_eliminated = all(
            player.status == PlayerStatus.ELIMINATED
            for player in team.players
        )

        if is_eliminated:
            self.awardPlacementPoints(team)

    def to_dict(self) -> dict:
        return {
            "teams": {
                name: {
                    "name": t.name,
                    "placement": t.placement,
                    "placement_points": t.placement_points,
                    "players": [
                        {
                            "name": p.name,
                            "kills": p.kills,
                            "status": p.status.value,
                            "placement": p.placement,
                            "placementPoints": p.placementPoints,
                        }
                        for p in t.players
                    ]
                }
                for name, t in self.teams.items()
            },
            "last_knocked_by": dict(self.last_knocked_by),
            "eliminatedTeams": self.eliminatedTeams,
        }

    def load_from_dict(self, data: dict) -> None:
        teams_data = data.get("teams", {})
        for team_name, t_info in teams_data.items():
            if team_name in self.teams:
                team = self.teams[team_name]
                team.placement = t_info.get("placement")
                team.placement_points = t_info.get("placement_points", 0)
                p_map = {p["name"]: p for p in t_info.get("players", [])}
                for player in team.players:
                    if player.name in p_map:
                        p_data = p_map[player.name]
                        player.kills = p_data.get("kills", 0)
                        try:
                            player.status = PlayerStatus(p_data.get("status", "alive"))
                        except Exception:
                            player.status = PlayerStatus.ALIVE
            else:
                players = []
                for p_data in t_info.get("players", []):
                    p_status = PlayerStatus.ALIVE
                    try:
                        p_status = PlayerStatus(p_data.get("status", "alive"))
                    except Exception:
                        pass
                    players.append(Player(
                        name=p_data["name"],
                        kills=p_data.get("kills", 0),
                        status=p_status,
                    ))
                team = Team(
                    name=team_name,
                    players=players,
                    placement=t_info.get("placement"),
                    placement_points=t_info.get("placement_points", 0),
                )
                self.teams[team_name] = team
                for p in players:
                    self.player_team_map[p.name] = team_name

        self.last_knocked_by = dict(data.get("last_knocked_by", {}))
        self.eliminatedTeams = data.get("eliminatedTeams", 0)
        self.initialize_player_matcher()

    def load_video_testing_teams(self) -> None:
        """Register the exact teams and players present in the testing video."""
        self.teams.clear()
        self.player_team_map.clear()
        self.alias_to_canonical.clear()

        self.add_team(Team(
            name="FLx",
            players=[
                Player(name="FLx_ELNoiX"),
                Player(name="OGxKRISH"),
                Player(name="LSxGBplayzYT"),
                Player(name="AyushShivam"),
            ],
        ))

        self.add_team(Team(
            name="SANDHU",
            players=[
                Player(name="SANDHU"),
                Player(name="KISHANKINGE"),
                Player(name="beastjokerrr"),
                Player(name="AyushRaj5513"),
            ],
        ))

        self.add_team(Team(
            name="TEAM 3",
            players=[
                Player(name="IMxVAISHNAV"),
                Player(name="KALASHI"),
                Player(name="DarthPotato"),
                Player(name="JAYKISHAN"),
            ],
        ))

        self.add_team(Team(
            name="NEMESIS",
            players=[
                Player(name="NEMESIS"),
                Player(name="YADAV"),
                Player(name="ALPHA_BEAST"),
                Player(name="UNKN0WN"),
            ],
        ))

        self.add_team(Team(
            name="DEVILS",
            players=[
                Player(name="Devils_Empero"),
                Player(name="JyotishmoyNar"),
                Player(name="tmkoc"),
                Player(name="abHishekSingha"),
            ],
        ))

        self.add_team(Team(
            name="TTx",
            players=[
                Player(name="SOHAMtheGR8"),
                Player(name="TTXAYUSH45"),
                Player(name="TTxRex8"),
                Player(name="Suryawannshi"),
            ],
        ))

        self.add_team(Team(
            name="CODESTROYER",
            players=[
                Player(name="codestroyer"),
                Player(name="kl0ishere"),
                Player(name="vapouriser2918"),
            ],
        ))

        self.add_team(Team(
            name="REAPER",
            players=[
                Player(name="AmanXY"),
                Player(name="Satlaw933"),
                Player(name="barbadaadmi69"),
                Player(name="REAPERislive"),
            ],
        ))

        self.add_team(Team(
            name="TS",
            players=[
                Player(name="TS_PRESENCE"),
                Player(name="TS_FRAGGER"),
                Player(name="TS_HARSH"),
                Player(name="SNIDE"),
            ],
        ))

        self.add_team(Team(
            name="4DM",
            players=[
                Player(name="4DMxRevdiiiii"),
                Player(name="TMPxKiNGOP"),
                Player(name="KGF_TONY"),
                Player(name="realnikk"),
            ],
        ))

        self.add_team(Team(
            name="EQX",
            players=[
                Player(name="EQX_SHUBH"),
                Player(name="AR_DYNAMIC"),
                Player(name="rathouranurag"),
                Player(name="EQX_SAHIL"),
            ],
        ))

        self.add_team(Team(
            name="IIIT",
            players=[
                Player(name="saxena_ji"),
                Player(name="IIITianAman"),
                Player(name="uv_is_Live"),
                Player(name="alphadevil"),
            ],
        ))

        self.add_team(Team(
            name="ANURAG",
            players=[
                Player(name="ANURAG"),
            ],
        ))

        self.initialize_player_matcher()

if __name__ == "__main__":
    manager = TeamManager()

    manager.add_team(Team(
        name="TS",
        players=[
            Player(name="TS_HARSH"),
            Player(name="TS_PRESENCE"),
        ],
    ))

    manager.add_team(Team(
        name="FLx",
        players=[
            Player(name="FLx_ELNdix"),
            Player(name="FLx_KRISH"),
        ],
    ))

    manager.initialize_player_matcher()

    # Test fuzzy matching through process_events()
    event = Event(
        attacker="TS HAR1H",
        icons=[Icon.KNOCK],
        victim="FLx ELNdix",
    )

    manager.process_events(event)

    victim = manager.get_player("FLx_ELNdix")

    print("Victim status:", victim.status.value)
    print("Last knocker:", manager.last_knocked_by.get("FLx_ELNdix"))

    assert victim.status == PlayerStatus.KNOCKED
    assert manager.last_knocked_by["FLx_ELNdix"] == "TS_HARSH"

    print("OPTION B TEST PASSED!")