from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from bling_app_zero.ai.ai_client import call_openai_json
from bling_app_zero.ai.ai_config import get_ai_settings
from bling_app_zero.ai.ai_schema import AIResult
from bling_app_zero.core.gtin import clean_gtin, looks_like_gtin_column
from bling_app_zero.core.text import clean_cell, normalize_key

MAX_SAMPLE_ROWS = 8
MAX_COLUMNS_FOR_AI = 80


@dataclass
class AIRealFinding:
    level: str
    title: str
    message: str
    column: str = ''
    rows: int = 0


@dataclass
class AIRealReport:
    ok: bool
    ready: bool
    summary: str
    findings: list[AIRealFinding] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)
    ai_message: str = ''
    ai_used: bool = False
    ai_error: str = ''


def _is_df(df: Any) -> bool:
    return isinstance(df, pd.DataFrame) and not df.empty and len(df.columns) > 0


def _safe_columns(df: pd.DataFrame | None) -> list[str]:
    return [str(column) for column in df.columns] if isinstance(df, pd.DataFrame) else []


def _non_empty_count(series: pd.Series) -> int:
    return int(series.astype(str).map(clean_cell).map(lambda value: bool(value and normalize_key(value) not in {'nan', 'none', 'null', 'na', 'n/a'})).sum())


def _empty_count(series: pd.Series) -> int:
    return int(len(series) - _non_empty_count(series))


def _find_columns(columns: list[str], terms: list[str]) -> list[str]:
    found: list[str] = []
    for column in columns:
        key = normalize_key(column)
        if any(term in key for term in terms):
            found.append(column)
    return found


def _sample_df(df: pd.DataFrame | None) -> list[dict[str, str]]:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return []
    safe = df.head(MAX_SAMPLE_ROWS).fillna('').copy()
    safe = safe.iloc[:, :MAX_COLUMNS_FOR_AI]
    return [{str(column): clean_cell(value)[:300] for column, value in row.items()} for row in safe.to_dict(orient='records')]


def _contract_findings(df_modelo: pd.DataFrame | None, df_final: pd.DataFrame | None) -> list[AIRealFinding]:
    findings: list[AIRealFinding] = []
    model_columns = _safe_columns(df_modelo)
    final_columns = _safe_columns(df_final)
    if not model_columns:
        return [AIRealFinding('erro', 'Modelo ausente', 'Envie um modelo de destino com cabeçalho antes de continuar.')]
    if not final_columns:
        return [AIRealFinding('erro', 'Arquivo final ausente', 'Confirme o mapeamento para gerar o arquivo final antes da conferência.')]

    missing = [column for column in model_columns if column not in final_columns]
    extra = [column for column in final_columns if column not in model_columns]
    order_ok = final_columns[: len(model_columns)] == model_columns

    if missing:
        findings.append(AIRealFinding('erro', 'Colunas do modelo faltando', 'O arquivo final não contém todas as colunas do modelo anexado.', rows=len(missing)))
    if extra:
        findings.append(AIRealFinding('aviso', 'Colunas extras detectadas', 'Existem colunas no arquivo final que não fazem parte do modelo anexado.', rows=len(extra)))
    if not order_ok:
        findings.append(AIRealFinding('aviso', 'Ordem de colunas diferente', 'A ordem das colunas finais parece diferente da ordem do modelo anexado.'))
    if not missing and not extra and order_ok:
        findings.append(AIRealFinding('ok', 'Contrato do modelo respeitado', 'As colunas finais seguem o modelo anexado.'))
    return findings


def _content_findings(df_final: pd.DataFrame | None) -> list[AIRealFinding]:
    findings: list[AIRealFinding] = []
    if not _is_df(df_final):
        return findings

    total_rows = len(df_final)
    columns = _safe_columns(df_final)
    if total_rows == 0:
        return [AIRealFinding('erro', 'Sem produtos', 'O arquivo final não possui linhas para baixar.')]

    empty_columns: list[str] = []
    for column in columns:
        empty = _empty_count(df_final[column])
        if empty == total_rows:
            empty_columns.append(column)
        elif empty > 0 and empty / max(total_rows, 1) >= 0.5:
            findings.append(AIRealFinding('aviso', 'Muitos vazios em uma coluna', f'A coluna "{column}" está vazia em {empty} de {total_rows} linha(s).', column=column, rows=empty))

    if empty_columns:
        findings.append(AIRealFinding('aviso', 'Colunas totalmente vazias', f'{len(empty_columns)} coluna(s) do modelo ficaram totalmente vazias porque não foram encontradas/preenchidas.', rows=len(empty_columns)))

    description_columns = _find_columns(columns, ['descricao', 'descrição', 'nome', 'produto'])
    if description_columns:
        for column in description_columns[:3]:
            suspicious = 0
            for value in df_final[column].astype(str).tolist():
                key = normalize_key(value)
                if any(term in key for term in ['ainda nao ha para este produto', 'calcule o frete', 'comprar', 'adicionar ao carrinho', 'avaliacoes']):
                    suspicious += 1
            if suspicious:
                findings.append(AIRealFinding('aviso', 'Descrição com ruído de site', f'A coluna "{column}" tem {suspicious} linha(s) com cara de texto sujo de página.', column=column, rows=suspicious))
    else:
        findings.append(AIRealFinding('aviso', 'Descrição não localizada', 'Não encontrei uma coluna com nome/descrição/produto no arquivo final.'))

    for column in _find_columns(columns, ['preco', 'preço', 'valor'])[:5]:
        empty = _empty_count(df_final[column])
        if empty:
            findings.append(AIRealFinding('aviso', 'Preço vazio', f'A coluna "{column}" possui {empty} linha(s) sem preço.', column=column, rows=empty))

    for column in _find_columns(columns, ['imagem', 'image', 'foto', 'url imagens', 'url_imagens'])[:4]:
        wrong_sep = 0
        for value in df_final[column].astype(str).tolist():
            text = clean_cell(value)
            if text and ',' in text and '|' not in text and ('http://' in text or 'https://' in text):
                wrong_sep += 1
        if wrong_sep:
            findings.append(AIRealFinding('aviso', 'Imagens podem estar com separador errado', f'A coluna "{column}" tem {wrong_sep} linha(s) com URLs possivelmente separadas por vírgula em vez de |.', column=column, rows=wrong_sep))

    for column in columns:
        if not looks_like_gtin_column(column):
            continue
        invalid = 0
        filled = 0
        for value in df_final[column].astype(str).tolist():
            text = clean_cell(value)
            if not text:
                continue
            filled += 1
            if not clean_gtin(text):
                invalid += 1
        if invalid:
            findings.append(AIRealFinding('aviso', 'GTIN/EAN inválido', f'A coluna "{column}" possui {invalid} valor(es) inválido(s). Eles devem ser limpos antes do download.', column=column, rows=invalid))
        elif filled:
            findings.append(AIRealFinding('ok', 'GTIN/EAN validado', f'A coluna "{column}" não apresentou GTIN inválido nas linhas preenchidas.', column=column))

    return findings


def _local_report(df_source: pd.DataFrame | None, df_modelo: pd.DataFrame | None, df_final: pd.DataFrame | None) -> AIRealReport:
    findings = _contract_findings(df_modelo, df_final) + _content_findings(df_final)
    source_rows = len(df_source) if isinstance(df_source, pd.DataFrame) else 0
    final_rows = len(df_final) if isinstance(df_final, pd.DataFrame) else 0
    if source_rows and final_rows and source_rows != final_rows:
        findings.append(AIRealFinding('erro', 'Quantidade de linhas diferente', f'A origem tem {source_rows} linha(s), mas o final tem {final_rows}. Confira antes de baixar.'))

    error_count = sum(1 for item in findings if item.level == 'erro')
    warning_count = sum(1 for item in findings if item.level == 'aviso')
    ok_count = sum(1 for item in findings if item.level == 'ok')

    actions: list[str] = []
    if error_count:
        actions.append('Corrija os erros antes de liberar o download final.')
    if warning_count:
        actions.append('Revise os avisos; eles não bloqueiam sempre, mas podem gerar planilha incompleta.')
    if not error_count:
        actions.append('Confira o preview final e baixe o modelo preenchido se os dados estiverem corretos.')

    return AIRealReport(ok=error_count == 0, ready=True, summary=f'{ok_count} item(ns) OK, {warning_count} aviso(s), {error_count} erro(s).', findings=findings, actions=actions)


def _payload_for_ai(df_source: pd.DataFrame | None, df_modelo: pd.DataFrame | None, df_final: pd.DataFrame | None, local: AIRealReport) -> dict[str, Any]:
    return {
        'goal': 'Conferir se a planilha final está pronta para o usuário baixar, respeitando 100% o modelo anexado.',
        'rules': ['Não inventar dados.', 'Priorizar fidelidade ao modelo anexado.', 'Explicar em português simples para usuário final.', 'Apontar campos vazios, ruídos, GTIN inválido, imagens e divergências de contrato.'],
        'source_shape': list(df_source.shape) if isinstance(df_source, pd.DataFrame) else [0, 0],
        'model_columns': _safe_columns(df_modelo)[:MAX_COLUMNS_FOR_AI],
        'final_shape': list(df_final.shape) if isinstance(df_final, pd.DataFrame) else [0, 0],
        'final_columns': _safe_columns(df_final)[:MAX_COLUMNS_FOR_AI],
        'local_findings': [item.__dict__ for item in local.findings[:40]],
        'final_sample': _sample_df(df_final),
    }


def _ask_ai_for_explanation(df_source: pd.DataFrame | None, df_modelo: pd.DataFrame | None, df_final: pd.DataFrame | None, local: AIRealReport) -> tuple[str, str, bool]:
    settings = get_ai_settings()
    if not settings.ready:
        return '', 'IA Real indisponível: configure a chave OpenAI no Secrets do app.', False

    instructions = '''Você é a IA Real do MapeiaAI. Sua função é ajudar o usuário final a entender se a planilha final está pronta.
Retorne JSON com: {"summary":"resumo curto em português simples", "actions":["ação prática"], "warnings":["aviso"], "ready_to_download":true/false}.
Não invente informações ausentes. Não mande o usuário configurar chave. Não fale de código.'''
    result: AIResult = call_openai_json('ai_real_final_check', instructions, _payload_for_ai(df_source, df_modelo, df_final, local), settings=settings)
    if not result.ok:
        return '', result.message or result.error or 'IA Real não concluiu a análise.', False
    data = result.data if isinstance(result.data, dict) else {}
    summary = str(data.get('summary') or '').strip()
    actions = data.get('actions') if isinstance(data.get('actions'), list) else []
    warnings = data.get('warnings') if isinstance(data.get('warnings'), list) else []
    parts: list[str] = []
    if summary:
        parts.append(summary)
    if warnings:
        parts.append('Avisos da IA: ' + ' | '.join(str(item) for item in warnings[:5]))
    if actions:
        parts.append('Próximos passos: ' + ' | '.join(str(item) for item in actions[:5]))
    return '\n'.join(parts), '', True


def run_ai_real_final_check(*, df_source: pd.DataFrame | None, df_modelo: pd.DataFrame | None, df_final: pd.DataFrame | None, use_openai: bool = True) -> AIRealReport:
    local = _local_report(df_source, df_modelo, df_final)
    if not use_openai:
        return local
    ai_message, ai_error, ai_used = _ask_ai_for_explanation(df_source, df_modelo, df_final, local)
    local.ai_message = ai_message
    local.ai_error = ai_error
    local.ai_used = ai_used
    if ai_message:
        local.actions.insert(0, ai_message)
    return local


__all__ = ['AIRealFinding', 'AIRealReport', 'run_ai_real_final_check']