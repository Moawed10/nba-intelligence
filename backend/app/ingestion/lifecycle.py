from app.models import GameStatus

S = GameStatus
ALLOWED_TRANSITIONS: dict[GameStatus, set[GameStatus]] = {
    S.scheduled: {S.delayed, S.in_progress, S.postponed, S.cancelled, S.final},
    S.delayed: {S.in_progress, S.postponed, S.cancelled, S.scheduled, S.final},
    S.in_progress: {S.final, S.postponed},
    S.postponed: {S.scheduled, S.cancelled, S.in_progress, S.final},
    S.final: set(),
    S.cancelled: set(),
}


def resolve_status(current: GameStatus | None, observed: GameStatus) -> tuple[GameStatus, bool]:
    """Returns (status to store, whether the observation was accepted).

    Unknown games take the observed status. Repeating the current status is accepted. Anything not
    in ALLOWED_TRANSITIONS keeps the stored status, so a stale response can never downgrade a final.
    """
    if current is None or current == observed:
        return observed, True
    if observed in ALLOWED_TRANSITIONS[current]:
        return observed, True
    return current, False
