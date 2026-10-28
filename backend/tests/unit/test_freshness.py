from datetime import UTC, datetime, timedelta

import pytest

from app.models import RunStatus as R
from app.sync.freshness import POLICIES, Freshness, classify

NOW = datetime(2026, 10, 28, 12, tzinfo=UTC)
POLICY = POLICIES["schedule"]


@pytest.mark.parametrize(
    ("age", "recent", "expected"),
    [
        (timedelta(minutes=5), [R.succeeded], Freshness.fresh),
        (timedelta(minutes=90), [R.succeeded], Freshness.aging),
        (timedelta(hours=3), [R.succeeded], Freshness.stale),
        (timedelta(hours=3), [R.failed, R.failed, R.failed], Freshness.unavailable),
        (timedelta(minutes=5), [R.failed, R.failed, R.failed], Freshness.fresh),
        (timedelta(hours=3), [R.failed, R.failed], Freshness.stale),
    ],
)
def test_classify(age, recent, expected):
    assert classify(NOW, NOW - age, recent, POLICY) == expected


def test_never_synced_is_unavailable():
    assert classify(NOW, None, [], POLICY) == Freshness.unavailable
