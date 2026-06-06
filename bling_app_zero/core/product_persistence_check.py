from __future__ import annotations

from typing import Any

REQUIRED_PRODUCT_FIELDS = (
    'nome',
    'codigo',
    'preco',
    'descricaoCurta',
    'marca',
    'categoria',
    'pesoLiquido',
    'pesoBruto',
    'dimensoes',
    'volumes',
    'itensPorCaixa',
    'imagens',
)
IMPORTANT_PRODUCT_FIELDS = REQUIRED_PRODUCT_FIELDS


def _filled(value: Any) -> bool:
    if isinstance(value, dict):
        return bool(value) and any(_filled(item) for item in value.values())
    if isinstance(value, list):
        return bool(value) and any(_filled(item) for item in value)
    return value not in (None, '', {}, [])


def _nonzero(value: Any) -> bool:
    try:
        return float(value) != 0.0
    except Exception:
        return _filled(value)


def _has_images(saved: dict[str, Any]) -> bool:
    if not isinstance(saved, dict):
        return False
    midia = saved.get('midia') if isinstance(saved.get('midia'), dict) else {}
    imagens = (
        saved.get('imagens')
        or midia.get('imagens')
        or midia.get('externas')
        or midia.get('internas')
        or midia.get('imagensURL')
    )
    return _filled(imagens)


def product_persistence_flags(saved: dict[str, Any]) -> dict[str, bool]:
    if not isinstance(saved, dict):
        saved = {}
    dims = saved.get('dimensoes') if isinstance(saved.get('dimensoes'), dict) else {}
    return {
        'nome': _filled(saved.get('nome')),
        'codigo': _filled(saved.get('codigo')),
        'preco': saved.get('preco') not in (None, ''),
        'descricaoCurta': _filled(saved.get('descricaoCurta')),
        'descricaoComplementar': _filled(saved.get('descricaoComplementar')),
        'marca': _filled(saved.get('marca')),
        'categoria': _filled(saved.get('categoria')),
        'pesoLiquido': _nonzero(saved.get('pesoLiquido')),
        'pesoBruto': _nonzero(saved.get('pesoBruto')),
        'dimensoes': bool(dims) and any(_nonzero(value) for value in dims.values()),
        'volumes': _nonzero(saved.get('volumes')),
        'itensPorCaixa': _nonzero(saved.get('itensPorCaixa')),
        'imagens': _has_images(saved),
    }


def missing_product_fields(saved: dict[str, Any], fields: tuple[str, ...] = REQUIRED_PRODUCT_FIELDS) -> list[str]:
    flags = product_persistence_flags(saved)
    return [field for field in fields if not flags.get(field)]


__all__ = ['IMPORTANT_PRODUCT_FIELDS', 'REQUIRED_PRODUCT_FIELDS', 'missing_product_fields', 'product_persistence_flags']
