# MLBB Matchmaking Engine

A conceptual 5v5 matchmaking engine for Mobile Legends: Bang Bang. It builds balanced matches from a queue of solo players and parties, using rank, winrate, total matches and current streak.

This is a learning/concept project. It is **not** how MLBB actually matches players, and every number in it (rank thresholds, search windows, protection cutoffs) is a placeholder guess. Use it to explore ideas and compare settings, not to predict the real game.

## Requirements

Python 3.8 or newer. No third-party packages, so there is no `requirements.txt`. (Developed and tested on Python 3.14.)

## Try it as a player

```
python -m mlbb_mm.play
```

Enter your mode, rank, total matches, winrate, streak and party size. You are dropped into a simulated queue and shown how you were rated, how long you waited, and who you were matched with.

Or pass the answers as flags. Anything you leave out is asked for:

```
python -m mlbb_mm.play --mode ranked --rank "Epic III" --matches 250 --winrate 58 --streak 4
python -m mlbb_mm.play --mode ranked --rank "Mythical Glory 70" --matches 900 --winrate 55 --streak 0 --party 2
```

Rank can be written as `Epic III`, `epic 3`, `Mythic 12` or `glory 60`. Divisions run from Warrior up to Legend; Mythic and above take a total star count. Use `--seed N` for a different simulated queue.

## Run the simulation

```
python -m mlbb_mm.sim --mode ranked --minutes 60 --rate 2 --seed 1
```

A headless run (no screen, no sleeping, fake clock) that prints wait times by tier and party size, how many players gave up, and how balanced the matches really were. Every simulated player has a hidden true skill that the matcher never sees, and the simulation uses it to grade each match afterwards. Options: `--mode ranked|classic`, `--minutes`, `--rate` (new parties per second), `--patience`, `--smurf-rate`, `--seed`. The same seed always gives the same result.

## Run the tests

```
python -m unittest discover -s tests -t .
```

## Use it in code

```python
from mlbb_mm import RANKED, Matchmaker, Party, Player, Rank

mm = Matchmaker(RANKED)
mm.add_to_queue(Party.of(Player("me", Rank("Epic", 3), matches=250, wins=145, streak=4)))
# ... add more parties ...
match = mm.find_match()        # one Match, or None
matches = mm.run_tick()        # every match possible right now
```

`Matchmaker` takes an optional `clock` function, which is how the tests and simulation run on fake time.

## How it works

**Rating a player.** Rank is the base, converted to a number where one division is 1.0 step (Mythic and above count in stars).

| Signal | Effect |
|---|---|
| Rank | The base skill. |
| Winrate | A capped adjustment. It is smoothed toward 50%, so 4-0 is not treated as 100%. |
| Streak | A small capped nudge for streaks of 3 or more. It only adjusts the skill estimate and never steers outcomes. |
| Total matches | Confidence. Low confidence widens the search window, and players under 50 matches get new-player protection (they are kept away from much stronger players). |

**Building a match.** The matcher:

1. Anchors on the longest-waiting party.
2. Gathers parties in the same region that fit its skill window. The window widens with waiting (capped), is wider at the thin top ranks and for low-confidence players, and the whole lobby must fit inside it.
3. Searches for whole parties totalling exactly 10 players.
4. Tries every assignment of whole parties to two teams of exactly 5 and keeps the one with the smallest skill gap. Parties are never split.

Group sets that total 10 but cannot split 5/5 (for example 4+3+3) are rejected.

## Project layout

```
mlbb_mm/
  ranks.py     rank ladder and rank parsing
  skill.py     effective skill (rank + winrate + streak) and confidence
  config.py    all tunable settings; RANKED and CLASSIC presets
  models.py    Player, Party, Match
  matcher.py   the matchmaker
  sim.py       headless simulation
  play.py      interactive player mode
tests/         unit tests
legacy/        the original prototype scripts (superseded, kept for reference)
```

## Known limits

- All thresholds and tuning values are placeholders. The rank ladder in `ranks.py` and the settings in `config.py` are meant to be edited.
- Top ranks wait a long time, because there are very few players there. At the default simulated traffic, Mythical Immortal players almost never get a match.
- There is no rating update after a match, so skill estimates do not learn from results.
- Smurf detection is not implemented.
- The matcher searches within a fixed budget and can miss the best possible match in a very large queue.
- Only one region is simulated, and there is no ping/latency or role/lane handling.
- Despite the "ML" in the name, there is no machine learning; "ML" means Mobile Legends.
