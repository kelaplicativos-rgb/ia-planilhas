from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import pandas as pd


@dataclass(frozen=True)
class FeatureContract:
    """Contrato declarativo de um recurso do sistema.

    Cada recurso informa o que precisa para funcionar. O roteador deixa de
    adivinhar fluxo com base em nomes de tela e passa a respeitar esse contrato.
    """

    key: str
    label: str
    operation: str
    mode: str
    supports_api: bool
    supports_csv: bool
    needs_model: bool
    needs_pricing: bool
    needs_mapping: bool
    needs_rules_review: bool
    needs_download: bool
    primary_action_label: str
    steps: tuple[str, ...]
    required_columns: tuple[str, ...] = ()
    optional_columns: tuple[str, ...] = ()

    @property
    def is_api(self) -> bool:
        return self.mode == 'api'

    @property
    def is_csv(self) -> bool:
        return self.mode == 'csv'

    def empty_dataframe(self) -> pd.DataFrame:
        columns = list(dict.fromkeys([*self.required_columns, *self.optional_columns]))
        return pd.DataFrame(columns=columns)


FeatureResolver = Callable[[str, str], FeatureContract]


__all__ = ['FeatureContract', 'FeatureResolver']
