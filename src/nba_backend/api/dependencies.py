from __future__ import annotations

from nba_backend.domain.models import UserContext

DEFAULT_USER = "system"


def get_user_context() -> UserContext:
    return UserContext(
        username=DEFAULT_USER,
        allowed_accounts=set(),
        allowed_clients=set(),
    )
