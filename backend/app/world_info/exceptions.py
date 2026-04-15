class WorldInfoError(Exception):
    """Base world info error."""


class WorldInfoDependencyError(WorldInfoError):
    """Missing optional dependency or unavailable external system."""


class WorldInfoStorageError(WorldInfoError):
    """Storage layer failure."""
