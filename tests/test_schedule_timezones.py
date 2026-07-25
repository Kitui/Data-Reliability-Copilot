from datetime import datetime, timezone

from app.api.routes.schedules import next_occurrence


def test_daily_schedule_converts_local_wall_clock_to_utc():
    # Nairobi is UTC+3, represented by JavaScript getTimezoneOffset() as -180.
    after = datetime(2026, 7, 23, 18, 20, tzinfo=timezone.utc)
    result = next_occurrence("daily", 21, 28, None, None, after, -180)
    assert result == datetime(2026, 7, 23, 18, 28, tzinfo=timezone.utc)


def test_daily_schedule_rolls_to_next_local_day_after_due_time():
    after = datetime(2026, 7, 23, 18, 29, tzinfo=timezone.utc)
    result = next_occurrence("daily", 21, 28, None, None, after, -180)
    assert result == datetime(2026, 7, 24, 18, 28, tzinfo=timezone.utc)
