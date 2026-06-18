from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

RESPONSIBLE_FILE = 'bling_app_zero/core/wizard_state.py'

STEP_MODELO = 'modelo'
STEP_ORIGEM = 'origem'
STEP_ENTRADA = 'entrada'
STEP_PRECIFICACAO = 'precificacao'
STEP_CATEGORIZACAO = 'categorizacao'
STEP_MAPEAMENTO = 'mapeamento'
STEP_REGRAS = 'regras'
STEP_IA = 'ia'
STEP_PREVIEW = 'preview'
STEP_DOWNLOAD = 'download'

WIZARD_STEPS: tuple[str, ...] = (
    STEP_MODELO,
    STEP_ORIGEM,
    STEP_ENTRADA,
    STEP_PRECIFICACAO,
    STEP_CATEGORIZACAO,
    STEP_MAPEAMENTO,
    STEP_REGRAS,
    STEP_IA,
    STEP_PREVIEW,
    STEP_DOWNLOAD,
)

API_STEPS: tuple[str, ...] = (
    STEP_ORIGEM,
    STEP_ENTRADA,
    STEP_DOWNLOAD,
)

CSV_STEPS: tuple[str, ...] = WIZARD_STEPS

OP_CADASTRO = 'cadastro'
OP_ESTOQUE = 'estoque'
OP_PRECO = 'atualizacao_preco'
OP_UNIVERSAL = 'universal'

ORIGIN_SITE = 'site'
ORIGIN_FILE = 'arquivo'

CONTEXT_API = 'api_direct'
CONTEXT_CSV = 'csv_download'
CONTEXT_UNIVERSAL = 'universal'


@dataclass(frozen=True)
class WizardState:
    step: str = STEP_MODELO
    operation: str = OP_CADASTRO
    origin: str = ''
    context: str = CONTEXT_CSV
    api_mode: bool = False
    has_model: bool = False
    has_origin: bool = False
    has_data: bool = False
    has_pricing: bool = False
    has_mapping: bool = False
    has_rules: bool = False
    has_preview: bool = False

    @property
    def steps(self) -> tuple[str, ...]:
        return API_STEPS if self.api_mode else CSV_STEPS

    @property
    def step_index(self) -> int:
        try:
            return self.steps.index(self.step)
        except ValueError:
            return 0

    @property
    def is_first_step(self) -> bool:
        return self.step_index <= 0

    @property
    def is_last_step(self) -> bool:
        return self.step_index >= len(self.steps) - 1

    def with_updates(self, **updates: Any) -> 'WizardState':
        values = self.to_dict()
        values.update(updates)
        return WizardState.from_mapping(values)

    def to_dict(self) -> dict[str, Any]:
        return {
            'step': self.step,
            'operation': self.operation,
            'origin': self.origin,
            'context': self.context,
            'api_mode': self.api_mode,
            'has_model': self.has_model,
            'has_origin': self.has_origin,
            'has_data': self.has_data,
            'has_pricing': self.has_pricing,
            'has_mapping': self.has_mapping,
            'has_rules': self.has_rules,
            'has_preview': self.has_preview,
        }

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any] | None = None) -> 'WizardState':
        data = dict(values or {})
        api_mode = bool(data.get('api_mode')) or str(data.get('context') or '') == CONTEXT_API or str(data.get('bling_finish_mode') or '') == CONTEXT_API
        step = str(data.get('step') or data.get('bling_wizard_step') or (STEP_ORIGEM if api_mode else STEP_MODELO)).strip()
        allowed = API_STEPS if api_mode else CSV_STEPS
        if step not in allowed:
            step = allowed[0]
        operation = str(
            data.get('operation')
            or data.get('direct_bling_operation_choice')
            or data.get('home_slim_flow_operation')
            or data.get('operacao_final')
            or OP_CADASTRO
        ).strip()
        origin = str(data.get('origin') or data.get('origem') or data.get('home_slim_flow_origin') or data.get('origem_final') or '').strip()
        context = CONTEXT_API if api_mode else str(data.get('context') or data.get('entry_context') or CONTEXT_CSV).strip()
        return cls(
            step=step,
            operation=operation,
            origin=origin,
            context=context,
            api_mode=api_mode,
            has_model=bool(data.get('has_model') or data.get('modelo_ok') or data.get('model_ready')),
            has_origin=bool(origin or data.get('has_origin')),
            has_data=bool(data.get('has_data') or data.get('df_origem') is not None or data.get('cadastro_wizard_df_origem') is not None),
            has_pricing=bool(data.get('has_pricing') or data.get('pricing_ready')),
            has_mapping=bool(data.get('has_mapping') or data.get('mapping_ready')),
            has_rules=bool(data.get('has_rules') or data.get('rules_ready')),
            has_preview=bool(data.get('has_preview') or data.get('preview_ready')),
        )


def normalize_step(step: object, *, api_mode: bool = False) -> str:
    text = str(step or '').strip()
    allowed = API_STEPS if api_mode else CSV_STEPS
    return text if text in allowed else allowed[0]


__all__ = [
    'API_STEPS',
    'CONTEXT_API',
    'CONTEXT_CSV',
    'CONTEXT_UNIVERSAL',
    'CSV_STEPS',
    'OP_CADASTRO',
    'OP_ESTOQUE',
    'OP_PRECO',
    'OP_UNIVERSAL',
    'ORIGIN_FILE',
    'ORIGIN_SITE',
    'STEP_CATEGORIZACAO',
    'STEP_DOWNLOAD',
    'STEP_ENTRADA',
    'STEP_IA',
    'STEP_MAPEAMENTO',
    'STEP_MODELO',
    'STEP_ORIGEM',
    'STEP_PRECIFICACAO',
    'STEP_PREVIEW',
    'STEP_REGRAS',
    'WIZARD_STEPS',
    'WizardState',
    'normalize_step',
]