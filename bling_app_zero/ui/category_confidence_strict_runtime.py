from __future__ import annotations

import importlib.abc
import importlib.machinery
import sys
from types import ModuleType
from typing import Any

RESPONSIBLE_FILE = 'bling_app_zero/ui/category_confidence_strict_runtime.py'
TARGET_MODULE = 'bling_app_zero.ui.universal_flow'
STRICT_CATEGORY_CONFIDENCE = 1.0


def _audit(event: str, *, status: str = 'OK', details: dict[str, Any] | None = None) -> None:
    try:
        from bling_app_zero.core.audit import add_audit_event
        add_audit_event(event, area='UNIVERSAL', status=status, details={**(details or {}), 'responsible_file': RESPONSIBLE_FILE})
    except Exception:
        pass


def patch_universal_flow(module: ModuleType) -> None:
    if getattr(module, '_mapeiaai_category_confidence_strict_patched', False):
        return

    def _render_category_group_strict(source):
        module.st.markdown('### 4. Categorização inteligente')
        enabled = module.st.toggle('Categorização inteligente', value=False, key='mapeiaai_universal_toggle_category')
        if not enabled:
            module.st.caption('Desligado. As categorias serão mantidas como vieram da origem/mapeamento.')
            module._audit('mapear_planilha_grupo_categoria_toggle', enabled=False, grouped_toggle=True, strict_confidence=True)
            return source, False
        try:
            analyzed, stats = module.classify_dataframe(source)
            module.st.session_state['mapeiaai_universal_category_confidence_min'] = STRICT_CATEGORY_CONFIDENCE
            output, applied = module.apply_category_suggestions(analyzed, confidence_min=STRICT_CATEGORY_CONFIDENCE, keep_helper_columns=True)
        except Exception as exc:
            module.st.warning(f'Categorização não aplicada: {exc}')
            module._audit('mapear_planilha_grupo_categoria_toggle', enabled=True, grouped_toggle=True, applied=False, error=str(exc)[:220], strict_confidence=True)
            return source, True
        module.st.success(f'Categorização analisada com confiança 100%: {stats.get("total", 0)} produto(s), {applied} categoria(s) aplicada(s).')
        module._audit('mapear_planilha_grupo_categoria_toggle', enabled=True, grouped_toggle=True, applied=True, rows=int(len(output)), confidence_min=STRICT_CATEGORY_CONFIDENCE, slider_removed=True, strict_confidence=True)
        return output, True

    module._render_category_group = _render_category_group_strict
    module._mapeiaai_category_confidence_strict_patched = True
    _audit('category_confidence_strict_runtime_installed', details={'confidence_min': STRICT_CATEGORY_CONFIDENCE, 'slider_removed': True, 'target': TARGET_MODULE})


class _PatchLoader(importlib.abc.Loader):
    def __init__(self, wrapped: importlib.abc.Loader) -> None:
        self._wrapped = wrapped

    def create_module(self, spec):
        creator = getattr(self._wrapped, 'create_module', None)
        return creator(spec) if creator else None

    def exec_module(self, module: ModuleType) -> None:
        self._wrapped.exec_module(module)
        if getattr(module, '__name__', '') == TARGET_MODULE:
            patch_universal_flow(module)


class _PatchFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname: str, path=None, target=None):
        if fullname != TARGET_MODULE:
            return None
        spec = importlib.machinery.PathFinder.find_spec(fullname, path)
        if spec and spec.loader and not isinstance(spec.loader, _PatchLoader):
            spec.loader = _PatchLoader(spec.loader)
        return spec


def install() -> None:
    loaded = sys.modules.get(TARGET_MODULE)
    if loaded is not None:
        patch_universal_flow(loaded)
    if not any(isinstance(finder, _PatchFinder) for finder in sys.meta_path):
        sys.meta_path.insert(0, _PatchFinder())


install()

__all__ = ['install', 'patch_universal_flow']
