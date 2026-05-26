from __future__ import annotations

import importlib

import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.ui.home_wizard_constants import STEP_REGRAS
from bling_app_zero.ui.home_wizard_state import (
    FINAL_CHECK_REPORT_KEY,
    SAFE_FIX_SUGGESTIONS_KEY,
    get_df_final_universal,
    looks_like_loaded_df,
    set_df_final_universal,
)

RESPONSIBLE_FILE = 'bling_app_zero/ui/home_wizard_review.py'


def run_final_checker(df_source: object, df_modelo: object, df_final: object) -> object:
    module = importlib.import_module('bling_app_zero.ai.ai_real_engine')
    checker = getattr(module, 'run_ai_real_final_check')
    return checker(
        df_source=df_source if looks_like_loaded_df(df_source) else None,
        df_modelo=df_modelo if looks_like_loaded_df(df_modelo) else None,
        df_final=df_final if looks_like_loaded_df(df_final) else None,
    )


def safe_fixes_module():
    return importlib.import_module('bling_app_zero.ai.ai_real_safe_fixes')


def render_checker_item(item: object) -> None:
    level = str(getattr(item, 'level', '') or '')
    title = str(getattr(item, 'title', '') or '')
    message = str(getattr(item, 'message', '') or '')
    column = str(getattr(item, 'column', '') or '')
    prefix = '⛔' if level == 'erro' else '⚠️' if level == 'aviso' else '✅'
    text = f'{prefix} **{title}** — {message}'
    if column:
        text += f'  \nCampo: `{column}`'
    if level == 'erro':
        st.error(text)
    elif level == 'aviso':
        st.warning(text)
    else:
        st.success(text)


def render_final_checker(df_source: object, df_modelo: object) -> None:
    df_final_universal = get_df_final_universal()
    if not looks_like_loaded_df(df_final_universal):
        st.warning('Conferência aguardando o arquivo final gerado pelo mapeamento.')
        return

    st.markdown('#### Conferência inteligente')
    st.caption('Verifica modelo, campos vazios, descrições, imagens e GTIN antes do preview/download. Não altera seus dados automaticamente.')

    if st.button('Verificar planilha agora', use_container_width=True, key='home_wizard_final_checker_run'):
        with st.spinner('Conferindo planilha final...'):
            report = run_final_checker(df_source, df_modelo, df_final_universal)
        st.session_state[FINAL_CHECK_REPORT_KEY] = report
        add_audit_event(
            'home_wizard_final_checker_finished',
            area='FINAL_CHECK',
            step=STEP_REGRAS,
            status='OK' if bool(getattr(report, 'ok', False)) else 'AVISO',
            details={
                'summary': str(getattr(report, 'summary', '') or ''),
                'findings_count': len(getattr(report, 'findings', []) or []),
                'responsible_file': RESPONSIBLE_FILE,
            },
        )

    report = st.session_state.get(FINAL_CHECK_REPORT_KEY)
    if report is None:
        st.caption('Clique em verificar para receber um diagnóstico antes do preview.')
        return

    summary = str(getattr(report, 'summary', '') or '')
    if bool(getattr(report, 'ok', False)):
        st.success(f'Conferência concluída: {summary}')
    else:
        st.warning(f'Conferência concluída: {summary}')

    ai_message = str(getattr(report, 'ai_message', '') or '')
    if ai_message:
        st.info(ai_message)

    actions = getattr(report, 'actions', []) or []
    if actions:
        st.markdown('##### Próximos passos')
        for action in list(actions)[:6]:
            st.write(f'• {action}')

    findings = getattr(report, 'findings', []) or []
    with st.expander('Detalhes encontrados pela conferência', expanded=not bool(getattr(report, 'ok', False))):
        if not findings:
            st.success('Nenhum problema encontrado.')
        for item in list(findings)[:30]:
            render_checker_item(item)


def render_safe_fixes() -> None:
    df_final_universal = get_df_final_universal()
    if not looks_like_loaded_df(df_final_universal):
        return

    fixes = safe_fixes_module()
    suggestions = fixes.build_safe_fix_suggestions(df_final_universal)
    st.markdown('#### Correções seguras')
    st.caption('Sugere ajustes automáticos de baixo risco. Nada é aplicado sem você clicar.')

    if not suggestions:
        st.success('Nenhuma correção segura pendente encontrada.')
        return

    options = [item.id for item in suggestions]
    labels = {item.id: f'{item.title} · {item.rows} linha(s) · {item.column}' for item in suggestions}
    selected = st.multiselect(
        'Escolha as correções para aplicar',
        options=options,
        default=options,
        format_func=lambda value: labels.get(value, value),
        key='home_wizard_safe_fix_selected',
    )

    with st.expander('Ver detalhes das correções sugeridas', expanded=True):
        for item in suggestions:
            st.write(f'• **{item.title}** — {item.description} ({item.rows} linha(s))')

    if not selected:
        st.caption('Selecione pelo menos uma correção para liberar o botão de aplicar.')
        return
    if st.button('Aplicar correções seguras', use_container_width=True, key='home_wizard_safe_fix_apply'):
        fixed_df, applied = fixes.apply_safe_fixes(df_final_universal, selected)
        if looks_like_loaded_df(fixed_df):
            set_df_final_universal(fixed_df)
            st.session_state[SAFE_FIX_SUGGESTIONS_KEY] = [getattr(item, 'id', '') for item in applied]
            add_audit_event(
                'home_wizard_safe_fixes_applied',
                area='FINAL_CHECK',
                step=STEP_REGRAS,
                status='OK',
                details={
                    'applied_count': len(applied),
                    'applied_ids': [getattr(item, 'id', '') for item in applied],
                    'responsible_file': RESPONSIBLE_FILE,
                },
            )
            st.success(f'{len(applied)} correção(ões) segura(s) aplicada(s). Confira o preview antes de baixar.')
            st.rerun()
        else:
            st.warning('Nenhuma alteração foi aplicada.')


__all__ = ['render_final_checker', 'render_safe_fixes']
