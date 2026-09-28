from types import SimpleNamespace

import pytest

from fantasy import config
from fantasy.ai import client as ai


class FakeMessages:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            stop_reason="end_turn",
            content=[SimpleNamespace(type="text", text="Nimm Jokić.")],
            usage=SimpleNamespace(input_tokens=1000, output_tokens=200),
        )


@pytest.fixture
def fake_anthropic(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("AI_DAILY_BUDGET_USD", "0.01")
    config.get_settings.cache_clear()
    messages = FakeMessages()
    monkeypatch.setattr(ai.anthropic, "Anthropic", lambda **kwargs: SimpleNamespace(messages=messages))
    return messages


def test_cost_estimate():
    assert ai.cost_of("claude-sonnet-5", 1_000_000, 100_000) == pytest.approx(3.0)


def test_answers_are_cached(fake_anthropic):
    first = ai.ask("draft", "system", "Frage")
    second = ai.ask("draft", "system", "Frage")
    assert first.text == second.text == "Nimm Jokić."
    assert not first.cached and second.cached
    assert len(fake_anthropic.calls) == 1
    assert fake_anthropic.calls[0]["model"] == "claude-sonnet-5"
    assert fake_anthropic.calls[0]["output_config"] == {"effort": "low"}


def test_daily_budget_stops_spending(fake_anthropic):
    ai.ask("draft", "system", "Frage 1")  # costs 0.004 $
    ai.ask("draft", "system", "Frage 2")
    ai.ask("draft", "system", "Frage 3")
    with pytest.raises(ai.AiUnavailable, match="Tagesbudget"):
        ai.ask("draft", "system", "Frage 4")


def test_without_key(monkeypatch):
    with pytest.raises(ai.AiUnavailable, match="ANTHROPIC_API_KEY"):
        ai.ask("draft", "system", "Frage")
