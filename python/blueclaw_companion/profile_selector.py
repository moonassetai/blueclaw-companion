from __future__ import annotations

from .game_type import GenreProfile
from .genre_profiles import GENRE_PROFILE_REGISTRY

def get_genre_profile(genre_id: str) -> GenreProfile | None:
    return GENRE_PROFILE_REGISTRY.get(genre_id)
