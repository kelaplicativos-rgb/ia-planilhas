from __future__ import annotations

from typing import Any

import pandas as pd

from ..io import empty_like_model
from ..schema import FieldIntent, RequestedField


def apply_payload_to_model(model_df: pd.DataFrame, schema: list[RequestedField], payloads: list[dict[FieldIntent, Any]]) -> pd.DataFrame:
    output = empty_like_model(model_df, rows=max(len(payloads), 1))
    for row_index, payload in enumerate(payloads or [{}]):
        for field in schema:
            value = payload.get(field.intent, "")
            if value is None:
                value = ""
            output.at[row_index, field.column] = str(value)
    return output


def blank_payload(schema: list[RequestedField]) -> dict[FieldIntent, str]:
    return {field.intent: "" for field in schema}
