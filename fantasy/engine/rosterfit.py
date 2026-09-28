"""Position eligibility: which starting slots a set of players can fill (bipartite matching)."""

SLOT_ACCEPTS = {
    "PG": {"PG"},
    "SG": {"SG"},
    "G": {"PG", "SG"},
    "SF": {"SF"},
    "PF": {"PF"},
    "F": {"SF", "PF"},
    "C": {"C"},
}


def _can_fill(slot: str, positions: list[str]) -> bool:
    if slot == "UTIL":
        return True
    return bool(SLOT_ACCEPTS.get(slot, {slot}) & set(positions))


def assign(players: list[list[str]], slots: list[str]) -> list[int | None]:
    """Maximum matching of players to slots. Returns for each slot the player index or None."""
    owner: list[int | None] = [None] * len(slots)

    def try_player(i: int, seen: set[int]) -> bool:
        for j, slot in enumerate(slots):
            if j in seen or not _can_fill(slot, players[i]):
                continue
            seen.add(j)
            if owner[j] is None or try_player(owner[j], seen):
                owner[j] = i
                return True
        return False

    for i in range(len(players)):
        try_player(i, set())
    return owner


def unfilled_slots(players: list[list[str]], slots: list[str]) -> list[str]:
    """Starting slots (without UTIL) that the players cannot fill."""
    specific = [s for s in slots if s != "UTIL"]
    owner = assign(players, specific)
    return [slot for slot, who in zip(specific, owner, strict=True) if who is None]


def fills_open_slot(candidate: list[str], players: list[list[str]], slots: list[str]) -> bool:
    before = len(unfilled_slots(players, slots))
    after = len(unfilled_slots(players + [candidate], slots))
    return after < before
