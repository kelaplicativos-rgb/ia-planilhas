from __future__ import annotations

import importlib

import pandas as pd
import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.ui.home_wizard_rerun import safe_rerun

RESPONSIBLE_FILE = 'bling_app_zero/ui/ai_real_advanced_panel.py'
FINAL_UNIVERSAL_LEGACY_KEY = 'df_final_cadastro'
FINAL_UNIVERSAL_KEY = 'df_final_universal'
FINAL_CHECK_REPORT_KEY = 'home_wizard_final_check_report'
ADVANCED_APPLIED_KEY = 'home_wizard_ai_real_advanced_applied'
IMAGE_LIMIT_DECISION_KEY = 'ai_real_bling_image_limit_decision'
IMAGE_LIMIT_GUARD_KEY = 'bling_image_limit_guard_enabled'


def _looks_like_df(value: object) -> bool:
    if value is None or not hasattr(value, 'columns'):
        return False
    try:
        return len(getattr(value, 'columns', [])) > 0
    except Exception:
        return False


def _get_df_final_universal() -> pd.DataFrame | None:
    value = st.session_state.get(FINAL_UNIVERSAL_KEY)
    if _looks_like_df(value):
        return value
    value = st.session_state.get(FINAL_UNIVERSAL_LEGACY_KEY)
    return value if _looks_like_df(value) else None


def _current_or_base_df(base: pd.DataFrame) -> pd.DataFrame:
    current = _get_df_final_universal()
    return current if _looks_like_df(current) else base


def _save_df_final_universal(df: pd.DataFrame) -> None:
    safe = df.copy().fillna('')
    st.session_state[FINAL_UNIVERSAL_LEGACY_KEY] = safe
    st.session_state[FINAL_UNIVERSAL_KEY] = safe
    st.session_state.pop('df_final_cadastro_preview_rules_applied', None)
    st.session_state.pop(FINAL_CHECK_REPORT_KEY, None)


def _enrichment_module():
    return importlib.import_module('bling_app_zero.ai.ai_real_enrichment')


def _ncm_module():
    return importlib.import_module('bling_app_zero.ai.ai_real_ncm')


def _report_module():
    return importlib.import_module('bling_app_zero.ai.ai_real_report')


def _image_rules_module():
    return importlib.import_module('bling_app_zero.ai.ai_real_image_rules')


def _render_bling_image_rules(df_final: pd.DataFrame) -> None:
    module = _image_rules_module()
    report = module.analyze_bling_image_limit(df_final)

    st.markdown('#### Regras Bling revisáveis')
    st.caption('Regras que podem alterar o arquivo final aparecem aqui para o usuário decidir antes de exportar ou enviar pela API.')

    if not report.image_columns:
        st.info('Nenhuma coluna de imagens foi identificada no arquivo final.')
        return

    col_products, col_removed = st.columns(2)
    col_products.metric('Produtos com ajuste de imagens', report.products_with_excess)
    col_removed.metric('Imagens excedentes/duplicadas', report.images_removed)

    if not report.has_issues:
        st.success('As imagens já estão dentro do padrão Bling: máximo de 6 por produto e sem excesso detectado.')
        st.session_state.setdefault(IMAGE_LIMIT_DECISION_KEY, 'sem_pendencia')
        st.session_state[IMAGE_LIMIT_GUARD_KEY] = True
        return

    st.warning('Existem produtos com mais imagens do que o Bling permite. O Bling pode recusar o cadastro/exportação se essa regra não for aplicada.')

    with st.expander('Ver produtos que serão ajustados', expanded=False):
        st.dataframe(report.as_dataframe(), use_container_width=True, hide_index=True, height=280)

    choice = st.radio(
        'Aplicar regra de imagens do Bling?',
        options=('Aplicar agora', 'Não aplicar nesta etapa'),
        index=0,
        horizontal=True,
        key='ai_real_bling_image_limit_choice',
    )

    if choice == 'Aplicar agora':
        st.caption('Mantém as 6 primeiras imagens válidas de cada produto, remove duplicadas e ignora o restante.')
        if st.button('Aplicar regra: limitar imagens para Bling', use_container_width=True, key='ai_real_bling_image_limit_apply'):
            fixed_df, _ = module.apply_bling_image_limit(df_final)
            if _looks_like_df(fixed_df):
                _save_df_final_universal(fixed_df)
                st.session_state[IMAGE_LIMIT_DECISION_KEY] = 'aplicada'
                st.session_state[IMAGE_LIMIT_GUARD_KEY] = True
                add_audit_event(
                    'ai_real_bling_image_limit_applied',
                    area='AI_REAL',
                    step='revisao_final',
                    status='OK',
                    details={
                        'products_with_excess': report.products_with_excess,
                        'images_removed': report.images_removed,
                        'image_columns': report.image_columns,
                        'max_images': getattr(module, 'MAX_BLING_IMAGES', 6),
                        'responsible_file': RESPONSIBLE_FILE,
                    },
                )
                st.success('Regra aplicada. Confira o preview antes de exportar ou enviar ao Bling.')
                safe_rerun('ai_real_bling_image_limit_applied')
    else:
        st.caption('O sistema não altera as imagens nesta etapa. Use apenas se você for corrigir a origem ou aceitar o risco de rejeição pelo Bling.')
        if st.button('Confirmar: não aplicar regra de imagens agora', use_container_width=True, key='ai_real_bling_image_limit_skip'):
            st.session_state[IMAGE_LIMIT_DECISION_KEY] = 'nao_aplicar'
            st.session_state[IMAGE_LIMIT_GUARD_KEY] = False
            add_audit_event(
                'ai_real_bling_image_limit_skipped_by_user',
                area='AI_REAL',
                step='revisao_final',
                status='AVISO',
                details={
                    'products_with_excess': report.products_with_excess,
                    'images_removed': report.images_removed,
                    'image_columns': report.image_columns,
                    'reason': 'Usuário decidiu não aplicar a regra de máximo 6 imagens nesta etapa.',
                    'responsible_file': RESPONSIBLE_FILE,
                },
            )
            st.warning('Regra não aplicada. Se o arquivo continuar com mais de 6 imagens por produto, o Bling poderá recusar o cadastro.')


def _render_enrichment(df_final: pd.DataFrame) -> None:
    module = _enrichment_module()
    suggestions = module.build_enrichment_suggestions(df_final)
    st.markdown('#### Enriquecimento de produtos')
    st.caption('Melhora títulos e descrições usando apenas os dados já presentes no arquivo final. Nada é aplicado sozinho.')

    if not suggestions:
        st.success('Nenhum enriquecimento textual pendente encontrado.')
        return

    options = [item.id for item in suggestions]
    labels = {item.id: f'{item.title} · {item.rows} linha(s) · {item.column}' for item in suggestions}
    selected = st.multiselect(
        'Escolha os enriquecimentos para aplicar',
        options=options,
        default=options,
        format_func=lambda value: labels.get(value, value),
        key='ai_real_enrichment_selected',
    )

    with st.expander('Ver sugestões de enriquecimento', expanded=False):
        for item in suggestions:
            st.write(f'• **{item.title}** — {item.description} ({item.rows} linha(s))')

    if not selected:
        st.caption('Selecione pelo menos uma opção para aplicar.')
        return
    if st.button('Aplicar enriquecimentos selecionados', use_container_width=True, key='ai_real_enrichment_apply'):
        fixed_df, applied = module.apply_enrichment(df_final, selected)
        if _looks_like_df(fixed_df):
            _save_df_final_universal(fixed_df)
            st.session_state[ADVANCED_APPLIED_KEY] = [getattr(item, 'id', '') for item in applied]
            add_audit_event(
                'ai_real_enrichment_applied',
                area='AI_REAL',
                step='revisao_final',
                status='OK',
                details={'applied_count': len(applied), 'responsible_file': RESPONSIBLE_FILE},
            )
            st.success(f'{len(applied)} enriquecimento(s) aplicado(s). Confira o preview antes de baixar.')
            safe_rerun('ai_real_enrichment_applied')


def _render_ncm_review(df_final: pd.DataFrame) -> None:
    module = _ncm_module()
    suggestions = module.build_ncm_suggestions(df_final)
    st.markdown('#### NCM com revisão')
    st.caption('Sugere NCM provável para campos vazios. Revise antes de aplicar. Não use como confirmação fiscal definitiva.')

    if not suggestions:
        st.success('Nenhum NCM pendente com sugestão automática encontrado.')
        return

    reviewed: dict[int, str] = {}
    with st.expander('Revisar sugestões de NCM', expanded=True):
        for item in suggestions[:80]:
            st.caption(f'Produto: {item.product_name}')
            col_ncm, col_reason = st.columns([1, 3])
            with col_ncm:
                value = st.text_input(
                    'NCM sugerido',
                    value=item.suggested_ncm,
                    key=f'ai_real_ncm_{item.row_index}_{item.suggested_ncm}',
                )
            with col_reason:
                st.write(f'Confiança: {item.confidence}')
                st.write(f'Motivo: {item.reason}')
            reviewed[item.row_index] = value

    if st.button('Aplicar NCMs revisados', use_container_width=True, key='ai_real_ncm_apply'):
        fixed_df = module.apply_reviewed_ncms(df_final, reviewed)
        if _looks_like_df(fixed_df):
            _save_df_final_universal(fixed_df)
            add_audit_event(
                'ai_real_ncm_reviewed_applied',
                area='AI_REAL',
                step='revisao_final',
                status='OK',
                details={'suggestions_count': len(suggestions), 'responsible_file': RESPONSIBLE_FILE},
            )
            st.success('NCMs revisados aplicados. Confira o preview antes de baixar.')
            safe_rerun('ai_real_ncm_reviewed_applied')


def _render_final_report(df_final: pd.DataFrame) -> None:
    module = _report_module()
    report = module.build_final_report(df_final)
    st.markdown('#### Relatório final / BLINGSCAN')
    st.caption('Mostra o que foi preenchido, o que ficou vazio, o motivo provável e onde corrigir.')
    st.info(report.summary)

    rows = []
    for item in report.field_reports:
        rows.append(
            {
                'Campo': item.column,
                'Preenchidos': item.filled,
                'Vazios': item.empty,
                'Status': item.status,
                'Por que ficou vazio': item.reason,
                'Onde corrigir': item.fix_step,
            }
        )
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True, height=360)


def render_ai_real_advanced_panel() -> None:
    df_final = _get_df_final_universal()
    if not _looks_like_df(df_final):
        st.warning('Recursos avançados aguardando o arquivo final universal.')
        return

    st.markdown('### IA Real avançada')
    st.caption('Recursos de enriquecimento, revisão, regras revisáveis e relatório. Todos respeitam o modelo anexado como contrato final.')

    _render_bling_image_rules(df_final)
    df_after_image_rules = _current_or_base_df(df_final)
    _render_enrichment(df_after_image_rules)
    df_after_enrichment = _current_or_base_df(df_after_image_rules)
    _render_ncm_review(df_after_enrichment)
    df_after_ncm = _current_or_base_df(df_after_enrichment)
    _render_final_report(df_after_ncm)


__all__ = ['render_ai_real_advanced_panel']
