from __future__ import annotations

import streamlit as st

import bling_app_zero.ui.home_wizard as legacy
from bling_app_zero.ui.category_conference_wizard_step import category_wizard_ready, render_category_conference_wizard_step

RESPONSIBLE_FILE = 'bling_app_zero/ui/home_wizard_v2.py'
STEP_CATEGORIZACAO = 'categorizacao'
STEP_MAPEAMENTO = 'mapeamento'
STEP_REGRAS = 'regras'
_PATCHED_KEY = 'home_wizard_v2_category_patch_applied'


def _insert_category_step() -> None:
    steps = list(getattr(legacy, 'ACTIVE_RENDER_STEPS', []))
    if STEP_CATEGORIZACAO in steps:
        return
    try:
        index = steps.index(STEP_MAPEAMENTO) + 1
    except ValueError:
        index = len(steps)
    steps.insert(index, STEP_CATEGORIZACAO)
    legacy.ACTIVE_RENDER_STEPS = steps


def _patch_legacy_wizard() -> None:
    _insert_category_step()
    if bool(getattr(legacy, _PATCHED_KEY, False)):
        return

    original_render_active_step = legacy._render_active_step
    original_can_advance_from = legacy._can_advance_from
    original_step_is_done = legacy._step_is_done

    def _render_category_step(section_number: int) -> None:
        legacy.render_step_anchor(STEP_CATEGORIZACAO)
        legacy._section_title(section_number, 'Conferência e Correção de Categorias')
        if not legacy._model_available():
            legacy.render_pending_notice('Liberado após modelo/dados e mapeamento.')
            return
        if not legacy.universal_mapping_ready():
            legacy.render_pending_notice('Confirme o mapeamento manual primeiro.')
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

    legacy._render_active_step = _render_active_step
    legacy._can_advance_from = _can_advance_from
    legacy._step_is_done = _step_is_done
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
    'STEP_REGRAS_LEGACY',
    'render_home_wizard',
    'wizard_next_target',
    'wizard_previous_target',
    'wizard_steps_for_operation',
]
