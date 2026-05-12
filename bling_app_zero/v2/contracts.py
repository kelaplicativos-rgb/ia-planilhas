from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Literal

import pandas as pd

BlingOperation = Literal['cadastro', 'estoque', 'preco', 'categoria', 'global']
BlingStage = Literal['input', 'adapt', 'calculate', 'map', 'validate', 'export', 'send', 'global']
ModuleRunner = Callable[['TablePayload'], 'ModuleResult']


@dataclass(frozen=True)
class StoreProfile:
    """Perfil limpo para adaptar planilhas por loja/canal.

    Exemplo futuro: loja com ID informado no Bling, marketplace, tabela de preço,
    regra de margem, regra de campos obrigatórios ou layout específico.
    """
    store_id: str = ''
    name: str = ''
    channel: str = ''
    operation: BlingOperation = 'global'
    required_columns: tuple[str, ...] = ()
    optional_columns: tuple[str, ...] = ()
    pricing_rules: dict[str, Any] = field(default_factory=dict)
    field_defaults: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TablePayload:
    """Pacote único que trafega entre módulos V2.

    Não depende de st.session_state e não carrega chaves antigas. Cada etapa recebe
    dados explícitos e devolve dados explícitos.
    """
    operation: BlingOperation
    stage: BlingStage
    df: pd.DataFrame = field(default_factory=pd.DataFrame)
    model_df: pd.DataFrame = field(default_factory=pd.DataFrame)
    store_profile: StoreProfile = field(default_factory=StoreProfile)
    mapping: dict[str, str] = field(default_factory=dict)
    config: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def with_df(self, df: pd.DataFrame, *, stage: BlingStage | None = None) -> 'TablePayload':
        return TablePayload(
            operation=self.operation,
            stage=stage or self.stage,
            df=df.copy().fillna('') if isinstance(df, pd.DataFrame) else pd.DataFrame(),
            model_df=self.model_df.copy().fillna('') if isinstance(self.model_df, pd.DataFrame) else pd.DataFrame(),
            store_profile=self.store_profile,
            mapping=dict(self.mapping),
            config=dict(self.config),
            metadata=dict(self.metadata),
        )


@dataclass(frozen=True)
class ModuleResult:
    ok: bool
    payload: TablePayload
    message: str = ''
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    metrics: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ModuleSpec:
    key: str
    title: str
    description: str
    operation: BlingOperation = 'global'
    stage: BlingStage = 'global'
    version: str = '2.0.0'
    enabled: bool = True
    depends_on: tuple[str, ...] = ()
    provides: tuple[str, ...] = ()
    runner: ModuleRunner | None = None


@dataclass(frozen=True)
class SheetAdapterSpec:
    """Contrato para adaptadores de planilha por tipo de loja/canal."""
    key: str
    title: str
    description: str
    store_id_required: bool = False
    operation: BlingOperation = 'global'
    required_input_columns: tuple[str, ...] = ()
    output_columns: tuple[str, ...] = ()
    runner: ModuleRunner | None = None


__all__ = [
    'BlingOperation',
    'BlingStage',
    'ModuleResult',
    'ModuleRunner',
    'ModuleSpec',
    'SheetAdapterSpec',
    'StoreProfile',
    'TablePayload',
]
