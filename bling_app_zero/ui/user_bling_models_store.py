from __future__ import annotations

import io
import json
from pathlib import Path

import pandas as pd
import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.ui.home_models import (
    DESTINATION_MODEL_UPLOAD_BYTES_KEY,
    DESTINATION_MODEL_UPLOAD_NAME_KEY,
    save_home_models,
)

RESPONSIBLE_FILE = 'bling_app_zero/ui/user_bling_models_store.py'
MODELS_DIR = Path('bling_user_models')
MANIFEST_PATH = MODELS_DIR / 'manifest.json'
MODEL_TYPES = ('cadastro', 'estoque', 'precos')
MODEL_LABELS = {
    'cadastro': 'Modelo Bling cadastro',
    'estoque': 'Modelo Bling estoque',
    'precos': 'Modelo Bling atualizar precos',
}
MODEL_FILE_NAMES = {
    'cadastro': 'modelo_bling_cadastro',
    'estoque': 'modelo_bling_estoque',
    'precos': 'modelo_bling_atualizar_precos',
}
VALID_EXTENSIONS = {'.csv', '.xlsx', '.xls', '.xlsm', '.xlsb'}


def ensure_dir() -> None:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)


def load_manifest() -> dict[str, dict[str, str]]:
    ensure_dir()
    if not MANIFEST_PATH.exists():
        return {}
    try:
        data = json.loads(MANIFEST_PATH.read_text(encoding='utf-8'))
        return data if isinstance(data, dict) else {}
    except Exception as exc:
        add_audit_event('user_bling_models_manifest_error', area='MODELOS_BLING', status='ERRO', details={'error': str(exc), 'responsible_file': RESPONSIBLE_FILE})
        return {}


def save_manifest(manifest: dict[str, dict[str, str]]) -> None:
    ensure_dir()
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')


def safe_suffix(file_name: str) -> str:
    suffix = Path(str(file_name or '')).suffix.lower().strip()
    return suffix if suffix in VALID_EXTENSIONS else '.csv'


def path_for_model(model_type: str, file_name: str) -> Path:
    return MODELS_DIR / f'{MODEL_FILE_NAMES[model_type]}{safe_suffix(file_name)}'


def read_model_bytes(file_name: str, file_bytes: bytes) -> pd.DataFrame:
    suffix = Path(str(file_name or '')).suffix.lower().strip()
    if suffix == '.csv':
        try:
            return pd.read_csv(io.BytesIO(file_bytes), sep=';', dtype=str).fillna('')
        except Exception:
            return pd.read_csv(io.BytesIO(file_bytes), sep=None, engine='python', dtype=str).fillna('')
    if suffix in {'.xlsx', '.xls', '.xlsm', '.xlsb'}:
        return pd.read_excel(io.BytesIO(file_bytes), dtype=str).fillna('')
    raise ValueError('Formato nao aceito. Use CSV, XLSX, XLS, XLSM ou XLSB.')


def csv_bytes(df: pd.DataFrame) -> bytes:
    buffer = io.StringIO()
    df.to_csv(buffer, sep=';', index=False)
    return buffer.getvalue().encode('utf-8-sig')


def sync_model_to_flow(model_type: str, df_model: pd.DataFrame, file_name: str) -> None:
    df_model = df_model.copy().fillna('')
    if model_type == 'cadastro':
        save_home_models(df_model, None, replace_missing=False)
        st.session_state['home_modelo_cadastro_df'] = df_model.copy()
        st.session_state['df_modelo_cadastro'] = df_model.copy()
        st.session_state['modelo_cadastro_df'] = df_model.copy()
    elif model_type == 'estoque':
        save_home_models(None, df_model, replace_missing=False)
        st.session_state['home_modelo_estoque_df'] = df_model.copy()
        st.session_state['df_modelo_estoque'] = df_model.copy()
        st.session_state['modelo_estoque_df'] = df_model.copy()
    elif model_type == 'precos':
        st.session_state['home_modelo_precos_df'] = df_model.copy()
        st.session_state['df_modelo_precos'] = df_model.copy()
        st.session_state['modelo_precos_df'] = df_model.copy()
    st.session_state[DESTINATION_MODEL_UPLOAD_NAME_KEY] = file_name
    st.session_state[DESTINATION_MODEL_UPLOAD_BYTES_KEY] = csv_bytes(df_model)


def save_user_model(model_type: str, file_name: str, file_bytes: bytes) -> pd.DataFrame:
    if model_type not in MODEL_TYPES:
        raise ValueError('Tipo de modelo invalido.')
    df = read_model_bytes(file_name, file_bytes)
    if not isinstance(df, pd.DataFrame) or not len(df.columns):
        raise ValueError('A planilha enviada nao possui colunas validas.')
    ensure_dir()
    target = path_for_model(model_type, file_name)
    target.write_bytes(file_bytes)
    manifest = load_manifest()
    manifest[model_type] = {'name': file_name, 'path': str(target), 'saved_at': pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}
    save_manifest(manifest)
    sync_model_to_flow(model_type, df, file_name)
    add_audit_event('user_bling_model_saved', area='MODELOS_BLING', status='OK', details={'model_type': model_type, 'file_name': file_name, 'columns': [str(c) for c in df.columns], 'responsible_file': RESPONSIBLE_FILE})
    return df.fillna('')


def get_user_model(model_type: str) -> tuple[pd.DataFrame | None, dict[str, str] | None]:
    manifest = load_manifest()
    info = manifest.get(model_type)
    if not isinstance(info, dict):
        return None, None
    path = Path(str(info.get('path') or ''))
    if not path.exists():
        manifest.pop(model_type, None)
        save_manifest(manifest)
        return None, None
    try:
        df = read_model_bytes(path.name, path.read_bytes())
        return df.fillna(''), {'name': str(info.get('name') or path.name), 'path': str(path), 'saved_at': str(info.get('saved_at') or '')}
    except Exception as exc:
        add_audit_event('user_bling_model_read_error', area='MODELOS_BLING', status='ERRO', details={'model_type': model_type, 'error': str(exc), 'responsible_file': RESPONSIBLE_FILE})
        return None, info


def remove_user_model(model_type: str) -> None:
    manifest = load_manifest()
    info = manifest.pop(model_type, None)
    if isinstance(info, dict):
        path = Path(str(info.get('path') or ''))
        if path.exists():
            path.unlink()
    save_manifest(manifest)
    keys_by_type = {
        'cadastro': ('home_modelo_cadastro_df', 'df_modelo_cadastro', 'modelo_cadastro_df'),
        'estoque': ('home_modelo_estoque_df', 'df_modelo_estoque', 'modelo_estoque_df'),
        'precos': ('home_modelo_precos_df', 'df_modelo_precos', 'modelo_precos_df'),
    }
    for key in keys_by_type.get(model_type, ()):
        st.session_state.pop(key, None)
    add_audit_event('user_bling_model_removed', area='MODELOS_BLING', status='OK', details={'model_type': model_type, 'responsible_file': RESPONSIBLE_FILE})


__all__ = ['MODEL_LABELS', 'MODEL_TYPES', 'csv_bytes', 'get_user_model', 'remove_user_model', 'save_user_model', 'sync_model_to_flow']
