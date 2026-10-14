"""Convert completed scoreboard DataFrames into WebSocket-safe records."""

from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from math import isfinite
from typing import Any


def dataframe_to_records(dataframe: Any) -> list[dict[str, Any]]:
    if not hasattr(dataframe, "copy") or not hasattr(dataframe, "to_dict"):
        raise TypeError("scoreboard update must be a pandas DataFrame")
    snapshot = dataframe.copy(deep=True)
    records = snapshot.to_dict(orient="records")
    if not isinstance(records, list) or any(not isinstance(row, dict) for row in records):
        raise ValueError("DataFrame conversion did not produce record dictionaries")

    return [_json_value(row, path=f"row {index}") for index, row in enumerate(records)]


def _json_value(value: Any, *, path: str) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not isfinite(value):
            raise ValueError(f"{path} contains a non-finite number")
        return value
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError(f"{path} contains a non-finite number")
        return float(value)
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, dict):
        if any(not isinstance(key, str) for key in value):
            raise ValueError(f"{path} contains a non-string column name")
        return {key: _json_value(item, path=f"{path}.{key}") for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item, path=f"{path}[]") for item in value]

    item = getattr(value, "item", None)
    if callable(item):  
        converted = item()
        if converted is value:
            raise ValueError(f"{path} is not JSON-compatible")
        return _json_value(converted, path=path)
    raise ValueError(f"{path} is not JSON-compatible")
