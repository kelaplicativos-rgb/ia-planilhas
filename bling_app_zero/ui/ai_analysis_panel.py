from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.ai.ai_config import ai_is_enabled, get_ai_settings
from bling_app_zero.ai.ai_orchestrator import analyze_mapping, analyze_origin
from bling_app_zero.core.audit import add_audit_event

RESPONSIBLE_FILE = 'bling_app_zero/ui/ai_analysis_panel.py'


def _render_quality(quality: dict) -> None:
    score = int(quality.get('score') or 0)
    issues = quality.get('issues') or []
    if score >= 85:
        st.success(f'Nota da origem: {score}/100')
    elif score >= 65:
        st.warning(f'Nota da origem: {score}/100')
    else:
        st.error(f'Nota da origem: {score}/100')

    if issues:
        st.caption('Pontos de atenção encontrados:')
        for issue in issues[:6]:
            st.warning(str(issue))
    else:
        st.caption('Nenhum alerta crítico encontrado na análise local.')


def _render_mapping_suggestions(suggestions: list[dict]) -> None:
    if not suggestions:
        st.caption('Sem sugestões de mapeamento ainda.')
        return

    rows = []
    for item in suggestions:
        confidence = float(item.get('confidence') or 0)
        if confidence < 0.45:
            continue
        rows.append(
            {
                'Campo do modelo': item.get('target_column', ''),
                'Origem sugerida': item.get('source_column', '') or '(revisar)',
                'Confiança': f'{round(confidence * 100)}%',
                'Motivo': item.get('reason', ''),
            }
        )
    if not rows:
        st.caption('Nenhuma sugestão com confiança mínima.')
        return
    st.dataframe(pd.DataFrame(rows).astype(str), use_container_width=True, height=260)


def _render_content_issues(coherence: dict) -> None:
    issues = coherence.get('issues') or []
    if not issues:
        return
    st.caption('Coerência entre cabeçalho e conteúdo:')
    for issue in issues[:5]:
        if isinstance(issue, dict):
            st.warning(issue.get('message') or 'Possível incoerência encontrada.')


def render_ai_origin_analysis_panel(
    source_df: pd.DataFrame | None,
    target_df: pd.DataFrame | None = None,
    *,
    operation: str = '',
) -> None:
    """Mostra análise segura da origem.

    Este painel não altera a planilha, não aplica mapeamento e não chama OpenAI
    automaticamente. Ele usa módulos locais e só aparece quando a IA está ativada
    no sidebar com chave do usuário.
    """
    if not isinstance(source_df, pd.DataFrame) or source_df.empty:
        return

    settings = get_ai_settings()
    if not ai_is_enabled():
        with st.expander('🤖 IA do Mapeia.AI', expanded=False):
            st.caption('IA desativada. Ative no sidebar e informe sua chave OpenAI para liberar análises inteligentes.')
        return

    with st.expander('🤖 Análise inteligente da origem', expanded=False):
        st.caption(f'Modo: {settings.mode} · Operação: {operation or "planilha"}. Nenhuma alteração automática será aplicada.')
        origin_result = analyze_origin(source_df)
        quality = origin_result.data.get('quality', {}) if isinstance(origin_result.data, dict) else {}
        coherence = origin_result.data.get('coherence', {}) if isinstance(origin_result.data, dict) else {}
        _render_quality(quality)
        _render_content_issues(coherence)

        if isinstance(target_df, pd.DataFrame) and len(target_df.columns):
            st.markdown('##### Sugestões de mapeamento')
            mapping_result = analyze_mapping(source_df, target_df)
            mapping_data = mapping_result.data.get('mapping', {}) if isinstance(mapping_result.data, dict) else {}
            suggestions = mapping_data.get('suggestions', []) if isinstance(mapping_data, dict) else []
            _render_mapping_suggestions(suggestions)

        add_audit_event(
            'ai_origin_analysis_rendered',
            area='AI',
            details={
                'operation': operation,
                'rows': int(len(source_df)),
                'columns': int(len(source_df.columns)),
                'ready': settings.ready,
                'responsible_file': RESPONSIBLE_FILE,
            },
        )


__all__ = ['render_ai_origin_analysis_panel']
