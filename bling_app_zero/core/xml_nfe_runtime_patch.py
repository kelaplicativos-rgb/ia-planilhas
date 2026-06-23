from __future__ import annotations

import re
from typing import Any, Callable

from bling_app_zero.core.audit import add_audit_event

RESPONSIBLE_FILE = 'bling_app_zero/core/xml_nfe_runtime_patch.py'
NFE_COST_COLUMN = 'Custo unitário calculado NFe'
NFE_COST_ALIAS_COLUMNS = ('Preço de compra', 'Preço de custo')
TAX_VALUE_SUFFIXES = ('vICMS', 'vIPI', 'vPIS', 'vCOFINS', 'vII', 'vFCP', 'vST', 'vICMSST')


def _to_number(value: object) -> float:
    text = str(value or '').strip().replace('R$', '').replace('%', '').replace(' ', '')
    if not text:
        return 0.0
    text = re.sub(r'[^0-9,.-]+', '', text)
    if ',' in text and '.' in text:
        text = text.replace('.', '').replace(',', '.')
    elif ',' in text:
        text = text.replace(',', '.')
    try:
        return float(text)
    except Exception:
        return 0.0


def _fmt(value: float) -> str:
    if value <= 0:
        return ''
    return f'{value:.2f}'.replace('.', ',')


def _first_number(row: dict[str, str], *keys: str) -> float:
    for key in keys:
        value = _to_number(row.get(key, ''))
        if value:
            return value
    return 0.0


def _sum_tax_values(row: dict[str, str]) -> float:
    total = 0.0
    for key, value in row.items():
        suffix = str(key or '').rsplit('.', 1)[-1]
        if suffix in TAX_VALUE_SUFFIXES:
            total += _to_number(value)
    return total


def _apply_nfe_unit_cost(row: dict[str, str]) -> dict[str, str]:
    out = dict(row or {})
    quantity = _first_number(out, 'qCom', 'qTrib', 'quantidade', 'Quantidade')
    if quantity <= 0:
        return out

    product_value = _first_number(out, 'vProd', 'valorProduto', 'Valor Produto')
    freight = _first_number(out, 'vFrete', 'frete', 'Frete')
    insurance = _first_number(out, 'vSeg', 'seguro', 'Seguro')
    other = _first_number(out, 'vOutro', 'outras', 'Outras despesas')
    discount = _first_number(out, 'vDesc', 'desconto', 'Desconto')
    taxes = _sum_tax_values(out)

    total_cost = product_value + freight + insurance + other + taxes - discount
    unit_cost = total_cost / quantity if total_cost > 0 else 0.0
    formatted = _fmt(unit_cost)
    if formatted:
        out[NFE_COST_COLUMN] = formatted
        for alias in NFE_COST_ALIAS_COLUMNS:
            out.setdefault(alias, formatted)
        out['Base cálculo custo NFe'] = _fmt(total_cost)
        out['Impostos somados NFe'] = _fmt(taxes)
    return out


def install_xml_nfe_runtime_patch() -> bool:
    try:
        from bling_app_zero.core import files
    except Exception as exc:
        add_audit_event('xml_nfe_runtime_patch_import_failed', area='XML_NFE', status='AVISO', details={'error': str(exc)[:220], 'responsible_file': RESPONSIBLE_FILE})
        return False

    if getattr(files, '_blingfix_xml_nfe_runtime_patch_installed', False):
        return False

    original: Callable[..., Any] | None = getattr(files, '_blingfix_original_nfe_item_to_row', None)
    if original is None:
        original = files._nfe_item_to_row
        setattr(files, '_blingfix_original_nfe_item_to_row', original)

    def nfe_item_to_row_with_unit_cost(det):
        row = original(det)
        return _apply_nfe_unit_cost(row)

    files._nfe_item_to_row = nfe_item_to_row_with_unit_cost
    files._blingfix_xml_nfe_runtime_patch_installed = True
    add_audit_event(
        'xml_nfe_runtime_patch_installed',
        area='XML_NFE',
        status='OK',
        details={
            'formula': '(vProd + vFrete + vSeg + vOutro + impostos - vDesc) / quantidade',
            'cost_column': NFE_COST_COLUMN,
            'alias_columns': list(NFE_COST_ALIAS_COLUMNS),
            'responsible_file': RESPONSIBLE_FILE,
        },
    )
    return True


__all__ = ['install_xml_nfe_runtime_patch']
