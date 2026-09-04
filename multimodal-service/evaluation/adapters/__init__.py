"""Offline adapters for archived public phishing datasets.

The adapters in this package never fetch a URL.  They only transform files that
the caller has already placed on local storage into FinDer's inert manifest.
"""

from .common import AdapterResult, AdapterStats, UnsafeContentError

__all__ = ["AdapterResult", "AdapterStats", "UnsafeContentError"]
