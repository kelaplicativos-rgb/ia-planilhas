import json
from typing import Any

import openai
import pandas as pd
import streamlit as st


CAMPOS_IA_VALIDOS = {
    "codigo",
    "nome",
    "descricao",
    "descricao_curta",
    "preco",
    "marca",
    "imagem",
    "estoque",
    "deposito",
    "situacao",
    "unidade",
    "categoria",
    "gtin",
    "ncm",
    "origem",
    "peso_liquido",
    "peso_bruto",
    "largura",
    "altura",
    "profundidade",
    "meses_garantia_fornecedor",
    "descricao_complementar",
}


def _sample_dataframe(df: pd.DataFrame, max_rows: int = 5) -> list[dict[str, Any]]:
    """
    Gera uma pequena amostra serializável da planilha para enviar à IA.
    """
    if df is None or df.empty:
        return []

    amostra = df.head(max_rows).copy()

    for col in amostra.columns:
        amostra[col] = amostra[col].fillna("").astype(str)

    return amostra.to_dict(orient="records")


def _extrair_json(texto: str) -> dict:
    """
    Extrai o primeiro bloco JSON válido encontrado no texto.
    """
    texto = str(texto).strip()

    inicio = texto.find("{")
    fim = texto.rfind("}") + 1

    if inicio == -1 or fim <= 0:
        return {}

    trecho = texto[inicio:fim]

    try:
        return json.loads(trecho)
    except Exception:
        return {}


def _normalizar_saida_ia(resultado: dict, colunas_validas: list[str]) -> dict:
    """
    Mantém apenas chaves válidas e colunas que realmente existem no DataFrame.
    """
    if not isinstance(resultado, dict):
        return {}

    colunas_set = set(colunas_validas)
    saida = {}

    for chave, valor in resultado.items():
        if chave not in CAMPOS_IA_VALIDOS:
            continue

        if valor is None:
            continue

        valor = str(valor).strip()

        if not valor:
            continue

        if valor in colunas_set:
            saida[chave] = valor

    return saida


def detectar_colunas_com_ia(df: pd.DataFrame) -> dict:
    """
    Usa IA para identificar colunas da planilha.
    Se a IA falhar, retorna {} e o fallback local assume.
    """
    if df is None or df.empty:
        return {}

    try:
        api_key = st.secrets["OPENAI_API_KEY"]
    except Exception:
        return {}

    try:
        client = openai.OpenAI(api_key=api_key, max_retries=1)

        colunas = list(df.columns)
        amostra = _sample_dataframe(df)

        prompt = f"""
Você é um especialista em integração com ERP Bling.

Analise uma planilha de produtos de fornecedor e identifique quais colunas representam os campos abaixo.

REGRAS IMPORTANTES:
- "nome" = título/nome do produto
- "descricao" = também representa o título/nome do produto quando houver uma coluna claramente de título
- "descricao_curta" = descrição real do produto, detalhes, resumo ou texto descritivo
- "video" NÃO deve ser detectado
- "link_externo" NÃO deve ser detectado porque no sistema final deve ficar vazio
- Se não encontrar um campo, retorne null

Campos para identificar:
- codigo
- nome
- descricao
- descricao_curta
- preco
- marca
- imagem
- estoque
- deposito
- situacao
- unidade
- categoria
- gtin
- ncm
- origem
- peso_liquido
- peso_bruto
- largura
- altura
- profundidade
- meses_garantia_fornecedor
- descricao_complementar

Responda SOMENTE em JSON no formato:

{{
  "codigo": null,
  "nome": null,
  "descricao": null,
  "descricao_curta": null,
  "preco": null,
  "marca": null,
  "imagem": null,
  "estoque": null,
  "deposito": null,
  "situacao": null,
  "unidade": null,
  "categoria": null,
  "gtin": null,
  "ncm": null,
  "origem": null,
  "peso_liquido": null,
  "peso_bruto": null,
  "largura": null,
  "altura": null,
  "profundidade": null,
  "meses_garantia_fornecedor": null,
  "descricao_complementar": null
}}

Colunas disponíveis:
{colunas}

Amostra de dados:
{amostra}
"""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Você é especialista em ERP Bling, planilhas de fornecedores "
                        "e mapeamento de colunas."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0,
        )

        texto = response.choices[0].message.content or ""
        resultado = _extrair_json(texto)

        return _normalizar_saida_ia(resultado, colunas)

    except Exception as e:
        st.warning(f"⚠️ IA falhou, usando apenas detecção local: {e}")
        return {}
