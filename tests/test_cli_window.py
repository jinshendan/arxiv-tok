import typer

from arxiv_agent.cli import _resolve_lookback_hours


def test_resolve_window_default() -> None:
    assert _resolve_lookback_hours(default_hours=30, days=0, months=0, years=0) == 30


def test_resolve_window_month_and_year() -> None:
    hours = _resolve_lookback_hours(default_hours=30, days=0, months=2, years=1)
    assert hours == int((2 * 30 + 365) * 24)


def test_resolve_window_negative_raises() -> None:
    try:
        _resolve_lookback_hours(default_hours=30, days=-1, months=0, years=0)
        assert False, "expected BadParameter"
    except typer.BadParameter:
        assert True
