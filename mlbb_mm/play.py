"""Queue up as a player and see what the matchmaker gives you.

    python -m mlbb_mm.play

Asks for your rank, total matches, winrate and streak (or pass them as flags),
drops you into a simulated queue full of other players, and prints how you were
rated, how long you waited and who you got matched with.
"""
import argparse
import random
from dataclasses import dataclass

from .config import CLASSIC, RANKED
from .matcher import Matchmaker
from .models import Party, Player
from .ranks import Rank
from .sim import Population
from .skill import confidence, shrunk_winrate, streak_adjustment, winrate_adjustment, effective_skill


@dataclass
class PlayResult:
    party: Party
    ticket: object
    match: object            # None if no match within the timeout
    waited: float
    window_start: float
    window_end: float
    queue_players: int       # players waiting when you joined


def play(party, match_cfg=RANKED, seed=1, rate=2.0, warmup=120, timeout=600, smurf_rate=0.03):
    """Warm up a busy queue, join it with `party`, and tick until matched or timeout."""
    rng = random.Random(seed)
    now = [0.0]
    mm = Matchmaker(match_cfg, clock=lambda: now[0])
    pop = Population(rng, rate, smurf_rate)

    def tick():
        for p in pop.arrivals():
            try:
                mm.add_to_queue(p)
            except ValueError:
                pass
        return mm.run_tick()

    for _ in range(warmup):
        now[0] += 1
        tick()

    ticket = mm.add_to_queue(party)   # raises ValueError if the party's own rank gap is too wide
    joined = now[0]
    queue_players = mm.queued_players()
    for _ in range(timeout):
        now[0] += 1
        for m in tick():
            if party in m.team_a or party in m.team_b:
                waited = now[0] - joined
                return PlayResult(party, ticket, m, waited, mm._window(ticket, 0),
                                  mm._window(ticket, waited), queue_players)
    waited = now[0] - joined
    return PlayResult(party, ticket, None, waited, mm._window(ticket, 0),
                      mm._window(ticket, waited), queue_players)


# ---- report ----

def _player_line(p, cfg, mine):
    wr = f"{p.wins / p.matches:.0%}" if p.matches else "n/a"
    streak = f"{p.streak:+d}" if p.streak else "0"
    tag = "  <-- you" if p in mine else ""
    return (f"    {_rank_name(p.rank):<24}"
            f"{p.matches:>5} games  wr {wr:>4}  streak {streak:>3}  skill {effective_skill(p, cfg):5.1f}{tag}")


def report(res, cfg, mode):
    lines = []
    add = lines.append
    me = res.party.players
    add(f"=== {mode} queue | {res.party.size}-stack | {res.queue_players} players already waiting ===")
    add("")
    add("How you were rated:")
    for p in me:
        wr = f"{p.wins / p.matches:.1%}" if p.matches else "n/a"
        add(f"  {_rank_name(p.rank)}, {p.matches} games, winrate {wr}, streak {p.streak:+d}")
        add(f"    rank                 {p.rank.score:6.2f} steps")
        add(f"    winrate adjustment   {winrate_adjustment(p, cfg):+6.2f}   (smoothed winrate {shrunk_winrate(p, cfg):.1%})")
        add(f"    streak adjustment    {streak_adjustment(p, cfg):+6.2f}")
        add(f"    effective skill      {effective_skill(p, cfg):6.2f}")
        add(f"    confidence           {confidence(p, cfg):6.0%}   new-player protection: "
            f"{'ON' if p.matches < cfg.protected_matches else 'off'}")
    add(f"  search window: {res.window_start:.1f} steps when you joined"
        + (f", {res.window_end:.1f} after {res.waited:.0f}s of waiting" if res.waited else ""))
    add("")
    if res.match is None:
        add(f"NO MATCH after {res.waited:.0f}s. Nobody the right skill was waiting, or no valid 5v5 "
            "could be built from them.")
        return "\n".join(lines)

    m = res.match
    add(f"MATCH FOUND after {res.waited:.0f}s of waiting")
    for label, team, avg in (("TEAM A", m.team_a, m.avg_skill_a), ("TEAM B", m.team_b, m.avg_skill_b)):
        add(f"  {label}  (avg skill {avg:.2f})")
        for party in team:
            for p in party.players:
                add(_player_line(p, cfg, me))
            if party.size > 1:
                add(f"    ^ {party.size}-stack")
    add("")
    add(f"  skill gap between teams: {m.skill_diff:.2f} steps   "
        f"(best vs worst player in the lobby: {m.spread:.1f} steps)")
    return "\n".join(lines)


def _rank_name(rank):
    """Same format Rank.parse reads: division for normal tiers, total stars for Mythic+."""
    return f"{rank.tier} {rank.division or rank.stars}"


def _mode(s):
    if s not in ("ranked", "classic"):
        raise ValueError("type ranked or classic")
    return s


# ---- input ----

def _ask(prompt, parse, default=None):
    while True:
        raw = input(f"{prompt}{f' [{default}]' if default is not None else ''}: ").strip()
        if not raw and default is not None:
            return default if not isinstance(default, str) else parse(default)
        try:
            return parse(raw)
        except ValueError as e:
            print(f"  ! {e}")


def _bounded(lo, hi, cast):
    def parse(s):
        v = cast(s)
        if not lo <= v <= hi:
            raise ValueError(f"must be between {lo} and {hi}")
        return v
    return parse


def _build_player(name, rank, matches, winrate, streak):
    wins = round(matches * winrate / 100)
    return Player(name, rank, matches=matches, wins=wins, streak=streak)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--mode", choices=["ranked", "classic"])
    ap.add_argument("--rank", help='e.g. "Epic III", "Mythic 12", "Mythical Glory 60"')
    ap.add_argument("--matches", type=int)
    ap.add_argument("--winrate", type=float, help="percent, e.g. 54.5")
    ap.add_argument("--streak", type=int, help="+3 = 3 wins in a row, -2 = 2 losses in a row")
    ap.add_argument("--party", type=int, help="party size 1-5 (teammates share your rank unless you give --mates)")
    ap.add_argument("--mates", nargs="*", help="ranks of your teammates, one per extra member")
    ap.add_argument("--seed", type=int, default=1, help="change to get a different queue")
    a = ap.parse_args()

    mode = a.mode or _ask("Mode (ranked/classic)", _mode, "ranked")
    rank = Rank.parse(a.rank) if a.rank else _ask('Your rank (e.g. Epic III, Mythic 12, Mythical Glory 60)', Rank.parse)
    matches = a.matches if a.matches is not None else _ask("Total matches played", _bounded(0, 100000, int), 0)
    winrate = 50.0
    if matches:
        winrate = a.winrate if a.winrate is not None else _ask("Winrate %", _bounded(0, 100, float), 50.0)
    streak = a.streak if a.streak is not None else _ask("Current streak (+wins / -losses)", _bounded(-50, 50, int), 0)
    size = a.party if a.party is not None else _ask("Party size (1-5)", _bounded(1, 5, int), 1)

    players = [_build_player("You", rank, matches, winrate, streak)]
    for i in range(size - 1):
        if a.mates is not None:
            mate_rank = Rank.parse(a.mates[i]) if i < len(a.mates) else rank
        elif a.party is not None:
            mate_rank = rank
        else:
            mate_rank = _ask(f"Teammate {i + 2} rank", Rank.parse, _rank_name(rank))
        players.append(_build_player(f"Mate{i + 2}", mate_rank, matches, winrate, streak))

    cfg = RANKED if mode == "ranked" else CLASSIC
    try:
        result = play(Party(players), cfg, seed=a.seed)
    except ValueError as e:
        raise SystemExit(f"The queue won't take that party: {e}")
    print()
    print(report(result, cfg, mode.capitalize()))


if __name__ == "__main__":
    main()
