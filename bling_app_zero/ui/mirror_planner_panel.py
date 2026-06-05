from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.bling_mirror_apply import build_apply_bundle, bundle_to_frames
from bling_app_zero.core.bling_mirror_bridge import bridge_reviewed_dataframe_to_official_flow
from bling_app_zero.core.bling_mirror_config import update_status_from_summary
from bling_app_zero.core.bling_mirror_planner import (
    MODE_BOTH,
    MODE_NEW_PRODUCTS,
    MODE_STOCK,
    MirrorPlanConfig,
    build_mirror_plan,
    decisions_dataframe,
    report_summary,
)
from bling_app_zero.ui.home_wizard_constants import STEP_PREVIEW
from bling_app_zero.ui.home_wizard_rerun import safe_rerun
from bling_app_zero.ui.mirror_monitor_panel import render_mirror_monitor_panel

RESPONSIBLE_FILE = 'bling_app_zero/ui/mirror_planner_panel.py'
MIRROR_APPROVED_STOCK_DF_KEY = 'mirror_approved_stock_df'
MIRROR_APPROVED_NEW_PRODUCTS_DF_KEY = 'mirror_approved_new_products_df'
MIRROR_APPROVED_BUNDLE_KEY = 'mirror_approved_bundle_summary'


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


def _prepare_bundle(report, *, operation: str, stock_balance_only: bool) -> dict[str, object]:
    bundle = build_apply_bundle(report)
    frames = bundle_to_frames(bundle)
    stock_df = frames.get('estoque')
    new_df = frames.get('cadastro')
    if isinstance(stock_df, pd.DataFrame) and not stock_df.empty:
        st.session_state[MIRROR_APPROVED_STOCK_DF_KEY] = stock_df.copy().fillna('')
    else:
        st.session_state.pop(MIRROR_APPROVED_STOCK_DF_KEY, None)
    if isinstance(new_df, pd.DataFrame) and not new_df.empty:
        st.session_state[MIRROR_APPROVED_NEW_PRODUCTS_DF_KEY] = new_df.copy().fillna('')
    else:
        st.session_state.pop(MIRROR_APPROVED_NEW_PRODUCTS_DF_KEY, None)
    summary = bundle.to_dict()
    summary['operation'] = operation
    summary['stock_balance_only'] = stock_balance_only
    st.session_state[MIRROR_APPROVED_BUNDLE_KEY] = summary
    add_audit_event(
        'mirror_reviewed_items_export_prepared',
        area='ESPELHAMENTO',
        status='PREPARADO',
        details={'summary': summary, 'responsible_file': RESPONSIBLE_FILE},
    )
    return summary


def _render_prepared_downloads() -> None:
    stock_df = st.session_state.get(MIRROR_APPROVED_STOCK_DF_KEY)
    new_df = st.session_state.get(MIRROR_APPROVED_NEW_PRODUCTS_DF_KEY)
    if isinstance(stock_df, pd.DataFrame) and not stock_df.empty:
        st.download_button(
            '⬇️ Baixar estoque revisado CSV',
            data=_csv_bytes(stock_df),
            file_name='espelhamento_estoque_revisado.csv',
            mime='text/csv; charset=utf-8',
            use_container_width=True,
            key=f'mirror_stock_reviewed_csv_{len(stock_df)}',
        )
    if isinstance(new_df, pd.DataFrame) and not new_df.empty:
        st.download_button(
            '⬇️ Baixar produtos novos revisados CSV',
            data=_csv_bytes(new_df),
            file_name='espelhamento_produtos_novos_revisados.csv',
            mime='text/csv; charset=utf-8',
            use_container_width=True,
            key=f'mirror_new_products_reviewed_csv_{len(new_df)}',
        )


def _render_official_flow_bridge(operation: str, stock_balance_only: bool) -> None:
    stock_df = st.session_state.get(MIRROR_APPROVED_STOCK_DF_KEY)
    new_df = st.session_state.get(MIRROR_APPROVED_NEW_PRODUCTS_DF_KEY)
    if not isinstance(stock_df, pd.DataFrame) and not isinstance(new_df, pd.DataFrame):
        return
    st.markdown('#### Usar no fluxo oficial')
    st.caption('Esta ponte prepara a base revisada para seguir pelo fluxo oficial, mantendo preview, validação e confirmação. Nada é enviado automaticamente.')

    if isinstance(stock_df, pd.DataFrame) and not stock_df.empty:
        if st.button('Usar estoque revisado no fluxo oficial', use_container_width=True, key=f'mirror_bridge_stock_{len(stock_df)}'):
            result = bridge_reviewed_dataframe_to_official_flow(
                stock_df,
                operation='estoque',
                source_label='espelhamento_estoque_revisado',
                target_step=STEP_PREVIEW,
            )
            if result.ok:
                st.success(result.message)
                safe_rerun('mirror_bridge_stock_to_official_flow_preview_first', target_step=result.target_step)
            else:
                st.error(result.message)

    if isinstance(new_df, pd.DataFrame) and not new_df.empty:
        if st.button('Usar produtos novos revisados no fluxo oficial', use_container_width=True, key=f'mirror_bridge_new_products_{len(new_df)}'):
            result = bridge_reviewed_dataframe_to_official_flow(
                new_df,
                operation='cadastro',
                source_label='espelhamento_produtos_novos_revisados',
                target_step=STEP_PREVIEW,
            )
            if result.ok:
                st.success(result.message)
                safe_rerun('mirror_bridge_new_products_to_official_flow', target_step=result.target_step)
            else:
                st.error(result.message)


def render_mirror_planner_panel(df_site: pd.DataFrame, *, operation: str = '', stock_balance_only: bool = False) -> None:
    if not isinstance(df_site, pd.DataFrame) or df_site.empty:
        return

    render_mirror_monitor_panel(default_site_url=st.session_state.get('site_capture_last_url', ''), default_deposit_name=st.session_state.get('estoque_deposito_nome', ''))

    st.markdown('### Espelhamento inteligente')
    st.caption('Simulação segura: o sistema separa o que poderia atualizar estoque, o que parece produto novo e o que virou pendência. Nada é aplicado sozinho.')

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
    update_status_from_summary(summary)
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

    ready_total = int(summary.get('stock_ready') or 0) + int(summary.get('new_products_ready') or 0)
    if ready_total:
        st.success('Simulação concluída. Há itens prontos para exportação revisada.')
        confirm = st.checkbox(
            'Confirmo que revisei a simulação e quero separar apenas os itens prontos',
            value=False,
            key=f'mirror_confirm_prepare_{operation}_{stock_balance_only}',
        )
        if st.button('Separar itens prontos para revisão', use_container_width=True, disabled=not confirm, key=f'mirror_prepare_reviewed_{operation}_{stock_balance_only}'):
            prepared = _prepare_bundle(report, operation=operation, stock_balance_only=stock_balance_only)
            st.success(f"Itens separados: {prepared.get('ready_rows', 0)} linha(s).")
        _render_prepared_downloads()
        _render_official_flow_bridge(operation, stock_balance_only)
    else:
        st.warning('Simulação concluída sem itens prontos. Revise identificadores, quantidade/saldo e qualidade dos produtos novos.')

    st.info('Esta etapa apenas separa, exporta e prepara os itens prontos para o fluxo oficial. O envio/cadastro real continua com revisão e confirmação.')
    add_audit_event(
        'mirror_planner_panel_rendered',
        area='ESPELHAMENTO',
        status='SIMULADO',
        details={
            'operation': operation,
            'stock_balance_only': stock_balance_only,
            'summary': summary,
            'preview_required_for_stock_bridge': True,
            'monitor_status_updated': True,
            'responsible_file': RESPONSIBLE_FILE,
        },
    )


__all__ = ['render_mirror_planner_panel']
