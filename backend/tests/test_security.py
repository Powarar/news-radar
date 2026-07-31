import time

from app.core.security import _is_recent_auth_date


def test_auth_date_must_be_numeric_recent_and_not_in_future():
    now = int(time.time())

    assert _is_recent_auth_date(now)
    assert not _is_recent_auth_date("not-a-timestamp")
    assert not _is_recent_auth_date(now - 601)
    assert not _is_recent_auth_date(now + 1)
