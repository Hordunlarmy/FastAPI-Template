from datetime import date, datetime, time
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel


def sanitize_fields(data: Any) -> Any:
    """
    Recursively remove empty fields (None, {}, [], '') from the data structure.
    Supports Pydantic models and converts UUID to string.
    """
    if isinstance(data, BaseModel):
        return sanitize_fields(data.dict(exclude_none=True))

    if isinstance(data, dict):

        key_mapping = {
            "_id": "id",
            "authors_data": "authors",
        }

        sanitized = {}
        for key, value in data.items():
            if value in (None, "", [], {}):
                continue
            new_key = key_mapping.get(key, key)
            sanitized[new_key] = sanitize_fields(value)
        return sanitized

    if isinstance(data, list):
        sanitized_list = [sanitize_fields(value) for value in data]
        return [v for v in sanitized_list if v not in ("", None)]

    if isinstance(data, UUID):
        return str(data)

    if isinstance(data, datetime):
        return data.isoformat()

    if isinstance(data, time):
        return data.strftime("%H:%M:%S")
    if isinstance(data, date):
        return data.isoformat()
    if isinstance(data, Decimal):
        return float(data)

    return data
