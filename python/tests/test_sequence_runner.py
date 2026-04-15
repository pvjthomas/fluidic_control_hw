"""
test_sequence_runner.py
Tests for SequenceRunner and load_protocol.
Runs entirely in memory with FakePump — no hardware required.

Run with:
    cd /Users/fio/Projects/fluidic_control_hw
    PYTHONPATH=python pytest python/tests/test_sequence_runner.py -v
"""

import os
import tempfile
import pytest

from core.sequence_runner import SequenceRunner, load_protocol, Step
from core.pumps.fake_pump import FakePump


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def make_csv(content: str) -> str:
    """Write content to a temp CSV file and return its path."""
    f = tempfile.NamedTemporaryFile(
        mode='w', suffix='.csv', delete=False, encoding='utf-8'
    )
    f.write(content)
    f.close()
    return f.name


def make_channels():
    """Return a simple two-channel setup with fake pumps."""
    return {
        'oil':    FakePump(pump_ids=[0]),
        'buffer': FakePump(pump_ids=[1]),
    }


# ------------------------------------------------------------------
# load_protocol — valid files
# ------------------------------------------------------------------

def test_load_csv_returns_correct_steps():
    path = make_csv(
        "step_name,duration_s,oil,buffer\n"
        "prime,30,10000,10000\n"
        "run,120,500,200\n"
    )
    steps = load_protocol(path, ['oil', 'buffer'])
    assert len(steps) == 2
    assert steps[0].name == 'prime'
    assert steps[0].duration_s == 30.0
    assert steps[0].setpoints == {'oil': 10000.0, 'buffer': 10000.0}
    assert steps[1].name == 'run'
    assert steps[1].setpoints == {'oil': 500.0, 'buffer': 200.0}
    os.unlink(path)


def test_empty_cell_means_no_change():
    path = make_csv(
        "step_name,duration_s,oil,buffer\n"
        "run,60,500,\n"
    )
    steps = load_protocol(path, ['oil', 'buffer'])
    assert 'oil' in steps[0].setpoints
    assert 'buffer' not in steps[0].setpoints
    os.unlink(path)


def test_negative_rate_allowed():
    path = make_csv(
        "step_name,duration_s,oil\n"
        "withdraw,30,-200\n"
    )
    steps = load_protocol(path, ['oil'])
    assert steps[0].setpoints['oil'] == -200.0
    os.unlink(path)


def test_float_duration_allowed():
    path = make_csv(
        "step_name,duration_s,oil\n"
        "short,0.5,100\n"
    )
    steps = load_protocol(path, ['oil'])
    assert steps[0].duration_s == 0.5
    os.unlink(path)


# ------------------------------------------------------------------
# load_protocol — validation errors
# ------------------------------------------------------------------

def test_missing_step_name_column_raises():
    path = make_csv(
        "duration_s,oil\n"
        "30,500\n"
    )
    with pytest.raises(ValueError, match="step_name"):
        load_protocol(path, ['oil'])
    os.unlink(path)


def test_missing_duration_column_raises():
    path = make_csv(
        "step_name,oil\n"
        "prime,500\n"
    )
    with pytest.raises(ValueError, match="duration_s"):
        load_protocol(path, ['oil'])
    os.unlink(path)


def test_unknown_channel_column_raises():
    path = make_csv(
        "step_name,duration_s,unknown_channel\n"
        "prime,30,500\n"
    )
    with pytest.raises(ValueError, match="Unknown channel"):
        load_protocol(path, ['oil'])
    os.unlink(path)


def test_invalid_duration_raises():
    path = make_csv(
        "step_name,duration_s,oil\n"
        "prime,notanumber,500\n"
    )
    with pytest.raises(ValueError, match="duration_s"):
        load_protocol(path, ['oil'])
    os.unlink(path)


def test_negative_duration_raises():
    path = make_csv(
        "step_name,duration_s,oil\n"
        "prime,-10,500\n"
    )
    with pytest.raises(ValueError, match="duration_s"):
        load_protocol(path, ['oil'])
    os.unlink(path)


def test_file_not_found_raises():
    with pytest.raises(FileNotFoundError):
        load_protocol('nonexistent.csv', ['oil'])


def test_unsupported_format_raises():
    with pytest.raises(ValueError, match="Unsupported"):
        load_protocol('protocol.txt', ['oil'])


def test_empty_file_raises():
    path = make_csv("step_name,duration_s,oil\n")
    with pytest.raises(ValueError, match="no valid steps"):
        load_protocol(path, ['oil'])
    os.unlink(path)


# ------------------------------------------------------------------
# SequenceRunner — setup
# ------------------------------------------------------------------

def test_runner_load_returns_steps():
    path = make_csv(
        "step_name,duration_s,oil\n"
        "prime,30,10000\n"
        "run,60,500\n"
    )
    runner = SequenceRunner(make_channels())
    steps = runner.load(path)
    assert len(steps) == 2
    assert runner.step_count == 2
    os.unlink(path)


def test_runner_initial_state():
    runner = SequenceRunner(make_channels())
    assert not runner.is_running
    assert not runner.is_paused
    assert runner.current_step is None


def test_runner_start_without_load_raises():
    runner = SequenceRunner(make_channels())
    with pytest.raises(RuntimeError, match="No protocol loaded"):
        runner.start()


# ------------------------------------------------------------------
# SequenceRunner — navigation (without running the loop)
# ------------------------------------------------------------------

@pytest.fixture
def loaded_runner():
    path = make_csv(
        "step_name,duration_s,oil,buffer\n"
        "prime,30,10000,10000\n"
        "equilibrate,60,500,500\n"
        "run,300,200,800\n"
        "flush,30,0,0\n"
    )
    runner = SequenceRunner(make_channels())
    runner.load(path)
    # Manually set index to test navigation without running the loop
    runner._current_index = 1
    runner._elapsed = 20.0
    yield runner
    os.unlink(path)


def test_next_step_advances_index(loaded_runner):
    loaded_runner.next_step()
    assert loaded_runner._current_index == 2
    assert loaded_runner._elapsed == 0.0


def test_previous_step_goes_back(loaded_runner):
    loaded_runner.previous_step()
    assert loaded_runner._current_index == 0
    assert loaded_runner._elapsed == 0.0


def test_next_step_at_last_step_does_not_overflow(loaded_runner):
    loaded_runner._current_index = 3  # last step
    loaded_runner.next_step()
    assert loaded_runner._current_index == 3


def test_previous_step_at_first_step_does_not_underflow(loaded_runner):
    loaded_runner._current_index = 0
    loaded_runner.previous_step()
    assert loaded_runner._current_index == 0


def test_seek_forward_within_step(loaded_runner):
    # elapsed=20, duration=60, seeking 10s -> elapsed=30
    loaded_runner.seek_forward(10.0)
    assert loaded_runner._elapsed == 30.0
    assert loaded_runner._current_index == 1


def test_seek_forward_past_step_end_advances(loaded_runner):
    # elapsed=20, duration=60, seeking 50s -> advances to next step
    loaded_runner.seek_forward(50.0)
    assert loaded_runner._current_index == 2
    assert loaded_runner._elapsed == 0.0


def test_seek_backward_within_step(loaded_runner):
    # elapsed=20, seeking back 10s -> elapsed=10
    loaded_runner.seek_backward(10.0)
    assert loaded_runner._elapsed == 10.0


def test_seek_backward_clamps_to_zero(loaded_runner):
    # elapsed=20, seeking back 30s -> clamps to 0
    loaded_runner.seek_backward(30.0)
    assert loaded_runner._elapsed == 0.0


# ------------------------------------------------------------------
# SequenceRunner — callbacks
# ------------------------------------------------------------------

def test_on_log_callback_called(loaded_runner):
    log_messages = []
    loaded_runner.on_log = lambda msg: log_messages.append(msg)
    loaded_runner.next_step()
    assert len(log_messages) > 0


def test_pause_and_resume(loaded_runner):
    loaded_runner.pause()
    assert loaded_runner.is_paused
    loaded_runner.resume()
    assert not loaded_runner.is_paused