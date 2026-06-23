from __future__ import annotations

import importlib.abc
import importlib.machinery
import sys
from types import ModuleType
from typing import Any

RESPONSIBLE_FILE = 'bling_app_zero/core/universal_model_upload_fast_patch.py'
TARGET_MODULE = 'bling_app_zero.ui.universal_flow'
PATCH_VERSION = 'fast_contract_first_20260623_v1'
MODEL_FILE_NAME_KEY = 'mapeiaai_universal_model_file_name'
MODEL_FILE_BYTES_KEY = 'mapeiaai_universal_model_file_bytes'


def _safe(value: Any, limit: int = 500) -> str:
    text = str(value if value is not None else '').replace('\x00', '').strip()
    return text[:limit] + '...' if len(text) > limit else text


def _audit(event: str, **details: Any) -> None:
    status = str(details.pop('status', 'OK'))
    payload = {'responsible_file': RESPONSIBLE_FILE, 'patch_version': PATCH_VERSION, **details}
    try:
        from bling_app_zero.core.audit import add_audit_event
        add_audit_event(event, area='MODELO', status=status, details=payload)
    except Exception:
        pass
    try:
        from bling_app_zero.core.diagnostico_boot import boot_event
        boot_event(event, area='MODELO', status=status, details=payload)
    except Exception:
        pass


def _valid_dataframe(module: ModuleType, df: Any) -> bool:
    try:
        pd = getattr(module, 'pd', None)
        return bool(pd is not None and isinstance(df, pd.DataFrame) and len(df.columns) > 0)
    except Exception:
        return False


def _read_contract_first(module: ModuleType, name: str, data: bytes) -> Any | None:
    if not name or not data:
        return None
    suffix = name.lower().rsplit('.', 1)[-1] if '.' in name else ''
    if suffix not in {'csv', 'xlsx', 'xlsm', 'zip'}:
        return None
    try:
        reader = getattr(module, '_model_contract_from_file')
        df = reader(name, data).fillna('')
        if _valid_dataframe(module, df):
            return df
    except Exception as exc:
        _audit('universal_model_contract_first_failed', file_name=name, error_type=type(exc).__name__, error=_safe(exc, 300), status='AVISO')
    return None


def _patch_module(module: ModuleType) -> None:
    if getattr(module, '_mapeiaai_universal_model_fast_patch_installed', False):
        return
    original = getattr(module, '_read_model_upload', None)
    if not callable(original):
        return
    st = getattr(module, 'st', None)

    def read_model_upload_contract_first(uploaded_file: Any):
        if uploaded_file is None:
            return original(uploaded_file)
        name = _safe(getattr(uploaded_file, 'name', ''), 240)
        try:
            data = bytes(uploaded_file.getvalue() or b'')
        except Exception:
            data = b''
        if st is not None and name and data:
            try:
                st.session_state[MODEL_FILE_NAME_KEY] = name
                st.session_state[MODEL_FILE_BYTES_KEY] = data
            except Exception:
                pass
        _audit('universal_model_contract_first_read_start', file_name=name, byte_size=len(data))
        df = _read_contract_first(module, name, data)
        if _valid_dataframe(module, df):
            _audit('universal_model_contract_first_read_ok', file_name=name, columns=int(len(df.columns)))
            return df.fillna('')
        _audit('universal_model_contract_first_fallback_original', file_name=name, status='AVISO')
        try:
            df = original(uploaded_file)
        except Exception as exc:
            _audit('universal_model_contract_first_original_failed', file_name=name, error_type=type(exc).__name__, error=_safe(exc, 400), status='ERRO')
            return None
        if _valid_dataframe(module, df):
            _audit('universal_model_contract_first_original_ok', file_name=name, columns=int(len(df.columns)))
        else:
            _audit('universal_model_contract_first_no_columns', file_name=name, status='ERRO')
        return df

    module._read_model_upload = read_model_upload_contract_first
    module._mapeiaai_universal_model_fast_patch_installed = True
    _audit('universal_model_contract_first_patch_installed', module=getattr(module, '__name__', TARGET_MODULE))


class _Loader(importlib.abc.Loader):
    def __init__(self, wrapped: importlib.abc.Loader) -> None:
        self._wrapped = wrapped

    def create_module(self, spec):
        create_module = getattr(self._wrapped, 'create_module', None)
        if create_module is None:
            return None
        return create_module(spec)

    def exec_module(self, module: ModuleType) -> None:
        self._wrapped.exec_module(module)
        _patch_module(module)


class _Finder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname: str, path=None, target=None):
        if fullname != TARGET_MODULE:
            return None
        spec = importlib.machinery.PathFinder.find_spec(fullname, path)
        if spec is None or spec.loader is None:
            return None
        if isinstance(spec.loader, _Loader):
            return spec
        spec.loader = _Loader(spec.loader)
        return spec


def install_universal_model_upload_fast_patch() -> None:
    loaded = sys.modules.get(TARGET_MODULE)
    if loaded is not None:
        _patch_module(loaded)
    if not any(isinstance(finder, _Finder) for finder in sys.meta_path):
        sys.meta_path.insert(0, _Finder())
    _audit('universal_model_contract_first_import_hook_installed', target=TARGET_MODULE)


__all__ = ['install_universal_model_upload_fast_patch']
