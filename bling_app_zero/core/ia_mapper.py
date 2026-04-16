
from __future__ import annotations

import json
import os
import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None  # type: ignore


@dataclass
class IAMappingResult:
    sucesso: bool
    provider: str
    model: str
    mapeamento: Dict[str, Dict[str, Any]]
    bruto: str
    erro: str = ""


SINONIMOS_PADRAO = {
    "codigo": [
        "codigo",
        "cod",
        "sku",
        "referencia",
        "ref",
        "id produto",
        "codigo produto",
        "codigo sku",
    ],
    "descricao": [
        "descricao",
        "descrição",
        "nome",
        "nome produto",
        "produto",
        "titulo",
        "título",
        "descricao produto",
        "descrição produto",
    ],
    "descricao curta": [
        "descricao curta",
        "descrição curta",
        "resumo",
        "nome curto",
        "titulo curto",
    ],
    "preco de venda": [
        "preco",
        "preço",
        "valor",
        "valor venda",
        "preco venda",
        "preço venda",
        "valor final",
        "preco final",
        "preço final",
        "preco varejo",
    ],
    "preco unitario (obrigatorio)": [
        "preco",
        "preço",
        "valor",
        "valor unitario",
        "valor unitário",
        "preco unitario",
        "preço unitário",
        "preco custo",
        "preço custo",
    ],
    "preco custo": [
        "preco custo",
        "preço custo",
        "custo",
        "valor custo",
        "preco compra",
        "preço compra",
    ],
    "estoque": [
        "estoque",
        "saldo",
        "quantidade",
        "qtd",
        "qtde",
        "disponivel",
        "disponível",
    ],
    "deposito (obrigatorio)": [
        "deposito",
        "depósito",
        "armazem",
        "armazém",
        "local estoque",
        "deposito nome",
    ],
    "balanco (obrigatorio)": [
        "balanco",
        "balanço",
        "tipo balanco",
        "tipo balanço",
        "operacao estoque",
        "operação estoque",
    ],
    "marca": [
        "marca",
        "fabricante",
        "brand",
    ],
    "ncm": [
        "ncm",
        "classificacao fiscal",
        "classificação fiscal",
    ],
    "gtin": [
        "gtin",
        "ean",
        "codigo barras",
        "código barras",
        "cod barras",
        "barcode",
    ],
    "categoria": [
        "categoria",
        "departamento",
        "secao",
        "seção",
        "grupo",
        "tipo",
    ],
    "unidade": [
        "unidade",
        "und",
        "un",
    ],
    "peso liquido": [
        "peso",
        "peso liquido",
        "peso líquido",
    ],
    "altura": [
        "altura",
    ],
    "largura": [
        "largura",
    ],
    "profundidade": [
        "profundidade",
        "comprimento",
    ],
    "imagens": [
        "imagem",
        "imagens",
        "foto",
        "fotos",
        "url imagem",
        "url imagens",
        "image",
        "images",
    ],
}


def _normalizar_texto(valor: Any) -> str:
    texto = str(valor or "").strip().lower()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(ch for ch in texto if not unicodedata.combining(ch))
    texto = re.sub(r"[^a-z0-9]+", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def _tokenizar(valor: Any) -> List[str]:
    txt = _normalizar_texto(valor)
    return [t for t in txt.split(" ") if t]


def _score_coluna(nome_modelo: str, nome_origem: str) -> float:
    modelo = _normalizar_texto(nome_modelo)
    origem = _normalizar_texto(nome_origem)

    if not modelo or not origem:
        return 0.0

    if modelo == origem:
        return 1.0

    score = 0.0

    if modelo in origem or origem in modelo:
        score += 0.45

    tokens_modelo = set(_tokenizar(modelo))
    tokens_origem = set(_tokenizar(origem))
    if tokens_modelo and tokens_origem:
        inter = len(tokens_modelo & tokens_origem)
        uni = len(tokens_modelo | tokens_origem)
        score += (inter / uni) * 0.35

    sinonimos = SINONIMOS_PADRAO.get(modelo, [])
    for sinonimo in sinonimos:
        s = _normalizar_texto(sinonimo)
        if s == origem:
            score += 0.55
        elif s in origem or origem in s:
            score += 0.30

    return min(score, 0.98)


def _mapear_por_heuristica(
    colunas_origem: List[str],
    colunas_modelo: List[str],
) -> Dict[str, Dict[str, Any]]:
    resultado: Dict[str, Dict[str, Any]] = {}
    usados: set[str] = set()

    for coluna_modelo in colunas_modelo:
        melhor_coluna: Optional[str] = None
        melhor_score = 0.0

        for coluna_origem in colunas_origem:
            if coluna_origem in usados:
                continue
            score = _score_coluna(coluna_modelo, coluna_origem)
            if score > melhor_score:
                melhor_score = score
                melhor_coluna = coluna_origem

        if melhor_coluna and melhor_score >= 0.45:
            usados.add(melhor_coluna)
            resultado[coluna_modelo] = {
                "source_column": melhor_coluna,
                "confidence": round(float(melhor_score), 4),
                "reason": "mapeamento heurístico por similaridade de nome",
            }
        else:
            resultado[coluna_modelo] = {
                "source_column": None,
                "confidence": 0.0,
                "reason": "sem correspondência segura por heurística",
            }

    return resultado


def _sample_rows(df: pd.DataFrame, limite: int = 3) -> List[Dict[str, Any]]:
    if df is None or df.empty:
        return []
    rows = df.head(limite).fillna("").to_dict(orient="records")
    return rows


def _extrair_json(texto: str) -> Dict[str, Any]:
    if not texto:
        raise ValueError("Resposta vazia da IA.")

    texto = texto.strip()

    bloco = re.search(r"```json\s*(\{.*?\})\s*```", texto, flags=re.S)
    if bloco:
        return json.loads(bloco.group(1))

    bloco = re.search(r"(\{.*\})", texto, flags=re.S)
    if bloco:
        return json.loads(bloco.group(1))

    return json.loads(texto)


def _get_openai_client() -> Tuple[Optional[Any], str, str]:
    api_key = ""
    model = "gpt-5.4"

    try:
        if "openai" in os.environ and not api_key:
            pass
    except Exception:
        pass

    try:
        api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        model = os.getenv("OPENAI_MODEL", model)
    except Exception:
        pass

    try:
        import streamlit as st

        if hasattr(st, "secrets"):
            api_key = api_key or st.secrets.get("OPENAI_API_KEY", "")
            openai_section = st.secrets.get("openai", {})
            if isinstance(openai_section, dict):
                api_key = api_key or openai_section.get("api_key", "")
                model = openai_section.get("model", model) or model
    except Exception:
        pass

    if not api_key or OpenAI is None:
        return None, "", model

    try:
        client = OpenAI(api_key=api_key)
        return client, api_key, model
    except Exception:
        return None, "", model


def _prompt_mapeamento(
    operacao: str,
    colunas_origem: List[str],
    colunas_modelo: List[str],
    amostras: List[Dict[str, Any]],
    contexto_extra: Optional[str] = None,
) -> str:
    contexto_extra = (contexto_extra or "").strip()

    return f"""
Você é um especialista em mapeamento de planilhas para importação no Bling.

Sua tarefa:
- analisar colunas de origem
- analisar colunas do modelo alvo
- sugerir o melhor DE -> PARA
- evitar inventar dados
- quando não houver confiança suficiente, retornar null
- não repetir a mesma coluna de origem em vários campos do modelo, exceto quando for inevitável
- priorizar correspondência semântica real
- considerar os nomes das colunas e o conteúdo das amostras

Operação atual: {operacao}

Colunas da origem:
{json.dumps(colunas_origem, ensure_ascii=False, indent=2)}

Colunas do modelo:
{json.dumps(colunas_modelo, ensure_ascii=False, indent=2)}

Amostras da origem:
{json.dumps(amostras, ensure_ascii=False, indent=2)}

Contexto extra:
{contexto_extra or "sem contexto extra"}

Responda SOMENTE em JSON válido no formato:
{{
  "mapping": {{
    "NOME_EXATO_DA_COLUNA_DO_MODELO": {{
      "source_column": "NOME_EXATO_DA_COLUNA_DA_ORIGEM ou null",
      "confidence": 0.0,
      "reason": "explicação curta"
    }}
  }}
}}

Regras:
- preserve exatamente o nome das colunas do modelo
- preserve exatamente o nome das colunas da origem
- confidence deve ficar entre 0 e 1
- se não souber, use null
- não escreva texto fora do JSON
""".strip()


def sugerir_mapeamento_ia(
    df_origem: pd.DataFrame,
    colunas_modelo: List[str],
    operacao: str = "cadastro",
    contexto_extra: Optional[str] = None,
    forcar_ia: bool = False,
) -> IAMappingResult:
    if df_origem is None or df_origem.empty:
        return IAMappingResult(
            sucesso=False,
            provider="local",
            model="heuristica",
            mapeamento={},
            bruto="",
            erro="DataFrame de origem vazio.",
        )

    colunas_origem = [str(c) for c in df_origem.columns.tolist()]
    colunas_modelo = [str(c) for c in colunas_modelo]

    heuristico = _mapear_por_heuristica(colunas_origem, colunas_modelo)
    client, _, model = _get_openai_client()

    if client is None and not forcar_ia:
        return IAMappingResult(
            sucesso=True,
            provider="local",
            model="heuristica",
            mapeamento=heuristico,
            bruto=json.dumps({"mapping": heuristico}, ensure_ascii=False, indent=2),
            erro="OpenAI não configurada. Usando fallback heurístico.",
        )

    if client is None and forcar_ia:
        return IAMappingResult(
            sucesso=False,
            provider="openai",
            model=model,
            mapeamento=heuristico,
            bruto="",
            erro="OpenAI não configurada. Defina OPENAI_API_KEY ou st.secrets.",
        )

    amostras = _sample_rows(df_origem, limite=3)
    prompt = _prompt_mapeamento(
        operacao=operacao,
        colunas_origem=colunas_origem,
        colunas_modelo=colunas_modelo,
        amostras=amostras,
        contexto_extra=contexto_extra,
    )

    try:
        response = client.responses.create(
            model=model,
            input=[
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "input_text",
                            "text": "Você responde apenas com JSON válido.",
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": prompt,
                        }
                    ],
                },
            ],
        )

        bruto = getattr(response, "output_text", "") or ""
        parsed = _extrair_json(bruto)
        mapping = parsed.get("mapping", {})

        if not isinstance(mapping, dict):
            raise ValueError("Campo 'mapping' inválido na resposta da IA.")

        saneado: Dict[str, Dict[str, Any]] = {}
        usados: set[str] = set()

        for coluna_modelo in colunas_modelo:
            item = mapping.get(coluna_modelo, {})
            source_column = item.get("source_column")
            confidence = item.get("confidence", 0.0)
            reason = item.get("reason", "")

            if source_column not in colunas_origem:
                source_column = None
                confidence = 0.0
                reason = "IA retornou coluna inexistente na origem"

            if source_column in usados and source_column is not None:
                source_column = None
                confidence = 0.0
                reason = "coluna repetida descartada para evitar conflito"

            if source_column is not None:
                usados.add(source_column)

            saneado[coluna_modelo] = {
                "source_column": source_column,
                "confidence": float(confidence or 0.0),
                "reason": str(reason or ""),
            }

        for coluna_modelo in colunas_modelo:
            if coluna_modelo not in saneado:
                saneado[coluna_modelo] = {
                    "source_column": None,
                    "confidence": 0.0,
                    "reason": "coluna não retornada pela IA",
                }

        return IAMappingResult(
            sucesso=True,
            provider="openai",
            model=model,
            mapeamento=saneado,
            bruto=bruto,
            erro="",
        )

    except Exception as exc:
        return IAMappingResult(
            sucesso=True,
            provider="local",
            model="heuristica",
            mapeamento=heuristico,
            bruto=json.dumps({"mapping": heuristico}, ensure_ascii=False, indent=2),
            erro=f"Falha na OpenAI, usando heurística: {exc}",
        )


def aplicar_mapeamento_df(
    df_origem: pd.DataFrame,
    mapeamento: Dict[str, str | None],
    manter_colunas_nao_mapeadas: bool = False,
) -> pd.DataFrame:
    if df_origem is None or df_origem.empty:
        return pd.DataFrame()

    saida = pd.DataFrame(index=df_origem.index)

    for coluna_modelo, coluna_origem in mapeamento.items():
        if coluna_origem and coluna_origem in df_origem.columns:
            saida[coluna_modelo] = df_origem[coluna_origem]
        else:
            saida[coluna_modelo] = ""

    if manter_colunas_nao_mapeadas:
        mapeadas = {c for c in mapeamento.values() if c}
        extras = [c for c in df_origem.columns if c not in mapeadas]
        for coluna in extras:
            saida[f"origem__{coluna}"] = df_origem[coluna]

    return saida


def normalizar_mapping_para_session(
    mapping_result: Dict[str, Dict[str, Any]],
) -> Dict[str, Optional[str]]:
    saida: Dict[str, Optional[str]] = {}
    for coluna_modelo, dados in mapping_result.items():
        source_column = None
        if isinstance(dados, dict):
            source_column = dados.get("source_column")
        saida[str(coluna_modelo)] = source_column if source_column else None
    return saida
