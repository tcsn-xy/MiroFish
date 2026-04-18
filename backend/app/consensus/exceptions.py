class ConsensusError(Exception):
    """Base consensus exception."""


class ConsensusConfigurationError(ConsensusError):
    """Raised when consensus config is invalid or unsupported."""


class ConsensusStorageError(ConsensusError):
    """Raised when consensus storage is unavailable or invalid."""
