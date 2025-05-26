from typing import Any, Optional

from decouple import config
from fastapi.responses import JSONResponse

from src.utils.sanitizer import sanitize_fields


class CustomResponse:
    """
    A class for custom JSON responses with message, status code, data, and
    optional metadata.
    """

    def __new__(
        cls,
        message: str = "Success",
        status_code: int = 200,
        data: Optional[Any] = None,
        meta: Optional[Any] = None,
    ):
        """Override __new__ to return a JSONResponse instead of an instance."""
        instance = super().__new__(cls)
        instance.message = message
        instance.status_code = status_code
        instance.base_url = instance._construct_base_url()
        instance.data = instance._prefix_urls(data or [])
        instance.meta = meta or []

        # Instead of returning the instance, return the JSONResponse
        return instance.__call__()

    def _construct_base_url(self) -> str:
        """Construct the base URL based on environment settings."""
        env = config("ENV", default="prod").lower()
        app_url = config("APP_URL", default="http://localhost")
        app_port = config("APP_PORT", default="8000")

        return f"{app_url}:{app_port}" if env == "dev" else app_url

    def _prefix_urls(self, data: Any) -> Any:
        """
        Recursively prefix 'url' keys in data with BASE_URL if in dev mode.
        """
        if config("ENV", default="prod").lower() != "dev":
            return data

        if isinstance(data, dict):
            return {
                k: (
                    f"{self.base_url}{v}"
                    if k == "url" and isinstance(v, str)
                    else self._prefix_urls(v)
                )
                for k, v in data.items()
            }
        elif isinstance(data, list):
            return [self._prefix_urls(item) for item in data]

        return data

    def __call__(self) -> JSONResponse:
        """Return a JSONResponse asynchronously"""
        response = {
            "message": self.message,
            "status_code": self.status_code,
            "data": sanitize_fields(self.data) or [],
            "meta": sanitize_fields(self.meta) or [],
        }
        return JSONResponse(content=response, status_code=self.status_code)


class CustomError(Exception):
    """
    Custom exception class for errors with HTTP status codes.
    """

    def __init__(self, message: str, status_code: int):
        self.message = message
        self.http_status_code = status_code
        super().__init__(self.message)

    def __str__(self):
        return f"{self.http_status_code}: {self.message}"
