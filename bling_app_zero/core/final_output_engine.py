from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping

import pandas as pd

from bling_app_zero.ai.ai_text_rules import clean_title_to_limit, is_description_column, is_title_column
from bling_app_zero.core.final_csv_exporter import (
    contract_columns_from_model,
    final_csv_bytes,
    sanitize_final_dataframe,
    validate_contract_identity,
)
from bling_app_zero.core.final_output_state import STATUS_DONE, STATUS_ERROR, FinalOutputRequest, FinalOutputResult, FinalOutputState
from bling_app_zero.core.universal_smart_rules import apply_universal_smart_rules, normalize_smart_rules_config
from bling_app_zero.universal.output_builder import build_universal_output, empty_universal_output
from bling_app_zero.universal.universal_contract import UniversalContract, build_universal_contract, validate_universal_output

RESPONSIBLE_FILE = 'bling_app_zero/core/final_output_engine.py'
CATEGORY_SOURCE_PRIORITY = ('Categoria do produto', 'Categoria', 'categoria', 'category', 'categoria_sugerida_ia')
EMPTY_CATEGORY_MARKERS = {'', 'nan', 'none', 'null', '<na>', 'revisar manualmente'}
SAFE_TARGET_SOURCE_ALIASES = {
    'preco de compra': ('preco de compra', 'preco compra', 'preco de custo', 'preco custo', 'custo', 'valor custo'),
    'cod no fornecedor': ('cod no fornecedor', 'cod fornecedor', 'codigo no fornecedor', 'codigo fornecedor', 'cod no fornecedor'),
    'codigo da lista de servicos': ('codigo da lista de servicos', 'codigo na lista de servicos'),
    'gtin ean da embalagem': ('gtin ean da embalagem',),
    'largura do produto': ('largura do produto', 'largura produto'),
    'condicao do produto': ('condicao do produto', 'condicao produto'),
    'unidade de medida': ('unidade de medida', 'unidade medida'),
    'estoque maximo': ('estoque maximo', 'estoque max'),
    'estoque minimo': ('estoque minimo', 'estoque min'),
}


@dataclass(frozen=True)
class FinalOutputCommandResult:
    state: FinalOutputState
    output: pd.DataFrame | None = None
    csv_bytes: bytes = b''
    smartcore_result: Any = None
    errors: tuple[str, ...] = ()
    smart_rules_report: dict[str, Any] | None = None


def _clean_cell(value: Any) -> str:
    return '' if value is None else str(value).strip()


def _norm_column(value: Any) -> str:
    text = _clean_cell(value).casefold()
    text = text.replace('ç', 'c').replace('ã', 'a').replace('á', 'a').replace('à', 'a').replace('â', 'a')
    text = text.replace('é', 'e').replace('ê', 'e').replace('í', 'i').replace('ó', 'o').replace('ô', 'o').replace('õ', 'o').replace('ú', 'u')
    text = re.sub(r'[^a-z0-9]+', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()


def _is_category_column(column: Any) -> bool:
    normalized = _norm_column(column)
    return normalized in {'categoria', 'category', 'categoria produto', 'categoria do produto'} or normalized.startswith('categoria ')


def _first_source_category_column(source: pd.DataFrame) -> str | None:
    if not isinstance(source, pd.DataFrame) or source.empty:
        return None
    exact = {_norm_column(column): str(column) for column in source.columns}
    for candidate in CATEGORY_SOURCE_PRIORITY:
        found = exact.get(_norm_column(candidate))
        if found and source[found].astype(str).str.strip().ne('').any():
            return found
    for column in source.columns:
        if _is_category_column(column) and source[column].astype(str).str.strip().ne('').any():
            return str(column)
    return None


def _clean_category_value(value: Any) -> str:
    text = _clean_cell(value)
    return '' if text.casefold() in EMPTY_CATEGORY_MARKERS else text


def _apply_safe_category_aliases(output: pd.DataFrame, source: pd.DataFrame, mapping: Mapping[str, str], *, enabled: bool) -> pd.DataFrame:
    if not enabled or not isinstance(output, pd.DataFrame) or output.empty:
        return output
    source_col = _first_source_category_column(source)
    if not source_col:
        return output

    out = output.copy().fillna('')
    source_values = source[source_col].reset_index(drop=True).map(_clean_category_value)
    if source_values.empty:
        return out

    for target_col in [str(column) for column in out.columns if _is_category_column(column)]:
        mapped_source = _clean_cell((mapping or {}).get(target_col))
        if mapped_source and mapped_source in source.columns and mapped_source != source_col:
            continue
        current = out[target_col].reset_index(drop=True).map(_clean_category_value)
        limit = min(len(current), len(source_values))
        if limit <= 0:
            continue
        merged = current.copy()
        for idx in range(limit):
            if not _clean_category_value(merged.iloc[idx]):
                merged.iloc[idx] = _clean_category_value(source_values.iloc[idx])
        out[target_col] = merged.reindex(range(len(out)), fill_value='').astype(str).values
    return out


def _source_columns_by_norm(source: pd.DataFrame) -> dict[str, str]:
    if not isinstance(source, pd.DataFrame):
        return {}
    out: dict[str, str] = {}
    for column in source.columns:
        name = str(column)
        key = _norm_column(name)
        if key and key not in out:
            out[key] = name
    return out


def _source_column_has_values(source: pd.DataFrame, column: str) -> bool:
    try:
        return bool(source[column].astype(str).str.strip().ne('').any())
    except Exception:
        return False


def _choose_alias_source(source: pd.DataFrame, normalized_sources: dict[str, str], target_column: str) -> str:
    target_key = _norm_column(target_column)
    candidates = list(SAFE_TARGET_SOURCE_ALIASES.get(target_key, ()))
    if not candidates:
        return ''
    for candidate in candidates:
        source_column = normalized_sources.get(_norm_column(candidate))
        if source_column and _source_column_has_values(source, source_column):
            return source_column
    for candidate in candidates:
        source_column = normalized_sources.get(_norm_column(candidate))
        if source_column:
            return source_column
    return ''


def _augment_mapping_with_safe_aliases(source: pd.DataFrame, contract: pd.DataFrame, mapping: Mapping[str, str]) -> dict[str, str]:
    clean_mapping = {str(key): _clean_cell(value) for key, value in dict(mapping or {}).items()}
    if not isinstance(source, pd.DataFrame) or not isinstance(contract, pd.DataFrame) or not len(contract.columns):
        return clean_mapping

    normalized_sources = _source_columns_by_norm(source)
    for target_column in [str(column) for column in contract.columns]:
        current_source = clean_mapping.get(target_column, '')
        if current_source and current_source in source.columns:
            continue
        alias_source = _choose_alias_source(source, normalized_sources, target_column)
        if alias_source:
            clean_mapping[target_column] = alias_source
        elif target_column not in clean_mapping:
            clean_mapping[target_column] = ''
    return clean_mapping


def apply_text_rules(output: pd.DataFrame) -> pd.DataFrame:
    out = output.copy().fillna('')
    for column in out.columns:
        if is_title_column(column):
            out[column] = out[column].map(clean_title_to_limit)
        elif is_description_column(column):
            out[column] = out[column].map(lambda value: re.sub(r'\s+', ' ', str(value or '').strip()))
    return out


def build_final_dataframe(source: pd.DataFrame, contract: pd.DataFrame, mapping: Mapping[str, str], *, apply_rules: bool = False) -> pd.DataFrame:
    """Monta o modelo anexado preenchido por linhas da origem.

    A regra deste fluxo é universal: o modelo anexado define somente colunas e
    ordem; os valores finais vêm da origem mapeada ou de valores fixos/manuais.
    Nenhuma linha de exemplo/instrução do modelo é copiada para o resultado.
    """
    safe_mapping = _augment_mapping_with_safe_aliases(source, contract, mapping)
    if not isinstance(source, pd.DataFrame) or source.empty:
        output = empty_universal_output(contract, rows=0)
    else:
        output = build_universal_output(source, contract, safe_mapping)
    if apply_rules:
        output = apply_text_rules(output)
    return output


def build_final_output(
    source: pd.DataFrame,
    contract: pd.DataFrame,
    mapping: Mapping[str, str],
    *,
    operation: str = 'universal',
    file_name: str = 'mapeiaai_planilha_final_mapeada.csv',
    run_smart_features: bool = True,
    smart_rules_config: Mapping[str, Any] | None = None,
) -> FinalOutputCommandResult:
    contract_columns = tuple(contract_columns_from_model(contract))
    request = FinalOutputRequest(operation=operation, file_name=file_name, contract_columns=contract_columns)
    contract_obj = build_universal_contract(contract)
    safe_mapping = _augment_mapping_with_safe_aliases(source, contract, mapping)

    # Saída universal fiel: não reescreve dados com IA. Regras inteligentes são
    # apenas tratamentos seguros e configurados pelo usuário nos valores finais.
    output = build_final_dataframe(source, contract, safe_mapping, apply_rules=False)

    rules_config = normalize_smart_rules_config(smart_rules_config, enabled=bool(run_smart_features))
    output = _apply_safe_category_aliases(
        output,
        source,
        safe_mapping,
        enabled=bool(rules_config.get('enabled')) and bool(rules_config.get('fill_category_aliases')),
    )

    errors = tuple(str(item) for item in validate_universal_output(output, contract_obj) or ())
    if errors:
        result = FinalOutputResult(status=STATUS_ERROR, file_name=file_name, errors=errors, message='Saída final bloqueada por erro de contrato.')
        return FinalOutputCommandResult(FinalOutputState(request=request, result=result), output=None, csv_bytes=b'', errors=errors)

    smartcore_result = None
    smart_rules_report: dict[str, Any] | None = None
    if bool(rules_config.get('enabled')):
        output, smart_rules_report = apply_universal_smart_rules(output, rules_config)

    output = sanitize_final_dataframe(output, operation=operation, contract_columns=list(contract_columns), run_download_features=False)

    identity_errors = tuple(str(item) for item in validate_contract_identity(output, list(contract_columns)) or ())
    if identity_errors:
        result = FinalOutputResult(status=STATUS_ERROR, file_name=file_name, errors=identity_errors, message='Saída final bloqueada por divergência de colunas.')
        return FinalOutputCommandResult(FinalOutputState(request=request, result=result), output=None, csv_bytes=b'', smartcore_result=smartcore_result, errors=identity_errors, smart_rules_report=smart_rules_report)

    try:
        csv_data = final_csv_bytes(output, operation=operation, contract_columns=list(contract_columns), run_download_features=False)
    except Exception as exc:
        csv_error = (str(exc),)
        result = FinalOutputResult(status=STATUS_ERROR, file_name=file_name, errors=csv_error, message='Saída final bloqueada por erro físico de CSV.')
        return FinalOutputCommandResult(FinalOutputState(request=request, result=result), output=None, csv_bytes=b'', smartcore_result=smartcore_result, errors=csv_error, smart_rules_report=smart_rules_report)

    result = FinalOutputResult(
        status=STATUS_DONE,
        rows=int(len(output)),
        columns=tuple(str(column) for column in output.columns),
        file_name=file_name,
        csv_size_bytes=len(csv_data),
        smartcore_score=int((smart_rules_report or {}).get('applied_cells') or 0),
        message='Modelo anexado preenchido com dados da origem.',
        warnings=tuple(),
    )
    return FinalOutputCommandResult(FinalOutputState(request=request, result=result), output=output, csv_bytes=csv_data, smartcore_result=smartcore_result, smart_rules_report=smart_rules_report)


def build_final_output_report(result: FinalOutputCommandResult) -> dict[str, Any]:
    return {
        'request': result.state.request.to_dict(),
        'result': result.state.result.to_dict(),
        'ok': result.state.result.ok,
        'smart_rules_report': result.smart_rules_report or {},
    }


__all__ = [
    'FinalOutputCommandResult',
    'apply_text_rules',
    'build_final_dataframe',
    'build_final_output',
    'build_final_output_report',
]
