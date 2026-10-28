import pytest

from app.ingestion.lifecycle import ALLOWED_TRANSITIONS, resolve_status
from app.models import GameStatus as S


@pytest.mark.parametrize("observed", list(S))
def test_unknown_game_takes_observed_status(observed):
    assert resolve_status(None, observed) == (observed, True)


@pytest.mark.parametrize("current", list(S))
def test_repeating_status_is_accepted(current):
    assert resolve_status(current, current) == (current, True)


@pytest.mark.parametrize("observed", [s for s in S if s != S.final])
def test_final_is_never_downgraded(observed):
    assert resolve_status(S.final, observed) == (S.final, False)


def test_cancelled_is_terminal():
    assert ALLOWED_TRANSITIONS[S.cancelled] == set()
    assert resolve_status(S.cancelled, S.scheduled) == (S.cancelled, False)


@pytest.mark.parametrize(
    ("current", "observed", "accepted"),
    [
        (S.scheduled, S.in_progress, True),
        (S.scheduled, S.final, True),
        (S.scheduled, S.delayed, True),
        (S.delayed, S.in_progress, True),
        (S.in_progress, S.final, True),
        (S.in_progress, S.scheduled, False),
        (S.postponed, S.scheduled, True),
        (S.postponed, S.final, True),
    ],
)
def test_transitions(current, observed, accepted):
    status, ok = resolve_status(current, observed)
    assert ok is accepted
    assert status == (observed if accepted else current)
