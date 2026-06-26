from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from bling_app_zero.core.audit import add_audit_event

RESPONSIBLE_FILE = 'bling_app_zero/ui/universal_model_preservation_runtime.py'
INSTALL_MARKER = 'universal_model_preservation_runtime_installed_v1'

PRESERVE_MODE_KEY = 'mapeiaai_universal_preserve_model_mode'
PRESERVE_ENABLED_KEY = 'mapeiaai_universal_preserve_model_enabled'
PRESERVE_COLUMNS_KEY = 'mapeiaai_universal_preserve_model_columns'
PRESERVE_MODEL_SIGNATURE_KEY = 'mapeiaai_universal_preserve_model_signature'
PRESERVE_KEYS = (
    PRESERVE_MODE_KEY,
    PRESERVE_ENABLED_KEY,
    PRESERVE_COLUMNS_KEY,
    PRESERVE_MODEL_SIGNATURE_KEY,
)

PRESERVE_MODES = (
    'Usar apenas a estrutura do modelo',
    'Preservar dados já preenchidos no modelo',
    'Preservar somente campos críticos',
)

CRITICAL_DEFAULT_COLUMNS = (
    'IdProduto',
    'ID na Loja',
    'Código',
    'Codigo',
    'SKU',
    'Preco',
    'Preço',
    'Preco Promocional',
    'Preço Promocional',
    'ID do Fornecedor',
    'ID da Marca',
    'Link Externo',
    'Nome Loja (Multilojas)',
)


def _audit(action: str, **details: Any) -> None:
    add_audit_event(
        action,
        area='UNIVERSAL',
        status='OK',
        details={'responsible_file': RESPONSIBLE_FILE, **details},
    )


def _model_signature(model: pd.DataFrame | None) -> str:
    if not isinstance(model, pd.DataFrame):
        return 'none'
    columns = '|'.join(map(str, model.columns))
    return f'{len(model)}x{len(model.columns)}:{columns}'


def _reset_preservation_state() -> None:
    for key in PRESERVE_KEYS:
        st.session_state.pop(key, None)


def _sanitize_preservation_state(model: pd.DataFrame) -> None:
    columns = [str(col) for col in model.columns]
    current_signature = _model_signature(model)
    previous_signature = str(st.session_state.get(PRESERVE_MODEL_SIGNATURE_KEY) or '')
    if previous_signature and previous_signature != current_signature:
        st.session_state.pop(PRESERVE_COLUMNS_KEY, None)
    st.session_state[PRESERVE_MODEL_SIGNATURE_KEY] = current_signature

    mode = str(st.session_state.get(PRESERVE_MODE_KEY) or '').strip()
    if mode and mode not in PRESERVE_MODES:
        st.session_state.pop(PRESERVE_MODE_KEY, None)

    selected = st.session_state.get(PRESERVE_COLUMNS_KEY)
    if isinstance(selected, (list, tuple, set)):
        valid = [str(col) for col in selected if str(col) in columns]
        st.session_state[PRESERVE_COLUMNS_KEY] = valid


def _default_preserve_columns(model: pd.DataFrame) -> list[str]:
    columns = [str(col) for col in model.columns]
    defaults = [col for col in CRITICAL_DEFAULT_COLUMNS if col in columns]
    return defaults or columns[: min(5, len(columns))]


def _render_model_preservation_options(model: pd.DataFrame) -> None:
    _sanitize_preservation_state(model)

    st.markdown('### 🔒 Preservação dos dados do modelo')
    st.caption(
        'Esta escolha fica junto do modelo anexado para decidir o que o sistema pode preencher '
        'e o que deve proteger na montagem final.'
    )

    mode = st.radio(
        'Como deseja tratar os dados já existentes neste modelo?',
        PRESERVE_MODES,
        key=PRESERVE_MODE_KEY,
    )

    preserve_enabled = mode != PRESERVE_MODES[0]
    st.session_state[PRESERVE_ENABLED_KEY] = preserve_enabled

    selected_columns: list[str] = []
    if preserve_enabled:
        selected_columns = st.multiselect(
            'Campos que não devem ser sobrescritos',
            options=[str(col) for col in model.columns],
            default=_default_preserve_columns(model),
            key=PRESERVE_COLUMNS_KEY,
            help='Use para proteger IDs, códigos, preços, vínculos, lojas ou qualquer coluna já preenchida no modelo.',
        )
        if not selected_columns:
            st.warning('Selecione ao menos uma coluna para preservar ou escolha usar apenas a estrutura do modelo.')
    else:
        st.session_state[PRESERVE_COLUMNS_KEY] = []
        st.info('O modelo será usado somente como estrutura final: colunas e ordem serão mantidas.')

    if model.empty:
        st.info(
            'Este modelo está sem linhas preenchidas. Mesmo assim, a estrutura e os campos críticos selecionados '
            'ficarão registrados para a montagem final.'
        )

    _audit(
        'universal_model_preservation_options_rendered_near_upload',
        mode=mode,
        enabled=bool(preserve_enabled),
        columns=len(selected_columns),
        model_rows=int(len(model)),
        model_columns=int(len(model.columns)),
    )


def _patch_universal_model_step() -> bool:
    from bling_app_zero.ui import universal_flow as uf

    current = getattr(uf, '_render_model_step', None)
    if current is None or getattr(current, '_universal_preservation_patch', False):
        return False

    def _render_model_step_patched() -> pd.DataFrame | None:
        st.markdown('### 1. Anexar Modelo / Mapear')
        model = uf._current_df(uf.UNIVERSAL_MODEL_KEY)
        uploaded = None
        if not isinstance(model, pd.DataFrame):
            st.caption('Anexe primeiro a planilha modelo exatamente no formato que você quer receber no final.')
            uploaded = st.file_uploader('Planilha modelo final', type=None, key='mapeiaai_universal_model_upload')
            df = uf._read_model_upload(uploaded)
            if isinstance(df, pd.DataFrame):
                current_sig = uf._df_signature(uf._current_df(uf.UNIVERSAL_MODEL_KEY))
                new_sig = uf._df_signature(df)
                if current_sig != 'none' and current_sig != new_sig:
                    uf._clear_after_model()
                    _reset_preservation_state()
                uf._store_df(uf.UNIVERSAL_MODEL_KEY, df)
                st.session_state['home_modelo_universal_df'] = df.copy().fillna('')
                st.session_state['df_modelo_universal'] = df.copy().fillna('')
                st.session_state['modelo_universal_df'] = df.copy().fillna('')
                uf._audit(
                    'mapear_planilha_modelo_anexado_primeiro',
                    rows=int(len(df)),
                    columns=int(len(df.columns)),
                    original_file_name=str(getattr(uploaded, 'name', '') or ''),
                )
            model = uf._current_df(uf.UNIVERSAL_MODEL_KEY)
        if not isinstance(model, pd.DataFrame):
            st.info('Envie a planilha modelo final para liberar a próxima etapa.')
            return None
        st.success('Modelo final carregado. A saída seguirá exatamente essas colunas e essa ordem.')
        _render_model_preservation_options(model)
        st.dataframe(model.head(3).astype(str), use_container_width=True, height=145)
        st.caption('Colunas finais: ' + ', '.join(map(str, model.columns)))
        if st.button('Continuar para origem dos dados ➡️', use_container_width=True, key='mapeiaai_universal_go_source'):
            uf._set_step(uf.STEP_SOURCE, 'model_confirmed')
        return model

    _render_model_step_patched._universal_preservation_patch = True  # type: ignore[attr-defined]
    uf._render_model_step = _render_model_step_patched
    return True


def _patch_universal_state_clear() -> bool:
    from bling_app_zero.ui import home_router_v2 as router

    original = getattr(router, '_clear_universal_operation_state', None)
    if original is None or getattr(original, '_universal_preservation_clear_patch', False):
        return False

    def _clear_universal_operation_state_patched(*, keep_model: bool = False) -> None:
        preserved = {key: st.session_state.get(key) for key in PRESERVE_KEYS if key in st.session_state} if keep_model else {}
        original(keep_model=keep_model)
        if keep_model:
            for key, value in preserved.items():
                st.session_state[key] = value
        else:
            _reset_preservation_state()

    _clear_universal_operation_state_patched._universal_preservation_clear_patch = True  # type: ignore[attr-defined]
    router._clear_universal_operation_state = _clear_universal_operation_state_patched
    return True


def install_universal_model_preservation_runtime() -> bool:
    installed_model_step = _patch_universal_model_step()
    installed_clear = _patch_universal_state_clear()
    installed_now = bool(installed_model_step or installed_clear)
    st.session_state[INSTALL_MARKER] = True
    _audit(
        'universal_model_preservation_runtime_installed',
        installed_now=installed_now,
        model_step_patch=installed_model_step,
        clear_state_patch=installed_clear,
    )
    return installed_now


__all__ = [
    'PRESERVE_COLUMNS_KEY',
    'PRESERVE_ENABLED_KEY',
    'PRESERVE_MODE_KEY',
    'PRESERVE_KEYS',
    'install_universal_model_preservation_runtime',
]
