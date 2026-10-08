"""Effective skill: rank is the base; winrate and streak are small, capped
corrections; total matches decides how much we trust the whole picture."""


def confidence(player, cfg):
    """0..1, rising with total matches played."""
    return player.matches / (player.matches + cfg.confidence_k)


def shrunk_winrate(player, cfg):
    """Winrate pulled toward 50% so a 4-0 record isn't treated as 100%."""
    prior = cfg.wr_prior_games
    return (player.wins + prior * 0.5) / (player.matches + prior)


def winrate_adjustment(player, cfg):
    adj = (shrunk_winrate(player, cfg) - 0.5) * cfg.wr_scale
    return max(-cfg.wr_cap, min(cfg.wr_cap, adj))


def streak_adjustment(player, cfg):
    n = abs(player.streak)
    if n < cfg.streak_min:
        return 0.0
    adj = min(cfg.streak_cap, cfg.streak_per_game * (n - cfg.streak_min + 1))
    return adj if player.streak > 0 else -adj


def effective_skill(player, cfg):
    return player.rank.score + winrate_adjustment(player, cfg) + streak_adjustment(player, cfg)
