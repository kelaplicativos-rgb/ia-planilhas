from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Literal

import pandas as pd

FeatureScope = Literal['cadastro', 'estoque', 'global']
FeatureStatus = Literal['stable', 'beta', 'experimental', 'disabled']
FeatureStage = Literal['entrada', 'mapeamento', 'preview', 'download', 'sidebar', 'global']
FeatureRunner = Callable[['FeatureContext'], 'FeatureResult']
FeatureRenderer = Callable[[], None]


@dataclass(frozen=True)
class FeatureContext:
    """Entrada padronizada para recursos plugáveis.

    Nenhum recurso novo deve depender diretamente de chaves soltas do Streamlit sem
    declarar o contrato aqui. O módulo pode receber dataframes, configuração e metadados
    já normalizados pelo ponto de integração.
    """
    operation: FeatureScope = 'global'
    stage: FeatureStage = 'global'
    source_df: pd.DataFrame | None = None
    model_df: pd.DataFrame | None = None
    final_df: pd.DataFrame | None = None
    config: dict[str, Any] = field(default_factory=dict)
    state: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FeatureResult:
    """Saída padronizada para recursos plugáveis."""
    ok: bool = True
    message: str = ''
    source_df: pd.DataFrame | None = None
    final_df: pd.DataFrame | None = None
    state_updates: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class FeatureDefinition:
    """Definição oficial de um recurso modular do sistema."""
    key: str
    title: str
    description: str
    scope: FeatureScope = 'global'
    stage: FeatureStage = 'global'
    status: FeatureStatus = 'beta'
    state_key: str = ''
    requires: tuple[str, ...] = ()
    provides: tuple[str, ...] = ()
    owner_file: str = ''
    renderer: FeatureRenderer | None = None
    runner: FeatureRunner | None = None

    @property
    def enabled_key(self) -> str:
        return self.state_key or f'feature_{self.key}_enabled'


__all__ = [
    'FeatureContext',
    'FeatureDefinition',
    'FeatureRenderer',
    'FeatureResult',
    'FeatureRunner',
    'FeatureScope',
    'FeatureStage',
    'FeatureStatus',
]
