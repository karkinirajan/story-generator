import pytest

from storylens.config import Config
from storylens.ratelimit import RateLimiter


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def test_calls_up_to_the_limit_pass_then_the_wait_is_reported():
    clock = Clock()
    limiter = RateLimiter(3, window=60, clock=clock)
    assert [limiter.check("a") for _ in range(3)] == [0, 0, 0]
    clock.now += 10
    assert limiter.check("a") == pytest.approx(50)  # until the first call leaves the window


def test_the_window_slides():
    clock = Clock()
    limiter = RateLimiter(2, window=60, clock=clock)
    limiter.check("a")
    clock.now += 30
    limiter.check("a")
    assert limiter.check("a") > 0
    clock.now += 31  # the first call is now 61 s old
    assert limiter.check("a") == 0


def test_each_client_has_its_own_allowance():
    limiter = RateLimiter(1, clock=Clock())
    assert limiter.check("a") == 0 and limiter.check("b") == 0 and limiter.check("a") > 0


def test_a_limit_of_zero_turns_it_off():
    limiter = RateLimiter(0, clock=Clock())
    assert all(limiter.check("a") == 0 for _ in range(50))


def test_a_refused_call_is_not_counted():
    clock = Clock()
    limiter = RateLimiter(1, window=60, clock=clock)
    limiter.check("a")
    for _ in range(5):
        limiter.check("a")
    clock.now += 61
    assert limiter.check("a") == 0  # refused calls did not extend the wait


def test_quiet_clients_are_forgotten():
    clock = Clock()
    limiter = RateLimiter(1, window=60, clock=clock)
    for n in range(10_001):
        limiter.check(f"client-{n}")
    clock.now += 120
    limiter.check("new")
    assert len(limiter._hits) < 100


class TestConfig:
    def test_defaults(self):
        c = Config.from_env({})
        assert (
            c.openai_api_key,
            c.openai_model,
            c.max_upload_mb,
            c.rate_limit_per_minute,
            c.trusted_proxies,
        ) == ("", "gpt-4o", 10, 10, 0)
        assert c.max_upload_bytes == 10 * 1024 * 1024 and c.openai_timeout == 60.0

    def test_values_come_from_the_environment_and_empty_counts_as_unset(self):
        c = Config.from_env(
            {
                "OPENAI_API_KEY": "sk-x",
                "OPENAI_MODEL": "m",
                "MAX_UPLOAD_MB": "3",
                "RATE_LIMIT_PER_MINUTE": "",
                "OPENAI_TIMEOUT": "7.5",
                "TRUSTED_PROXIES": "1",
                "MAX_COMPLETION_TOKENS": "99",
            }
        )
        assert (
            c.openai_api_key,
            c.openai_model,
            c.max_upload_mb,
            c.rate_limit_per_minute,
            c.openai_timeout,
            c.trusted_proxies,
            c.max_completion_tokens,
        ) == ("sk-x", "m", 3, 10, 7.5, 1, 99)

    @pytest.mark.parametrize(
        "name",
        [
            "MAX_UPLOAD_MB",
            "RATE_LIMIT_PER_MINUTE",
            "OPENAI_TIMEOUT",
            "TRUSTED_PROXIES",
            "MAX_COMPLETION_TOKENS",
        ],
    )
    def test_a_bad_number_names_the_variable(self, name):
        with pytest.raises(ValueError, match=name):
            Config.from_env({name: "lots"})

    def test_it_reads_the_real_environment_by_default(self, monkeypatch):
        monkeypatch.setenv("OPENAI_MODEL", "from-env")
        assert Config.from_env().openai_model == "from-env"
