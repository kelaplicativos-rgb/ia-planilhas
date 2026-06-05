from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.bling_mirror_planner import (
    MODE_BOTH,
    MODE_NEW_PRODUCTS,
    MODE_STOCK,
    MirrorPlanConfig,
    build_mirror_plan,
    decisions_dataframe,
    report_summary,
)

RESPONSIBLE_FILE = 'bling_app_zero/ui/mirror_planner_panel.py'


def _csv_bytes(df: pd.DataFrame) -> bytes:
    try:
        return df.fillna('').to_csv(index=False, sep=';', encoding='utf-8-sig').encode('utf-8-sig')
    except Exception:
        return b''


def _default_mode(operation: str, stock_balance_only: bool) -> str:
    if stock_balance_only or str(operation or '').strip().lower() == 'estoque':
        return MODE_STOCK
    if str(operation or '').strip().lower() == 'cadastro':
        return MODE_NEW_PRODUCTS
    return MODE_BOTH


def _mode_label(mode: str) -> str:
    labels = {
        MODE_STOCK: 'Somente estoque',
        MODE_NEW_PRODUCTS: 'Somente produtos novos',
        MODE_BOTH: 'Estoque + produtos novos',
    }
    return labels.get(mode, 'Estoque + produtos novos')


def render_mirror_planner_panel(df_site: pd.DataFrame, *, operation: str = '', stock_balance_only: bool = False) -> None:
    if not isinstance(df_site, pd.DataFrame) or df_site.empty:
        return

    st.markdown('### Espelhamento inteligente')
    st.caption('Simulação segura: o sistema separa o que poderia atualizar estoque, o que parece produto novo e o que virou pendência. Nada é aplicado automaticamente.')

    default_mode = _default_mode(operation, stock_balance_only)
    mode_options = [MODE_STOCK, MODE_NEW_PRODUCTS, MODE_BOTH]
    selected_mode = st.radio(
        'Tipo de simulação',
        options=mode_options,
        index=mode_options.index(default_mode) if default_mode in mode_options else 0,
        format_func=_mode_label,
        horizontal=True,
        key=f'mirror_planner_mode_{operation}_{stock_balance_only}',
    )

    col_a, col_b = st.columns(2)
    with col_a:
        interval_minutes = st.number_input('Intervalo futuro entre ciclos', min_value=5, max_value=240, value=15, step=5, key=f'mirror_interval_{operation}_{stock_balance_only}')
    with col_b:
        max_rows = st.number_input('Máximo de linhas na simulação', min_value=1, max_value=1500, value=min(len(df_site), 1500), step=50, key=f'mirror_max_rows_{operation}_{stock_balance_only}')

    include_stock = selected_mode in {MODE_STOCK, MODE_BOTH}
    include_new = selected_mode in {MODE_NEW_PRODUCTS, MODE_BOTH}
    config = MirrorPlanConfig(
        enabled=True,
        mode=selected_mode,
        interval_minutes=int(interval_minutes),
        max_rows_per_cycle=int(max_rows),
        include_stock=include_stock,
        include_new_products=include_new,
        simulation_only=True,
    )
    report = build_mirror_plan(df_site, config)
    summary = report_summary(report)
    st.session_state['mirror_planner_last_report'] = report.to_dict()
    st.session_state['mirror_planner_last_summary'] = summary

    cols = st.columns(4)
    cols[0].metric('Estoque pronto', int(summary.get('stock_ready') or 0))
    cols[1].metric('Produtos novos', int(summary.get('new_products_ready') or 0))
    cols[2].metric('Pendências', int(summary.get('pending') or 0))
    cols[3].metric('Pulados', int(summary.get('skipped') or 0))

    decisions_df = decisions_dataframe(report)
    if isinstance(decisions_df, pd.DataFrame) and not decisions_df.empty:
        with st.expander('Ver decisões da simulação', expanded=False):
            st.dataframe(decisions_df, use_container_width=True, hide_index=True)
            data = _csv_bytes(decisions_df)
            if data:
                st.download_button(
                    '⬇️ Baixar decisões CSV',
                    data=data,
                    file_name='espelhamento_decisoes.csv',
                    mime='text/csv; charset=utf-8',
                    use_container_width=True,
                    key=f'mirror_decisions_csv_{operation}_{stock_balance_only}_{len(decisions_df)}',
                )

    if int(summary.get('stock_ready') or 0) or int(summary.get('new_products_ready') or 0):
        st.success('Simulação concluída. Há itens prontos para uma futura aplicação assistida, com confirmação manual.')
    else:
        st.warning('Simulação concluída sem itens prontos para aplicação. Revise identificadores, quantidade/saldo e qualidade dos produtos novos.')

    st.info('Aplicação automática ainda está bloqueada por segurança. O próximo passo será criar “Aplicar somente itens aprovados” com confirmação e logs.')
    add_audit_event(
        'mirror_planner_panel_rendered',
        area='ESPELHAMENTO',
        status='SIMULADO',
        details={
            'operation': operation,
            'stock_balance_only': stock_balance_only,
            'summary': summary,
            'responsible_file': RESPONSIBLE_FILE,
        },
    )


__all__ = ['render_mirror_planner_panel']
