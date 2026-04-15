"""
test_fake_pump.py
Tests for FakePump — runs entirely in memory, no hardware required.

Run with:
    pytest python/tests/test_fake_pump.py -v
"""

import pytest
from core.pumps.fake_pump import FakePump, PRIME_RATE_UL_HR


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture
def pump() -> FakePump:
    """A FakePump with 4 pumps for use in tests."""
    return FakePump(pump_ids=[0, 1, 2, 3])


# ------------------------------------------------------------------
# Setup
# ------------------------------------------------------------------

def test_find_pumps_returns_correct_ids(pump: FakePump) -> None:
    assert pump.find_pumps() == [0, 1, 2, 3]


def test_initial_rates_are_zero(pump: FakePump) -> None:
    rates = pump.get_rates([0, 1, 2, 3])
    assert all(r == 0.0 for r in rates.values())


def test_initial_state_is_not_running(pump: FakePump) -> None:
    assert pump.is_running is False


# ------------------------------------------------------------------
# Rates
# ------------------------------------------------------------------

def test_set_single_rate(pump: FakePump) -> None:
    pump.set_rates({0: 500.0})
    assert pump.get_rates([0])[0] == 500.0


def test_set_negative_rate_withdraw(pump: FakePump) -> None:
    pump.set_rates({1: -200.0})
    assert pump.get_rates([1])[1] == -200.0


def test_set_multiple_rates(pump: FakePump) -> None:
    pump.set_rates({0: 100.0, 1: 200.0, 2: 300.0, 3: 400.0})
    rates = pump.get_rates([0, 1, 2, 3])
    assert rates[0] == 100.0
    assert rates[1] == 200.0
    assert rates[2] == 300.0
    assert rates[3] == 400.0


def test_set_rate_does_not_affect_other_pumps(pump: FakePump) -> None:
    pump.set_rates({0: 999.0})
    rates = pump.get_rates([1, 2, 3])
    assert all(r == 0.0 for r in rates.values())


# ------------------------------------------------------------------
# Run and stop
# ------------------------------------------------------------------

def test_run_all_sets_running(pump: FakePump) -> None:
    pump.run_all()
    assert pump.is_running is True


def test_stop_all_clears_running(pump: FakePump) -> None:
    pump.run_all()
    pump.stop_all()
    assert pump.is_running is False


def test_stop_all_zeros_all_rates(pump: FakePump) -> None:
    pump.set_rates({0: 500.0, 1: 300.0, 2: 100.0, 3: 800.0})
    pump.run_all()
    pump.stop_all()
    rates = pump.get_rates([0, 1, 2, 3])
    assert all(r == 0.0 for r in rates.values())


def test_stop_pump_zeros_only_that_pump(pump: FakePump) -> None:
    pump.set_rates({0: 500.0, 1: 300.0})
    pump.run_all()
    pump.stop_pump(1)
    assert pump.get_rates([0])[0] == 500.0
    assert pump.get_rates([1])[1] == 0.0


# ------------------------------------------------------------------
# Diameter
# ------------------------------------------------------------------

def test_set_and_get_diameter(pump: FakePump) -> None:
    pump.set_diameter(0, 14.57)
    assert pump.get_diameter(0) == 14.57


def test_diameter_change_does_not_affect_other_pumps(pump: FakePump) -> None:
    from core.pumps.fake_pump import DEFAULT_DIAMETER_MM
    pump.set_diameter(0, 14.57)
    assert pump.get_diameter(1) == DEFAULT_DIAMETER_MM


# ------------------------------------------------------------------
# Prime
# ------------------------------------------------------------------

def test_prime_sets_correct_rate(pump: FakePump) -> None:
    pump.prime(0)
    assert pump.get_rates([0])[0] == PRIME_RATE_UL_HR


def test_prime_sets_running(pump: FakePump) -> None:
    pump.prime(0)
    assert pump.is_running is True


def test_prime_does_not_affect_other_pumps(pump: FakePump) -> None:
    pump.prime(0)
    rates = pump.get_rates([1, 2, 3])
    assert all(r == 0.0 for r in rates.values())


# ------------------------------------------------------------------
# Error handling
# ------------------------------------------------------------------

def test_set_rates_invalid_id_raises(pump: FakePump) -> None:
    with pytest.raises(ValueError):
        pump.set_rates({99: 500.0})


def test_get_rates_invalid_id_raises(pump: FakePump) -> None:
    with pytest.raises(ValueError):
        pump.get_rates([99])


def test_stop_pump_invalid_id_raises(pump: FakePump) -> None:
    with pytest.raises(ValueError):
        pump.stop_pump(99)


def test_set_diameter_invalid_id_raises(pump: FakePump) -> None:
    with pytest.raises(ValueError):
        pump.set_diameter(99, 10.0)


def test_get_diameter_invalid_id_raises(pump: FakePump) -> None:
    with pytest.raises(ValueError):
        pump.get_diameter(99)


def test_prime_invalid_id_raises(pump: FakePump) -> None:
    with pytest.raises(ValueError):
        pump.prime(99)