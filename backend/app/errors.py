"""Errors shared by the engine and the provider adapters."""


class DebateError(RuntimeError):
    """Raised when the debate cannot be completed."""


class ModelRefusal(DebateError):
    """The model declined to produce a turn."""


class ProviderConfigError(DebateError):
    """The provider is misconfigured, e.g. an unknown provider name."""
