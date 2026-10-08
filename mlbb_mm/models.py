import uuid
from dataclasses import dataclass, field

from .ranks import Rank


@dataclass
class Player:
    name: str
    rank: Rank
    matches: int = 0
    wins: int = 0
    streak: int = 0          # +n = current win streak, -n = current loss streak
    region: str = "SEA"
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:6])

    def __post_init__(self):
        if self.matches < 0 or not 0 <= self.wins <= self.matches:
            raise ValueError("need 0 <= wins <= matches")


@dataclass(eq=False)  # identity equality: two identical-looking parties are still different parties
class Party:
    players: tuple

    def __post_init__(self):
        self.players = tuple(self.players)
        if not 1 <= len(self.players) <= 5:
            raise ValueError("a party has 1-5 players")
        if len({p.region for p in self.players}) != 1:
            raise ValueError("all party members must be in the same region")

    @classmethod
    def of(cls, *players):
        return cls(players)

    @property
    def size(self):
        return len(self.players)

    @property
    def region(self):
        return self.players[0].region


@dataclass
class Match:
    team_a: list             # list[Party]
    team_b: list
    avg_skill_a: float
    avg_skill_b: float
    skill_diff: float        # |avg_a - avg_b|, in rank steps
    spread: float            # best minus worst effective skill among the 10 players
    max_wait: float          # longest wait among the matched parties, seconds
