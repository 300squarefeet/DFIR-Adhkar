"""FastAPI dependency providers."""

from fastapi import Depends

from adhkar.core.settings import Settings
from adhkar.core.settings import get_settings as _get_settings


def get_settings(settings: Settings = Depends(_get_settings)) -> Settings:  # noqa: B008
    # Depends() in default position is FastAPI's canonical injection pattern.
    return settings
