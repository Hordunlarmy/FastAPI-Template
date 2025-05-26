from datetime import datetime


def filter_valid_fields(data: dict, allowed_fields: set):
    from src import logger

    """
    Filter incoming data to match allowed fields.
    """
    filtered_data = {
        k: v for k, v in data.items() if k in allowed_fields and v is not None
    }

    if not filtered_data:
        logger.warning(
            "No valid fields found in the incoming data. "
            "Please check the provided fields."
        )
        filtered_data = {"updated_at": datetime.utcnow()}

    return filtered_data


def filter_null_fields(data: dict) -> dict:
    """
    Removes keys from the filter dictionary where values are None,
    'null', or empty strings.
    """
    return {
        key: value
        for key, value in data.items()
        if value is not None and value != "" and value != "null"
    }
