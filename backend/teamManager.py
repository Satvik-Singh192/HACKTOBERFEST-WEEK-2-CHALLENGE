import pandas as pd
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

        if attacker is not None and attacker.casefold() != "playzone":
            attacker = self.player_matcher.match(attacker)

            if attacker is None:
                raise ValueError(
                    f"Could not confidently match attacker: {event.attacker}"
                )

        from dataclasses import replace

        return replace(event, attacker=attacker, victim=victim)

    def process_events(self, event: Event) -> None:
        event=self.resolve_event(event)
        victim = self.get_player(event.victim)
        victim_team = self.get_team(event.victim)

        # knock handler
        if Icon.KNOCK in event.icons:
            if event.attacker is None:
                return

            victim.status = PlayerStatus.KNOCKED

        
            self.last_knocked_by[event.victim] = event.attacker
            return

        #finish handler
        if Icon.OBJECT in event.icons:
            previous_knocker = self.last_knocked_by.get(event.victim)

            # Victim is eliminated regardless of who finished them.
           
            victim.status = PlayerStatus.ELIMINATED
            self.check_team_elimination(victim_team)

            if event.attacker is not None and event.attacker != "Playzone":
                # A known, actual player finished the victim.
                finisher_team = self.get_team(event.attacker)
            
                if finisher_team.name != victim_team.name:
                  
            
                    self.get_player(event.attacker).kills += 1

                elif (
                    previous_knocker is not None
                    and previous_knocker != "Playzone" 
                ):
                    knocker_team = self.get_team(previous_knocker)
                  
                    if knocker_team.name != victim_team.name:
                        self.get_player(previous_knocker).kills += 1

            elif previous_knocker is not None:
            
                if previous_knocker != "Playzone":
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

                # Skip teams already eliminated
                if other_team.placement is not None:
                    continue

                # Award only to teams with at least one non-eliminated player
                is_alive = any(
                    player.status != PlayerStatus.ELIMINATED
                    for player in other_team.players
                )

                if is_alive:
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

    def load_video_testing_teams(self) -> None:
        """Register the exact teams and players present in the testing video."""
        self.teams.clear()
        self.player_team_map.clear()
        self.alias_to_canonical.clear()

        self.add_team(Team(
            name="TS",
            players=[
                Player(name="TS_FRAGGER", aliases=["TS-FRAGGER", "TS卍FRAGGER", "TS FRAGGER", "TSPEFRAGGER", "TSALFRAGGER", "FRAGGER"]),
                Player(name="SNIDE", aliases=["SNIDE.", "· SNIDE ·", "- SNIDE -", "SNIDE"]),
                Player(name="TS_HARSH", aliases=["TS-HARSH", "TS卍HARSH", "TS HARSH", "TS HAR1H", "HARSH"]),
                Player(name="TS_PRESENCE", aliases=["TS-PRESENCE", "TS卍PRESENCE", "TS PRESENCE", "PRESENCE"]),
            ],
        ))

        self.add_team(Team(
            name="NEMESIS",
            players=[
                Player(name="NEMESIS", aliases=["NÈMÈSîS", "NEMES IS", "NEMESIS1"]),
                Player(name="YADAV", aliases=["Y A D A V", "YADAV_", "「 YADAV 」"]),
                Player(name="UNKN0WN", aliases=["UNKNOWN", "bUnkn0wn", "Unknown", "OUNKNDWN", "BUNKNWN"]),
                Player(name="ALPHA_BEAST", aliases=["ALPHA-Beast", "ALPHA文Beast", "ALPHABeast", "BEASTJOKERRR"]),
            ],
        ))

        self.add_team(Team(
            name="FLx",
            players=[
                Player(name="FLx_ELNdix", aliases=["FLx ELNdix", "ELNdix"]),
                Player(name="FLx_KRISH", aliases=["FLx KRISH", "KRISH"]),
                Player(name="SANDHU", aliases=["SANDHU", "SANDHU_OP"]),
                Player(name="MPX_KING", aliases=["MPXKINGOP", "TMPXKINGOP"]),
            ],
        ))

        self.add_team(Team(
            name="TEAM 9",
            players=[
                Player(name="JAYKISHAN", aliases=["जयंतार", "JAY", "JAYKISHAN"]),
                Player(name="KALASHI", aliases=["『KALASHI』", "KALASHI"]),
                Player(name="VAISHNAV", aliases=["IMxVAISHNAV", "VAISHNAV"]),
                Player(name="OP_PLAYER", aliases=["OP_PLAYER", "PLAYER9"]),
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