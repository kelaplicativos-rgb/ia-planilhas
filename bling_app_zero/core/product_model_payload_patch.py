from __future__ import annotations

import importlib.abc
import importlib.machinery
import math
import re
import sys
from types import ModuleType
from typing import Any

RESPONSIBLE_FILE = 'bling_app_zero/core/product_model_payload_patch.py'
TARGET_MODULES = {'bling_app_zero.core.bling_direct_sender_smart', 'bling_app_zero.core.verified_api_sender'}


def _audit(event: str, details: dict[str, Any] | None = None, status: str = 'OK') -> None:
    try:
        from bling_app_zero.core.audit import add_audit_event
        add_audit_event(event, area='BLING_ENVIO', status=status, details={**(details or {}), 'responsible_file': RESPONSIBLE_FILE})
    except Exception:
        pass


def _blank(value: Any) -> bool:
    if value is None:
        return True
    try:
        if isinstance(value, float) and math.isnan(value):
            return True
    except Exception:
        pass
    text = str(value).strip()
    return text == '' or text.lower() in {'nan', 'none', 'nat'}


def _norm(value: object) -> str:
    text = str(value or '').strip().lower()
    for old, new in {'ã':'a','á':'a','à':'a','â':'a','é':'e','ê':'e','í':'i','ó':'o','ô':'o','õ':'o','ú':'u','ç':'c'}.items():
        text = text.replace(old, new)
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9]+', ' ', text)).strip()


def _row(row: Any, *names: str) -> str:
    wanted = {_norm(name) for name in names}
    try:
        items = row.items()
    except Exception:
        return ''
    for key, value in items:
        if _norm(key) in wanted:
            return '' if _blank(value) else str(value).strip()
    return ''


def _num(module: ModuleType, value: object) -> float | None:
    if _blank(value):
        return None
    try:
        return module._number_value(value)
    except Exception:
        return None


def _api_num(module: ModuleType, value: object) -> int | float | None:
    number = _num(module, value)
    if number is None or number < 0:
        return None
    return module._api_number(number)


def _link(row: Any) -> str:
    value = _row(row, 'Link Externo')
    return value if value.startswith(('http://', 'https://')) else ''


def _model_id(row: Any) -> str:
    value = _row(row, 'ID', 'ID Produto', 'IdProduto')
    digits = re.sub(r'\D+', '', value)
    return digits if digits else ''


def _status(value: str) -> str:
    return 'I' if _norm(value) in {'inativo', 'desativado', 'inactive'} else 'A'


def _yes_no(value: str) -> bool | None:
    text = _norm(value)
    if text in {'sim', 's', 'yes', 'true', '1'}:
        return True
    if text in {'nao', 'não', 'n', 'no', 'false', '0'}:
        return False
    return None


def _extend_aliases(current: tuple[str, ...], *new_values: str) -> tuple[str, ...]:
    out = list(current or tuple())
    seen = {str(item).strip().lower() for item in out}
    for value in new_values:
        text = str(value or '').strip()
        if text and text.lower() not in seen:
            out.append(text)
            seen.add(text.lower())
    return tuple(out)


def _enrich(module: ModuleType, payload: dict[str, Any], row: Any, meta: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    out = dict(payload or {})
    meta = dict(meta or {})
    product_id = _model_id(row)
    if product_id:
        meta['code'] = product_id
        meta['bling_product_id'] = product_id
        meta['product_id_source'] = 'modelo_oficial_id'
    for source, target in [('Código','codigo'), ('Unidade','unidade'), ('Condição do produto','condicao'), ('Departamento','departamento')]:
        value = _row(row, source)
        if value:
            out[target] = value[:80] if target == 'codigo' else value[:120]
    if out.get('unidade'):
        out['unidade'] = str(out['unidade']).upper()[:6]
    situation = _row(row, 'Situação', 'Situacao')
    if situation:
        out['situacao'] = _status(situation)
    link = _link(row)
    if link:
        out['linkExterno'] = link
    short = _row(row, 'Descrição Curta', 'Descricao Curta')
    if short:
        out['descricaoCurta'] = short[:3500]
    for source, target in [('Preço de compra','precoCusto'), ('Peso líquido (Kg)','pesoLiquido'), ('Peso bruto (Kg)','pesoBruto'), ('Volumes','volumes'), ('Itens p/ caixa','itensPorCaixa')]:
        number = _api_num(module, _row(row, source, source.replace('ç','c')))
        if number is not None:
            out[target] = number
    dims = dict(out.get('dimensoes') or {}) if isinstance(out.get('dimensoes'), dict) else {}
    for source, target in [('Largura do Produto','largura'), ('Altura do Produto','altura'), ('Profundidade do produto','profundidade')]:
        number = _api_num(module, _row(row, source))
        if number is not None and number > 0:
            dims[target] = number
    measure_unit = _row(row, 'Unidade de medida')
    if measure_unit:
        dims['unidadeMedida'] = measure_unit
    if dims:
        out['dimensoes'] = dims
    free_shipping = _yes_no(_row(row, 'Frete Grátis', 'Frete Gratis'))
    if free_shipping is not None:
        out['freteGratis'] = free_shipping
    return module._clean_payload(out), meta


def patch_smart_sender(module: ModuleType) -> None:
    if getattr(module, '_mapeiaai_product_model_payload_patched', False):
        return
    aliases = getattr(module, 'COLUMN_ALIASES', None)
    if isinstance(aliases, dict):
        aliases['id'] = _extend_aliases(aliases.get('id', tuple()), 'ID', 'ID Produto', 'IdProduto')
        aliases['imagens'] = _extend_aliases(aliases.get('imagens', tuple()), 'URL Imagens Externas')
    original_base = module._base_payload
    original_resolve = module._resolve_product_id
    def _base_payload(row, mapping):
        base, meta = original_base(row, mapping)
        return (base, meta) if not base else _enrich(module, base, row, meta)
    def _resolve_product_id(token: dict[str, Any], candidates):
        for candidate in candidates:
            value = str(candidate or '').strip()
            if value.isdigit() and len(value) >= 5:
                try:
                    response = module.requests.get(module._url(f'/produtos/{value}'), headers=module._headers(token), timeout=module.LOOKUP_TIMEOUT)
                    if response.status_code < 400:
                        return value
                except Exception:
                    pass
        return original_resolve(token, candidates)
    module._base_payload = _base_payload
    module._resolve_product_id = _resolve_product_id
    module._mapeiaai_product_model_payload_patched = True
    _audit('product_model_payload_patch_installed', {'rule': 'modelo oficial cadastro; ID direto; NaN vazio; Link Externo exato; Unidade preservada'})


def patch_verified_sender(module: ModuleType) -> None:
    if getattr(module, '_mapeiaai_product_model_verified_patched', False):
        return
    original_row_link = module._row_link
    original_force = module._force_default_fields
    def _row_link(row: Any) -> str:
        return _link(row) or original_row_link(row)
    def _force_default_fields(payload: dict[str, Any], row: Any | None = None) -> dict[str, Any]:
        updated = original_force(payload, row)
        if row is not None:
            unit = _row(row, 'Unidade')
            if unit:
                updated['unidade'] = unit.upper()[:6]
            link = _link(row)
            if link:
                updated['linkExterno'] = link
        return updated
    module._row_link = _row_link
    module._force_default_fields = _force_default_fields
    try:
        import bling_app_zero.core.bling_direct_sender_smart as smart
        patch_smart_sender(smart)
        module._payload_variants = smart._payload_variants
        module._resolve_product_id = smart._resolve_product_id
    except Exception:
        pass
    module._mapeiaai_product_model_verified_patched = True
    _audit('product_model_verified_sender_patch_installed', {'rule': 'sender verificado usa modelo oficial e preserva unidade/link'})


def _patch_module(module: ModuleType) -> None:
    name = getattr(module, '__name__', '')
    if name == 'bling_app_zero.core.bling_direct_sender_smart':
        patch_smart_sender(module)
    elif name == 'bling_app_zero.core.verified_api_sender':
        patch_verified_sender(module)


class _PatchLoader(importlib.abc.Loader):
    def __init__(self, wrapped: importlib.abc.Loader) -> None:
        self._wrapped = wrapped
    def create_module(self, spec):
        creator = getattr(self._wrapped, 'create_module', None)
        return creator(spec) if creator else None
    def exec_module(self, module: ModuleType) -> None:
        self._wrapped.exec_module(module)
        _patch_module(module)


class _PatchFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname: str, path=None, target=None):
        if fullname not in TARGET_MODULES:
            return None
        spec = importlib.machinery.PathFinder.find_spec(fullname, path)
        if spec and spec.loader and not isinstance(spec.loader, _PatchLoader):
            spec.loader = _PatchLoader(spec.loader)
        return spec


def install() -> None:
    for name in list(TARGET_MODULES):
        module = sys.modules.get(name)
        if module is not None:
            _patch_module(module)
    if not any(isinstance(finder, _PatchFinder) for finder in sys.meta_path):
        sys.meta_path.insert(0, _PatchFinder())


install()

__all__ = ['install', 'patch_smart_sender', 'patch_verified_sender']
