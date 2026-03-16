import httpx

from arxiv_agent.arxiv_client import ArxivClient


def test_retry_delay_respects_retry_after_header() -> None:
    client = ArxivClient(user_agent="test", min_request_interval_seconds=0.0)
    response = httpx.Response(429, headers={"Retry-After": "7"})
    assert client._retry_delay_seconds(attempt=1, response=response) == 7.0


def test_retry_delay_has_min_backoff_for_429_without_header() -> None:
    client = ArxivClient(user_agent="test", min_request_interval_seconds=0.0)
    response = httpx.Response(429)
    assert client._retry_delay_seconds(attempt=1, response=response) >= 3.0
