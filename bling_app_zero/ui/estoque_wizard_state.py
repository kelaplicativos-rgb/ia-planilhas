from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.ui.estoque_sources import file_name, safe_read_source, source_files_from_upload
from bling_app_zero.ui.home_models_state import get_home_estoque_model, get_home_universal_model
from bling_app_zero.ui.home_shared import df_signature

ESTOQUE_SOURCE_SIGNATURE_KEY = 'estoque_source_signature_atual'
ESTOQUE_UPLOAD_KEY = 'estoque_wizard_upload'
ESTOQUE_ORIGEM_SITE_KEY = 'estoque_wizard_df_origem_site'
ESTOQUE_MODELO_KEY = 'estoque_wizard_df_modelo'
ESTOQUE_FINAL_KEY = 'df_final_estoque'
ESTOQUE_MAPPING_KEY = 'mapping_estoque'
ESTOQUE_CONFIDENCE_KEY = 'mapping_confidence_estoque'
LEGACY_ESTOQUE_FINAL_KEY = 'df_final_estoque_from_cadastro'
LEGACY_ESTOQUE_MAPPING_KEY = 'mapping_estoque_from_cadastro'
LEGACY_ESTOQUE_CONFIDENCE_KEY = 'mapping_confidence_estoque_from_cadastro'
BLING_IMPORTADOR_ESTOQUE_URL = 'https://www.bling.com.br/importador.saldos.estoque.php'

RESPONSIBLE_FILE = 'bling_app_zero/ui/estoque_wizard_state.py'

ESTOQUE_MODEL_FALLBACK_KEYS = (
    ESTOQUE_MODELO_KEY,
    'home_modelo_estoque_df',
    'df_modelo_estoque',
    'modelo_estoque_df',
    'home_modelo_universal_df',
    'df_modelo_universal',
    'modelo_universal_df',
)

ESTOQUE_SITE_SOURCE_FALLBACK_KEYS = (
    ESTOQUE_ORIGEM_SITE_KEY,
    'df_site_bruto_estoque',
    'df_site_bruto',
    'df_origem_site',
    'df_origem_estoque',
    'df_origem_universal',
)

ESTOQUE_OUTPUT_KEYS = [
    'estoque_multi_outputs',
    ESTOQUE_FINAL_KEY,
    ESTOQUE_MAPPING_KEY,
    ESTOQUE_CONFIDENCE_KEY,
    LEGACY_ESTOQUE_FINAL_KEY,
    LEGACY_ESTOQUE_MAPPING_KEY,
    LEGACY_ESTOQUE_CONFIDENCE_KEY,
]


def valid_model(df_modelo: pd.DataFrame | None) -> bool:
    return isinstance(df_modelo, pd.DataFrame) and len(df_modelo.columns) > 0


def _copy_df(df: pd.DataFrame | None) -> pd.DataFrame | None:
    if isinstance(df, pd.DataFrame) and len(df.columns) > 0:
        return df.copy().fillna('')
    return None


def resolve_stock_model_df(df_modelo: pd.DataFrame | None = None, *, persist: bool = True) -> pd.DataFrame | None:
    """
    Resolve o modelo de destino de estoque mesmo quando ele foi salvo pela etapa
    universal/modelo inicial.

    Corrige o falso erro:
    "Modelo de destino ausente. Volte para a entrada."

    O fluxo novo salva o modelo em:
    - home_modelo_estoque_df
    - df_modelo_estoque
    - modelo_estoque_df

    A tela legada de estoque esperava apenas:
    - estoque_wizard_df_modelo
    """
    direct = _copy_df(df_modelo)
    if direct is not None:
        if persist:
            st.session_state[ESTOQUE_MODELO_KEY] = direct.copy()
        return direct

    for key in ESTOQUE_MODEL_FALLBACK_KEYS:
        candidate = _copy_df(st.session_state.get(key))
        if candidate is not None:
            if persist:
                st.session_state[ESTOQUE_MODELO_KEY] = candidate.copy()
                add_audit_event(
                    'estoque_model_resolved_from_session_fallback',
                    area='ESTOQUE',
                    step='mapeamento',
                    status='OK',
                    details={
                        'source_key': key,
                        'rows': int(len(candidate)),
                        'columns': [str(column) for column in candidate.columns],
                        'responsible_file': RESPONSIBLE_FILE,
                    },
                )
            return candidate

    for label, getter in (
        ('get_home_estoque_model', get_home_estoque_model),
        ('get_home_universal_model', get_home_universal_model),
    ):
        try:
            candidate = _copy_df(getter())
        except Exception as exc:
            add_audit_event(
                'estoque_model_getter_failed',
                area='ESTOQUE',
                step='mapeamento',
                status='IGNORADO',
                details={
                    'getter': label,
                    'error': str(exc),
                    'responsible_file': RESPONSIBLE_FILE,
                },
            )
            candidate = None

        if candidate is not None:
            if persist:
                st.session_state[ESTOQUE_MODELO_KEY] = candidate.copy()
                add_audit_event(
                    'estoque_model_resolved_from_home_models',
                    area='ESTOQUE',
                    step='mapeamento',
                    status='OK',
                    details={
                        'source': label,
                        'rows': int(len(candidate)),
                        'columns': [str(column) for column in candidate.columns],
                        'responsible_file': RESPONSIBLE_FILE,
                    },
                )
            return candidate

    return None


def is_site_origin() -> bool:
    return str(st.session_state.get('home_slim_flow_origin') or st.session_state.get('origem_final') or '').strip().lower() == 'site'


def _site_source_df() -> pd.DataFrame | None:
    for key in ESTOQUE_SITE_SOURCE_FALLBACK_KEYS:
        df = st.session_state.get(key)
        if isinstance(df, pd.DataFrame) and not df.empty:
            if key != ESTOQUE_ORIGEM_SITE_KEY:
                st.session_state[ESTOQUE_ORIGEM_SITE_KEY] = df.copy().fillna('')
            return df.copy().fillna('')
    return None


def current_source_signature(df_origem_site: pd.DataFrame | None, upload) -> str:
    df_site = df_origem_site
    if not isinstance(df_site, pd.DataFrame) or df_site.empty:
        df_site = _site_source_df()

    if isinstance(df_site, pd.DataFrame) and not df_site.empty:
        return 'site:' + df_signature(df_site)

    files = source_files_from_upload(upload)
    names = [str(getattr(file, 'name', 'arquivo')) for file in files]
    sizes = [str(getattr(file, 'size', '')) for file in files]
    return 'upload:' + '|'.join(names + sizes)


def clear_estoque_outputs() -> None:
    for key in ESTOQUE_OUTPUT_KEYS:
        st.session_state.pop(key, None)


def clear_estoque_outputs_if_source_changed(df_origem_site: pd.DataFrame | None, upload) -> None:
    signature = current_source_signature(df_origem_site, upload)
    previous = st.session_state.get(ESTOQUE_SOURCE_SIGNATURE_KEY)
    if previous == signature:
        return
    clear_estoque_outputs()
    st.session_state[ESTOQUE_SOURCE_SIGNATURE_KEY] = signature


def store_estoque_context(upload, df_origem_site: pd.DataFrame | None, df_modelo: pd.DataFrame | None) -> None:
    st.session_state[ESTOQUE_UPLOAD_KEY] = upload

    df_site = df_origem_site
    if not isinstance(df_site, pd.DataFrame) or df_site.empty:
        df_site = _site_source_df()

    if isinstance(df_site, pd.DataFrame) and not df_site.empty:
        st.session_state[ESTOQUE_ORIGEM_SITE_KEY] = df_site.copy().fillna('')
    else:
        st.session_state.pop(ESTOQUE_ORIGEM_SITE_KEY, None)

    resolved_model = resolve_stock_model_df(df_modelo, persist=True)
    if resolved_model is None:
        st.session_state.pop(ESTOQUE_MODELO_KEY, None)


def has_stock_source(upload=None, df_site=None) -> bool:
    current_upload = st.session_state.get(ESTOQUE_UPLOAD_KEY) if upload is None else upload
    current_site = st.session_state.get(ESTOQUE_ORIGEM_SITE_KEY) if df_site is None else df_site

    if not isinstance(current_site, pd.DataFrame) or current_site.empty:
        current_site = _site_source_df()

    has_site = isinstance(current_site, pd.DataFrame) and not current_site.empty
    has_upload = bool(current_upload is not None and source_files_from_upload(current_upload))
    return has_site or has_upload


def estoque_context_ready() -> bool:
    df_modelo = resolve_stock_model_df(st.session_state.get(ESTOQUE_MODELO_KEY), persist=True)
    return has_stock_source() and valid_model(df_modelo)


def set_stock_output(df_final: pd.DataFrame | None, mapping: dict | None = None, confidence: dict | None = None) -> None:
    if isinstance(df_final, pd.DataFrame):
        st.session_state[ESTOQUE_FINAL_KEY] = df_final
        st.session_state[LEGACY_ESTOQUE_FINAL_KEY] = df_final
    if isinstance(mapping, dict):
        st.session_state[ESTOQUE_MAPPING_KEY] = mapping
        st.session_state[LEGACY_ESTOQUE_MAPPING_KEY] = mapping
    if isinstance(confidence, dict):
        st.session_state[ESTOQUE_CONFIDENCE_KEY] = confidence
        st.session_state[LEGACY_ESTOQUE_CONFIDENCE_KEY] = confidence


def stock_final_df() -> pd.DataFrame | None:
    df_final = st.session_state.get(ESTOQUE_FINAL_KEY)
    if isinstance(df_final, pd.DataFrame) and not df_final.empty:
        return df_final

    legacy = st.session_state.get(LEGACY_ESTOQUE_FINAL_KEY)
    if isinstance(legacy, pd.DataFrame) and not legacy.empty:
        st.session_state[ESTOQUE_FINAL_KEY] = legacy
        return legacy

    return None


def stock_mapping() -> dict:
    mapping = st.session_state.get(ESTOQUE_MAPPING_KEY)
    if isinstance(mapping, dict):
        return mapping

    legacy = st.session_state.get(LEGACY_ESTOQUE_MAPPING_KEY)
    if isinstance(legacy, dict):
        st.session_state[ESTOQUE_MAPPING_KEY] = legacy
        return legacy

    return {}


def stock_confidence() -> dict:
    confidence = st.session_state.get(ESTOQUE_CONFIDENCE_KEY)
    if isinstance(confidence, dict):
        return confidence

    legacy = st.session_state.get(LEGACY_ESTOQUE_CONFIDENCE_KEY)
    if isinstance(legacy, dict):
        st.session_state[ESTOQUE_CONFIDENCE_KEY] = legacy
        return legacy

    return {}


def generated_output_ready() -> bool:
    outputs = st.session_state.get('estoque_multi_outputs')
    if isinstance(outputs, list) and outputs:
        return True

    df_final = stock_final_df()
    return isinstance(df_final, pd.DataFrame) and not df_final.empty


def estoque_output_ready() -> bool:
    return generated_output_ready()


def current_stock_source() -> tuple[pd.DataFrame | None, str]:
    df_site = _site_source_df()
    if isinstance(df_site, pd.DataFrame) and not df_site.empty:
        return df_site, 'Origem criada pelo site'

    upload = st.session_state.get(ESTOQUE_UPLOAD_KEY)
    files = source_files_from_upload(upload)
    if not files:
        return None, ''

    if len(files) > 1:
        st.warning('Mapeamento manual de estoque usa uma origem por vez. Para múltiplos arquivos, gere um CSV por arquivo.')

    first_file = files[0]
    df_file = safe_read_source(first_file)
    if isinstance(df_file, pd.DataFrame) and not df_file.empty:
        return df_file, file_name(first_file)

    return None, ''


def sync_manual_stock_output(name: str) -> bool:
    df_final = stock_final_df()
    mapping = stock_mapping()

    if not isinstance(df_final, pd.DataFrame) or df_final.empty:
        return False

    result = {
        'index': 1,
        'name': name or 'Origem de estoque',
        'df_final': df_final,
        'mapping': mapping,
    }

    st.session_state['estoque_multi_outputs'] = [result]
    set_stock_output(df_final, mapping)
    return True


def build_stock_outputs_if_possible() -> bool:
    if generated_output_ready():
        return True
    return sync_manual_stock_output('Origem de estoque')


__all__ = [
    'BLING_IMPORTADOR_ESTOQUE_URL',
    'ESTOQUE_CONFIDENCE_KEY',
    'ESTOQUE_FINAL_KEY',
    'ESTOQUE_MAPPING_KEY',
    'ESTOQUE_MODELO_KEY',
    'build_stock_outputs_if_possible',
    'clear_estoque_outputs_if_source_changed',
    'current_stock_source',
    'estoque_context_ready',
    'estoque_output_ready',
    'is_site_origin',
    'resolve_stock_model_df',
    'set_stock_output',
    'stock_confidence',
    'stock_final_df',
    'stock_mapping',
    'store_estoque_context',
    'sync_manual_stock_output',
    'valid_model',
]
