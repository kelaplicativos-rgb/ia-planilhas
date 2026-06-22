from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.ui.home_wizard_constants import (
    STEP_DOWNLOAD,
    STEP_ENTRADA,
    STEP_IA,
    STEP_MAPEAMENTO,
    STEP_OPERACAO,
    STEP_ORIGEM,
    STEP_PREVIEW,
    STEP_REGRAS,
)

PATCHED_KEY = 'home_wizard_api_stock_flow_patch_applied_v3'
OP_ESTOQUE = 'estoque'


def _api_direct_flow() -> bool:
    return bool(
        st.session_state.get('home_bling_connected_same_flow_api_send')
        or st.session_state.get('bling_connected_api_flow_active')
        or st.session_state.get('direct_bling_api_contract_active')
        or str(st.session_state.get('flow_spine_final_destination') or '').strip().lower() == 'api_bling'
    )


def _valid_df(value: object) -> bool:
    return isinstance(value, pd.DataFrame) and not value.empty and len(value.columns) > 0


def _first_source_df(legacy) -> pd.DataFrame | None:
    keys = (
        'cadastro_wizard_df_para_mapear',
        'cadastro_wizard_df_origem',
        'df_origem_planilha',
        'df_origem_site_como_planilha',
        'df_origem_site_como_planilha_estoque',
        'df_site_bruto',
        'df_site_bruto_estoque',
        'estoque_wizard_df_origem_site',
    )
    for key in keys:
        value = st.session_state.get(key)
        if _valid_df(value):
            return value.copy().fillna('')
    for attr in ('UNIVERSAL_ORIGEM_PRICED_KEY', 'UNIVERSAL_ORIGEM_KEY'):
        key = getattr(legacy, attr, '')
        value = st.session_state.get(key)
        if _valid_df(value):
            return value.copy().fillna('')
    return None


def _signature(df: pd.DataFrame) -> str:
    try:
        from bling_app_zero.ui.home_shared import df_signature
        return df_signature(df)
    except Exception:
        return f'api_stock_auto_{len(df)}_{len(df.columns)}'


def _ensure_api_base(legacy) -> bool:
    df = _first_source_df(legacy)
    if not _valid_df(df):
        return False
    mapping = {str(column): str(column) for column in df.columns}
    confidence = {str(column): 1.0 for column in df.columns}
    signature = _signature(df)
    for key in ('df_final_bling_api', 'df_final_universal', 'df_final_cadastro'):
        st.session_state[key] = df.copy()
    st.session_state['mapping_bling_api'] = mapping
    st.session_state['mapping_confidence_bling_api'] = confidence
    st.session_state['cadastro_mapping_confirmed'] = True
    st.session_state['cadastro_mapping_confirmed_signature'] = signature
    st.session_state['api_stock_auto_base_ready'] = True
    return True


def _insert_after(steps: list[str], anchor: str, value: str) -> list[str]:
    if value in steps:
        return steps
    if anchor in steps:
        steps.insert(steps.index(anchor) + 1, value)
    else:
        steps.append(value)
    return steps


def _stock_api_steps_from_base(base_steps: list[str]) -> list[str]:
    """Preserva o contrato atual do wizard e só acrescenta Regras/IA.

    A Home agora define o núcleo Bling como: Conectar -> Origem -> Dados ->
    Operação -> recursos -> Preview -> Enviar Bling. Este patch não pode mais
    mover Operação para o início, senão quebra o objetivo final do MapeiaAI.
    """
    steps = [str(step).strip().lower() for step in list(base_steps or []) if str(step or '').strip()]
    if not steps:
        steps = [STEP_ORIGEM, STEP_ENTRADA, STEP_OPERACAO]

    # Mantém a ordem recebida do wizard principal. Se Operação não existir por
    # algum estado antigo, insere depois de Dados importados.
    if STEP_OPERACAO not in steps:
        if STEP_ENTRADA in steps:
            steps.insert(steps.index(STEP_ENTRADA) + 1, STEP_OPERACAO)
        else:
            steps.append(STEP_OPERACAO)

    regras_anchor = STEP_MAPEAMENTO if STEP_MAPEAMENTO in steps else STEP_ENTRADA
    steps = _insert_after(steps, regras_anchor, STEP_REGRAS)
    steps = _insert_after(steps, STEP_REGRAS, STEP_IA)

    # Garante que Prévia/Envio continuem depois de Regras e IA.
    for terminal in (STEP_PREVIEW, STEP_DOWNLOAD):
        if terminal in steps:
            steps.remove(terminal)
            steps.append(terminal)
    return steps


def _rules_ready() -> bool:
    try:
        from bling_app_zero.ui.rules_center_state import rules_center_ready
        return bool(rules_center_ready())
    except Exception:
        return True


def apply_api_stock_flow_patch_v2(legacy) -> None:
    if bool(getattr(legacy, PATCHED_KEY, False)):
        return

    original_steps = legacy._steps
    original_done = legacy._done
    original_nav = legacy._nav
    original_render_step = legacy._render_step

    def _is_api_stock() -> bool:
        return legacy.selected_operation() == OP_ESTOQUE and _api_direct_flow()

    def _steps() -> list[str]:
        if _is_api_stock():
            return _stock_api_steps_from_base(original_steps())
        return original_steps()

    def _done(step: str) -> bool:
        step = str(step or '').strip().lower()
        if _is_api_stock() and step == STEP_REGRAS:
            return bool(_ensure_api_base(legacy) and _rules_ready())
        if _is_api_stock() and step == STEP_IA:
            return bool(_ensure_api_base(legacy) and _rules_ready())
        return bool(original_done(step))

    def _progress_only(step: str) -> None:
        if not _is_api_stock():
            original_nav(step)
            return
        steps = _steps()
        if step not in steps:
            return
        index = steps.index(step)
        st.caption(f'Etapa {index + 1} de {len(steps)} · {legacy._label(step)}')
        st.progress(max(1, min(100, int(((index + 1) / len(steps)) * 100))))

    def _footer_nav(step: str) -> None:
        steps = _steps()
        if step not in steps:
            return
        index = steps.index(step)
        prev_step = steps[index - 1] if index > 0 else ''
        next_step = steps[index + 1] if index + 1 < len(steps) else ''
        st.markdown('---')
        st.caption('Navegação do fluxo')
        left, right = st.columns(2)
        with left:
            if prev_step and st.button('⬅️ Voltar', use_container_width=True, key=f'wizard_footer_back_{step}'):
                legacy._go(prev_step)
                legacy.safe_rerun('wizard_back_clicked', target_step=prev_step)
        with right:
            if next_step:
                if _done(step):
                    if st.button(f'Próximo: {legacy._label(next_step)}', use_container_width=True, key=f'wizard_footer_next_{step}'):
                        legacy._go(next_step)
                        legacy.safe_rerun('wizard_next_clicked', target_step=next_step)
                else:
                    st.caption(f'🔒 Próximo bloqueado: {legacy._label(next_step)}')

    def _render_rules(n: int) -> None:
        legacy.render_step_anchor(STEP_REGRAS)
        legacy._section_title(n, legacy._label(STEP_REGRAS))
        if not _ensure_api_base(legacy):
            legacy.render_pending_notice('Carregue a origem dos dados para preparar a base automática da API antes das regras.')
            return
        st.caption('Base automática da API preparada. Configure as regras e recursos inteligentes antes da IA.')
        from bling_app_zero.ui.rules_center_step import render_rules_center_step
        render_rules_center_step(key_scope='rules_resources_api_stock')

    def _render_ai(n: int) -> None:
        legacy.render_step_anchor(STEP_IA)
        legacy._section_title(n, legacy._label(STEP_IA))
        if not _ensure_api_base(legacy):
            legacy.render_pending_notice('Carregue a origem dos dados antes da Inteligência Artificial.')
            return
        if not _rules_ready():
            legacy.render_pending_notice('Revise e salve as Regras e Recursos Inteligentes antes de usar ou pular a IA.')
            return
        from bling_app_zero.ui.ai_real_advanced_panel import render_ai_real_advanced_panel
        render_ai_real_advanced_panel()

    def _render_step(step: str, n: int) -> None:
        normalized = str(step or '').strip().lower()
        if not _is_api_stock():
            original_render_step(step, n)
            return
        if normalized == STEP_REGRAS:
            _render_rules(n)
        elif normalized == STEP_IA:
            _render_ai(n)
        else:
            original_render_step(step, n)
        _footer_nav(normalized)

    legacy._steps = _steps
    legacy._done = _done
    legacy._nav = _progress_only
    legacy._render_step = _render_step
    setattr(legacy, PATCHED_KEY, True)
