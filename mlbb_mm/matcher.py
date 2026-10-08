"""Build-then-split matchmaker.

1. Anchor on the longest-waiting party.
2. Gather compatible parties (region, skill window, new-player protection).
3. Search for a set of whole parties totalling exactly 10 players.
4. Find the assignment of whole parties to two teams of exactly 5 that
   minimises the skill gap. Parties are never split.
"""
import time
from dataclasses import dataclass

from .config import CLASSIC
from .models import Match
from .skill import confidence, effective_skill


@dataclass(eq=False)
class Ticket:
    party: object
    enqueued_at: float
    player_skills: tuple
    skill: float         # strongest member: what the party is matched on
    strength: float      # sum of member skills: what team balance uses
    confidence: float    # weakest member's confidence
    protected: bool      # any member under the new-player threshold
    tier: int            # highest tier index among members

    @property
    def size(self):
        return self.party.size


class Matchmaker:
    def __init__(self, config=CLASSIC, clock=time.monotonic):
        self.cfg = config
        self.clock = clock
        self.tickets = []

    # ---- queue ----

    def add_to_queue(self, party):
        cfg = self.cfg
        scores = [p.rank.score for p in party.players]
        if max(scores) - min(scores) > cfg.party_max_rank_gap:
            raise ValueError(f"party rank gap exceeds {cfg.party_max_rank_gap} steps")
        skills = tuple(effective_skill(p, cfg) for p in party.players)
        ticket = Ticket(
            party=party,
            enqueued_at=self.clock(),
            player_skills=skills,
            skill=max(skills),
            strength=sum(skills),
            confidence=min(confidence(p, cfg) for p in party.players),
            protected=any(p.matches < cfg.protected_matches for p in party.players),
            tier=max(p.rank.tier_index for p in party.players),
        )
        self.tickets.append(ticket)
        return ticket

    def remove_from_queue(self, party):
        self.tickets = [t for t in self.tickets if t.party is not party]

    def queued_players(self):
        return sum(t.size for t in self.tickets)

    # ---- matching ----

    def run_tick(self):
        """Form every match currently possible."""
        matches = []
        while (m := self.find_match()) is not None:
            matches.append(m)
        return matches

    def find_match(self):
        if self.queued_players() < 10:
            return None
        now = self.clock()
        for anchor in sorted(self.tickets, key=lambda t: t.enqueued_at):
            match = self._try_anchor(anchor, now)
            if match is not None:
                return match
        return None

    def _window(self, anchor, wait):
        cfg = self.cfg
        base = cfg.base_window * cfg.tier_window_scale[anchor.tier]
        base *= 1 + (1 - anchor.confidence) * cfg.uncertainty_widen
        return base + min(wait * cfg.expansion_rate, cfg.max_expansion)

    def _compatible(self, anchor, other, window):
        cfg = self.cfg
        if other.party.region != anchor.party.region:
            return False
        if cfg.isolate_five_stacks and (anchor.size == 5) != (other.size == 5):
            return False
        limit = window
        if anchor.protected or other.protected:
            limit = min(limit, cfg.protected_max_gap)
        return abs(anchor.skill - other.skill) <= limit

    def _try_anchor(self, anchor, now):
        cfg = self.cfg
        wait = now - anchor.enqueued_at
        window = self._window(anchor, wait)
        cands = [t for t in self.tickets if t is not anchor and self._compatible(anchor, t, window)]
        cands.sort(key=lambda t: abs(t.skill - anchor.skill))
        cands = cands[:cfg.max_candidates]
        if anchor.size + sum(t.size for t in cands) < 10:
            return None

        max_diff = min(cfg.team_diff_cap, cfg.team_diff_base + wait * cfg.team_diff_rate)
        best = None  # (cost, diff, spread, group, team_a_group)
        for group in self._subsets(anchor, cands):
            split = _best_split(group)
            if split is None or split[0] > max_diff:
                continue
            diff, team_a = split
            all_skills = [s for t in group for s in t.player_skills]
            spread = max(all_skills) - min(all_skills)
            cost = diff + cfg.spread_weight * spread
            if best is None or cost < best[0]:
                best = (cost, diff, spread, group, team_a)
        if best is None:
            return None
        return self._commit(best, now)

    def _subsets(self, anchor, cands):
        """Yield groups (anchor first) of tickets totalling exactly 10 players,
        nearest-skill first, within a node/result budget."""
        cfg = self.cfg
        n = len(cands)
        suffix = [0] * (n + 1)
        for i in range(n - 1, -1, -1):
            suffix[i] = suffix[i + 1] + cands[i].size
        budget = {"nodes": 0, "found": 0}
        chosen = []

        def dfs(i, total):
            budget["nodes"] += 1
            if budget["nodes"] > cfg.max_nodes or budget["found"] >= cfg.max_subsets:
                return
            if total == 10:
                budget["found"] += 1
                yield [anchor] + chosen
                return
            if i == n or total + suffix[i] < 10:
                return
            c = cands[i]
            if total + c.size <= 10:
                chosen.append(c)
                yield from dfs(i + 1, total + c.size)
                chosen.pop()
            yield from dfs(i + 1, total)

        yield from dfs(0, anchor.size)

    def _commit(self, best, now):
        _, diff, spread, group, team_a_group = best
        team_a = [t for t in group if t in team_a_group]
        team_b = [t for t in group if t not in team_a_group]
        self.tickets = [t for t in self.tickets if t not in group]
        avg_a = sum(t.strength for t in team_a) / 5
        avg_b = sum(t.strength for t in team_b) / 5
        return Match(
            team_a=[t.party for t in team_a],
            team_b=[t.party for t in team_b],
            avg_skill_a=avg_a,
            avg_skill_b=avg_b,
            skill_diff=abs(avg_a - avg_b),
            spread=spread,
            max_wait=max(now - t.enqueued_at for t in group),
        )


def _best_split(group):
    """Best assignment of whole tickets to two teams of exactly 5.
    The anchor (group[0]) is pinned to team A, which halves the search.
    Returns (avg-skill gap, team A tickets) or None if no 5/5 split exists."""
    anchor, rest = group[0], group[1:]
    total = sum(t.strength for t in group)
    best = None
    for mask in range(1 << len(rest)):
        size_a, str_a = anchor.size, anchor.strength
        for i, t in enumerate(rest):
            if mask >> i & 1:
                size_a += t.size
                str_a += t.strength
        if size_a != 5:
            continue
        diff = abs(str_a - (total - str_a)) / 5
        if best is None or diff < best[0]:
            best = (diff, mask)
    if best is None:
        return None
    diff, mask = best
    team_a = [anchor] + [t for i, t in enumerate(rest) if mask >> i & 1]
    return diff, team_a
