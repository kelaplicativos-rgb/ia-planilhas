from __future__ import annotations

import importlib.abc
import importlib.machinery
import re
import sys
from types import ModuleType
from typing import Any

RESPONSIBLE_FILE = 'bling_app_zero/core/product_model_payload_patch.py'
TARGET_MODULES = {
    'bling_app_zero.core.bling_direct_sender_smart',
    'bling_app_zero.core.verified_api_sender',
}


def _audit(event: str, *, status: str = 'OK', details: dict[str, Any] | None = None) -> None:
    try:
        from bling_app_zero.core.audit import add_audit_event
        add_audit_event(event, area='BLING_ENVIO', status=status, details={**(details or {}), 'responsible_file': RESPONSIBLE_FILE})
    except Exception:
        pass


def _extend_aliases(current: tuple[str, ...], *new_values: str) -> tuple[str, ...]:
    out = list(current or tuple())
    seen = {str(item).strip().lower() for item in out}
    for value in new_values:
        text = str(value or '').strip()
        key = text.lower()
        if text and key not in seen:
            out.append(text)
            seen.add(key)
    return tuple(out)


def _is_blank(value: Any) -> bool:
    if value is None:
        return True
    try:
        import pandas as pd
        if pd.isna(value):
            return True
    except Exception:
        pass
    text = str(value).strip()
    return text == '' or text.lower() in {'nan', 'none', 'nat'}


def _norm(value: object) -> str:
    text = str(value or '').strip().lower()
    for old, new in {'ã': 'a', 'á': 'a', 'à': 'a', 'â': 'a', 'é': 'e', 'ê': 'e', 'í': 'i', 'ó': 'o', 'ô': 'o', 'õ': 'o', 'ú': 'u', 'ç': 'c'}.items():
        text = text.replace(old, new)
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9]+', ' ', text)).strip()


def _row_value(row: Any, *names: str) -> str:
    try:
        items = list(row.items())
    except Exception:
        return ''
    wanted = {_norm(name) for name in names}
    for key, value in items:
        if _norm(key) in wanted:
            return '' if _is_blank(value) else str(value).strip()
    return ''


def _number(module: ModuleType, value: object) -> float | None:
    if _is_blank(value):
        return None
    try:
        return module._number_value(value)
    except Exception:
        text = str(value or '').strip().replace('R$', '').replace('\xa0', '').replace(' ', '')
        if not text:
            return None
        text = text.replace('.', '').replace(',', '.') if ',' in text and '.' in text else text.replace(',', '.')
        text = re.sub(r'[^0-9.\-]+', '', text)
        try:
            return float(text) if text not in {'', '-', '.', '-.'} else None
        except Exception:
            return None


def _put_number(module: ModuleType, payload: dict[str, Any], key: str, value: object, *, positive: bool = False) -> None:
    number = _number(module, value)
    if number is None:
        return
    if positive and number <= 0:
        return
    if number < 0:
        return
    payload[key] = module._api_number(number)


def _exact_link_externo(row: Any) -> str:
    link = _row_value(row, 'Link Externo')
    if link.startswith(('http://', 'https://')):
        return link
    return ''


def _official_id(row: Any) -> str:
    value = _row_value(row, 'ID', 'ID Produto', 'IdProduto')
    digits = re.sub(r'\D+', '', value)
    return digits if digits else value.strip()


def _status(value: str) -> str:
    text = _norm(value)
    if text in {'inativo', 'inactive', 'desativado'}:
        return 'I'
    return 'A'


def _yes_no_bool(value: str) -> bool | None:
    text = _norm(value)
    if text in {'sim', 's', 'yes', 'true', '1'}:
        return True
    if text in {'nao', 'não', 'n', 'no', 'false', '0'}:
        return False
    return None


def _enrich_payload_from_official_model(module: ModuleType, payload: dict[str, Any], row: Any, meta: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    out = dict(payload or {})
    meta_out = dict(meta or {})

    model_id = _official_id(row)
    if model_id:
        meta_out['bling_product_id'] = model_id
        meta_out['code'] = model_id
        meta_out['product_id_source'] = 'modelo_oficial_id'

    code = _row_value(row, 'Código', 'Codigo')
    if code and not out.get('codigo'):
        out['codigo'] = code[:80]

    unit = _row_value(row, 'Unidade')
    if unit:
        out['unidade'] = unit[:6].upper()

    status = _row_value(row, 'Situação', 'Situacao')
    if status:
        out['situacao'] = _status(status)

    condition = _row_value(row, 'Condição do produto', 'Condicao do produto')
    if condition:
        out['condicao'] = condition

    department = _row_value(row, 'Departamento')
    if department:
        out['departamento'] = department

    link = _exact_link_externo(row)
    if link:
        out['linkExterno'] = link

    short_description = _row_value(row, 'Descrição Curta', 'Descricao Curta')
    if short_description:
        out['descricaoCurta'] = short_description[:3500]

    complement = _row_value(row, 'Descrição Complementar', 'Descricao Complementar', 'Informações Adicionais', 'Informacoes Adicionais')
    if complement and complement.strip() and complement.strip() != short_description.strip():
        out['descricaoComplementar'] = complement[:3500]

    _put_number(module, out, 'precoCusto', _row_value(row, 'Preço de compra', 'Preco de compra', 'Preço de Compra', 'Preco de Compra'))
    _put_number(module, out, 'pesoLiquido', _row_value(row, 'Peso líquido (Kg)', 'Peso liquido (Kg)'))
    _put_number(module, out, 'pesoBruto', _row_value(row, 'Peso bruto (Kg)'))
    _put_number(module, out, 'volumes', _row_value(row, 'Volumes'))
    _put_number(module, out, 'itensPorCaixa', _row_value(row, 'Itens p/ caixa', 'Itens por caixa'))

    dimensoes = dict(out.get('dimensoes') or {}) if isinstance(out.get('dimensoes'), dict) else {}
    for column, key in (('Largura do Produto', 'largura'), ('Altura do Produto', 'altura'), ('Profundidade do produto', 'profundidade')):
        number = _number(module, _row_value(row, column))
        if number is not None and number > 0:
            dimensoes[key] = module._api_number(number)
    measure_unit = _row_value(row, 'Unidade de medida')
    if measure_unit:
        dimensoes['unidadeMedida'] = measure_unit
    if dimensoes:
        out['dimensoes'] = dimensoes

    free_shipping = _yes_no_bool(_row_value(row, 'Frete Grátis', 'Frete Gratis'))
    if free_shipping is not None:
        out['freteGratis'] = free_shipping

    gtin_pack = re.sub(r'\D+', '', _row_value(row, 'GTIN/EAN da embalagem'))
    if len(gtin_pack) in {8, 12, 13, 14}:
        tributacao = dict(out.get('tributacao') or {}) if isinstance(out.get('tributacao'), dict) else {}
        tributacao['gtinEmbalagem'] = gtin_pack
        out['tributacao'] = tributacao

    return module._clean_payload(out), meta_out


def patch_smart_sender(module: ModuleType) -> None:
    if getattr(module, '_mapeiaai_product_model_payload_patched', False):
        return
    aliases = getattr(module, 'COLUMN_ALIASES', None)
    if isinstance(aliases, dict):
        aliases['id'] = _extend_aliases(aliases.get('id', tuple()), 'ID', 'ID Produto', 'IdProduto', 'id produto bling')
        aliases['imagens'] = _extend_aliases(aliases.get('imagens', tuple()), 'URL Imagens Externas', 'url imagens externas')
        aliases['link_externo'] = _extend_aliases(aliases.get('link_externo', tuple()), 'Link Externo', 'link externo')
        aliases['preco_compra'] = _extend_aliases(aliases.get('preco_compra', tuple()), 'Preço de compra', 'Preco de compra')
        aliases['unidade_medida'] = _extend_aliases(aliases.get('unidade_medida', tuple()), 'Unidade de medida')

    original_resolve = module._resolve_product_id
    original_base = module._base_payload

    def _resolve_product_id_model(token: dict[str, Any], candidates):
        for candidate in candidates:
            value = str(candidate or '').strip()
            if value.isdigit() and len(value) >= 5:
                try:
                    response = module.requests.get(module._url(f'/produtos/{value}'), headers=module._headers(token), timeout=module.LOOKUP_TIMEOUT)
                    if response.status_code < 400:
                        data = response.json() if str(response.text or '').strip() else {}
                        item_id = str(data.get('id') or data.get('idProduto') or value).strip() if isinstance(data, dict) else value
                        if item_id:
                            _audit('product_model_resolved_by_direct_id', details={'candidate': value, 'product_id': item_id})
                            return item_id
                except Exception as exc:
                    _audit('product_model_direct_id_lookup_exception', status='AVISO', details={'candidate': value, 'error': str(exc)[:180]})
        return original_resolve(token, candidates)

    def _base_payload_model(row, mapping):
        base, meta = original_base(row, mapping)
        if not base:
            return base, meta
        return _enrich_payload_from_official_model(module, base, row, meta)

    module._resolve_product_id = _resolve_product_id_model
    module._base_payload = _base_payload_model
    module._mapeiaai_product_model_payload_patched = True
    _audit('product_model_payload_patch_installed', details={'model_columns': ['ID', 'Código', 'Descrição', 'Unidade', 'Preço', 'Estoque', 'Marca', 'Descrição Curta', 'URL Imagens Externas', 'Link Externo', 'Preço de compra', 'Categoria do produto']})


def patch_verified_sender(module: ModuleType) -> None:
    if getattr(module, '_mapeiaai_product_model_verified_patched', False):
        return
    original_row_link = module._row_link
    original_force_defaults = module._force_default_fields

    def _row_link_model(row: Any) -> str:
        link = _exact_link_externo(row)
        return link or original_row_link(row)

    def _force_default_fields_model(payload: dict[str, Any], row: Any | None = None) -> dict[str, Any]:
        updated = original_force_defaults(payload, row)
        if row is not None:
            unit = _row_value(row, 'Unidade')
            if unit:
                updated['unidade'] = unit[:6].upper()
            link = _exact_link_externo(row)
            if link:
                updated['linkExterno'] = link
        return updated

    module._row_link = _row_link_model
    module._force_default_fields = _force_default_fields_model
    try:
        import bling_app_zero.core.bling_direct_sender_smart as smart
        patch_smart_sender(smart)
        module._payload_variants = smart._payload_variants
        module._resolve_product_id = smart._resolve_product_id
    except Exception:
        pass
    module._mapeiaai_product_model_verified_patched = True
    _audit('product_model_verified_sender_patch_installed', details={'rule': 'Link Externo preferido; Unidade oficial preservada; ID usado para atualização delta quando existir'})


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
        create_module = getattr(self._wrapped, 'create_module', None)
        return create_module(spec) if create_module is not None else None

    def exec_module(self, module: ModuleType) -> None:
        self._wrapped.exec_module(module)
        _patch_module(module)


class _PatchFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname: str, path=None, target=None):
        if fullname not in TARGET_MODULES:
            return None
        spec = importlib.machinery.PathFinder.find_spec(fullname, path)
        if spec is None or spec.loader is None or isinstance(spec.loader, _PatchLoader):
            return spec
        spec.loader = _PatchLoader(spec.loader)
        return spec


def install() -> None:
    for module_name in list(TARGET_MODULES):
        loaded = sys.modules.get(module_name)
        if loaded is not None:
            _patch_module(loaded)
    if not any(isinstance(finder, _PatchFinder) for finder in sys.meta_path):
        sys.meta_path.insert(0, _PatchFinder())


install()

__all__ = ['install', 'patch_smart_sender', 'patch_verified_sender']
