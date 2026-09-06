from datetime import datetime, timezone

from omniverse_solar_system.simulation_clock import SimulationClock, format_playback_rate


def test_clock_runs_forward_and_backward_without_jumping():
    epoch = datetime(2026, 1, 1, tzinfo=timezone.utc)
    clock = SimulationClock.paused_at(epoch, monotonic_now=10.0)
    clock.set_rate(86_400.0, monotonic_now=10.0)
    assert clock.current(monotonic_now=12.0) == datetime(2026, 1, 3, tzinfo=timezone.utc)
    clock.set_rate(-86_400.0, monotonic_now=12.0)
    assert clock.current(monotonic_now=13.0) == datetime(2026, 1, 2, tzinfo=timezone.utc)


def test_pause_and_reset_to_now():
    epoch = datetime(2026, 1, 1, tzinfo=timezone.utc)
    clock = SimulationClock.paused_at(epoch, monotonic_now=0.0)
    clock.set_rate(3_600.0, monotonic_now=0.0)
    clock.pause(monotonic_now=2.0)
    assert clock.current(monotonic_now=100.0) == datetime(2026, 1, 1, 2, tzinfo=timezone.utc)
    reset = datetime(2026, 7, 29, 8, tzinfo=timezone.utc)
    clock.reset_to_now(reset, monotonic_now=100.0)
    assert clock.current(monotonic_now=200.0) == reset
    assert not clock.is_playing


def test_format_playback_rate():
    assert format_playback_rate(0.0) == "paused"
    assert format_playback_rate(3_600.0) == "+1 hour/s"
    assert format_playback_rate(-864_000.0) == "−10 days/s"
