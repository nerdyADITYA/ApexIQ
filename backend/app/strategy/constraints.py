DRY = {"SOFT", "MEDIUM", "HARD"}
MAX_STOPS = 4
MIN_STINT_LAPS = 3


def check_strategy(compounds: list[str], pit_laps: list[int], total_laps: int, wet_race: bool = False) -> list[str]:
    """Returns violations (empty list = legal under the modelled rules)."""
    v = []
    compounds = [c.upper() for c in compounds]
    if len(compounds) != len(pit_laps) + 1:
        v.append("Need exactly one more stint compound than pit stops")
    if len(pit_laps) > MAX_STOPS:
        v.append(f"At most {MAX_STOPS} stops are modelled")
    if list(pit_laps) != sorted(set(pit_laps)):
        v.append("Pit laps must be strictly increasing")
    if pit_laps and (min(pit_laps) < 1 or max(pit_laps) >= total_laps):
        v.append(f"Pit laps must be within 1..{total_laps - 1}")
    bounds = [0, *sorted(pit_laps), total_laps]
    if any(b - a < MIN_STINT_LAPS for a, b in zip(bounds, bounds[1:])):
        v.append(f"Each stint must be at least {MIN_STINT_LAPS} laps")
    if not wet_race:
        if any(c not in DRY for c in compounds):
            v.append("Only SOFT, MEDIUM and HARD are supported in a dry race")
        if len(set(compounds)) < 2:
            v.append("Dry-race rule: at least two different dry compounds must be used")
    return v
