import pandas as pd
from teams import Team,Player,PlayerStatus
from events import Event,Icon
class TeamManager:
    def __init__(self):
        self.teams:dict[str,Team]={}
        self.player_team_map:dict[str,str]={}
        self.last_knocked_by:dict[str,str]={}
        self.eliminatedTeams=0
    def add_team(self,team:Team)->None:
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
    def get_player(self, player_name: str) -> Player:
        team_name = self.player_team_map.get(player_name)

        if team_name is None:
            raise KeyError(f"Unknown player: {player_name}")

        team = self.teams[team_name]

        for player in team.players:
            if player.name == player_name:
                return player

        raise RuntimeError("Player-team mapping is inconsistent")
    def get_team(self, player_name: str) -> Team:
        team_name = self.player_team_map.get(player_name)

        if team_name is None:
            raise KeyError(f"Unknown player: {player_name}")

        return self.teams[team_name]
    
    
    def process_events(self, event: Event) -> None:
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


# def print_match_state(manager, step, event):
#     print("\n" + "=" * 75)
#     print(f"STEP {step}: {event.attacker} -> {event.victim}")
#     print(f"ICONS: {[icon.value for icon in event.icons]}")
#     print("-" * 75)

#     for team_name, team in manager.teams.items():
#         players_info = []

#         for player in team.players:
#             players_info.append(
#                 f"{player.name}"
#                 f"(kills={player.kills}, status={player.status.value})"
#             )

#         print(f"{team_name}: {' | '.join(players_info)}")

#     print(f"\nKnock history: {manager.last_knocked_by}")
#     print("=" * 75)




# def print_match_state(manager, step, event):
#     print("\n" + "=" * 75)
#     print(f"STEP {step}: {event.attacker} -> {event.victim}")
#     print(f"ICONS: {[icon.value for icon in event.icons]}")
#     print("-" * 75)

#     for team_name, team in manager.teams.items():
#         players_info = []

#         for player in team.players:
#             players_info.append(
#                 f"{player.name}"
#                 f"(kills={player.kills}, status={player.status.value})"
#             )

#         print(f"{team_name}: {' | '.join(players_info)}")

#     print(f"\nKnock history: {manager.last_knocked_by}")
#     print("=" * 75)


# if __name__ == "__main__":
#     manager = TeamManager()

#     # Create 5 teams with 4 players each
#     manager.add_team(
#         Team("Alpha", [
#             Player("PlayerA"), Player("PlayerB"),
#             Player("PlayerC"), Player("PlayerD")
#         ])
#     )

#     manager.add_team(
#         Team("Bravo", [
#             Player("PlayerE"), Player("PlayerF"),
#             Player("PlayerG"), Player("PlayerH")
#         ])
#     )

#     manager.add_team(
#         Team("Charlie", [
#             Player("PlayerI"), Player("PlayerJ"),
#             Player("PlayerK"), Player("PlayerL")
#         ])
#     )

#     manager.add_team(
#         Team("Delta", [
#             Player("PlayerM"), Player("PlayerN"),
#             Player("PlayerO"), Player("PlayerP")
#         ])
#     )

#     manager.add_team(
#         Team("Echo", [
#             Player("PlayerQ"), Player("PlayerR"),
#             Player("PlayerS"), Player("PlayerT")
#         ])
#     )

#     # (attacker, icon, victim)
#     scenario = [
#         ("PlayerA", Icon.KNOCK,  "PlayerE"),
#         ("PlayerF", Icon.KNOCK,  "PlayerB"),
#         ("PlayerC", Icon.OBJECT, "PlayerE"),
#         ("PlayerG", Icon.OBJECT, "PlayerB"),

#         ("PlayerI", Icon.KNOCK,  "PlayerM"),
#         ("PlayerN", Icon.OBJECT, "PlayerM"),

#         ("PlayerJ", Icon.KNOCK,  "PlayerO"),
#         ("Playzone", Icon.OBJECT, "PlayerO"),

#         ("Playzone", Icon.KNOCK, "PlayerK"),
#         ("PlayerN", Icon.OBJECT, "PlayerK"),

#         ("PlayerQ", Icon.KNOCK,  "PlayerD"),
#         ("PlayerB", Icon.OBJECT, "PlayerD"),

#         ("PlayerR", Icon.KNOCK,  "PlayerH"),
#         ("PlayerS", Icon.OBJECT, "PlayerH"),

#         ("PlayerT", Icon.KNOCK,  "PlayerP"),
#         ("PlayerQ", Icon.OBJECT, "PlayerP"),

#         ("PlayerE", Icon.KNOCK,  "PlayerI"),
#         ("PlayerF", Icon.OBJECT, "PlayerI"),

#         ("PlayerN", Icon.KNOCK,  "PlayerA"),
#         ("Playzone", Icon.OBJECT, "PlayerA"),
#     ]

#     print("MATCH STARTED: 20 players, 5 teams")
#     print_match_state(
#         manager,
#         0,
#         Event(attacker="SYSTEM", icons=[], victim="SYSTEM")
#     )

#     for step, (attacker, icon, victim) in enumerate(scenario, start=1):
#         event = Event(
#             attacker=attacker,
#             icons=[icon],
#             victim=victim
#         )

#         print(f"\nPROCESSING EVENT {step}/20...")
#         manager.process_events(event)
#         print_match_state(manager, step, event)

#     print("\n\nMATCH FINISHED!")
#     print("\nFINAL KILL LEADERBOARD:")

#     all_players = [
#         player
#         for team in manager.teams.values()
#         for player in team.players
#     ]

#     all_players.sort(key=lambda player: player.kills, reverse=True)

#     for rank, player in enumerate(all_players, start=1):
#         print(
#             f"{rank:2}. {player.name:10} "
#             f"Kills: {player.kills} | "
#             f"Status: {player.status.value}"
#         )

#     print("\nFINAL KNOCK HISTORY:")
#     print(manager.last_knocked_by)

import random

def run_full_match():
    random.seed(42)

    manager = TeamManager()

    # 13 teams, 4 players each.
    # Replace placeholder names with exact OCR names where needed.
    rosters = {
        "FLx": [
            "FLx_ELNdix", "DGxKRISH", "LSxGoplayzYT", "AyushShivam"
        ],
        "SANDHU": [
            "SANDHU", "KISHANKINGE", "beastjoker", "AyushRaj5513"
        ],
        "Team3": [
            "IMxVAISHNAV", "PKAKASHI", "DarthPotato", "Jayant"
        ],
        "Team4": [
            "NEMESIS", "TYADAV", "ALPHABeast", "Player4D"
        ],
        "Team5": [
            "DevilsEmperd", "Jyotishm", "Player5C", "abhishekSingha"
        ],
        "Team6": [
            "SOHAMtheGR8", "TTxAYUSH45", "TTxRex8", "Suryawanshi"
        ],
        "Team7": [
            "codestroyer", "KIDishere", "vapouriser2918", "Player7D"
        ],
        "Team8": [
            "AmenxYY", "SatAqua933", "harshadami916", "REAPERislive"
        ],
        "TS": [
            "TS_PRESENCE", "TS_FRAGGER", "TS_HARSH", "SNIDE"
        ],
        "Team10": [
            "4DMxRevd", "TMPxKINGoP", "PKGF_TONY", "realnikk"
        ],
        "Team11": [
            "EDX_Player", "AR_DYNAMIC", "rathouranurag", "EDX_SAHIL"
        ],
        "Team12": [
            "saXena", "IITianAman", "UV_is_Live", "Ealphadevil"
        ],
        "Team13": [
            "ANURAG", "Player13B", "Player13C", "Player13D"
        ],
    }

    for team_name, names in rosters.items():
        manager.add_team(
            Team(team_name, [Player(name) for name in names])
        )

    all_players = [
        player
        for team in manager.teams.values()
        for player in team.players
    ]

    player_names = [player.name for player in all_players]

    # Leave three TS members alive at the end.
    # This is a synthetic test, not a claim about the real match.
    survivors = {"TS_PRESENCE", "TS_FRAGGER", "TS_HARSH"}

    # The fourth TS player and all players from the other teams
    # will be eliminated: 52 players - 3 survivors = 49 finishes.
    finish_targets = [
        name for name in player_names
        if name not in survivors
    ]

    # Eliminate SNIDE early while enemies are still available.
    finish_targets.remove("SNIDE")
    finish_targets.insert(0, "SNIDE")

    # Randomize the remaining finish order reproducibly.
    first_target = finish_targets[0]
    rest = finish_targets[1:]
    random.shuffle(rest)
    finish_targets = [first_target] + rest

    print("=" * 90)
    print("BGMI SYNTHETIC MATCH: 13 TEAMS")
    print("Planned events: 160 KNOCKS + 49 FINISHES")
    print("Intended winner for this test: TS")
    print("=" * 90)

    event_number = 0
    knock_count = 0
    finish_count = 0

    # 13 targets receive 4 knocks; remaining 36 receive 3.
    # Total = (13 * 4) + (36 * 3) = 160 knock events.
    for target_index, victim_name in enumerate(finish_targets):
        knock_repetitions = 4 if target_index < 13 else 3

        for repetition in range(knock_repetitions):
            victim = manager.get_player(victim_name)

            # Simulate a revive before re-knocking a knocked player.
            # The current Event model has no REVIVE icon.
            if victim.status == PlayerStatus.KNOCKED:
                victim.status = PlayerStatus.ALIVE
                manager.last_knocked_by.pop(victim_name, None)
                print(f"  REVIVE: {victim_name} is alive again")

            victim_team = manager.get_team(victim_name)

            possible_attackers = [
                player
                for player in all_players
                if player.name != victim_name
                and player.status == PlayerStatus.ALIVE
                and manager.get_team(player.name).name != victim_team.name
            ]

            if possible_attackers:
                attacker = random.choice(possible_attackers).name
            else:
                attacker = "Playzone"

            event = Event(
                attacker=attacker,
                icons=[Icon.KNOCK],
                victim=victim_name,
            )

            event_number += 1
            knock_count += 1

            print(
                f"\n[{event_number:03}] KNOCK | "
                f"{attacker} knocked {victim_name}"
            )
            manager.process_events(event)

        # Finish the victim after their final knock.
        victim_team = manager.get_team(victim_name)

        possible_finishers = [
            player
            for player in all_players
            if player.name != victim_name
            and player.status == PlayerStatus.ALIVE
            and manager.get_team(player.name).name != victim_team.name
        ]

        if possible_finishers and random.random() < 0.90:
            finisher = random.choice(possible_finishers).name
        else:
            finisher = "Playzone"

        event = Event(
            attacker=finisher,
            icons=[Icon.OBJECT],
            victim=victim_name,
        )

        event_number += 1
        finish_count += 1

        print(
            f"\n[{event_number:03}] FINISH | "
            f"{finisher} finished {victim_name}"
        )
        manager.process_events(event)

        # Compact live scoreboard after every finish.
        print("\nLIVE TEAM SCOREBOARD")
        for team in manager.teams.values():
            alive_count = sum(
                player.status != PlayerStatus.ELIMINATED
                for player in team.players
            )
            print(
                f"{team.name:12} "
                f"alive={alive_count} "
                f"placement={team.placement} "
                f"placement_points={team.placement_points} "
                f"kills={sum(p.kills for p in team.players)}"
            )

    print("\n" + "=" * 90)
    print("SIMULATION COMPLETE")
    print(f"Total events: {event_number}")
    print(f"Knock events: {knock_count}")
    print(f"Finish events: {finish_count}")

    print("\nFINAL PLACEMENT LEADERBOARD")
    ranked_teams = sorted(
        manager.teams.values(),
        key=lambda team: (
            team.placement if team.placement is not None else 1,
            team.name,
        ),
    )

    for team in ranked_teams:
        alive_count = sum(
            player.status != PlayerStatus.ELIMINATED
            for player in team.players
        )
        print(
            f"{str(team.placement or 'ALIVE'):>5} | "
            f"{team.name:12} | "
            f"placement points={team.placement_points:2} | "
            f"alive={alive_count} | "
            f"kills={sum(p.kills for p in team.players)}"
        )

    print("\nPLAYER KILL LEADERBOARD")
    for player in sorted(
        all_players,
        key=lambda player: player.kills,
        reverse=True,
    ):
        print(
            f"{player.name:20} "
            f"kills={player.kills:2} "
            f"status={player.status.value}"
        )

    print("\nFinal knock history:", manager.last_knocked_by)


if __name__ == "__main__":
    run_full_match()
