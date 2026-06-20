from __future__ import annotations

import streamlit as st

from bling_app_zero.ui.home_wizard_constants import (
    STEP_CATEGORIZACAO,
    STEP_DOWNLOAD,
    STEP_ENTRADA,
    STEP_IA,
    STEP_MAPEAMENTO,
    STEP_OPERACAO,
    STEP_ORIGEM,
    STEP_PRECIFICACAO,
    STEP_PREVIEW,
    STEP_REGRAS,
)

RESPONSIBLE_FILE = 'bling_app_zero/ui/home_wizard_api_stock_flow_patch.py'
_PATCHED_KEY = 'home_wizard_api_stock_flow_patch_applied_v1'

OP_CADASTRO = 'cadastro'
OP_ESTOQUE = 'estoque'
OP_PRECO = 'atualizacao_preco'


def _api_direct_flow() -> bool:
    return bool(
        st.session_state.get('home_bling_connected_same_flow_api_send')
        or st.session_state.get('bling_connected_api_flow_active')
        or st.session_state.get('direct_bling_api_contract_active')
        or str(st.session_state.get('flow_spine_final_destination') or '').strip().lower() == 'api_bling'
    )


def apply_api_stock_flow_patch(legacy) -> None:
    """Corrige o fluxo real do estoque via API sem tocar no fluxo manual.

    Fluxo corrigido:
    Origem -> Entrada -> Operação/Depósito -> Precificação opcional ->
    Regras e Recursos Inteligentes -> Inteligência Artificial -> Prévia -> Enviar.
    """
    if bool(getattr(legacy, _PATCHED_KEY, False)):
        return

    original_steps = legacy._steps
    original_done = legacy._done
    original_render_step = legacy._render_step

    def _steps() -> list[str]:
        steps = [STEP_ORIGEM, STEP_ENTRADA, STEP_OPERACAO]
        op = legacy.selected_operation()
        if op == OP_ESTOQUE and _api_direct_flow():
            steps += [STEP_PRECIFICACAO, STEP_REGRAS, STEP_IA, STEP_PREVIEW, STEP_DOWNLOAD]
        elif op == OP_CADASTRO and _api_direct_flow():
            steps += [STEP_PRECIFICACAO, STEP_CATEGORIZACAO, STEP_REGRAS, STEP_IA, STEP_PREVIEW, STEP_DOWNLOAD]
        else:
            steps = original_steps()
        return steps

    def _done(step: str) -> bool:
        normalized = str(step or '').strip().lower()
        if normalized == STEP_CATEGORIZACAO:
            try:
                from bling_app_zero.ui.category_conference_wizard_step import category_wizard_ready
                return bool(category_wizard_ready())
            except Exception:
                return True
        if normalized == STEP_REGRAS and legacy.selected_operation() in {OP_CADASTRO, OP_ESTOQUE}:
            try:
                from bling_app_zero.ui.rules_center_state import rules_center_ready
                return bool(legacy.universal_mapping_ready() and rules_center_ready())
            except Exception:
                return bool(legacy.universal_mapping_ready())
        if normalized == STEP_IA:
            try:
                from bling_app_zero.ui.rules_center_state import rules_center_ready
                if STEP_REGRAS in _steps() and not rules_center_ready():
                    return False
            except Exception:
                pass
            return bool(legacy.universal_mapping_ready())
        return bool(original_done(step))

    def _render_progress_only(step: str) -> None:
        steps = _steps()
        idx = steps.index(step)
        st.caption(f'Etapa {idx + 1} de {len(steps)} · {legacy._label(step)}')
        st.progress(max(1, min(100, int(((idx + 1) / len(steps)) * 100))))

    def _render_footer_nav(step: str) -> None:
        steps = _steps()
        idx = steps.index(step)
        prev_step = steps[idx - 1] if idx > 0 else ''
        next_step = steps[idx + 1] if idx + 1 < len(steps) else ''
        st.markdown('---')
        st.caption('Navegação do fluxo')
        col1, col2 = st.columns(2)
        with col1:
            if prev_step and st.button('⬅️ Voltar', use_container_width=True, key=f'wizard_footer_back_{step}'):
                legacy._go(prev_step)
                legacy.safe_rerun('wizard_back_clicked', target_step=prev_step)
        with col2:
            if next_step:
                if _done(step):
                    if st.button(f'Próximo: {legacy._label(next_step)}', use_container_width=True, key=f'wizard_footer_next_{step}'):
                        legacy._go(next_step)
                        legacy.safe_rerun('wizard_next_clicked', target_step=next_step)
                else:
                    st.caption(f'🔒 Próximo bloqueado: {legacy._label(next_step)}')

    def _render_category(n: int) -> None:
        legacy.render_step_anchor(STEP_CATEGORIZACAO)
        legacy._section_title(n, legacy._label(STEP_CATEGORIZACAO))
        if not legacy.operation_ready():
            legacy.render_pending_notice('Escolha a operação e confirme os obrigatórios primeiro.')
            return
        if not legacy.universal_context_ready():
            legacy.render_pending_notice('Carregue a origem dos dados antes de categorizar.')
            return
        from bling_app_zero.ui.category_conference_wizard_step import render_category_conference_wizard_step
        render_category_conference_wizard_step()

    def _render_rules(n: int) -> None:
        op = legacy.selected_operation()
        if op == OP_ESTOQUE and _api_direct_flow():
            legacy.render_step_anchor(STEP_REGRAS)
            legacy._section_title(n, legacy._label(STEP_REGRAS))
            if not legacy.universal_mapping_ready():
                legacy.render_pending_notice('Preparando a base automática da API antes de aplicar regras e recursos inteligentes.')
                return
            from bling_app_zero.ui.rules_center_step import render_rules_center_step
            render_rules_center_step(key_scope='rules_resources_api_stock')
            return
        original_render_step(STEP_REGRAS, n)

    def _render_ai(n: int) -> None:
        legacy.render_step_anchor(STEP_IA)
        legacy._section_title(n, legacy._label(STEP_IA))
        if not legacy.universal_mapping_ready():
            legacy.render_pending_notice('Preparando a base automática da API antes da Inteligência Artificial.')
            return
        try:
            from bling_app_zero.ui.rules_center_state import rules_center_ready
            if STEP_REGRAS in _steps() and not rules_center_ready():
                legacy.render_pending_notice('Revise e salve as Regras e Recursos Inteligentes antes de usar ou pular a IA.')
                return
        except Exception:
            pass
        from bling_app_zero.ui.ai_real_advanced_panel import render_ai_real_advanced_panel
        render_ai_real_advanced_panel()

    def _render_step(step: str, n: int) -> None:
        normalized = str(step or '').strip().lower()
        if normalized == STEP_CATEGORIZACAO:
            _render_category(n)
        elif normalized == STEP_REGRAS and legacy.selected_operation() == OP_ESTOQUE and _api_direct_flow():
            _render_rules(n)
        elif normalized == STEP_IA:
            _render_ai(n)
        else:
            original_render_step(step, n)
        _render_footer_nav(normalized)

    legacy._steps = _steps
    legacy._done = _done
    legacy._nav = _render_progress_only
    legacy._render_step = _render_step
    setattr(legacy, _PATCHED_KEY, True)
