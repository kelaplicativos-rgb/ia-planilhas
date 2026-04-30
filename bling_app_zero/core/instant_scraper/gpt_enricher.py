from __future__ import annotations

import json
import os
from typing import Any

import pandas as pd


COLUNAS_GPT = [
    "_gpt_enriquecido",
    "_gpt_status",
    "_gpt_alertas",
]


CAMPOS_EDITAVEIS_GPT = [
    "nome",
    "marca",
    "categoria",
    "descricao",
]


CAMPOS_PROTEGIDOS = [
    "preco",
    "gtin",
    "url_produto",
    "imagens",
    "sku",
    "estoque",
]


def _txt(valor: Any) -> str:
    return str(valor or "").strip()


def gpt_disponivel() -> bool:
    return bool(_txt(os.environ.get("OPENAI_API_KEY", "")))


def _cliente_openai():
    try:
        from openai import OpenAI
    except Exception:
        return None

    if not gpt_disponivel():
        return None

    try:
        return OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    except Exception:
        return None


def _montar_payload_produto(row: pd.Series) -> dict[str, str]:
    campos = [
        "nome",
        "marca",
        "categoria",
        "descricao",
        "preco",
        "sku",
        "gtin",
        "url_produto",
    ]
    return {campo: _txt(row.get(campo, "")) for campo in campos}


def _prompt_produto(produto: dict[str, str]) -> str:
    return (
        "Você é um normalizador de catálogo para importação no Bling. "
        "Corrija e enriqueça APENAS os campos nome, marca, categoria e descricao. "
        "Não invente preço, GTIN, SKU, URL ou imagem. "
        "Se não tiver certeza, deixe o campo como está ou vazio. "
        "Responda SOMENTE JSON válido com as chaves: nome, marca, categoria, descricao, alertas.\n\n"
        f"Produto:\n{json.dumps(produto, ensure_ascii=False)}"
    )


def _extrair_json(texto: str) -> dict[str, Any]:
    texto = _txt(texto)
    if not texto:
        return {}

    try:
        return json.loads(texto)
    except Exception:
        pass

    inicio = texto.find("{")
    fim = texto.rfind("}")
    if inicio >= 0 and fim > inicio:
        try:
            return json.loads(texto[inicio : fim + 1])
        except Exception:
            return {}

    return {}


def _enriquecer_linha_gpt(row: pd.Series, client, model: str) -> dict[str, Any]:
    produto = _montar_payload_produto(row)

    try:
        resposta = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "Você corrige dados de produtos para e-commerce brasileiro e responde apenas JSON válido.",
                },
                {"role": "user", "content": _prompt_produto(produto)},
            ],
            temperature=0.1,
            max_tokens=350,
        )
        conteudo = resposta.choices[0].message.content or ""
        dados = _extrair_json(conteudo)
        if not isinstance(dados, dict):
            return {}
        return dados
    except Exception as exc:
        return {"alertas": f"erro_gpt: {exc}"}


def enriquecer_produtos_gpt(
    df: pd.DataFrame,
    limite: int = 30,
    score_minimo: int = 0,
    model: str = "gpt-4o-mini",
) -> pd.DataFrame:
    """
    BLINGAI GPT MODE opcional.

    - Só roda se OPENAI_API_KEY existir no ambiente.
    - Enriquecer no máximo `limite` linhas para controlar custo.
    - Preserva campos críticos: preço, gtin, url, imagens, sku e estoque.
    """
    if not isinstance(df, pd.DataFrame) or df.empty:
        return pd.DataFrame()

    base = df.copy().fillna("")

    for coluna in COLUNAS_GPT:
        if coluna not in base.columns:
            base[coluna] = ""

    if not gpt_disponivel():
        base["_gpt_enriquecido"] = "NAO"
        base["_gpt_status"] = "sem_chave_openai"
        base["_gpt_alertas"] = "OPENAI_API_KEY não configurada; IA local mantida."
        return base

    client = _cliente_openai()
    if client is None:
        base["_gpt_enriquecido"] = "NAO"
        base["_gpt_status"] = "cliente_indisponivel"
        base["_gpt_alertas"] = "Não foi possível iniciar cliente OpenAI."
        return base

    total = 0

    for idx, row in base.iterrows():
        if total >= int(limite):
            base.at[idx, "_gpt_enriquecido"] = "NAO"
            base.at[idx, "_gpt_status"] = "limite_nao_processado"
            continue

        try:
            score = int(str(row.get("_ai_score", "0") or "0"))
        except Exception:
            score = 0

        if score < int(score_minimo):
            base.at[idx, "_gpt_enriquecido"] = "NAO"
            base.at[idx, "_gpt_status"] = "abaixo_score_minimo"
            continue

        dados = _enriquecer_linha_gpt(row, client, model=model)
        alertas = _txt(dados.get("alertas", "")) if isinstance(dados, dict) else ""

        if not dados:
            base.at[idx, "_gpt_enriquecido"] = "NAO"
            base.at[idx, "_gpt_status"] = "sem_retorno"
            base.at[idx, "_gpt_alertas"] = "GPT não retornou JSON útil."
            total += 1
            continue

        for campo in CAMPOS_EDITAVEIS_GPT:
            valor = _txt(dados.get(campo, ""))
            if valor:
                base.at[idx, campo] = valor[:900] if campo == "descricao" else valor[:180]

        # garante que campos protegidos não foram alterados por acidente
        for campo in CAMPOS_PROTEGIDOS:
            if campo in df.columns:
                base.at[idx, campo] = row.get(campo, "")

        base.at[idx, "_gpt_enriquecido"] = "SIM"
        base.at[idx, "_gpt_status"] = "ok" if not alertas else "ok_com_alertas"
        base.at[idx, "_gpt_alertas"] = alertas
        total += 1

    return base.fillna("").reset_index(drop=True)
