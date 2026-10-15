import re
from rapidfuzz import fuzz,process

class PlayerMatcher:
    def __init__(self,player_team_map:dict[str,str]):
        self.cache:dict[str,str | None]={}
        self.rebuild(player_team_map)
    @staticmethod
    def normalize(name:str)->str:
        return re.sub(r"[^A-Z0-9]", "", name.upper())
    
    def rebuild(self, player_team_map: dict[str, str]):
        
        self.canonical_names = list(player_team_map.keys())

        self.normalized_to_names: dict[str, list[str]] = {}

        for name in self.canonical_names:
            normalized = self.normalize(name)
            self.normalized_to_names.setdefault(normalized, []).append(name)

        
        self.cache.clear()
    def match(self, detected_name: str | None) -> str | None:
        if detected_name is None:
            return None

        detected_name = detected_name.strip()
        if not detected_name:
            return None

        normalized = self.normalize(detected_name)

        
        exact = self.normalized_to_names.get(normalized, [])

        if len(exact) == 1:
            return exact[0]

       
        if len(exact) > 1:
            return None

        if normalized in self.cache:
            return self.cache[normalized]

        
        if len(normalized) < 5:
            self.cache[normalized] = None
            return None

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

        second_score = candidates[1][1] if len(candidates) > 1 else 0

        
        if best_score < 85 or best_score - second_score < 8:
            self.cache[normalized] = None
            return None

        matching_names = self.normalized_to_names[best_key]

        if len(matching_names) != 1:
            self.cache[normalized] = None
            return None

        result = matching_names[0]
        self.cache[normalized] = result
        return result

    