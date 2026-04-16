from __future__ import annotations

import json
import os
from typing import Dict, List

import pandas as pd

try:
    from openai import OpenAI
except Exception:
    OpenAI = None


def _sample_rows(df: pd.DataFrame, limite: int = 3) -> list[dict]:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return []
    return df.head(limite).fillna("").to_dict(orient="records")


def _fallback_mapping(colunas_origem: List[str], colunas_modelo: List[str]) -> Dict[str, str]:
    mapping = {}
    origem_norm = {str(c).strip().lower(): str(c) for c in colunas_origem}

    regras = {
        "Código": ["codigo", "código", "sku", "id"],
        "Descrição": ["descricao", "descrição", "nome", "produto", "titulo"],
        "Descrição Curta": ["descricao curta", "descrição curta", "descricao", "descrição", "nome"],
        "Preço de venda": ["_preco_calculado", "preço calculado", "preco calculado"],
        "Preço unitário (OBRIGATÓRIO)": ["_preco_calculado", "preço calculado", "preco calculado"],
        "Preço": ["_preco_calculado", "preço calculado", "preco calculado", "preco", "preço"],
        "Valor": ["_preco_calculado", "valor", "preco", "preço"],
        "GTIN/EAN": ["gtin", "ean", "codigo de barras", "código de barras"],
        "GTIN": ["gtin", "ean", "codigo de barras", "código de barras"],
        "URL Imagens": ["url imagens", "url_imagens", "imagem", "imagens", "image", "images"],
        "Categoria": ["categoria", "departamento", "grupo"],
        "NCM": ["ncm"],
        "Unidade": ["unidade", "ucom", "un"],
        "Quantidade": ["quantidade", "qtd", "estoque", "saldo"],
    }

    for coluna_modelo in colunas_modelo:
        candidatos = regras.get(str(coluna_modelo), [])
        escolhido = ""
        for candidato in candidatos:
            candidato_n = candidato.strip().lower()
            if candidato_n in origem_norm:
                escolhido = origem_norm[candidato_n]
                break

        if not escolhido:
            alvo = str(coluna_modelo).strip().lower()
            for col in colunas_origem:
                if alvo and alvo in str(col).strip().lower():
                    escolhido = str(col)
                    break

        mapping[str(coluna_modelo)] = escolhido

    return mapping


def _get_client_and_model():
    api_key = os.getenv("OPENAI_API_KEY", "")
    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

    try:
        import streamlit as st

        if hasattr(st, "secrets"):
            openai_section = st.secrets.get("openai", {})
            if isinstance(openai_section, dict):
                api_key = api_key or openai_section.get("api_key", "")
                model = openai_section.get("model", model) or model
            else:
                api_key = api_key or st.secrets.get("OPENAI_API_KEY", "")
    except Exception:
        pass

    if not api_key or OpenAI is None:
        return None, model

    try:
        client = OpenAI(api_key=api_key)
        return client, model
    except Exception:
        return None, model


def sugerir_mapping_gpt(
    df_base: pd.DataFrame,
    df_modelo: pd.DataFrame,
    operacao: str,
) -> dict:
    colunas_origem = [str(c) for c in df_base.columns.tolist()]
    colunas_modelo = [str(c) for c in df_modelo.columns.tolist()]

    fallback = _fallback_mapping(colunas_origem, colunas_modelo)
    client, model = _get_client_and_model()

    if client is None:
        return {
            "provider": "fallback",
            "model": "local",
            "mapping": fallback,
            "erro": "OpenAI não configurada. Usando sugestão local.",
        }

    prompt = f"""
Você é especialista em mapear planilhas para modelo Bling.

Operação: {operacao}

Colunas da origem:
{json.dumps(colunas_origem, ensure_ascii=False, indent=2)}

Colunas do modelo:
{json.dumps(colunas_modelo, ensure_ascii=False, indent=2)}

Amostras da origem:
{json.dumps(_sample_rows(df_base, 3), ensure_ascii=False, indent=2)}

Responda SOMENTE em JSON válido no formato:
{{
  "mapping": {{
    "COLUNA_MODELO": "COLUNA_ORIGEM ou vazio"
  }}
}}

Regras:
- preserve os nomes exatos das colunas do modelo
- use vazio quando não tiver certeza
- priorize _preco_calculado para colunas de preço
- para imagens, priorize colunas de imagens/url
- não invente colunas
""".strip()

    try:
        response = client.chat.completions.create(
            model=model,
            temperature=0,
            messages=[
                {"role": "system", "content": "Responda apenas JSON válido."},
                {"role": "user", "content": prompt},
            ],
        )

        content = response.choices[0].message.content or "{}"
        parsed = json.loads(content)
        mapping = parsed.get("mapping", {})

        saneado = {}
        for coluna_modelo in colunas_modelo:
            valor = mapping.get(coluna_modelo, "")
            if valor in colunas_origem:
                saneado[coluna_modelo] = valor
            else:
                saneado[coluna_modelo] = fallback.get(coluna_modelo, "")

        return {
            "provider": "openai",
            "model": model,
            "mapping": saneado,
            "erro": "",
        }

    except Exception as exc:
        return {
            "provider": "fallback",
            "model": "local",
            "mapping": fallback,
            "erro": f"Falha na OpenAI, usando fallback local: {exc}",
        }
