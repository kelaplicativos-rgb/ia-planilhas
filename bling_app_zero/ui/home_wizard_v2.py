from __future__ import annotations

import streamlit as st

import bling_app_zero.ui.home_wizard as legacy
from bling_app_zero.ui.category_conference_wizard_step import category_wizard_ready, render_category_conference_wizard_step

RESPONSIBLE_FILE = 'bling_app_zero/ui/home_wizard_v2.py'
STEP_CATEGORIZACAO = 'categorizacao'
STEP_PRECIFICACAO = 'precificacao'
STEP_MAPEAMENTO = 'mapeamento'
STEP_REGRAS = 'regras'
_PATCHED_KEY = 'home_wizard_v2_category_patch_applied'


def _insert_category_step() -> None:
    steps = [step for step in list(getattr(legacy, 'ACTIVE_RENDER_STEPS', [])) if step != STEP_CATEGORIZACAO]
    try:
        # Quando a etapa de precificação existir, categorias vem logo depois dela.
        index = steps.index(STEP_PRECIFICACAO) + 1
    except ValueError:
        try:
            # Quando o fluxo não exigir preço, categorias continua disponível antes do mapeamento.
            index = steps.index(STEP_MAPEAMENTO)
        except ValueError:
            index = len(steps)
    steps.insert(index, STEP_CATEGORIZACAO)
    legacy.ACTIVE_RENDER_STEPS = steps


def _category_or_mapping_step(steps: list[str], active_step: str) -> str:
    if STEP_CATEGORIZACAO in steps:
        return STEP_CATEGORIZACAO
    if STEP_MAPEAMENTO in steps:
        return STEP_MAPEAMENTO
    return active_step


def _patch_legacy_wizard() -> None:
    _insert_category_step()
    if bool(getattr(legacy, _PATCHED_KEY, False)):
        return

    original_render_active_step = legacy._render_active_step
    original_can_advance_from = legacy._can_advance_from
    original_step_is_done = legacy._step_is_done
    original_step_after_model_when_source_ready = legacy._step_after_model_when_source_ready
    original_resolve_active_step = legacy._resolve_active_step

    def _render_category_step(section_number: int) -> None:
        legacy.render_step_anchor(STEP_CATEGORIZACAO)
        legacy._section_title(section_number, 'Categorização Inteligente Automática')
        if not legacy._model_available():
            legacy.render_pending_notice('Liberado após modelo/dados. Se houver precificação no fluxo, esta etapa virá logo depois dela.')
            return
        if not legacy.universal_context_ready():
            legacy.render_pending_notice('Carregue os dados primeiro. A precificação é opcional quando o fluxo não exigir preço.')
            return
        render_category_conference_wizard_step()

    def _render_active_step(step: str, section_number: int) -> None:
        if str(step or '').strip().lower() == STEP_CATEGORIZACAO:
            _render_category_step(section_number)
            return
        original_render_active_step(step, section_number)

    def _can_advance_from(step: str) -> bool:
        if str(step or '').strip().lower() == STEP_CATEGORIZACAO:
            return bool(category_wizard_ready())
        return bool(original_can_advance_from(step))

    def _step_is_done(step: str) -> bool:
        if str(step or '').strip().lower() == STEP_CATEGORIZACAO:
            return bool(category_wizard_ready())
        return bool(original_step_is_done(step))

    def _step_after_model_when_source_ready(contract, steps: list[str], active_step: str) -> str:
        if getattr(contract, 'is_api', False):
            return legacy.STEP_DOWNLOAD if legacy.STEP_DOWNLOAD in steps else active_step
        if not legacy.feature_needs_pricing():
            return _category_or_mapping_step(list(steps), active_step)
        return original_step_after_model_when_source_ready(contract, steps, active_step)

    def _resolve_active_step(active_step: str, *, has_model: bool, start_at_origin: bool) -> str:
        steps = list(legacy._flow_plan().steps)
        if str(active_step or '').strip().lower() == STEP_PRECIFICACAO and not legacy.feature_needs_pricing():
            return _category_or_mapping_step(steps, active_step)
        return original_resolve_active_step(active_step, has_model=has_model, start_at_origin=start_at_origin)

    legacy._render_active_step = _render_active_step
    legacy._can_advance_from = _can_advance_from
    legacy._step_is_done = _step_is_done
    legacy._step_after_model_when_source_ready = _step_after_model_when_source_ready
    legacy._resolve_active_step = _resolve_active_step
    setattr(legacy, _PATCHED_KEY, True)


def render_home_wizard() -> None:
    _patch_legacy_wizard()
    st.session_state['home_wizard_v2_active'] = True
    legacy.render_home_wizard()


# Compatibilidade com imports antigos.
CADASTRO_STEPS = legacy.CADASTRO_STEPS
ESTOQUE_STEPS = legacy.ESTOQUE_STEPS
HOME_CHOICE_TARGET = legacy.HOME_CHOICE_TARGET
STEP_DOWNLOAD = legacy.STEP_DOWNLOAD
STEP_GERAR_ESTOQUE = legacy.STEP_GERAR_ESTOQUE
STEP_MAPEAMENTO_LEGACY = legacy.STEP_MAPEAMENTO
STEP_REGRAS_LEGACY = legacy.STEP_REGRAS
wizard_next_target = legacy.wizard_next_target
wizard_previous_target = legacy.wizard_previous_target
wizard_steps_for_operation = legacy.wizard_steps_for_operation

__all__ = [
    'CADASTRO_STEPS',
    'ESTOQUE_STEPS',
    'HOME_CHOICE_TARGET',
    'STEP_CATEGORIZACAO',
    'STEP_DOWNLOAD',
    'STEP_GERAR_ESTOQUE',
    'STEP_MAPEAMENTO_LEGACY',
    'STEP_PRECIFICACAO',
    'STEP_REGRAS_LEGACY',
    'render_home_wizard',
    'wizard_next_target',
    'wizard_previous_target',
    'wizard_steps_for_operation',
]
