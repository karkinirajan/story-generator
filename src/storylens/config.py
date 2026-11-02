"""Settings from environment variables (``flask run`` also reads a local ``.env``).
An empty value counts as unset."""

import os
from dataclasses import dataclass


def _value(env, name, default):
    raw = env.get(name, "")
    return raw if raw != "" else default


def _number(env, name, default, kind):
    raw = _value(env, name, None)
    if raw is None:
        return default
    try:
        return kind(raw)
    except ValueError:
        raise ValueError(f"{name} must be a number, not {raw!r}") from None


@dataclass(frozen=True)
class Config:
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    openai_timeout: float = 60.0
    max_completion_tokens: int = 700
    max_upload_mb: int = 10
    rate_limit_per_minute: int = 10  # per client address; 0 turns the limit off
    trusted_proxies: int = 0  # number of reverse proxies in front (for the client address)

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @classmethod
    def from_env(cls, env=None):
        env = os.environ if env is None else env
        return cls(
            openai_api_key=_value(env, "OPENAI_API_KEY", ""),
            openai_model=_value(env, "OPENAI_MODEL", cls.openai_model),
            openai_timeout=_number(env, "OPENAI_TIMEOUT", cls.openai_timeout, float),
            max_completion_tokens=_number(
                env, "MAX_COMPLETION_TOKENS", cls.max_completion_tokens, int
            ),
            max_upload_mb=_number(env, "MAX_UPLOAD_MB", cls.max_upload_mb, int),
            rate_limit_per_minute=_number(
                env, "RATE_LIMIT_PER_MINUTE", cls.rate_limit_per_minute, int
            ),
            trusted_proxies=_number(env, "TRUSTED_PROXIES", cls.trusted_proxies, int),
        )
