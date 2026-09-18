from relay.cartographer.config import DEFAULT_BASE_URL, CartographerConfig


def test_from_env_defaults_to_default_base_url_when_unset(monkeypatch):
    monkeypatch.delenv("CARTOGRAPHER_URL", raising=False)

    config = CartographerConfig.from_env()

    assert config.base_url == DEFAULT_BASE_URL == "https://cartographer.apik.tech"


def test_from_env_uses_env_var_when_set(monkeypatch):
    monkeypatch.setenv("CARTOGRAPHER_URL", "http://cartographer.internal")

    config = CartographerConfig.from_env()

    assert config.base_url == "http://cartographer.internal"
