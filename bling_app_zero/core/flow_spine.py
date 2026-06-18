from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import streamlit as st

from bling_app_zero.features_runtime.contracts import FeatureContract
from bling_app_zero.features_runtime.router import (
    active_contract,
    feature_needs_mapping,
    feature_needs_pricing,
    feature_needs_rules_review,
    feature_requires_destination_model,
)

RESPONSIBLE_FILE = 'bling_app_zero/core/flow_spine.py'

STEP_MODELO = 'modelo'
STEP_ORIGEM = 'origem'
STEP_ENTRADA = 'entrada'
STEP_PRECIFICACAO = 'precificacao'
STEP_CATEGORIZACAO = 'categorizacao'
STEP_MAPEAMENTO = 'mapeamento'
STEP_REGRAS = 'regras'
STEP_PREVIEW = 'preview'
STEP_DOWNLOAD = 'download'

DESTINATION_API = 'api_bling'
DESTINATION_CSV = 'csv_download'
UNIFIED_BLING_SEND_KEY = 'home_bling_connected_same_flow_api_send'

DEFAULT_RENDER_STEPS = (
    STEP_MODELO,
    STEP_ORIGEM,
    STEP_ENTRADA,
    STEP_PRECIFICACAO,
    STEP_CATEGORIZACAO,
    STEP_MAPEAMENTO,
    STEP_REGRAS,
    STEP_PREVIEW,
    STEP_DOWNLOAD,
)

DEFAULT_LABELS = {
    STEP_MODELO: 'Modelo para mapear',
    STEP_ORIGEM: 'Origem dos dados',
    STEP_ENTRADA: 'Dados',
    STEP_PRECIFICACAO: 'Precificação',
    STEP_CATEGORIZACAO: 'Categorização Inteligente Automática',
    STEP_MAPEAMENTO: 'Mapeamento',
    STEP_REGRAS: 'Regras e IA',
    STEP_PREVIEW: 'Prévia final',
    STEP_DOWNLOAD: 'Download',
}


@dataclass(frozen=True)
class FlowSpinePlan:
    contract_key: str
    operation: str
    mode: str
    is_api: bool
    steps: tuple[str, ...]
    labels: dict[str, str]
    primary_action_label: str
    final_destination: str
    final_title: str
    final_caption: str
    backup_enabled: bool
    needs_model: bool
    needs_pricing: bool
    needs_mapping: bool
    needs_rules_review: bool
    needs_download: bool
    responsible_file: str = RESPONSIBLE_FILE

    def has_step(self, step: str) -> bool:
        return str(step or '').strip().lower() in self.steps

    def label_for(self, step: str) -> str:
        normalized = str(step or '').strip().lower()
        return str(self.labels.get(normalized, normalized)).strip()

    def index_of(self, step: str) -> int:
        normalized = str(step or '').strip().lower()
        try:
            return list(self.steps).index(normalized)
        except ValueError:
            return -1

    def previous_step(self, step: str) -> str:
        index = self.index_of(step)
        if index <= 0:
            return ''
        return self.steps[index - 1]

    def next_step(self, step: str) -> str:
        index = self.index_of(step)
        if index < 0 or index >= len(self.steps) - 1:
            return ''
        return self.steps[index + 1]

    def to_dict(self) -> dict[str, object]:
        return {
            'contract_key': self.contract_key,
            'operation': self.operation,
            'mode': self.mode,
            'is_api': self.is_api,
            'steps': list(self.steps),
            'primary_action_label': self.primary_action_label,
            'final_destination': self.final_destination,
            'final_title': self.final_title,
            'backup_enabled': self.backup_enabled,
            'needs_model': self.needs_model,
            'needs_pricing': self.needs_pricing,
            'needs_mapping': self.needs_mapping,
            'needs_rules_review': self.needs_rules_review,
            'needs_download': self.needs_download,
            'responsible_file': self.responsible_file,
        }


def _unified_bling_send_enabled() -> bool:
    return bool(st.session_state.get(UNIFIED_BLING_SEND_KEY))


def _labels_for_contract(contract: FeatureContract, steps: Iterable[str]) -> dict[str, str]:
    labels = dict(DEFAULT_LABELS)
    if contract.is_api or _unified_bling_send_enabled():
        labels[STEP_ENTRADA] = 'Dados'
        labels[STEP_DOWNLOAD] = 'Enviar / Download'
    return {step: labels.get(step, step) for step in steps}


def _final_destination_for(contract: FeatureContract) -> str:
    # BLINGFIX 2026-06-13:
    # Bling conectado não deve trocar o wizard para contrato API curto.
    # O fluxo permanece CSV/universal e apenas o destino final vira envio API.
    if _unified_bling_send_enabled():
        return DESTINATION_API
    return DESTINATION_API if contract.is_api else DESTINATION_CSV


def _final_title_for(contract: FeatureContract) -> str:
    if contract.is_api or _unified_bling_send_enabled():
        return 'Enviar ao Bling'
    return 'Download'


def _final_caption_for(contract: FeatureContract) -> str:
    if contract.is_api or _unified_bling_send_enabled():
        return 'Confira a base revisada antes de enviar ao Bling. O CSV fica como backup opcional.'
    return 'Baixe o modelo mapeado usando exatamente o layout anexado.'


def build_flow_spine_plan(*, render_steps: Iterable[str] = DEFAULT_RENDER_STEPS) -> FlowSpinePlan:
    contract = active_contract()
    requires_model = feature_requires_destination_model()
    allowed_render_steps = [str(step).strip().lower() for step in render_steps if str(step).strip()]
    steps = [step for step in contract.steps if step in allowed_render_steps]
    if not requires_model:
        steps = [step for step in steps if step != STEP_MODELO]
    if not feature_needs_pricing():
        steps = [step for step in steps if step != STEP_PRECIFICACAO]
    if not feature_needs_mapping():
        steps = [step for step in steps if step != STEP_MAPEAMENTO]
    if not feature_needs_rules_review():
        steps = [step for step in steps if step != STEP_REGRAS]
    if not steps:
        steps = [STEP_ORIGEM, STEP_ENTRADA, STEP_DOWNLOAD]

    final_destination = _final_destination_for(contract)
    final_title = _final_title_for(contract)
    plan = FlowSpinePlan(
        contract_key=contract.key,
        operation=contract.operation,
        mode=contract.mode,
        is_api=bool(contract.is_api or _unified_bling_send_enabled()),
        steps=tuple(steps),
        labels=_labels_for_contract(contract, steps),
        primary_action_label='Enviar ao Bling' if final_destination == DESTINATION_API else contract.primary_action_label,
        final_destination=final_destination,
        final_title=final_title,
        final_caption=_final_caption_for(contract),
        backup_enabled=final_destination == DESTINATION_API,
        needs_model=requires_model,
        needs_pricing=feature_needs_pricing(),
        needs_mapping=feature_needs_mapping(),
        needs_rules_review=feature_needs_rules_review(),
        needs_download=bool(getattr(contract, 'needs_download', False)),
    )
    st.session_state['flow_spine_contract_key'] = plan.contract_key
    st.session_state['flow_spine_operation'] = plan.operation
    st.session_state['flow_spine_mode'] = plan.mode
    st.session_state['flow_spine_steps'] = list(plan.steps)
    st.session_state['flow_spine_primary_action_label'] = plan.primary_action_label
    st.session_state['flow_spine_final_destination'] = plan.final_destination
    st.session_state['flow_spine_final_title'] = plan.final_title
    return plan


def resolve_step(plan: FlowSpinePlan, candidate: object) -> str:
    step = str(candidate or '').strip().lower()
    if plan.has_step(step):
        return step
    return plan.steps[0] if plan.steps else STEP_ORIGEM


def pending_message_for(plan: FlowSpinePlan, step: str) -> str:
    normalized = str(step or '').strip().lower()
    if normalized == STEP_MODELO:
        return 'Anexe ou confirme o modelo para mapear para liberar a próxima etapa.'
    if normalized == STEP_ORIGEM:
        return 'Escolha se os dados virão de Arquivo ou Site para continuar.'
    if normalized == STEP_ENTRADA:
        return 'Carregue os dados da origem para liberar a próxima etapa.'
    if normalized == STEP_PRECIFICACAO:
        return 'Revise ou confirme a precificação para continuar.'
    if normalized == STEP_CATEGORIZACAO:
        return 'Escolha se vai categorizar. Se sim, aplique a conferência; se não, siga sem alterar categorias.'
    if normalized == STEP_MAPEAMENTO:
        return 'Confirme o mapeamento obrigatório antes de avançar.'
    if normalized in {STEP_REGRAS, STEP_PREVIEW}:
        return 'Confirme o mapeamento e revise os dados antes de continuar.'
    return 'Conclua esta etapa para continuar.'


def is_api_destination(plan: FlowSpinePlan) -> bool:
    return plan.final_destination == DESTINATION_API


def is_csv_destination(plan: FlowSpinePlan) -> bool:
    return plan.final_destination == DESTINATION_CSV


__all__ = [
    'DEFAULT_RENDER_STEPS',
    'DESTINATION_API',
    'DESTINATION_CSV',
    'FlowSpinePlan',
    'STEP_CATEGORIZACAO',
    'STEP_DOWNLOAD',
    'STEP_ENTRADA',
    'STEP_MAPEAMENTO',
    'STEP_MODELO',
    'STEP_ORIGEM',
    'STEP_PRECIFICACAO',
    'STEP_PREVIEW',
    'STEP_REGRAS',
    'build_flow_spine_plan',
    'is_api_destination',
    'is_csv_destination',
    'pending_message_for',
    'resolve_step',
]
