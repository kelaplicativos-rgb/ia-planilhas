from __future__ import annotations

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
    current_mirror_status,
    save_mirror_config,
)
from bling_app_zero.core.bling_mirror_store import save_persistent_config

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


def render_mirror_monitor_panel(*, default_site_url: str = '', default_deposit_name: str = '') -> None:
    cfg = current_mirror_config()
    status = current_mirror_status()

    with st.expander('Configuração do espelhamento automático futuro', expanded=False):
        st.caption('Esta configuração liga apenas o modo monitoramento. O ciclo automático real ainda não roda dentro do Streamlit.')
        enabled = st.toggle('Espelhamento ativo em modo monitoramento', value=bool(cfg.enabled), key='mirror_monitor_enabled_toggle')
        site_url = st.text_input('Site/fornecedor', value=cfg.site_url or default_site_url, placeholder='https://fornecedor.com.br', key='mirror_monitor_site_url')
        deposit_name = st.text_input('Depósito Bling', value=cfg.deposit_name or default_deposit_name, placeholder='Ex.: iFood, Loja, Padrão', key='mirror_monitor_deposit_name')
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
            interval_minutes = st.number_input('Intervalo entre ciclos futuros', min_value=MIN_INTERVAL_MINUTES, max_value=MAX_INTERVAL_MINUTES, value=int(cfg.interval_minutes), step=5, key='mirror_monitor_interval')
        with col_b:
            max_products = st.number_input('Máximo por ciclo futuro', min_value=1, max_value=MAX_PRODUCTS_PER_CYCLE, value=int(cfg.max_products_per_cycle), step=50, key='mirror_monitor_max_products')

        stock_auto_allowed = st.checkbox('Permitir estoque automático no futuro após validação', value=bool(cfg.stock_auto_allowed), key='mirror_monitor_stock_auto_allowed')
        st.checkbox('Produtos novos sempre passam por revisão', value=True, disabled=True, key='mirror_monitor_new_products_review_only')
        st.checkbox('Preview obrigatório antes da saída final', value=True, disabled=True, key='mirror_monitor_preview_required')
        st.checkbox('Modo monitoramento seguro', value=True, disabled=True, key='mirror_monitor_only')

        if st.button('Salvar configuração de monitoramento', use_container_width=True, key='mirror_monitor_save_config'):
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
            st.success('Configuração de monitoramento salva de forma persistente. Nenhum ciclo automático foi iniciado dentro da tela.')
            add_audit_event(
                'mirror_monitor_config_saved',
                area='ESPELHAMENTO',
                status='CONFIGURADO',
                details={'config': persistent.to_dict(), 'persistent_store': True, 'responsible_file': RESPONSIBLE_FILE},
            )

        status = current_mirror_status()
        st.markdown('#### Status do monitoramento')
        cols = st.columns(3)
        cols[0].metric('Estado', status.state)
        cols[1].metric('Última simulação', status.last_run_at or '—')
        cols[2].metric('Próximo ciclo previsto', status.next_run_at or '—')
        st.caption(status.last_message or 'Aguardando configuração.')
        st.info('Para virar automático real, o próximo passo é configurar o executor agendado fora da tela Streamlit.')


__all__ = ['render_mirror_monitor_panel']
