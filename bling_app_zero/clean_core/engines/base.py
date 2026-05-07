from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

import pandas as pd

from ..operations import Operation
from ..schema import RequestedField


@dataclass
class EngineResult:
    dataframe: pd.DataFrame
    logs: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class ProductEngine(Protocol):
    operation: Operation
    name: str

    def run(self, *, model_df: pd.DataFrame, requested_schema: list[RequestedField], urls: list[str], deposit_name: str = "") -> EngineResult:
        ...
