import re
from rapidfuzz import fuzz,process

class PlayerMatcher:
    def __init__(self, player_team_map: dict[str, str], alias_map: dict[str, str] | None = None):
        self.cache: dict[str, str | None] = {}
        self.rebuild(player_team_map, alias_map)

    @staticmethod
    def normalize(name: str) -> str:
        return re.sub(r"[^A-Z0-9]", "", name.upper())

    def rebuild(self, player_team_map: dict[str, str], alias_map: dict[str, str] | None = None):
        self.alias_map = alias_map or {}
        # Only true canonical names (exclude aliases)
        self.canonical_names = [k for k in player_team_map.keys() if k not in self.alias_map]
        self.normalized_to_names: dict[str, str] = {}

        # Canonical player names map to themselves
        for name in self.canonical_names:
            normalized = self.normalize(name)
            if normalized:
                self.normalized_to_names[normalized] = name

        # Register aliases to point directly to canonical name
        for alias, canonical in self.alias_map.items():
            norm_alias = self.normalize(alias)
            if norm_alias:
                self.normalized_to_names[norm_alias] = canonical

        self.cache.clear()

    def match(self, detected_name: str | None) -> str | None:
        if detected_name is None:
            return None

        detected_name = detected_name.strip()
        if not detected_name:
            return None

        normalized = self.normalize(detected_name)
        if not normalized:
            return None

        # 1. Exact match (canonical name or known alias)
        if normalized in self.normalized_to_names:
            return self.normalized_to_names[normalized]

        # 2. Check cached resolution
        if normalized in self.cache:
            return self.cache[normalized]

        # Ignore noise shorter than 3 characters
        if len(normalized) < 3:
            self.cache[normalized] = None
            return None

        # 3. Fuzzy match against all known canonical names & aliases
        candidates = process.extract(
            normalized,
            list(self.normalized_to_names.keys()),
            scorer=fuzz.ratio,
            limit=3,
        )

        if not candidates:
            self.cache[normalized] = None
            return None

        best_key, best_score, _ = candidates[0]
        best_player = self.normalized_to_names[best_key]

        # Find the highest scoring candidate that points to a DIFFERENT player
        second_diff_player_score = 0
        for cand_key, cand_score, _ in candidates[1:]:
            cand_player = self.normalized_to_names.get(cand_key)
            if cand_player != best_player:
                second_diff_player_score = cand_score
                break

        # Dynamic threshold based on name length:
        # For short 3-4 letter tags, a 1-character typo gives ~75% ratio
        min_threshold = 70 if len(normalized) <= 4 else 80

        if best_score < min_threshold or (
            best_score - second_diff_player_score < 6 and second_diff_player_score > 0
        ):
            self.cache[normalized] = None
            return None

        self.cache[normalized] = best_player
        return best_player

    