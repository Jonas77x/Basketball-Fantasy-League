"""Small wrapper around the Anthropic API: caching, daily budget, German error messages.

The AI is optional. Without ANTHROPIC_API_KEY every feature falls back to template texts.
"""

import hashlib
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, time

import anthropic
from sqlalchemy import func, select

from fantasy.config import get_settings
from fantasy.db import AiText, session_scope
from fantasy.timeutil import DISPLAY_TZ, utcnow

log = logging.getLogger(__name__)

# USD per million tokens (input, output), see PLAN.md cost estimate.
PRICES = {
    "claude-sonnet-5": (2.0, 10.0),
    "claude-haiku-4-5": (1.0, 5.0),
    "claude-opus-5": (5.0, 25.0),
}


class AiUnavailable(RuntimeError):
    """Raised with a German message that can be shown to Jonas directly."""


@dataclass
class AiResult:
    text: str
    cost_usd: float
    cached: bool


def cost_of(model: str, input_tokens: int, output_tokens: int) -> float:
    price_in, price_out = PRICES.get(model, PRICES["claude-sonnet-5"])
    return input_tokens * price_in / 1e6 + output_tokens * price_out / 1e6


def spent_today() -> float:
    # Budget day = calendar day in Berlin. SQLite keeps the UTC wall time, so compare in UTC.
    local_day = utcnow().astimezone(DISPLAY_TZ).date()
    start = datetime.combine(local_day, time.min, tzinfo=DISPLAY_TZ).astimezone(UTC)
    with session_scope() as session:
        total = session.scalar(select(func.sum(AiText.cost_usd)).where(AiText.created_at >= start))
    return float(total or 0.0)


def _model_options(model: str) -> dict:
    # Short, simple texts: little reasoning needed. Haiku 4.5 does not accept the effort setting.
    if model.startswith("claude-haiku"):
        return {}
    return {"output_config": {"effort": "low"}}


def ask(purpose: str, system: str, prompt: str, max_tokens: int = 700) -> AiResult:
    settings = get_settings()
    if not settings.ai_enabled:
        raise AiUnavailable("Die KI ist nicht eingerichtet (kein ANTHROPIC_API_KEY in der .env-Datei).")
    model = settings.ai_model
    key = hashlib.sha256(f"{model}\n{system}\n{prompt}".encode()).hexdigest()

    with session_scope() as session:
        hit = session.scalars(select(AiText).where(AiText.cache_key == key)).first()
        if hit is not None:
            return AiResult(hit.text, 0.0, cached=True)

    if spent_today() >= settings.ai_daily_budget_usd:
        raise AiUnavailable(
            f"Das KI-Tagesbudget von {settings.ai_daily_budget_usd:.2f} $ ist aufgebraucht. Morgen geht es weiter."
        )

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key, timeout=60.0, max_retries=2)
    try:
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
            **_model_options(model),
        )
    except anthropic.AuthenticationError as exc:
        raise AiUnavailable("Der Anthropic-API-Key ist ungültig. Bitte in der .env-Datei prüfen.") from exc
    except anthropic.PermissionDeniedError as exc:
        raise AiUnavailable("Kein Zugriff auf das KI-Modell. Guthaben und Modellname prüfen.") from exc
    except anthropic.NotFoundError as exc:
        raise AiUnavailable(f"Das KI-Modell „{model}“ gibt es nicht. AI_MODEL in der .env prüfen.") from exc
    except anthropic.RateLimitError as exc:
        raise AiUnavailable("Gerade zu viele KI-Anfragen. Versuch es in einer Minute noch mal.") from exc
    except anthropic.APIStatusError as exc:
        log.warning("Anthropic API error %s: %s", exc.status_code, exc.message)
        raise AiUnavailable("Die KI ist gerade nicht erreichbar. Versuch es gleich noch mal.") from exc
    except anthropic.APIConnectionError as exc:
        raise AiUnavailable("Keine Verbindung zur KI. Internet prüfen.") from exc

    if response.stop_reason == "refusal":
        raise AiUnavailable("Die KI wollte diese Anfrage nicht beantworten.")
    text = "".join(block.text for block in response.content if block.type == "text").strip()
    cost = cost_of(model, response.usage.input_tokens, response.usage.output_tokens)
    with session_scope() as session:
        session.add(
            AiText(
                cache_key=key,
                purpose=purpose,
                model=model,
                text=text,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                cost_usd=cost,
            )
        )
    return AiResult(text, cost, cached=False)
