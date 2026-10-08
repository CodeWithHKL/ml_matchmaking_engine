"""Tunable matchmaking parameters. Skill-related distances are in rank "steps"
(1.0 = one division, see ranks.py). Every number here is a starting guess."""
from dataclasses import dataclass

from .ranks import TIER_NAMES


@dataclass(frozen=True)
class MatchConfig:
    # --- search window (distance from the anchor party's skill) ---
    base_window: float
    expansion_rate: float            # steps added per second of waiting
    max_expansion: float             # cap on the wait-based widening
    uncertainty_widen: float         # low-confidence anchors search up to (1 + this) x wider
    tier_window_scale: tuple         # per-tier multiplier, one entry per TIER_NAMES (thin top ranks)

    # --- parties ---
    party_max_rank_gap: float        # max rank-step gap between members of one party
    isolate_five_stacks: bool = False  # 5-stacks only meet 5-stacks (and vice versa)

    # --- new-player protection ---
    protected_matches: int = 50      # fewer total matches than this => protected
    protected_max_gap: float = 1.5   # hard skill gap cap involving a protected player

    # --- team balance ---
    team_diff_base: float = 0.5      # allowed avg-skill gap between teams at wait 0
    team_diff_rate: float = 0.01     # ... grows by this per second waited
    team_diff_cap: float = 2.0
    spread_weight: float = 0.25      # penalty on (best player - worst player) when ranking candidates

    # --- effective skill ---
    confidence_k: float = 30         # confidence = matches / (matches + k)
    wr_prior_games: float = 20       # winrate is shrunk toward 50% as if this many 50% games existed
    wr_scale: float = 20.0           # steps per 1.0 of (shrunk) winrate above 50%
    wr_cap: float = 2.0
    streak_min: int = 3              # streaks shorter than this are ignored
    streak_per_game: float = 0.25
    streak_cap: float = 1.0

    # --- search budget ---
    max_candidates: int = 30
    max_subsets: int = 200
    max_nodes: int = 20000

    def __post_init__(self):
        if len(self.tier_window_scale) != len(TIER_NAMES):
            raise ValueError(f"tier_window_scale needs {len(TIER_NAMES)} entries")


# Warrior..Legend are one density; the thin Mythic+ ranks get wider windows.
_TIER_SCALE = (1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.5, 2.0, 3.0, 4.0)

RANKED = MatchConfig(
    base_window=3.0,
    expansion_rate=0.05,
    max_expansion=6.0,
    uncertainty_widen=1.0,
    tier_window_scale=_TIER_SCALE,
    party_max_rank_gap=4.0,
)

CLASSIC = MatchConfig(
    base_window=5.0,
    expansion_rate=0.10,
    max_expansion=10.0,
    uncertainty_widen=1.0,
    tier_window_scale=_TIER_SCALE,
    party_max_rank_gap=8.0,
    protected_max_gap=3.0,
    team_diff_base=1.0,
    team_diff_rate=0.02,
    team_diff_cap=3.0,
)
