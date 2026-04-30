from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable

import pandas as pd


@dataclass
class AutoSellConfig:
    tipo_operacao: str = "cadastro"
    deposito_nome: str = ""
    strategy: str = "inteligente"
    auto_mode: str = "manual"
    dry_run: bool = True
    max_items: int = 200


def _txt(valor: Any) -> str:
    texto = str(valor or "").strip()
    if texto.lower() in {"nan", "none", "null"}:
        return ""
    return texto


def _norm(valor: Any) -> str:
    return _txt(valor).lower()


def _agora_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _coluna_por_termos(df: pd.DataFrame, termos: list[str]) -> str:
    if not isinstance(df, pd.DataFrame):
        return ""
    for col in df.columns:
        nome = _norm(col)
        if any(t in nome for t in termos):
            return str(col)
    return ""


def detectar_colunas_auto_sell(df: pd.DataFrame) -> dict[str, str]:
    return {
        "codigo": _coluna_por_termos(df, ["codigo", "código", "sku", "referencia", "referência"]),
        "nome": _coluna_por_termos(df, ["descricao", "descrição", "nome", "titulo", "título", "produto"]),
        "preco": _coluna_por_termos(df, ["preco", "preço", "valor"]),
        "estoque": _coluna_por_termos(df, ["estoque", "quantidade", "saldo", "balanco", "balanço"]),
        "gtin": _coluna_por_termos(df, ["gtin", "ean", "barras"]),
        "imagem": _coluna_por_termos(df, ["imagem", "imagens", "foto"]),
        "categoria": _coluna_por_termos(df, ["categoria", "departamento"]),
    }


def validar_df_auto_sell(df: pd.DataFrame) -> tuple[bool, list[str], dict[str, str]]:
    erros: list[str] = []
    if not isinstance(df, pd.DataFrame) or df.empty:
        return False, ["DataFrame final vazio."], {}

    cols = detectar_colunas_auto_sell(df)
    if not cols.get("codigo"):
        erros.append("Coluna de código/SKU não detectada.")
    if not cols.get("nome"):
        erros.append("Coluna de nome/descrição não detectada.")
    if not cols.get("preco"):
        erros.append("Coluna de preço não detectada.")

    return len(erros) == 0, erros, cols


def _montar_item(row: pd.Series, cols: dict[str, str], config: AutoSellConfig) -> dict[str, Any]:
    codigo = _txt(row.get(cols.get("codigo", ""), ""))
    nome = _txt(row.get(cols.get("nome", ""), ""))
    preco = _txt(row.get(cols.get("preco", ""), ""))
    estoque = _txt(row.get(cols.get("estoque", ""), ""))
    gtin = _txt(row.get(cols.get("gtin", ""), ""))
    imagem = _txt(row.get(cols.get("imagem", ""), ""))
    categoria = _txt(row.get(cols.get("categoria", ""), ""))

    return {
        "codigo": codigo,
        "nome": nome,
        "preco": preco,
        "estoque": estoque,
        "gtin": gtin,
        "imagem": imagem,
        "categoria": categoria,
        "deposito_nome": config.deposito_nome,
        "tipo_operacao": config.tipo_operacao,
    }


def _enviar_item_simulado(item: dict[str, Any], config: AutoSellConfig) -> dict[str, Any]:
    codigo = _txt(item.get("codigo"))
    nome = _txt(item.get("nome"))
    preco = _txt(item.get("preco"))

    if not codigo or not nome:
        return {
            "ok": False,
            "status": "erro",
            "acao": "validacao",
            "codigo": codigo,
            "mensagem": "Código ou nome vazio.",
        }

    if config.tipo_operacao != "estoque" and not preco:
        return {
            "ok": False,
            "status": "erro",
            "acao": "validacao",
            "codigo": codigo,
            "mensagem": "Preço vazio para cadastro de produto.",
        }

    acao = "auto_update_or_create" if config.strategy == "inteligente" else config.strategy
    return {
        "ok": True,
        "status": "simulado" if config.dry_run else "pendente_api_real",
        "acao": acao,
        "codigo": codigo,
        "mensagem": "Item validado para envio automático.",
    }


def executar_auto_sell(
    df_final: pd.DataFrame,
    config: AutoSellConfig,
    callback: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    ok, erros, cols = validar_df_auto_sell(df_final)
    if not ok:
        return {
            "ok": False,
            "modo": "auto_sell_validacao",
            "mensagem": "Falha na validação do AUTO SELL.",
            "erros": erros,
            "colunas": cols,
            "processado_em": _agora_iso(),
            "resultados": [],
        }

    base = df_final.copy().fillna("").head(max(1, int(config.max_items)))
    total = int(len(base))
    resultados: list[dict[str, Any]] = []
    criados = 0
    atualizados = 0
    erros_total = 0

    if callable(callback):
        callback({"phase": "start", "total": total, "processed": 0})

    for idx, (_, row) in enumerate(base.iterrows(), start=1):
        item = _montar_item(row, cols, config)
        if callable(callback):
            callback({
                "phase": "item_start",
                "index": idx,
                "total": total,
                "processed": idx - 1,
                "codigo": item.get("codigo", ""),
                "descricao": item.get("nome", ""),
            })

        resultado = _enviar_item_simulado(item, config)
        resultados.append(resultado)

        if resultado.get("ok"):
            if config.strategy == "atualizar_existentes" or config.tipo_operacao == "estoque":
                atualizados += 1
            else:
                criados += 1
        else:
            erros_total += 1

        if callable(callback):
            callback({
                "phase": "item_result",
                "total": total,
                "processed": idx,
                "item": resultado,
                "total_criados": criados,
                "total_atualizados": atualizados,
                "total_erros": erros_total,
                "total_ignorados": 0,
            })

    summary = {
        "ok": erros_total == 0,
        "modo": "auto_sell_dry_run" if config.dry_run else "auto_sell_preparado",
        "mensagem": "AUTO SELL finalizado em modo seguro.",
        "total_itens": total,
        "total_processados": len(resultados),
        "total_criados": criados,
        "total_atualizados": atualizados,
        "total_ignorados": 0,
        "total_erros": erros_total,
        "processado_em": _agora_iso(),
        "colunas": cols,
        "resultados": resultados,
        "dry_run": config.dry_run,
    }

    if callable(callback):
        callback({"phase": "finish", "summary": summary})

    return summary
