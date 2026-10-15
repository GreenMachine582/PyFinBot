"""The market sync lock through greentechhub-core's held_lock (v0.15):
market_sync_guard is held_lock on a per-market name, in PyFinBot's lock
directory, with the sync TTL."""
from unittest.mock import patch

import pytest

from pyfinbot.core import market_sync
from pyfinbot.core.market_sync import market_sync_guard


def test_second_caller_is_refused_while_held():
    with market_sync_guard("held-a") as first:
        with market_sync_guard("held-a") as second:
            assert first and not second
    with market_sync_guard("held-a") as again:
        assert again


def test_released_when_the_sync_raises():
    with pytest.raises(RuntimeError):
        with market_sync_guard("held-b") as acquired:
            assert acquired
            raise RuntimeError("sync failed")
    with market_sync_guard("held-b") as acquired:
        assert acquired


def test_market_guard_is_per_market_case_insensitive():
    with market_sync_guard("asx") as asx, market_sync_guard("ASX") as again, market_sync_guard("NYSE") as nyse:
        assert asx and not again and nyse


def test_uses_cores_held_lock_with_the_sync_ttl():
    with patch.object(market_sync, "held_lock", wraps=market_sync.held_lock) as spy:
        with market_sync_guard("held-c"):
            pass
    spy.assert_called_once_with(market_sync.settings, "market-sync-HELD-C",
                                ttl=market_sync.SYNC_LOCK_TTL_SECONDS)
