from arxiv_agent.search_service import resolve_lookback_hours


def test_resolve_window_default() -> None:
    assert resolve_lookback_hours(default_hours=30, days=0, months=0, years=0) == 30


def test_resolve_window_month_and_year() -> None:
    hours = resolve_lookback_hours(default_hours=30, days=0, months=2, years=1)
    assert hours == int((2 * 30 + 365) * 24)


def test_resolve_window_negative_raises() -> None:
    try:
        resolve_lookback_hours(default_hours=30, days=-1, months=0, years=0)
        assert False, "expected ValueError"
    except ValueError:
        assert True
