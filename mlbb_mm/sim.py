"""Headless queue simulation: fake clock, seeded randomness, summary metrics.

    python -m mlbb_mm.sim --mode ranked --minutes 60 --rate 2 --seed 1

Every simulated player has a hidden TRUE skill. Their rank, winrate, match
count and streak are generated from it (rank lags the truth, so some players
are under- or over-ranked, plus a few smurfs). The matcher never sees the true
skill; the simulation uses it afterwards to grade how fair each match really was.
"""
import argparse
import math
import random
from collections import defaultdict
from dataclasses import dataclass, field

from .config import CLASSIC, RANKED
from .matcher import Matchmaker
from .models import Party, Player
from .ranks import TIER_NAMES, Rank

PARTY_SIZES = [1, 2, 3, 4, 5]
PARTY_WEIGHTS = [55, 20, 10, 8, 7]


@dataclass
class SimConfig:
    minutes: float = 60
    arrivals_per_sec: float = 2.0     # new parties per second
    patience: float = 300             # seconds before a party gives up and leaves
    smurf_rate: float = 0.03          # share of solo arrivals that are new, high-skill accounts
    win_prob_slope: float = 0.4       # P(A wins) = logistic(slope * true-skill gap in steps)
    seed: int = 1


@dataclass
class SimResult:
    generated: int = 0                # players accepted into the queue
    rejected_parties: int = 0
    matched_players: int = 0
    abandoned_players: int = 0
    still_queued: int = 0
    matches: int = 0
    waits: list = field(default_factory=list)                    # per player, seconds
    waits_by_tier: dict = field(default_factory=lambda: defaultdict(list))
    waits_by_party: dict = field(default_factory=lambda: defaultdict(list))
    abandoned_by_tier: dict = field(default_factory=lambda: defaultdict(int))
    effective_gaps: list = field(default_factory=list)           # what the matcher saw
    true_gaps: list = field(default_factory=list)                # what was really there
    win_probs: list = field(default_factory=list)                # P(team A wins)
    queue_sizes: list = field(default_factory=list)              # sampled every second

    def summary(self):
        lines = []
        add = lines.append
        add(f"players generated {self.generated}: matched {self.matched_players}, "
            f"abandoned {self.abandoned_players}, still queued {self.still_queued} "
            f"({self.rejected_parties} parties rejected at the door)")
        add(f"matches formed: {self.matches}   avg queue size: {_mean(self.queue_sizes):.1f}")
        add("")
        add(f"wait (s)            {_stats(self.waits)}")
        add("  by highest tier in party")
        for tier in TIER_NAMES:
            if tier in self.waits_by_tier or tier in self.abandoned_by_tier:
                gone = self.abandoned_by_tier.get(tier, 0)
                add(f"    {tier:<18}{_stats(self.waits_by_tier.get(tier, []))}   abandoned {gone}")
        add("  by party size")
        for size in sorted(self.waits_by_party):
            add(f"    {size}-stack           {_stats(self.waits_by_party[size])}")
        add("")
        add(f"team gap, effective {_stats(self.effective_gaps, 'steps', 2)}")
        add(f"team gap, TRUE      {_stats(self.true_gaps, 'steps', 2)}")
        if self.win_probs:
            fair = sum(1 for p in self.win_probs if 0.45 <= p <= 0.55) / len(self.win_probs)
            worst = max(max(p, 1 - p) for p in self.win_probs)
            add(f"predicted win chance of the stronger team: avg "
                f"{_mean([max(p, 1 - p) for p in self.win_probs]):.1%}, worst {worst:.1%}")
            add(f"matches inside 45-55%: {fair:.1%}")
        return "\n".join(lines)


def run(match_cfg=RANKED, sim_cfg=None):
    sim = sim_cfg or SimConfig()
    rng = random.Random(sim.seed)
    now = [0.0]
    mm = Matchmaker(match_cfg, clock=lambda: now[0])
    result = SimResult()
    true_skill = {}     # player id -> hidden skill
    enqueued = {}       # party -> time it joined
    counter = [0]

    def spawn(party_size):
        leader = _true_skill(rng)
        smurf = party_size == 1 and rng.random() < sim.smurf_rate
        players = []
        for i in range(party_size):
            truth = leader if i == 0 else max(0.0, leader + rng.gauss(0, 1.5))
            if smurf:
                truth = min(truth + 10, 24.9)
            counter[0] += 1
            p = _make_player(rng, f"p{counter[0]}", truth, smurf)
            true_skill[p.id] = truth
            players.append(p)
        return Party(players)

    for second in range(int(sim.minutes * 60)):
        now[0] = float(second)
        for _ in range(_poisson(rng, sim.arrivals_per_sec)):
            party = spawn(rng.choices(PARTY_SIZES, PARTY_WEIGHTS)[0])
            try:
                mm.add_to_queue(party)
            except ValueError:
                result.rejected_parties += 1
                continue
            enqueued[party] = now[0]
            result.generated += party.size

        for m in mm.run_tick():
            _record_match(result, m, now[0], enqueued, true_skill, sim.win_prob_slope)

        for t in list(mm.tickets):
            if now[0] - t.enqueued_at > sim.patience:
                mm.remove_from_queue(t.party)
                result.abandoned_players += t.size
                result.abandoned_by_tier[TIER_NAMES[t.tier]] += t.size
        result.queue_sizes.append(mm.queued_players())

    result.still_queued = mm.queued_players()
    return result


# ---- generation ----

def _true_skill(rng):
    if rng.random() < 0.04:                       # thin top: Mythic and above
        return 25 + rng.expovariate(0.1)
    return min(max(rng.gauss(14, 5), 0.0), 24.9)


def _make_player(rng, pid, truth, smurf):
    rank = Rank.from_score(max(0.0, truth - 10) if smurf else max(0.0, truth + rng.gauss(0, 1.5)))
    matches = rng.randint(5, 30) if smurf else int(rng.expovariate(1 / 300))
    p = min(max(0.5 + 0.04 * (truth - rank.score), 0.2), 0.8)   # better than rank => wins more
    wins = round(rng.gauss(matches * p, math.sqrt(matches * p * (1 - p))))
    wins = min(max(wins, 0), matches)
    streak = 0
    if rng.random() >= 0.6:
        streak = (1 + int(rng.expovariate(0.5))) * rng.choice([-1, 1])
    return Player(pid, rank, matches=matches, wins=wins, streak=streak, id=pid)


def _poisson(rng, rate):
    n, t = 0, rng.expovariate(rate)
    while t < 1:
        n += 1
        t += rng.expovariate(rate)
    return n


# ---- measuring ----

def _record_match(result, match, now, enqueued, true_skill, slope):
    result.matches += 1
    for party in match.team_a + match.team_b:
        wait = now - enqueued.pop(party)
        tier = TIER_NAMES[max(p.rank.tier_index for p in party.players)]
        result.matched_players += party.size
        result.waits.extend([wait] * party.size)
        result.waits_by_tier[tier].extend([wait] * party.size)
        result.waits_by_party[party.size].extend([wait] * party.size)
    avg = lambda team: sum(true_skill[p.id] for party in team for p in party.players) / 5
    gap = avg(match.team_a) - avg(match.team_b)
    result.effective_gaps.append(match.skill_diff)
    result.true_gaps.append(abs(gap))
    result.win_probs.append(1 / (1 + math.exp(-slope * gap)))


def _mean(values):
    return sum(values) / len(values) if values else 0.0


def _pct(values, q):
    s = sorted(values)
    return s[min(len(s) - 1, int(q * len(s)))]


def _stats(values, unit="", digits=0):
    if not values:
        return "n/a"
    f = lambda x: f"{x:.{digits}f}"
    tail = f" {unit}" if unit else ""
    return (f"avg {f(_mean(values))}  median {f(_pct(values, .5))}  "
            f"p90 {f(_pct(values, .9))}  max {f(max(values))}{tail}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--mode", choices=["ranked", "classic"], default="ranked")
    ap.add_argument("--minutes", type=float, default=60)
    ap.add_argument("--rate", type=float, default=2.0, help="new parties per second")
    ap.add_argument("--patience", type=float, default=300)
    ap.add_argument("--smurf-rate", type=float, default=0.03)
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()
    cfg = RANKED if a.mode == "ranked" else CLASSIC
    sim = SimConfig(a.minutes, a.rate, a.patience, a.smurf_rate, seed=a.seed)
    print(run(cfg, sim).summary())


if __name__ == "__main__":
    main()
