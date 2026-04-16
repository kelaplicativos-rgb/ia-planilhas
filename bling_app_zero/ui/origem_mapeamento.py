from __future__ import annotations

import re

import pandas as pd
import streamlit as st

from bling_app_zero.ui.app_helpers import (
    ir_para_etapa,
    safe_df,
    safe_df_estrutura,
    voltar_etapa_anterior,
)


def _normalizar_texto(valor) -> str:
    texto = str(valor or "").strip().lower()
    texto = re.sub(r"\s+", " ", texto)
    return texto


def _normalizar_url_imagens(valor) -> str:
    texto = str(valor or "").strip()
    if not texto:
        return ""

    texto = texto.replace("\n", "|").replace("\r", "|")
    texto = texto.replace(";", "|").replace(",", "|")

    partes = [p.strip() for p in texto.split("|") if p.strip()]
    vistos = set()
    urls = []

    for parte in partes:
        if parte not in vistos:
            vistos.add(parte)
            urls.append(parte)

    return "|".join(urls)


def _obter_df_base() -> pd.DataFrame:
    df_precificado = st.session_state.get("df_precificado")
    if safe_df(df_precificado):
        return df_precificado.copy()

    df_origem = st.session_state.get("df_origem")
    if safe_df(df_origem):
        return df_origem.copy()

    return pd.DataFrame()


def _obter_df_modelo() -> pd.DataFrame:
    df_modelo = st.session_state.get("df_modelo")
    if safe_df_estrutura(df_modelo):
        return df_modelo.copy()
    return pd.DataFrame()


def _detectar_operacao() -> str:
    operacao = str(st.session_state.get("tipo_operacao") or "").strip().lower()
    if operacao not in {"cadastro", "estoque"}:
        operacao = "cadastro"
    return operacao


def _sugerir_coluna(coluna_modelo: str, colunas_origem: list[str]) -> str:
    regras = {
        "Código": ["codigo", "código", "sku", "id"],
        "Descrição": ["descricao", "descrição", "nome", "produto", "titulo"],
        "Descrição Curta": ["descricao curta", "descrição curta", "descricao", "descrição", "nome"],
        "Preço de venda": ["_preco_calculado", "preço calculado", "preco calculado"],
        "Preço unitário (OBRIGATÓRIO)": ["_preco_calculado", "preço calculado", "preco calculado"],
        "Preço": ["_preco_calculado", "preço calculado", "preco calculado", "preco", "preço"],
        "Valor": ["_preco_calculado", "preço calculado", "preco calculado", "valor"],
        "GTIN/EAN": ["gtin", "ean", "codigo de barras", "código de barras"],
        "GTIN": ["gtin", "ean", "codigo de barras", "código de barras"],
        "URL Imagens": ["url imagens", "url_imagens", "imagem", "imagens", "image", "images"],
        "Categoria": ["categoria", "departamento", "grupo"],
        "Depósito (OBRIGATÓRIO)": [],
        "Preço calculado": ["_preco_calculado", "preço calculado", "preco calculado"],
    }

    candidatos = regras.get(coluna_modelo, [])
    mapa_origem = {_normalizar_texto(c): c for c in colunas_origem}

    for candidato in candidatos:
        candidato_n = _normalizar_texto(candidato)
        if candidato_n in mapa_origem:
            return mapa_origem[candidato_n]

    alvo = _normalizar_texto(coluna_modelo)

    for col in colunas_origem:
        col_n = _normalizar_texto(col)
        if alvo and alvo in col_n:
            return col

    for col in colunas_origem:
        col_n = _normalizar_texto(col)
        if any(_normalizar_texto(token) in col_n for token in candidatos):
            return col

    return ""


def _sugerir_mapping(df_base: pd.DataFrame, df_modelo: pd.DataFrame) -> dict[str, str]:
    colunas_origem = [str(c) for c in df_base.columns.tolist()]
    colunas_modelo = [str(c) for c in df_modelo.columns.tolist()]

    mapping = {}
    for coluna_modelo in colunas_modelo:
        mapping[coluna_modelo] = _sugerir_coluna(coluna_modelo, colunas_origem)

    return mapping


def _inicializar_mapping(df_base: pd.DataFrame, df_modelo: pd.DataFrame) -> dict[str, str]:
    mapping_salvo = st.session_state.get("mapping_manual", {})
    colunas_modelo = [str(c) for c in df_modelo.columns.tolist()]

    if not isinstance(mapping_salvo, dict) or not mapping_salvo:
        sugerido = _sugerir_mapping(df_base, df_modelo)
        st.session_state["mapping_sugerido"] = sugerido
        st.session_state["mapping_manual"] = sugerido.copy()
        return sugerido

    for coluna in colunas_modelo:
        mapping_salvo.setdefault(coluna, "")

    st.session_state["mapping_manual"] = mapping_salvo
    return mapping_salvo


def _colunas_preco_modelo(df_modelo: pd.DataFrame) -> list[str]:
    candidatos = []
    for col in df_modelo.columns:
        nome = str(col)
        n = _normalizar_texto(nome)

        if n in {
            "preco",
            "preço",
            "preco de venda",
            "preço de venda",
            "preco unitario obrigatorio",
            "preço unitário obrigatório",
            "preco unitario",
            "preço unitário",
            "valor",
            "valor venda",
            "valor unitario",
            "valor unitário",
        }:
            candidatos.append(nome)
            continue

        if "preco" in n or "preço" in n or "valor" in n:
            candidatos.append(nome)

    vistos = set()
    saida = []
    for c in candidatos:
        if c not in vistos:
            vistos.add(c)
            saida.append(c)
    return saida


def _coluna_preco_prioritaria(df_modelo: pd.DataFrame, operacao: str) -> str:
    prioridades_estoque = [
        "Preço",
        "Preço unitário (OBRIGATÓRIO)",
        "Preço unitário",
        "Valor",
    ]
    prioridades_cadastro = [
        "Preço de venda",
        "Preço",
        "Valor",
    ]

    colunas = [str(c) for c in df_modelo.columns.tolist()]
    prioridades = prioridades_estoque if operacao == "estoque" else prioridades_cadastro

    for prioridade in prioridades:
        if prioridade in colunas:
            return prioridade

    candidatas = _colunas_preco_modelo(df_modelo)
    return candidatas[0] if candidatas else ""


def _coluna_imagens_modelo(df_modelo: pd.DataFrame) -> str:
    colunas = [str(c) for c in df_modelo.columns.tolist()]
    for prioridade in ["URL Imagens", "Url Imagens", "Imagens", "Imagem"]:
        if prioridade in colunas:
            return prioridade

    for col in colunas:
        n = _normalizar_texto(col)
        if "imagem" in n or "image" in n:
            return col

    return ""


def _coluna_deposito_modelo(df_modelo: pd.DataFrame) -> str:
    colunas = [str(c) for c in df_modelo.columns.tolist()]
    for prioridade in ["Depósito (OBRIGATÓRIO)", "Depósito", "Deposito (OBRIGATÓRIO)", "Deposito"]:
        if prioridade in colunas:
            return prioridade

    for col in colunas:
        n = _normalizar_texto(col)
        if "deposito" in n or "depósito" in n:
            return col

    return ""


def _aplicar_mapping(df_base: pd.DataFrame, df_modelo: pd.DataFrame, mapping: dict[str, str]) -> pd.DataFrame:
    operacao = _detectar_operacao()
    saida = pd.DataFrame(index=df_base.index)

    for coluna_modelo in df_modelo.columns:
        coluna_modelo = str(coluna_modelo)
        coluna_origem = str(mapping.get(coluna_modelo, "") or "").strip()

        if coluna_origem and coluna_origem in df_base.columns:
            saida[coluna_modelo] = df_base[coluna_origem]
        else:
            saida[coluna_modelo] = ""

    # ===== preço calculado vai para a coluna real do modelo =====
    if "_preco_calculado" in df_base.columns:
        coluna_preco_destino = _coluna_preco_prioritaria(df_modelo, operacao)
        if coluna_preco_destino:
            saida[coluna_preco_destino] = df_base["_preco_calculado"]

    # ===== estoque: depósito =====
    if operacao == "estoque":
        coluna_deposito = _coluna_deposito_modelo(df_modelo)
        if coluna_deposito:
            saida[coluna_deposito] = str(st.session_state.get("deposito_nome", "") or "").strip()

    # ===== cadastro: imagens com | =====
    coluna_imagens = _coluna_imagens_modelo(df_modelo)
    if coluna_imagens and coluna_imagens in saida.columns:
        saida[coluna_imagens] = saida[coluna_imagens].apply(_normalizar_url_imagens)

    return saida.fillna("")


def _preview_mapping(df_final: pd.DataFrame) -> None:
    if not safe_df_estrutura(df_final):
        return

    st.markdown("### Preview do resultado mapeado")

    if df_final.empty:
        st.dataframe(pd.DataFrame(columns=df_final.columns), use_container_width=True)
    else:
        st.dataframe(df_final.head(50), use_container_width=True)


def render_origem_mapeamento() -> None:
    st.subheader("3. Mapeamento")
    st.caption(
        "Aqui o sistema cruza a planilha de origem com o modelo anexado e monta a saída final."
    )

    df_base = _obter_df_base()
    df_modelo = _obter_df_modelo()

    if not safe_df(df_base):
        st.warning("A origem precisa estar carregada antes do mapeamento.")
        if st.button("⬅️ Voltar para precificação", use_container_width=True, key="btn_voltar_mapeamento_sem_base"):
            voltar_etapa_anterior()
        return

    if not safe_df_estrutura(df_modelo):
        st.warning("O modelo precisa estar carregado antes do mapeamento.")
        if st.button("⬅️ Voltar para precificação", use_container_width=True, key="btn_voltar_mapeamento_sem_modelo"):
            voltar_etapa_anterior()
        return

    mapping = _inicializar_mapping(df_base, df_modelo)

    st.markdown("### Revisão do mapeamento")

    opcoes_origem = [""] + [str(c) for c in df_base.columns.tolist()]

    for coluna_modelo in df_modelo.columns:
        coluna_modelo = str(coluna_modelo)
        valor_atual = st.session_state["mapping_manual"].get(coluna_modelo, "")
        index_atual = opcoes_origem.index(valor_atual) if valor_atual in opcoes_origem else 0

        st.session_state["mapping_manual"][coluna_modelo] = st.selectbox(
            f"{coluna_modelo}",
            options=opcoes_origem,
            index=index_atual,
            key=f"map_{coluna_modelo}",
        )

    st.markdown("### Aplicar montagem final")

    if st.button("Aplicar mapeamento", use_container_width=True, key="btn_aplicar_mapeamento"):
        df_final = _aplicar_mapping(
            df_base=df_base,
            df_modelo=df_modelo,
            mapping=st.session_state["mapping_manual"],
        )

        st.session_state["df_final"] = df_final
        st.success("Mapeamento aplicado com sucesso.")

    df_final = st.session_state.get("df_final")
    if safe_df_estrutura(df_final):
        _preview_mapping(df_final)

    st.markdown("---")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("⬅️ Voltar para precificação", use_container_width=True, key="btn_voltar_mapeamento"):
            voltar_etapa_anterior()

    with col2:
        if st.button("Continuar ➜", use_container_width=True, key="btn_continuar_mapeamento"):
            if not safe_df_estrutura(st.session_state.get("df_final")):
                st.error("Aplique o mapeamento antes de continuar.")
                return

            ir_para_etapa("preview_final")
