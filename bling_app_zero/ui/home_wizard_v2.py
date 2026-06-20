from __future__ import annotations

import streamlit as st

import bling_app_zero.ui.home_wizard as legacy
from bling_app_zero.ui.category_conference_wizard_step import category_wizard_ready, render_category_conference_wizard_step
from bling_app_zero.ui.home_wizard_api_stock_flow_patch import apply_api_stock_flow_patch
from bling_app_zero.ui.rules_center_state import rules_center_ready

RESPONSIBLE_FILE = 'bling_app_zero/ui/home_wizard_v2.py'
STEP_CATEGORIZACAO = 'categorizacao'
STEP_PRECIFICACAO = 'precificacao'
STEP_MAPEAMENTO = 'mapeamento'
STEP_REGRAS = 'regras'
STEP_IA = 'ia'
STEP_PREVIEW = 'preview'
_PATCHED_KEY = 'home_wizard_v2_category_ai_split_patch_applied'


def _register_router_steps() -> None:
    try:
        import bling_app_zero.ui.home_router as home_router

        home_router.VALID_SINGLE_PAGE_STEPS.add('operacao')
        home_router.VALID_SINGLE_PAGE_STEPS.add(STEP_CATEGORIZACAO)
        home_router.VALID_SINGLE_PAGE_STEPS.add(STEP_REGRAS)
        home_router.VALID_SINGLE_PAGE_STEPS.add(STEP_IA)
    except Exception:
        pass


_register_router_steps()


def _insert_category_and_ai_steps() -> None:
    steps = [
        step
        for step in list(getattr(legacy, 'ACTIVE_RENDER_STEPS', []))
        if step not in {STEP_CATEGORIZACAO, STEP_IA}
    ]
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

    try:
        # IA entra somente depois que Regras/Recursos Inteligentes ficarem isolados.
        ai_index = steps.index(STEP_REGRAS) + 1
    except ValueError:
        try:
            ai_index = steps.index(STEP_PREVIEW)
        except ValueError:
            ai_index = len(steps)
    steps.insert(ai_index, STEP_IA)
    legacy.ACTIVE_RENDER_STEPS = steps


def _category_or_mapping_step(steps: list[str], active_step: str) -> str:
    if STEP_CATEGORIZACAO in steps:
        return STEP_CATEGORIZACAO
    if STEP_MAPEAMENTO in steps:
        return STEP_MAPEAMENTO
    return active_step


def _source_dataframe():
    df_source = legacy.st.session_state.get(legacy.UNIVERSAL_ORIGEM_PRICED_KEY)
    if not legacy.looks_like_loaded_df(df_source):
        df_source = legacy.st.session_state.get(legacy.UNIVERSAL_ORIGEM_KEY)
    return df_source


def _target_columns() -> list[str]:
    df_modelo = legacy.st.session_state.get(legacy.UNIVERSAL_MODELO_KEY)
    return [str(column) for column in getattr(df_modelo, 'columns', [])]


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


def _render_rules_resources_step(section_number: int) -> None:
    legacy.render_step_anchor(STEP_REGRAS)
    legacy._section_title(section_number, 'Regras e Recursos Inteligentes')
    if not legacy._model_available():
        legacy.render_pending_notice('Liberado após modelo/dados e mapeamento.')
        return
    if not legacy.universal_mapping_ready():
        legacy.render_pending_notice('Confirme o mapeamento manual primeiro.')
        return

    st.caption('Etapa independente da IA: aplica revisão de campos, correções seguras, proteções finais e recursos determinísticos antes da etapa de Inteligência Artificial.')
    legacy.render_mapping_review_panel(
        operation=legacy.UNIVERSAL_REVIEW_OPERATION,
        mapping=legacy._context_mapping(),
        confidence=legacy._context_confidence(),
        df_source=_source_dataframe(),
        target_columns=_target_columns(),
    )
    legacy.render_final_checker(_source_dataframe(), legacy.st.session_state.get(legacy.UNIVERSAL_MODELO_KEY))
    legacy.render_safe_fixes()
    st.markdown('#### Recursos inteligentes e proteções finais')
    legacy.render_rules_center_step(key_scope='rules_resources')


def _render_ai_step(section_number: int) -> None:
    legacy.render_step_anchor(STEP_IA)
    legacy._section_title(section_number, 'Inteligência Artificial')
    if not legacy._model_available():
        legacy.render_pending_notice('Liberado após modelo/dados e mapeamento.')
        return
    if not legacy.universal_mapping_ready():
        legacy.render_pending_notice('Confirme o mapeamento manual primeiro.')
        return
    if not rules_center_ready():
        legacy.render_pending_notice('Revise e salve as Regras e Recursos Inteligentes antes de usar ou pular a IA.')
        return
    st.caption('Etapa opcional e separada: a IA só aparece depois das regras e recursos inteligentes independentes.')
    legacy.render_ai_real_advanced_panel()


def _patch_legacy_wizard() -> None:
    _register_router_steps()
    required_attrs = (
        '_render_active_step',
        '_can_advance_from',
        '_step_is_done',
        '_step_after_model_when_source_ready',
        '_resolve_active_step',
    )
    missing = [name for name in required_attrs if not hasattr(legacy, name)]
    if missing:
        # O wizard source-first novo não expõe mais estes hooks privados.
        # Nesse caso, não aplicamos o patch antigo de categoria/IA e deixamos
        # o fluxo principal renderizar sem quebrar a inicialização do app.
        st.session_state['home_wizard_v2_legacy_patch_skipped_missing'] = missing
        return

    _insert_category_and_ai_steps()
    if bool(getattr(legacy, _PATCHED_KEY, False)):
        return

    original_render_active_step = legacy._render_active_step
    original_can_advance_from = legacy._can_advance_from
    original_step_is_done = legacy._step_is_done
    original_step_after_model_when_source_ready = legacy._step_after_model_when_source_ready
    original_resolve_active_step = legacy._resolve_active_step

    def _render_active_step(step: str, section_number: int) -> None:
        normalized = str(step or '').strip().lower()
        if normalized == STEP_CATEGORIZACAO:
            _render_category_step(section_number)
            return
        if normalized == STEP_REGRAS:
            _render_rules_resources_step(section_number)
            return
        if normalized == STEP_IA:
            _render_ai_step(section_number)
            return
        original_render_active_step(step, section_number)

    def _can_advance_from(step: str) -> bool:
        normalized = str(step or '').strip().lower()
        if normalized == STEP_CATEGORIZACAO:
            return bool(category_wizard_ready())
        if normalized == STEP_REGRAS:
            return bool(legacy.universal_mapping_ready() and rules_center_ready())
        if normalized == STEP_IA:
            return bool(legacy.universal_mapping_ready() and rules_center_ready())
        return bool(original_can_advance_from(step))

    def _step_is_done(step: str) -> bool:
        normalized = str(step or '').strip().lower()
        if normalized == STEP_CATEGORIZACAO:
            return bool(category_wizard_ready())
        if normalized == STEP_REGRAS:
            return bool(legacy.universal_mapping_ready() and rules_center_ready())
        if normalized == STEP_IA:
            return bool(legacy.universal_mapping_ready() and rules_center_ready())
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
    apply_api_stock_flow_patch(legacy)
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
    'STEP_DOWNLOAD',
    'STEP_GERAR_ESTOQUE',
    'STEP_MAPEAMENTO_LEGACY',
    'STEP_REGRAS_LEGACY',
    'render_home_wizard',
    'wizard_next_target',
    'wizard_previous_target',
    'wizard_steps_for_operation',
]
