"""Official Python client for the hlthstack partner REST API."""

from . import types, webhooks
from ._async_client import AsyncHlthstack
from ._base_client import ENVIRONMENTS, FileInput
from ._client import Hlthstack
from ._exceptions import (
    APIConnectionError,
    AuthenticationError,
    BadRequestError,
    ConflictError,
    HlthstackError,
    NotFoundError,
    PermissionDeniedError,
    ServerError,
    UnprocessableEntityError,
    ValidationError,
    ValidationErrorDetail,
    WebhookVerificationError,
)
from ._version import __version__

__all__ = [
    "ENVIRONMENTS",
    "APIConnectionError",
    "AsyncHlthstack",
    "AuthenticationError",
    "BadRequestError",
    "ConflictError",
    "FileInput",
    "Hlthstack",
    "HlthstackError",
    "NotFoundError",
    "PermissionDeniedError",
    "ServerError",
    "UnprocessableEntityError",
    "ValidationError",
    "ValidationErrorDetail",
    "WebhookVerificationError",
    "__version__",
    "types",
    "webhooks",
]
