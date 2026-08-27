# github/config.py
import os
from dataclasses import dataclass, field

from ..core.config import TransportConfig


@dataclass(frozen=True, slots=True)
class GithubConfig:
    token: str | None = None
    app_id: str | None = None
    installation_id: str | None = None
    private_key: str | None = None
    base_url: str = "https://api.github.com"
    transport: TransportConfig = field(default_factory=TransportConfig)

    def __post_init__(self) -> None:
        has_app_field = any((self.app_id, self.installation_id, self.private_key))
        has_full_app = all((self.app_id, self.installation_id, self.private_key))
        if has_app_field and not has_full_app:
            raise ValueError(
                "partial GitHub App config: app_id, installation_id, and "
                "private_key must all be set together"
            )
        if self.token is None and not has_full_app:
            raise ValueError(
                "GithubConfig needs either token or app_id+installation_id+private_key"
            )

    @classmethod
    def from_env(cls, prefix: str = "GITHUB_") -> "GithubConfig":
        app_id = os.environ.get(f"{prefix}APP_ID")
        installation_id = os.environ.get(f"{prefix}APP_INSTALLATION_ID")
        private_key = os.environ.get(f"{prefix}APP_PRIVATE_KEY")
        if app_id or installation_id or private_key:
            return cls(app_id=app_id, installation_id=installation_id, private_key=private_key)
        return cls(token=os.environ[f"{prefix}TOKEN"])  # raises if unset — mandatory fallback
