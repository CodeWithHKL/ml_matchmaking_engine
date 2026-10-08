import dataclasses
import unittest

from mlbb_mm import RANKED, Matchmaker, Party, Player, Rank
from mlbb_mm.ranks import TIER_NAMES
from mlbb_mm.skill import confidence, effective_skill, streak_adjustment, winrate_adjustment


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def player(rank=Rank("Epic", 3), matches=500, wins=250, streak=0, region="SEA"):
    return Player("p", rank, matches=matches, wins=wins, streak=streak, region=region)


def solo(**kw):
    return Party.of(player(**kw))


def party(size, **kw):
    return Party.of(*[player(**kw) for _ in range(size)])


def new_mm(cfg=RANKED):
    clock = Clock()
    return Matchmaker(cfg, clock), clock


def team_size(team):
    return sum(p.size for p in team)


class RankTests(unittest.TestCase):
    def test_ladder_is_strictly_increasing(self):
        ranks = [Rank("Warrior", 3), Rank("Warrior", 1), Rank("Elite", 3), Rank("Epic", 5),
                 Rank("Legend", 1), Rank.from_stars(0), Rank.from_stars(25),
                 Rank.from_stars(50), Rank.from_stars(100), Rank.from_stars(150)]
        scores = [r.score for r in ranks]
        self.assertEqual(scores, sorted(set(scores)))

    def test_star_tiers(self):
        self.assertEqual(Rank.from_stars(24).tier, "Mythic")
        self.assertEqual(Rank.from_stars(25).tier, "Mythical Honor")
        self.assertEqual(Rank.from_stars(49).tier, "Mythical Honor")
        self.assertEqual(Rank.from_stars(50).tier, "Mythical Glory")
        self.assertEqual(Rank.from_stars(100).tier, "Mythical Immortal")
        self.assertEqual(Rank.from_stars(500).tier, "Mythical Immortal")
        self.assertEqual(len(TIER_NAMES), 10)

    def test_invalid_ranks(self):
        with self.assertRaises(ValueError):
            Rank("Warrior", 4)
        with self.assertRaises(ValueError):
            Rank("Mythical Honor", stars=10)
        with self.assertRaises(ValueError):
            Rank("Mythic", stars=30)
        with self.assertRaises(ValueError):
            Rank("Bronze", 1)


class SkillTests(unittest.TestCase):
    def test_few_games_winrate_is_shrunk(self):
        lucky = player(matches=4, wins=4)
        proven = player(matches=400, wins=300)
        self.assertLess(winrate_adjustment(lucky, RANKED), winrate_adjustment(proven, RANKED))
        self.assertGreater(winrate_adjustment(lucky, RANKED), 0)

    def test_winrate_adjustment_is_capped_both_ways(self):
        self.assertEqual(winrate_adjustment(player(matches=5000, wins=5000), RANKED), RANKED.wr_cap)
        self.assertEqual(winrate_adjustment(player(matches=5000, wins=0), RANKED), -RANKED.wr_cap)

    def test_streaks(self):
        self.assertEqual(streak_adjustment(player(streak=2), RANKED), 0)
        self.assertGreater(streak_adjustment(player(streak=3), RANKED), 0)
        self.assertLess(streak_adjustment(player(streak=-3), RANKED), 0)
        self.assertEqual(streak_adjustment(player(streak=99), RANKED), RANKED.streak_cap)
        self.assertEqual(streak_adjustment(player(streak=-99), RANKED), -RANKED.streak_cap)

    def test_confidence_rises_with_matches(self):
        self.assertEqual(confidence(player(matches=0, wins=0), RANKED), 0)
        self.assertLess(confidence(player(matches=10, wins=5), RANKED),
                        confidence(player(matches=500, wins=250), RANKED))

    def test_hot_player_is_rated_above_plain_rank(self):
        plain = player()
        hot = player(matches=300, wins=210, streak=6)
        self.assertGreater(effective_skill(hot, RANKED), effective_skill(plain, RANKED))


class MatchTests(unittest.TestCase):
    def test_ten_similar_solos_make_a_5v5(self):
        mm, _ = new_mm()
        for _ in range(10):
            mm.add_to_queue(solo())
        m = mm.find_match()
        self.assertEqual((team_size(m.team_a), team_size(m.team_b)), (5, 5))
        self.assertEqual(mm.queued_players(), 0)

    def test_fewer_than_ten_players_no_match(self):
        mm, _ = new_mm()
        for _ in range(9):
            mm.add_to_queue(solo())
        self.assertIsNone(mm.find_match())

    def test_sizes_that_cannot_split_5_5_do_not_match(self):
        # 4+3+3 and 3+3+3+1 both total 10 but have no 5/5 split.
        for sizes in [(4, 3, 3), (3, 3, 3, 1)]:
            mm, _ = new_mm()
            for s in sizes:
                mm.add_to_queue(party(s))
            self.assertIsNone(mm.find_match(), sizes)
            self.assertEqual(mm.queued_players(), 10)

    def test_four_three_two_one_splits_correctly(self):
        mm, _ = new_mm()
        for s in (4, 3, 2, 1):
            mm.add_to_queue(party(s))
        m = mm.find_match()
        self.assertEqual((team_size(m.team_a), team_size(m.team_b)), (5, 5))

    def test_search_finds_split_a_greedy_pack_would_miss(self):
        # 3,3,3,1,... : anchor 3 must pair with 2s, not the other 3s.
        mm, _ = new_mm()
        for s in (3, 3, 2, 2):
            mm.add_to_queue(party(s))
        m = mm.find_match()
        self.assertEqual((team_size(m.team_a), team_size(m.team_b)), (5, 5))

    def test_parties_are_never_split(self):
        mm, _ = new_mm()
        duo = Party.of(player(Rank("Epic", 2)), player(Rank("Epic", 3)))
        mm.add_to_queue(duo)
        for _ in range(8):
            mm.add_to_queue(solo())
        m = mm.find_match()
        in_a, in_b = duo in m.team_a, duo in m.team_b
        self.assertTrue(in_a != in_b)  # whole party on exactly one team

    def test_teams_are_balanced(self):
        mm, _ = new_mm()
        for r in (1, 2, 3, 4, 5, 1, 2, 3, 4, 5):
            mm.add_to_queue(solo(rank=Rank("Epic", r)))
        m = mm.find_match()
        self.assertLessEqual(m.skill_diff, 0.5)

    def test_huge_skill_gap_never_matches_even_after_long_wait(self):
        mm, clock = new_mm()
        for _ in range(5):
            mm.add_to_queue(solo(rank=Rank("Warrior", 3)))
        for _ in range(5):
            mm.add_to_queue(solo(rank=Rank.from_stars(150)))
        clock.t = 100_000
        self.assertIsNone(mm.find_match())

    def test_window_widens_with_waiting(self):
        mm, clock = new_mm()
        for _ in range(5):
            mm.add_to_queue(solo(rank=Rank("Epic", 5)))
        for _ in range(5):
            mm.add_to_queue(solo(rank=Rank("Epic", 1)))  # 4 steps higher
        self.assertIsNone(mm.find_match())
        clock.t = 90
        self.assertIsNotNone(mm.find_match())

    def test_window_widening_is_capped(self):
        cfg = dataclasses.replace(RANKED, max_expansion=0.5)  # window tops out ~3.7 < the 4-step gap
        mm, clock = new_mm(cfg)
        for _ in range(5):
            mm.add_to_queue(solo(rank=Rank("Epic", 5)))
        for _ in range(5):
            mm.add_to_queue(solo(rank=Rank("Epic", 1)))
        clock.t = 100_000
        self.assertIsNone(mm.find_match())

    def test_new_player_is_protected_from_much_higher_players(self):
        rookie_queue, _ = new_mm()
        vet_queue, _ = new_mm()
        for mm in (rookie_queue, vet_queue):
            for _ in range(9):
                mm.add_to_queue(solo(rank=Rank("Epic", 1)))
        # 2 steps below the veterans: within the normal window, beyond the protected gap.
        rookie_queue.add_to_queue(solo(rank=Rank("Epic", 3), matches=5, wins=3))
        vet_queue.add_to_queue(solo(rank=Rank("Epic", 3)))
        self.assertIsNone(rookie_queue.find_match())
        self.assertIsNotNone(vet_queue.find_match())

    def test_different_regions_do_not_match(self):
        mm, _ = new_mm()
        for _ in range(5):
            mm.add_to_queue(solo(region="SEA"))
        for _ in range(5):
            mm.add_to_queue(solo(region="NA"))
        self.assertIsNone(mm.find_match())

    def test_party_with_too_wide_rank_gap_is_rejected(self):
        mm, _ = new_mm()
        bad = Party.of(player(Rank("Warrior", 3)), player(Rank("Legend", 1)))
        with self.assertRaises(ValueError):
            mm.add_to_queue(bad)

    def test_mixed_region_party_is_rejected(self):
        with self.assertRaises(ValueError):
            Party.of(player(region="SEA"), player(region="NA"))

    def test_five_stack_isolation_flag(self):
        cfg = dataclasses.replace(RANKED, isolate_five_stacks=True)
        mm, _ = new_mm(cfg)
        mm.add_to_queue(party(5))
        for _ in range(5):
            mm.add_to_queue(solo())
        self.assertIsNone(mm.find_match())
        mm.add_to_queue(party(5))
        m = mm.find_match()
        self.assertEqual([p.size for p in m.team_a + m.team_b], [5, 5])

    def test_run_tick_drains_multiple_matches(self):
        mm, _ = new_mm()
        for _ in range(25):
            mm.add_to_queue(solo())
        self.assertEqual(len(mm.run_tick()), 2)
        self.assertEqual(mm.queued_players(), 5)

    def test_longest_waiting_party_is_served_first(self):
        mm, clock = new_mm()
        first = solo(rank=Rank("Epic", 3))
        mm.add_to_queue(first)
        clock.t = 5
        for _ in range(14):
            mm.add_to_queue(solo(rank=Rank("Epic", 3)))
        m = mm.find_match()
        self.assertIn(first, m.team_a + m.team_b)

    def test_search_budget_keeps_big_queues_fast(self):
        mm, _ = new_mm()
        for _ in range(500):
            mm.add_to_queue(solo())
        self.assertIsNotNone(mm.find_match())


if __name__ == "__main__":
    unittest.main()
