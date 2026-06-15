from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from bling_app_zero.core.validators import price_validation_details, validate_price_update_values

RESPONSIBLE_FILE = 'bling_app_zero/core/bling_api_send_guard.py'


@dataclass(frozen=True)
class SendGuardResult:
    ok: bool
    status: str
    messages: tuple[str, ...]
    details: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            'ok': self.ok,
            'status': self.status,
            'messages': list(self.messages),
            'details': dict(self.details),
        }


def _operation(value: object) -> str:
    text = str(value or '').strip().lower()
    if 'estoque' in text or 'saldo' in text or 'stock' in text:
        return 'estoque'
    if 'preco' in text or 'price' in text:
        return 'atualizacao_preco'
    if 'cadastro' in text or 'produto' in text:
        return 'cadastro'
    return text or 'cadastro'


def _has_column(df: pd.DataFrame, name: str) -> bool:
    wanted = str(name or '').strip().lower()
    return any(str(col or '').strip().lower() == wanted for col in df.columns)


def _non_blank_column(df: pd.DataFrame, name: str) -> bool:
    for col in df.columns:
        if str(col or '').strip().lower() == str(name or '').strip().lower():
            return bool(df[col].fillna('').astype(str).str.strip().ne('').any())
    return False


def validate_before_bling_send(df: pd.DataFrame, operation: object) -> SendGuardResult:
    op = _operation(operation)
    messages: list[str] = []
    details: dict[str, Any] = {
        'operation': op,
        'rows': int(len(df)) if isinstance(df, pd.DataFrame) else 0,
        'responsible_file': RESPONSIBLE_FILE,
    }

    if not isinstance(df, pd.DataFrame) or df.empty:
        return SendGuardResult(False, 'BLOQUEADO', ('Nenhuma linha pronta para envio ao Bling.',), details)

    if op == 'atualizacao_preco':
        price_details = price_validation_details(df)
        details['price_columns'] = list(price_details.get('price_columns') or [])
        details['invalid_price_count'] = int(price_details.get('invalid_count') or 0)
        details['invalid_price_rows'] = list(price_details.get('invalid_rows') or [])[:30]
        messages.extend(validate_price_update_values(df, label='Envio de preços bloqueado'))

        if not _has_column(df, 'Bling preço destino'):
            messages.append('Escolha Preço geral ou Canal de venda antes de enviar preços ao Bling.')
        elif str(df['Bling preço destino'].fillna('').astype(str).iloc[0]).strip().lower() != 'preço geral':
            if not _non_blank_column(df, 'Bling canal venda id'):
                messages.append('Canal de venda selecionado sem ID do canal. Selecione a loja/canal correto.')
    elif op == 'estoque':
        if not _non_blank_column(df, 'Bling depósito id'):
            messages.append('Selecione o depósito do Bling antes de atualizar estoque.')

    if messages:
        return SendGuardResult(False, 'BLOQUEADO', tuple(messages), details)
    return SendGuardResult(True, 'OK', ('Envio liberado pela validação de destino e conteúdo.',), details)


__all__ = ['SendGuardResult', 'validate_before_bling_send']
