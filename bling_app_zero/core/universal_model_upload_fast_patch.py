from __future__ import annotations

import hashlib
import importlib.abc
import importlib.machinery
import sys
from types import ModuleType
from typing import Any

RESPONSIBLE_FILE = 'bling_app_zero/core/universal_model_upload_fast_patch.py'
TARGET_MODULE = 'bling_app_zero.ui.universal_flow'
TARGET_ROUTER_MODULE = 'bling_app_zero.ui.home_router_v2'
PATCH_VERSION = 'fast_contract_first_20260624_light_v3_preservation_near_upload_and_reset_guard'
MODEL_FILE_NAME_KEY = 'mapeiaai_universal_model_file_name'
MODEL_FILE_BYTES_KEY = 'mapeiaai_universal_model_file_bytes'
MODEL_LAST_READ_SIGNATURE_KEY = 'mapeiaai_universal_model_fast_patch_last_read_signature_v1'
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


def _safe(value: Any, limit: int = 500) -> str:
    text = str(value if value is not None else '').replace('\x00', '').strip()
    return text[:limit] + '...' if len(text) > limit else text


def _sha16(data: bytes) -> str:
    return hashlib.sha256(bytes(data or b'')).hexdigest()[:16]


def _state_from_module(module: ModuleType | None = None) -> Any | None:
    st = getattr(module, 'st', None) if module is not None else sys.modules.get('streamlit')
    if st is None:
        return None
    try:
        return st.session_state
    except Exception:
        return None


def _audit(event: str, *, module: ModuleType | None = None, important: bool = False, **details: Any) -> None:
    """Audita só o necessário.

    O diagnóstico de boot já foi desligado. Este patch continua funcional, mas
    evita gravar eventos repetidos a cada rerun/leitura normal de arquivo.
    """
    status = str(details.pop('status', 'OK'))
    if not important and status == 'OK':
        return
    payload = {'responsible_file': RESPONSIBLE_FILE, 'patch_version': PATCH_VERSION, **details}
    try:
        from bling_app_zero.core.audit import add_audit_event
        add_audit_event(event, area='MODELO', status=status, details=payload)
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
        _audit('universal_model_contract_first_failed', module=module, important=True, file_name=name, error_type=type(exc).__name__, error=_safe(exc, 300), status='AVISO')
    return None


def _should_log_read(module: ModuleType, signature: str) -> bool:
    state = _state_from_module(module)
    if state is None:
        return False
    try:
        previous = str(state.get(MODEL_LAST_READ_SIGNATURE_KEY) or '')
        if previous == signature:
            return False
        state[MODEL_LAST_READ_SIGNATURE_KEY] = signature
        return True
    except Exception:
        return False


def _model_signature(module: ModuleType, model: Any) -> str:
    if not _valid_dataframe(module, model):
        return 'none'
    return f'{len(model)}x{len(model.columns)}:' + '|'.join(map(str, model.columns))


def _reset_preservation_state(module: ModuleType | None = None) -> None:
    state = _state_from_module(module)
    if state is None:
        return
    for key in PRESERVE_KEYS:
        state.pop(key, None)


def _sanitize_preservation_state(module: ModuleType, model: Any) -> None:
    state = _state_from_module(module)
    if state is None or not _valid_dataframe(module, model):
        return
    columns = [str(col) for col in model.columns]
    current_signature = _model_signature(module, model)
    previous_signature = str(state.get(PRESERVE_MODEL_SIGNATURE_KEY) or '')
    if previous_signature and previous_signature != current_signature:
        state.pop(PRESERVE_COLUMNS_KEY, None)
    state[PRESERVE_MODEL_SIGNATURE_KEY] = current_signature

    mode = str(state.get(PRESERVE_MODE_KEY) or '').strip()
    if mode and mode not in PRESERVE_MODES:
        state.pop(PRESERVE_MODE_KEY, None)

    selected = state.get(PRESERVE_COLUMNS_KEY)
    if isinstance(selected, (list, tuple, set)):
        state[PRESERVE_COLUMNS_KEY] = [str(col) for col in selected if str(col) in columns]


def _default_preserve_columns(model: Any) -> list[str]:
    columns = [str(col) for col in getattr(model, 'columns', [])]
    defaults = [col for col in CRITICAL_DEFAULT_COLUMNS if col in columns]
    return defaults or columns[: min(5, len(columns))]


def _render_model_preservation_options(module: ModuleType, model: Any) -> None:
    st = getattr(module, 'st', None)
    state = _state_from_module(module)
    if st is None or state is None or not _valid_dataframe(module, model):
        return

    _sanitize_preservation_state(module, model)
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
    state[PRESERVE_ENABLED_KEY] = preserve_enabled

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
        state[PRESERVE_COLUMNS_KEY] = []
        st.info('O modelo será usado somente como estrutura final: colunas e ordem serão mantidas.')

    if len(model) == 0:
        st.info(
            'Este modelo está sem linhas preenchidas. Mesmo assim, a estrutura e os campos críticos selecionados '
            'ficarão registrados para a montagem final.'
        )

    _audit(
        'universal_model_preservation_options_rendered_near_upload',
        module=module,
        important=True,
        mode=mode,
        enabled=bool(preserve_enabled),
        selected_columns=len(selected_columns),
        model_rows=int(len(model)),
        model_columns=int(len(model.columns)),
    )


def _patch_model_step(module: ModuleType) -> None:
    if getattr(module, '_mapeiaai_universal_model_preservation_near_upload_installed', False):
        return
    original = getattr(module, '_render_model_step', None)
    if not callable(original):
        return
    pd = getattr(module, 'pd', None)
    st = getattr(module, 'st', None)
    if pd is None or st is None:
        return

    def render_model_step_with_preservation():
        st.markdown('### 1. Anexar Modelo / Mapear')
        model = module._current_df(module.UNIVERSAL_MODEL_KEY)
        uploaded = None
        if not isinstance(model, pd.DataFrame):
            st.caption('Anexe primeiro a planilha modelo exatamente no formato que você quer receber no final.')
            uploaded = st.file_uploader('Planilha modelo final', type=None, key='mapeiaai_universal_model_upload')
            df = module._read_model_upload(uploaded)
            if isinstance(df, pd.DataFrame):
                current_sig = module._df_signature(module._current_df(module.UNIVERSAL_MODEL_KEY))
                new_sig = module._df_signature(df)
                if current_sig != 'none' and current_sig != new_sig:
                    module._clear_after_model()
                    _reset_preservation_state(module)
                module._store_df(module.UNIVERSAL_MODEL_KEY, df)
                st.session_state['home_modelo_universal_df'] = df.copy().fillna('')
                st.session_state['df_modelo_universal'] = df.copy().fillna('')
                st.session_state['modelo_universal_df'] = df.copy().fillna('')
                module._audit('mapear_planilha_modelo_anexado_primeiro', rows=int(len(df)), columns=int(len(df.columns)), original_file_name=str(getattr(uploaded, 'name', '') or ''))
            model = module._current_df(module.UNIVERSAL_MODEL_KEY)
        if not isinstance(model, pd.DataFrame):
            st.info('Envie a planilha modelo final para liberar a próxima etapa.')
            return None
        st.success('Modelo final carregado. A saída seguirá exatamente essas colunas e essa ordem.')
        _render_model_preservation_options(module, model)
        st.dataframe(model.head(3).astype(str), use_container_width=True, height=145)
        st.caption('Colunas finais: ' + ', '.join(map(str, model.columns)))
        if st.button('Continuar para origem dos dados ➡️', use_container_width=True, key='mapeiaai_universal_go_source'):
            module._set_step(module.STEP_SOURCE, 'model_confirmed')
        return model

    module._render_model_step = render_model_step_with_preservation
    module._mapeiaai_universal_model_preservation_near_upload_installed = True
    _audit('universal_model_preservation_near_upload_patch_installed', module=module, important=True, target=getattr(module, '__name__', TARGET_MODULE))


def _patch_read_model_upload(module: ModuleType) -> None:
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
        signature = f'{name}:{len(data)}:{_sha16(data)}'
        should_log = _should_log_read(module, signature)
        if st is not None and name and data:
            try:
                st.session_state[MODEL_FILE_NAME_KEY] = name
                st.session_state[MODEL_FILE_BYTES_KEY] = data
            except Exception:
                pass
        if should_log:
            _audit('universal_model_contract_first_read_start', module=module, important=True, file_name=name, byte_size=len(data))
        df = _read_contract_first(module, name, data)
        if _valid_dataframe(module, df):
            if should_log:
                _audit('universal_model_contract_first_read_ok', module=module, important=True, file_name=name, columns=int(len(df.columns)))
            return df.fillna('')
        _audit('universal_model_contract_first_fallback_original', module=module, important=should_log, file_name=name, status='AVISO')
        try:
            df = original(uploaded_file)
        except Exception as exc:
            _audit('universal_model_contract_first_original_failed', module=module, important=True, file_name=name, error_type=type(exc).__name__, error=_safe(exc, 400), status='ERRO')
            return None
        if _valid_dataframe(module, df):
            if should_log:
                _audit('universal_model_contract_first_original_ok', module=module, important=True, file_name=name, columns=int(len(df.columns)))
        else:
            _audit('universal_model_contract_first_no_columns', module=module, important=True, file_name=name, status='ERRO')
        return df

    module._read_model_upload = read_model_upload_contract_first
    module._mapeiaai_universal_model_fast_patch_installed = True
    _audit('universal_model_contract_first_patch_installed', module=module, important=False, target=getattr(module, '__name__', TARGET_MODULE))


def _patch_universal_flow_module(module: ModuleType) -> None:
    _patch_read_model_upload(module)
    _patch_model_step(module)


def _patch_home_router_module(module: ModuleType) -> None:
    if getattr(module, '_mapeiaai_universal_preservation_clear_guard_installed', False):
        return
    original = getattr(module, '_clear_universal_operation_state', None)
    if not callable(original):
        return
    state = _state_from_module(module)
    if state is None:
        return

    def clear_universal_operation_state_with_preservation_guard(*, keep_model: bool = False) -> None:
        current_state = _state_from_module(module)
        preserved = {}
        if keep_model and current_state is not None:
            preserved = {key: current_state.get(key) for key in PRESERVE_KEYS if key in current_state}
        original(keep_model=keep_model)
        current_state = _state_from_module(module)
        if current_state is None:
            return
        if keep_model:
            for key, value in preserved.items():
                current_state[key] = value
        else:
            for key in PRESERVE_KEYS:
                current_state.pop(key, None)
        _audit(
            'universal_model_preservation_state_reset_guard_applied',
            module=module,
            important=True,
            keep_model=bool(keep_model),
            preserved_keys=len(preserved),
        )

    module._clear_universal_operation_state = clear_universal_operation_state_with_preservation_guard
    module._mapeiaai_universal_preservation_clear_guard_installed = True
    _audit('universal_model_preservation_clear_guard_installed', module=module, important=True, target=getattr(module, '__name__', TARGET_ROUTER_MODULE))


def _patch_module(module: ModuleType) -> None:
    name = getattr(module, '__name__', '')
    if name == TARGET_MODULE:
        _patch_universal_flow_module(module)
    elif name == TARGET_ROUTER_MODULE:
        _patch_home_router_module(module)


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
    TARGETS = {TARGET_MODULE, TARGET_ROUTER_MODULE}

    def find_spec(self, fullname: str, path=None, target=None):
        if fullname not in self.TARGETS:
            return None
        spec = importlib.machinery.PathFinder.find_spec(fullname, path)
        if spec is None or spec.loader is None:
            return None
        if isinstance(spec.loader, _Loader):
            return spec
        spec.loader = _Loader(spec.loader)
        return spec


def _loaded_module_needs_patch(module: ModuleType) -> bool:
    name = getattr(module, '__name__', '')
    if name == TARGET_MODULE:
        return not getattr(module, '_mapeiaai_universal_model_fast_patch_installed', False) or not getattr(module, '_mapeiaai_universal_model_preservation_near_upload_installed', False)
    if name == TARGET_ROUTER_MODULE:
        return not getattr(module, '_mapeiaai_universal_preservation_clear_guard_installed', False)
    return False


def install_universal_model_upload_fast_patch() -> None:
    installed_now = False
    for target in (TARGET_MODULE, TARGET_ROUTER_MODULE):
        loaded = sys.modules.get(target)
        if loaded is not None and _loaded_module_needs_patch(loaded):
            _patch_module(loaded)
            installed_now = True
    if not any(isinstance(finder, _Finder) for finder in sys.meta_path):
        sys.meta_path.insert(0, _Finder())
        installed_now = True
    if installed_now:
        _audit('universal_model_contract_first_import_hook_installed', important=False, targets=[TARGET_MODULE, TARGET_ROUTER_MODULE])


__all__ = ['install_universal_model_upload_fast_patch']
