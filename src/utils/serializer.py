import json

from src import logger


async def decode_json_fields(rows, json_keys: list[str]):
    """
    Parses specified JSON fields in each row of the result set.
    """
    for row in rows:
        for key in json_keys:
            if (
                key in row
                and isinstance(row[key], str)
                and (
                    row[key].strip().startswith("{")
                    or row[key].strip().startswith("[")
                )
            ):
                try:
                    row[key] = json.loads(row[key])
                except json.JSONDecodeError as e:
                    logger.error(f"Error decoding JSON for key '{key}': {e}")
                    continue
    return rows


async def encode_json_fields(rows, json_keys: list[str]):
    """
    Serializes specified dictionary fields into JSON strings.
    """
    for row in rows:
        for key in json_keys:
            if key in row and isinstance(row[key], (dict, list)):
                try:
                    row[key] = json.dumps(row[key])
                except (TypeError, OverflowError) as e:
                    logger.error(f"Error encoding JSON for key '{key}': {e}")
                    continue
    return rows if len(rows) > 1 else rows[0]
