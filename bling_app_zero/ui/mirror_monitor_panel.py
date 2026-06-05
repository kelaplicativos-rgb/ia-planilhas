from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.bling_mirror_config import (
    MAX_INTERVAL_MINUTES,
    MAX_PRODUCTS_PER_CYCLE,
    MIN_INTERVAL_MINUTES,
    MIRROR_MODE_BOTH,
    MIRROR_MODE_NEW_PRODUCTS,
    MIRROR_MODE_STOCK,
    MirrorMonitorConfig,
    current_mirror_config,
    save_mirror_config,
)
from bling_app_zero.core.bling_mirror_store import (
    load_persistent_config,
    load_persistent_status,
    mirror_store_payload,
    save_persistent_config,
)

RESPONSIBLE_FILE = 'bling_app_zero/ui/mirror_monitor_panel.py'


def _mode_label(mode: str) -> str:
    labels = {
        MIRROR_MODE_STOCK: 'Somente estoque automático futuro',
        MIRROR_MODE_NEW_PRODUCTS: 'Somente produtos novos em revisão',
        MIRROR_MODE_BOTH: 'Estoque + produtos novos',
    }
    return labels.get(mode, 'Somente estoque automático futuro')


def _mode_options() -> list[str]:
    return [MIRROR_MODE_STOCK, MIRROR_MODE_NEW_PRODUCTS, MIRROR_MODE_BOTH]


def _config_for_panel() -> MirrorMonitorConfig:
    session_cfg = current_mirror_config()
    persistent_cfg = load_persistent_config()

    if persistent_cfg.updated_at and not session_cfg.updated_at:
        return persistent_cfg

    if persistent_cfg.updated_at and persistent_cfg.updated_at > session_cfg.updated_at:
        return persistent_cfg

    return session_cfg


def _run_rows(limit: int = 8) -> pd.DataFrame:
    payload = mirror_store_payload()
    runs = payload.get('runs') if isinstance(payload.get('runs'), list) else []

    rows: list[dict[str, object]] = []

    for item in list(reversed(runs))[: max(1, int(limit or 8))]:
        if not isinstance(item, dict):
            continue

        cycle = item.get('cycle') if isinstance(item.get('cycle'), dict) else {}
        diff = item.get('diff') if isinstance(item.get('diff'), dict) else {}

        rows.append(
            {
                'quando': item.get('finished_at') or item.get('created_at') or '',
                'estado': item.get('state') or '',
                'modo': item.get('execution_mode') or item.get('mode') or '',
                'linhas': cycle.get('extracted_rows') or cycle.get('rows_seen') or 0,
                'itens': cycle.get('item_snapshot_total') or 0,
                'sem_id': cycle.get('item_snapshot_missing_identity') or 0,
                'estoque_pronto': cycle.get('stock_ready') or 0,
                'novos_produtos': cycle.get('new_products_ready') or 0,
                'pendencias': cycle.get('pending') or 0,
                'mudou': 'Sim' if diff.get('changed') else 'Não',
                'novos': diff.get('item_new') or 0,
                'alterados': diff.get('item_changed') or 0,
                'removidos': diff.get('item_removed') or 0,
                'iguais': diff.get('item_unchanged') or 0,
                'mensagem': item.get('message') or cycle.get('message') or diff.get('message') or '',
            }
        )

    return pd.DataFrame(rows)


def _latest_diff() -> dict[str, object]:
    payload = mirror_store_payload()
    runs = payload.get('runs') if isinstance(payload.get('runs'), list) else []

    for item in reversed(runs):
        if isinstance(item, dict) and isinstance(item.get('diff'), dict):
            return dict(item.get('diff') or {})

    return {}


def _render_store_health() -> None:
    payload = mirror_store_payload()
    health = payload.get('health') if isinstance(payload.get('health'), dict) else {}

    with st.expander('Diagnóstico do store persistente', expanded=False):
        cols = st.columns(4)
        cols[0].metric('Store OK', 'Sim' if health.get('ok') else 'Não')
        cols[1].metric('Existe', 'Sim' if health.get('exists') else 'Não')
        cols[2].metric('Legível', 'Sim' if health.get('readable') else 'Não')
        cols[3].metric('Pasta gravável', 'Sim' if health.get('writable_parent') else 'Não')

        st.caption(str(health.get('message') or 'Diagnóstico do store indisponível.'))
        st.code(str(health.get('store_path') or payload.get('store_path') or 'caminho não definido'))


def _render_persistent_history() -> None:
    payload = mirror_store_payload()
    status = payload.get('status') if isinstance(payload.get('status'), dict) else {}
    runs = payload.get('runs') if isinstance(payload.get('runs'), list) else []
    diff = _latest_diff()

    st.markdown('#### Histórico persistente')

    cols = st.columns(6)
    cols[0].metric('Execuções', len(runs))
    cols[1].metric('Linhas lidas', int(status.get('last_rows_seen') or 0))
    cols[2].metric('Estoque pronto', int(status.get('last_stock_ready') or 0))
    cols[3].metric('Produtos novos', int(status.get('last_new_products_ready') or 0))
    cols[4].metric('Pendências', int(status.get('last_pending') or 0))
    cols[5].metric('Mudou?', 'Sim' if diff.get('changed') else 'Não')

    if diff:
        st.caption(str(diff.get('message') or 'Comparação entre ciclos registrada.'))

        diff_cols = st.columns(4)
        diff_cols[0].metric('Itens novos', int(diff.get('item_new') or 0))
        diff_cols[1].metric('Itens alterados', int(diff.get('item_changed') or 0))
        diff_cols[2].metric('Itens removidos', int(diff.get('item_removed') or 0))
        diff_cols[3].metric('Itens iguais', int(diff.get('item_unchanged') or 0))

    df_runs = _run_rows()

    if isinstance(df_runs, pd.DataFrame) and not df_runs.empty:
        with st.expander('Ver últimas execuções monitoradas', expanded=False):
            st.dataframe(df_runs, use_container_width=True, hide_index=True)
    else:
        st.caption('Ainda não há execução persistente registrada pelo executor externo.')


def _render_monitor_status() -> None:
    status = load_persistent_status()

    st.markdown('#### Status do monitoramento')

    cols = st.columns(3)
    cols[0].metric('Estado', status.state)
    cols[1].metric('Último ciclo persistente', status.last_run_at or '—')
    cols[2].metric('Próximo ciclo previsto', status.next_run_at or '—')

    st.caption(status.last_message or 'Aguardando configuração persistente.')


def render_mirror_monitor_panel(*, default_site_url: str = '', default_deposit_name: str = '') -> None:
    cfg = _config_for_panel()

    with st.expander('Configuração do espelhamento automático futuro', expanded=False):
        st.caption(
            'Esta configuração liga apenas o modo monitoramento. '
            'O ciclo automático real ainda não roda dentro do Streamlit.'
        )

        enabled = st.toggle(
            'Espelhamento ativo em modo monitoramento',
            value=bool(cfg.enabled),
            key='mirror_monitor_enabled_toggle',
        )

        site_url = st.text_input(
            'Site/fornecedor',
            value=cfg.site_url or default_site_url,
            placeholder='https://fornecedor.com.br',
            key='mirror_monitor_site_url',
        )

        deposit_name = st.text_input(
            'Depósito Bling',
            value=cfg.deposit_name or default_deposit_name,
            placeholder='Ex.: iFood, Loja, Padrão',
            key='mirror_monitor_deposit_name',
        )

        options = _mode_options()

        mode = st.radio(
            'Modo do espelhamento',
            options=options,
            index=options.index(cfg.mode) if cfg.mode in options else 0,
            format_func=_mode_label,
            horizontal=False,
            key='mirror_monitor_mode',
        )

        col_a, col_b = st.columns(2)

        with col_a:
            interval_minutes = st.number_input(
                'Intervalo entre ciclos futuros',
                min_value=MIN_INTERVAL_MINUTES,
                max_value=MAX_INTERVAL_MINUTES,
                value=int(cfg.interval_minutes),
                step=5,
                key='mirror_monitor_interval',
            )

        with col_b:
            max_products = st.number_input(
                'Máximo por ciclo futuro',
                min_value=1,
                max_value=MAX_PRODUCTS_PER_CYCLE,
                value=int(cfg.max_products_per_cycle),
                step=50,
                key='mirror_monitor_max_products',
            )

        stock_auto_allowed = st.checkbox(
            'Permitir estoque automático no futuro após validação',
            value=bool(cfg.stock_auto_allowed),
            key='mirror_monitor_stock_auto_allowed',
        )

        st.checkbox(
            'Produtos novos sempre passam por revisão',
            value=True,
            disabled=True,
            key='mirror_monitor_new_products_review_only',
        )

        st.checkbox(
            'Preview obrigatório antes da saída final',
            value=True,
            disabled=True,
            key='mirror_monitor_preview_required',
        )

        st.checkbox(
            'Modo monitoramento seguro',
            value=True,
            disabled=True,
            key='mirror_monitor_only',
        )

        if st.button(
            'Salvar configuração de monitoramento',
            use_container_width=True,
            key='mirror_monitor_save_config',
        ):
            saved = save_mirror_config(
                MirrorMonitorConfig(
                    enabled=enabled,
                    site_url=site_url,
                    deposit_name=deposit_name,
                    mode=mode,
                    interval_minutes=int(interval_minutes),
                    max_products_per_cycle=int(max_products),
                    stock_auto_allowed=bool(stock_auto_allowed),
                    new_products_review_only=True,
                    require_preview=True,
                    monitor_only=True,
                )
            )

            persistent = save_persistent_config(saved)

            st.success(
                'Configuração de monitoramento salva de forma persistente. '
                'Nenhum ciclo automático foi iniciado dentro da tela.'
            )

            add_audit_event(
                'mirror_monitor_config_saved',
                area='ESPELHAMENTO',
                status='CONFIGURADO',
                details={
                    'config': persistent.to_dict(),
                    'persistent_store': True,
                    'responsible_file': RESPONSIBLE_FILE,
                },
            )

    # Estes blocos precisam ficar fora do expander de configuração.
    # O Streamlit não permite st.expander dentro de outro st.expander.
    _render_monitor_status()
    _render_store_health()
    _render_persistent_history()

    st.info(
        'Para virar automático real, o próximo passo é configurar o executor agendado fora da tela Streamlit.'
    )


__all__ = ['render_mirror_monitor_panel']
