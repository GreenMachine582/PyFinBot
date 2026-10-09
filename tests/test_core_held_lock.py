"""The sync locks through greentechhub-core's held (v0.13): sync_guard binds
PyFinBot's FileLock and TTL to it instead of hand-rolling acquire/release."""
from unittest.mock import patch

import pytest

from pyfinbot.core import market_sync
from pyfinbot.core.market_sync import market_sync_guard, sync_guard


def test_second_caller_is_refused_while_held():
    with sync_guard("held-lock-a") as first:
        with sync_guard("held-lock-a") as second:
            assert first and not second
    with sync_guard("held-lock-a") as again:
        assert again


def test_released_when_the_sync_raises():
    with pytest.raises(RuntimeError):
        with sync_guard("held-lock-b") as acquired:
            assert acquired
            raise RuntimeError("sync failed")
    with sync_guard("held-lock-b") as acquired:
        assert acquired


def test_market_guard_is_per_market_case_insensitive():
    with market_sync_guard("asx") as asx, market_sync_guard("ASX") as again, market_sync_guard("NYSE") as nyse:
        assert asx and not again and nyse


def test_uses_cores_held_with_the_sync_ttl():
    with patch.object(market_sync, "held", wraps=market_sync.held) as spy:
        with sync_guard("held-lock-c"):
            pass
    spy.assert_called_once_with(market_sync._sync_locks(), "held-lock-c", ttl=market_sync.SYNC_LOCK_TTL_SECONDS)
