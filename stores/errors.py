"""Errors the runner uses to stop one store without stopping the others."""


class StoreTimeout(Exception):
    """Raised when a store exceeds its time limit. Not a failed product row."""
