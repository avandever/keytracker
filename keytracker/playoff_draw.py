"""Drawing the playoff brackets.

Placement is not seeded. Each bracket is drawn separately so a team meets
different opponents in different formats, but the draw is balanced rather than
free: across the brackets, every pair of teams should meet in round one about
as often as every other. With four teams and eleven brackets that means the
three possible arrangements come up three or four times each.

Pure functions, so the balancing can be checked without a database.
"""

import itertools
import random
from typing import Dict, List, Optional, Sequence, Tuple


def bracket_size(team_count: int) -> int:
    """Slots in the tree: the next power of two at or above the field."""
    size = 1
    while size < team_count:
        size *= 2
    return size


def rounds_needed(team_count: int) -> int:
    """How many rounds -- and so how many weeks -- the playoffs take."""
    size, rounds = bracket_size(team_count), 0
    while size > 1:
        size //= 2
        rounds += 1
    return rounds


def byes_needed(team_count: int) -> int:
    return bracket_size(team_count) - team_count


def all_pairings(teams: Sequence[int]) -> List[List[Tuple[int, int]]]:
    """Every way to pair these teams up, each pair in a fixed order."""
    if not teams:
        return [[]]
    first, rest = teams[0], list(teams[1:])
    pairings = []
    for i, partner in enumerate(rest):
        remainder = rest[:i] + rest[i + 1:]
        for tail in all_pairings(remainder):
            pairings.append([(first, partner)] + tail)
    return pairings


def _pair_key(a: int, b: int) -> Tuple[int, int]:
    return (a, b) if a <= b else (b, a)


def choose_pairing(
    teams: Sequence[int],
    seen: Dict[Tuple[int, int], int],
    rng: random.Random,
) -> List[Tuple[int, int]]:
    """Pair these teams so the least-used meetings are used next.

    Scored on the most-used pair it contains first, then the total, so one
    repeated meeting is worse than two spread around.
    """
    options = all_pairings(list(teams))
    scored = []
    for pairing in options:
        counts = [seen.get(_pair_key(a, b), 0) for a, b in pairing]
        scored.append(((max(counts) if counts else 0, sum(counts)), pairing))
    best = min(score for score, _ in scored)
    candidates = [pairing for score, pairing in scored if score == best]
    return rng.choice(candidates)


def choose_byes(
    teams: Sequence[int],
    count: int,
    bye_counts: Dict[int, int],
    rng: random.Random,
) -> List[int]:
    """Whoever has sat out least so far, ties broken at random."""
    if count <= 0:
        return []
    pool = list(teams)
    rng.shuffle(pool)
    pool.sort(key=lambda team_id: bye_counts.get(team_id, 0))
    return pool[:count]


def draw_bracket(
    teams: Sequence[int],
    bye_teams: Sequence[int],
    seen: Dict[Tuple[int, int], int],
    rng: random.Random,
) -> List[Optional[int]]:
    """One bracket's opening slots: a team id per slot, None beside a bye."""
    playing = [t for t in teams if t not in set(bye_teams)]
    pairing = choose_pairing(playing, seen, rng) if playing else []
    slot_pairs: List[Tuple[Optional[int], Optional[int]]] = []
    for a, b in pairing:
        pair = [a, b]
        rng.shuffle(pair)
        slot_pairs.append((pair[0], pair[1]))
    for team_id in bye_teams:
        slot_pairs.append((team_id, None))
    rng.shuffle(slot_pairs)
    slots: List[Optional[int]] = []
    for first, second in slot_pairs:
        slots.extend([first, second])
    return slots


def draw_all(
    teams: Sequence[int],
    bracket_count: int,
    byes_for: Optional[callable] = None,
    rng: Optional[random.Random] = None,
) -> List[List[Optional[int]]]:
    """Draw every bracket, keeping round-one meetings evenly spread.

    ``byes_for(bracket_index, bye_counts)`` picks the teams sitting out that
    bracket; the default spreads them evenly, like the pairings.
    """
    rng = rng or random.Random()
    need = byes_needed(len(teams))
    seen: Dict[Tuple[int, int], int] = {}
    bye_counts: Dict[int, int] = {t: 0 for t in teams}
    drawn = []
    for index in range(bracket_count):
        if need and byes_for is not None:
            bye_teams = list(byes_for(index, dict(bye_counts)))
        elif need:
            bye_teams = choose_byes(teams, need, bye_counts, rng)
        else:
            bye_teams = []
        for team_id in bye_teams:
            bye_counts[team_id] = bye_counts.get(team_id, 0) + 1
        slots = draw_bracket(teams, bye_teams, seen, rng)
        for i in range(0, len(slots), 2):
            a, b = slots[i], slots[i + 1]
            if a is not None and b is not None:
                key = _pair_key(a, b)
                seen[key] = seen.get(key, 0) + 1
        drawn.append(slots)
    return drawn


def round_one_pairs(slots: Sequence[Optional[int]]) -> List[Tuple[Optional[int], Optional[int]]]:
    return [(slots[i], slots[i + 1]) for i in range(0, len(slots), 2)]
