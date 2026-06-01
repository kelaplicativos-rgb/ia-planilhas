from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.features.registry import list_features
from bling_app_zero.features.state import clear_feature_state, set_feature_enabled
from bling_app_zero.features.validator import validate_feature_architecture
from bling_app_zero.ui.home_wizard_rerun import safe_rerun

RESPONSIBLE_FILE = 'bling_app_zero/ui/features_panel.py'
STATUS_LABELS = {
    'stable': 'Estável',
    'beta': 'Beta',
    'experimental': 'Experimental',
    'disabled': 'Desativado',
}
SCOPE_LABELS = {
    'cadastro': 'Cadastro',
    'estoque': 'Estoque',
    'global': 'Global',
}
STAGE_LABELS = {
    'entrada': 'Entrada',
    'mapeamento': 'Mapeamento',
    'preview': 'Preview',
    'download': 'Download',
    'sidebar': 'Sidebar',
    'global': 'Global',
}


def _feature_row(feature) -> dict[str, str]:
    return {
        'Módulo': feature.title,
        'Chave': feature.key,
        'Escopo': SCOPE_LABELS.get(feature.scope, feature.scope),
        'Etapa': STAGE_LABELS.get(feature.stage, feature.stage),
        'Status': STATUS_LABELS.get(feature.status, feature.status),
        'Arquivo dono': feature.owner_file,
    }


def _render_architecture_status() -> None:
    report = validate_feature_architecture()
    if report.ok and not report.warnings:
        st.success(f'Arquitetura modular OK · {report.total_features} módulo(s) registrado(s).')
        return

    if report.ok:
        st.warning(f'Arquitetura modular com aviso(s) · {len(report.warnings)} aviso(s).')
    else:
        st.error(f'Arquitetura modular com erro(s) · {len(report.errors)} erro(s).')

    with st.expander('Ver validação BLINGMODULE', expanded=not report.ok):
        for issue in report.issues:
            prefix = '❌' if issue.severity == 'erro' else '⚠️'
            st.caption(f'{prefix} `{issue.feature}` · {issue.message}')


def _render_feature_detail(feature) -> None:
    state_key = feature.enabled_key
    current = bool(st.session_state.get(state_key, feature.status != 'disabled'))
    disabled = feature.status == 'disabled'

    st.markdown(f'**{feature.title}**')
    st.caption(feature.description)
    st.caption(f'Arquivo dono: `{feature.owner_file or "não definido"}`')
    st.caption(f'Estado: `{state_key}`')

    if feature.requires:
        st.caption('Entrada exigida: ' + ', '.join(f'`{item}`' for item in feature.requires))
    if feature.provides:
        st.caption('Entrega: ' + ', '.join(f'`{item}`' for item in feature.provides))

    new_value = st.toggle(
        'Ativo',
        value=current,
        key=f'feature_panel_toggle_{feature.key}',
        disabled=disabled,
        help='Controle modular do recurso. Recursos estáveis já podem estar ligados por padrão no fluxo.',
    )
    if new_value != current:
        set_feature_enabled(feature.key, new_value)
        st.session_state[state_key] = new_value
        safe_rerun('feature_panel_toggle_changed')

    if st.button('Limpar estado deste módulo', use_container_width=True, key=f'feature_panel_clear_{feature.key}'):
        clear_feature_state(feature.key)
        safe_rerun('feature_panel_state_cleared')


def render_features_panel() -> None:
    features = list_features()
    with st.sidebar:
        with st.expander('Módulos e recursos', expanded=False):
            st.caption('Registry oficial BLINGMODULE: todo recurso novo deve ter contrato, estado e arquivo dono.')
            _render_architecture_status()
            if not features:
                st.info('Nenhum módulo registrado ainda.')
                return

            df = pd.DataFrame([_feature_row(feature) for feature in features])
            st.dataframe(df, use_container_width=True, hide_index=True, height=220)

            labels = [f'{feature.title} · {feature.key}' for feature in features]
            selected_label = st.selectbox(
                'Inspecionar módulo',
                labels,
                index=0,
                key='feature_panel_selected_module',
            )
            selected_index = labels.index(selected_label) if selected_label in labels else 0
            feature = features[selected_index]
            st.divider()
            _render_feature_detail(feature)

            add_audit_event(
                'features_panel_rendered',
                area='FEATURES',
                details={
                    'features_count': len(features),
                    'selected_feature': feature.key,
                    'responsible_file': RESPONSIBLE_FILE,
                },
            )


__all__ = ['render_features_panel']
