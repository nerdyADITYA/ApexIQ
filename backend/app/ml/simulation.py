"""Season-specific scoring and Monte Carlo championship simulation.

Race finishing orders are sampled from a Plackett-Luce model (Gumbel trick):
order = argsort(-(log_strength + Gumbel noise)). Constructor points are the sum
of their drivers' points *in the same simulated race*, so driver and constructor
outcomes are consistent. Each driver may also retire with probability `dnf_prob`.
"""

from dataclasses import dataclass

import numpy as np

MODEL_VERSION = "mc-plackett-luce-v1"

_POINTS_2010_PLUS = [25, 18, 15, 12, 10, 8, 6, 4, 2, 1]
_SPRINT_POINTS = [8, 7, 6, 5, 4, 3, 2, 1]


def race_points_table(year: int) -> list[int]:
    if year < 2010:
        raise ValueError("Scoring rules before 2010 are not supported")
    return _POINTS_2010_PLUS


def fastest_lap_point_applies(year: int) -> bool:
    """FL bonus point existed 2019-2024 (top-10 finishers only)."""
    return 2019 <= year <= 2024


def sprint_points_table(year: int) -> list[int]:
    return _SPRINT_POINTS


def points_for_position(year: int, position: int, sprint: bool = False) -> int:
    table = sprint_points_table(year) if sprint else race_points_table(year)
    return table[position - 1] if 1 <= position <= len(table) else 0


@dataclass
class ChampionshipResult:
    driver_win_prob: dict[str, float]
    constructor_win_prob: dict[str, float]
    n_sims: int
    seed: int
    model_version: str = MODEL_VERSION


def finishing_ranks(rng, logs: np.ndarray, dnf: np.ndarray, n_sims: int):
    """Sample race outcomes. Returns (order, ranks, retired); ranks are 0-based finishing
    positions with retired drivers sorted behind everyone who finished."""
    n = len(logs)
    noise = rng.gumbel(size=(n_sims, n))
    retired = rng.random((n_sims, n)) < dnf
    score = np.where(retired, -np.inf, logs + noise)
    order = np.argsort(-score, axis=1)
    ranks = np.empty_like(order)
    np.put_along_axis(ranks, order, np.broadcast_to(np.arange(n), (n_sims, n)), axis=1)
    return order, ranks, retired


def simulate_championship(
    year: int,
    drivers: list[str],
    constructor_of: dict[str, str],
    driver_points: dict[str, float],
    constructor_points: dict[str, float],
    strengths: dict[str, float],
    remaining_races: int,
    dnf_prob: dict[str, float] | None = None,
    n_sims: int = 10000,
    seed: int = 0,
    sprints_remaining: int = 0,
) -> ChampionshipResult:
    """Ties are broken by simulated wins in remaining races, then at random
    (a simplification of the FIA countback; see docs/model-methodology.md)."""
    if not drivers:
        raise ValueError("No drivers")
    rng = np.random.default_rng(seed)
    n = len(drivers)
    teams = sorted(set(constructor_of[d] for d in drivers) | set(constructor_points))
    onehot = np.zeros((n, len(teams)))
    for i, d in enumerate(drivers):
        onehot[i, teams.index(constructor_of[d])] = 1.0

    logs = np.log(np.array([max(strengths.get(d, 1e-6), 1e-6) for d in drivers]))
    dnf = np.array([(dnf_prob or {}).get(d, 0.04) for d in drivers])
    full = np.array(race_points_table(year) + [0] * max(0, n - 10), dtype=float)
    spr = np.array(sprint_points_table(year) + [0] * max(0, n - 8), dtype=float)

    drv_pts = np.tile(np.array([driver_points.get(d, 0.0) for d in drivers], dtype=float), (n_sims, 1))
    team_pts = np.tile(np.array([constructor_points.get(t, 0.0) for t in teams], dtype=float), (n_sims, 1))
    wins = np.zeros((n_sims, n))
    sim_idx = np.arange(n_sims)

    def race(table, with_fl, count_wins):
        order, ranks, retired = finishing_ranks(rng, logs, dnf, n_sims)
        pts = np.where(retired, 0.0, table[ranks])
        if with_fl:
            fl = rng.integers(0, n, size=n_sims)
            ok = (ranks[sim_idx, fl] < 10) & ~retired[sim_idx, fl]
            pts[sim_idx, fl] += ok
        if count_wins:
            wins[sim_idx, order[:, 0]] += 1
        return pts

    fl = fastest_lap_point_applies(year)
    for _ in range(remaining_races):
        pts = race(full, fl, True)
        drv_pts += pts
        team_pts += pts @ onehot
    for _ in range(sprints_remaining):
        pts = race(spr, False, False)
        drv_pts += pts
        team_pts += pts @ onehot

    d_champ = _winners(drv_pts, wins, rng)
    t_champ = _winners(team_pts, np.zeros_like(team_pts), rng)
    return ChampionshipResult(
        driver_win_prob=dict(zip(drivers, (d_champ / n_sims).tolist())),
        constructor_win_prob=dict(zip(teams, (t_champ / n_sims).tolist())),
        n_sims=n_sims, seed=seed,
    )


def _winners(points: np.ndarray, wins: np.ndarray, rng) -> np.ndarray:
    key = points * 1e4 + wins * 1e1 + rng.random(points.shape)
    return np.bincount(np.argmax(key, axis=1), minlength=points.shape[1]).astype(float)
