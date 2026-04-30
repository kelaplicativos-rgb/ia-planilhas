from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher
from typing import Any

import pandas as pd
import streamlit as st


CANONICAL_SOURCE_ALIASES = {
    "descricao": [
        "descricao",
        "descrição",
        "nome",
        "produto",
        "titulo",
        "title",
        "name",
        "xprod",
    ],
    "descricao_complementar": [
        "descricao complementar",
        "descrição complementar",
        "descricao longa",
        "detalhes",
        "complemento",
        "informacoes",
        "informações",
    ],
    "codigo": ["codigo", "código", "sku", "referencia", "referência", "ref", "cod", "cprod"],
    "gtin": ["gtin", "ean", "codigo de barras", "código de barras", "barcode", "cean"],
    "preco": ["preco", "preço", "valor", "price", "preco venda", "preço venda", "preco unitario", "preço unitário"],
    "preco_custo": ["preco custo", "preço custo", "custo", "valor custo", "vuncom"],
    "estoque": ["estoque", "quantidade", "saldo", "qtd", "stock", "available", "qcom", "status", "disponibilidade"],
    "imagem": ["imagem", "imagens", "image", "images", "foto", "fotos", "url imagem", "url imagens"],
    "marca": ["marca", "brand", "fabricante"],
    "categoria": ["categoria", "category", "departamento", "breadcrumb"],
    "ncm": ["ncm"],
    "deposito": ["deposito", "depósito", "localizacao", "localização", "almoxarifado"],
}

TARGET_HINTS = {
    "descricao_complementar": ["complementar", "detalhada", "longa"],
    "descricao": ["descricao", "descrição", "nome", "produto"],
    "codigo": ["codigo", "código", "sku", "referencia", "referência"],
    "gtin": ["gtin", "ean", "barras"],
    "preco_custo": ["custo"],
    "preco": ["preco", "preço", "valor", "unitario", "unitário", "venda"],
    "estoque": ["estoque", "quantidade", "saldo", "balanco", "balanço", "status", "disponibilidade"],
    "imagem": ["imagem", "imagens", "foto", "fotos"],
    "marca": ["marca", "fabricante"],
    "categoria": ["categoria", "departamento"],
    "ncm": ["ncm"],
    "deposito": ["deposito", "depósito"],
}


def normalizar_texto(valor: Any) -> str:
    texto = str(valor or "").strip().lower()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(ch for ch in texto if not unicodedata.combining(ch))
    texto = re.sub(r"[^a-z0-9]+", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def modelo_bling_valido(df_modelo: object) -> bool:
    return isinstance(df_modelo, pd.DataFrame) and len(df_modelo.columns) > 0


def origem_valida(df_origem: object) -> bool:
    return isinstance(df_origem, pd.DataFrame) and len(df_origem.columns) > 0 and not df_origem.empty


def _canonical_from_name(nome: str) -> str:
    norm = normalizar_texto(nome)
    for canonical, aliases in CANONICAL_SOURCE_ALIASES.items():
        for alias in aliases:
            alias_norm = normalizar_texto(alias)
            if norm == alias_norm or alias_norm in norm or norm in alias_norm:
                return canonical
    return norm


def _score_coluna_destino_para_origem(col_destino: str, col_origem: str) -> float:
    destino_norm = normalizar_texto(col_destino)
    origem_norm = normalizar_texto(col_origem)
    destino_can = _canonical_from_name(destino_norm)
    origem_can = _canonical_from_name(origem_norm)

    if destino_can == origem_can:
        return 1.0

    score = SequenceMatcher(None, destino_norm, origem_norm).ratio()

    for canonical, hints in TARGET_HINTS.items():
        if any(normalizar_texto(h) in destino_norm for h in hints):
            aliases = CANONICAL_SOURCE_ALIASES.get(canonical, [])
            if origem_can == canonical or any(normalizar_texto(a) in origem_norm for a in aliases):
                score = max(score, 0.92)

    if "complement" in destino_norm and origem_can == "descricao":
        score = min(score, 0.40)

    if any(x in destino_norm for x in ["video", "youtube", "propaganda"]):
        score = 0.0

    return float(score)


def _classificar_score(score: float) -> tuple[str, str]:
    if score >= 0.90:
        return "🟢", "Alta"
    if score >= 0.72:
        return "🟡", "Média"
    return "🔴", "Baixa"


def _texto_para_estoque(valor: Any, estoque_disponivel: int, estoque_baixo: int) -> str:
    texto = normalizar_texto(valor)
    if not texto:
        return str(estoque_disponivel)

    if any(token in texto for token in ["esgotado", "indisponivel", "indisponivel", "sem estoque", "zerado", "fora estoque"]):
        return "0"

    if any(token in texto for token in ["baixo", "poucas", "ultimas", "ultimas unidades", "limitado"]):
        return str(estoque_baixo)

    if any(token in texto for token in ["disponivel", "em estoque", "pronta entrega", "comprar"]):
        return str(estoque_disponivel)

    if re.fullmatch(r"\d+", texto):
        return texto

    return str(estoque_disponivel)


def _destino_eh_estoque(coluna_destino: str) -> bool:
    destino_norm = normalizar_texto(coluna_destino)
    return any(token in destino_norm for token in ["estoque", "quantidade", "saldo", "balanco", "qtd", "qtde"])


def encontrar_melhor_coluna(col_destino: str, colunas_origem: list[str], usadas: set[str]) -> tuple[str, float]:
    candidatos: list[tuple[str, float]] = []
    for col_origem in colunas_origem:
        if col_origem in usadas:
            continue
        score = _score_coluna_destino_para_origem(col_destino, col_origem)
        candidatos.append((col_origem, score))
    if not candidatos:
        return "", 0.0
    candidatos.sort(key=lambda item: item[1], reverse=True)
    melhor_coluna, melhor_score = candidatos[0]
    if melhor_score < 0.55:
        return "", melhor_score
    return melhor_coluna, melhor_score


def montar_preview_inteligente(df_origem: pd.DataFrame, df_modelo: pd.DataFrame, operacao: str = "cadastro") -> tuple[pd.DataFrame, pd.DataFrame]:
    origem = df_origem.copy().fillna("") if origem_valida(df_origem) else pd.DataFrame()
    modelo = df_modelo.copy().fillna("") if modelo_bling_valido(df_modelo) else pd.DataFrame()

    if origem.empty or len(modelo.columns) == 0:
        return pd.DataFrame(), pd.DataFrame()

    resultado = pd.DataFrame(index=origem.index, columns=[str(c).strip() for c in modelo.columns]).fillna("")
    usadas: set[str] = set()
    linhas_mapa = []
    deposito_nome = str(st.session_state.get("deposito_nome", "") or "").strip()
    estoque_disponivel = int(st.session_state.get("estoque_padrao_disponivel", 5) or 5)
    estoque_baixo = int(st.session_state.get("estoque_padrao_baixo", 1) or 1)

    for col_destino in resultado.columns:
        destino_norm = normalizar_texto(col_destino)

        if "video" in destino_norm or "youtube" in destino_norm:
            linhas_mapa.append({"Campo Bling": col_destino, "Origem usada": "", "Confiança": "🔴 Ignorado", "Score": 0.0})
            continue

        if operacao == "estoque" and deposito_nome and "deposito" in destino_norm:
            resultado[col_destino] = deposito_nome
            linhas_mapa.append({"Campo Bling": col_destino, "Origem usada": "Depósito informado", "Confiança": "🟢 Automático", "Score": 1.0})
            continue

        col_origem, score = encontrar_melhor_coluna(col_destino, list(origem.columns), usadas)
        emoji, nivel = _classificar_score(score)

        if col_origem and score >= 0.55:
            serie = origem[col_origem].astype(str).fillna("")
            if _destino_eh_estoque(col_destino):
                resultado[col_destino] = serie.apply(lambda v: _texto_para_estoque(v, estoque_disponivel, estoque_baixo))
            else:
                resultado[col_destino] = serie
            if score >= 0.72:
                usadas.add(col_origem)
            linhas_mapa.append({"Campo Bling": col_destino, "Origem usada": col_origem, "Confiança": f"{emoji} {nivel}", "Score": round(score, 2)})
        else:
            linhas_mapa.append({"Campo Bling": col_destino, "Origem usada": "", "Confiança": "🔴 Sem mapa", "Score": round(score, 2)})

    mapa = pd.DataFrame(linhas_mapa)
    return resultado.fillna(""), mapa


def render_preview_inteligente(df_origem: pd.DataFrame, df_modelo: pd.DataFrame, titulo: str = "Preview inteligente no modelo do Bling") -> pd.DataFrame:
    if not origem_valida(df_origem):
        st.info("Carregue ou capture os dados do fornecedor antes de gerar o preview.")
        return pd.DataFrame()

    if not modelo_bling_valido(df_modelo):
        st.warning("Envie primeiro o modelo do Bling. O preview oficial só será gerado nas colunas do modelo anexado.")
        return pd.DataFrame()

    operacao = str(st.session_state.get("tipo_operacao", "cadastro") or "cadastro").strip().lower()
    df_preview, df_mapa = montar_preview_inteligente(df_origem, df_modelo, operacao=operacao)

    if df_preview.empty:
        st.info("Preview inteligente ainda não disponível.")
        return df_preview

    st.markdown(f"#### 🧠 {titulo}")
    st.caption("A tabela abaixo já usa exatamente as colunas do modelo Bling anexado. Sem modelo Bling, o sistema não gera preview nem download.")
    st.dataframe(df_preview.head(30), use_container_width=True)

    with st.expander("Mapa automático de colunas", expanded=False):
        st.dataframe(df_mapa, use_container_width=True)

    st.session_state["df_preview_inteligente"] = df_preview.copy()
    st.session_state["df_auto_mapa"] = df_mapa.copy()
    return df_preview
