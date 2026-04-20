"""Consensus QA exceptions."""


class ConsensusError(Exception):
    """Base error for consensus QA."""


class ConsensusConfigurationError(ConsensusError):
    """Raised when consensus runtime configuration is invalid."""


class ConsensusStorageError(ConsensusError):
    """Raised when consensus storage is unavailable or inconsistent."""

