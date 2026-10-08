"""MLBB rank ladder -> a single comparable number ("steps").

All thresholds are PLACEHOLDERS (they change between seasons) -- edit the two
tables below to match the current season.

Division convention: a higher division number is a LOWER rank (Epic V is the
bottom of Epic, Epic I the top), as in the game.
"""
from dataclasses import dataclass

# Tiers with divisions, lowest to highest: (name, number of divisions).
DIVISIONED_TIERS = [
    ("Warrior", 3),
    ("Elite", 3),
    ("Master", 4),
    ("Grandmaster", 5),
    ("Epic", 5),
    ("Legend", 5),
]

# Star-based tiers: (name, first total-star count at which the tier starts).
# Stars count from the start of Mythic, so they keep growing past Mythic.
STAR_TIERS = [
    ("Mythic", 0),
    ("Mythical Honor", 25),
    ("Mythical Glory", 50),
    ("Mythical Immortal", 100),
]

# How many stars equal one "step" (one division) on the skill scale.
STARS_PER_STEP = 5

TIER_NAMES = [name for name, _ in DIVISIONED_TIERS] + [name for name, _ in STAR_TIERS]
_DIVISIONS = dict(DIVISIONED_TIERS)
_STAR_START = dict(STAR_TIERS)
_ROMAN = {"i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5}


@dataclass(frozen=True)
class Rank:
    tier: str
    division: int = 0   # divisioned tiers only (1 = top of the tier)
    stars: int = 0      # star tiers only (total stars since Mythic began)

    def __post_init__(self):
        if self.tier in _DIVISIONS:
            if not 1 <= self.division <= _DIVISIONS[self.tier]:
                raise ValueError(f"{self.tier} has divisions 1..{_DIVISIONS[self.tier]}, got {self.division}")
        elif self.tier in _STAR_START:
            if self.stars < _STAR_START[self.tier]:
                raise ValueError(f"{self.tier} starts at {_STAR_START[self.tier]} stars, got {self.stars}")
            nxt = _next_star_start(self.tier)
            if nxt is not None and self.stars >= nxt:
                raise ValueError(f"{self.stars} stars is above {self.tier}")
        else:
            raise ValueError(f"unknown tier {self.tier!r}")

    @classmethod
    def from_stars(cls, stars):
        """Rank for a total star count (Mythic and above)."""
        tier = max((n for n, start in STAR_TIERS if stars >= start), key=lambda n: _STAR_START[n])
        return cls(tier, stars=stars)

    @classmethod
    def parse(cls, text):
        """'Epic III', 'epic 3', 'Mythic 12', 'glory 60', 'Mythical Immortal 130'.
        Divisioned tiers take a division (number or roman numeral); star tiers
        take a total star count (omit it for the tier's first star)."""
        words = text.strip().lower().split()
        if words and words[0] in ("honor", "glory", "immortal"):
            words.insert(0, "mythical")
        for name in sorted(TIER_NAMES, key=len, reverse=True):
            n = len(name.split())
            if words[:n] == name.lower().split():
                rest = " ".join(words[n:])
                break
        else:
            raise ValueError(f"unknown rank {text!r}; tiers: {', '.join(TIER_NAMES)}")
        if rest in _ROMAN:
            num = _ROMAN[rest]
        elif rest.isdigit():
            num = int(rest)
        elif rest == "" and name in _STAR_START:
            num = _STAR_START[name]
        else:
            raise ValueError(f"can't read {rest!r} as a division or star count")
        return cls(name, division=num) if name in _DIVISIONS else cls(name, stars=num)

    @classmethod
    def from_score(cls, score):
        """Inverse of `score` (rounded down to a whole division / star)."""
        steps = 0
        for name, n in DIVISIONED_TIERS:
            if score < steps + n:
                return cls(name, division=n - int(max(score, 0) - steps))
            steps += n
        return cls.from_stars(int((score - steps) * STARS_PER_STEP))

    @property
    def tier_index(self):
        return TIER_NAMES.index(self.tier)

    @property
    def score(self):
        """Position on the ladder in steps; one division = 1.0."""
        steps = 0
        for name, n in DIVISIONED_TIERS:
            if name == self.tier:
                return steps + (n - self.division)
            steps += n
        return steps + self.stars / STARS_PER_STEP


def _next_star_start(tier):
    starts = sorted(_STAR_START.values())
    later = [s for s in starts if s > _STAR_START[tier]]
    return later[0] if later else None
