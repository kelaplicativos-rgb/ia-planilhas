from __future__ import annotations

import pandas as pd
import streamlit as st


def _safe_df(df) -> bool:
    try:
        return isinstance(df, pd.DataFrame) and not df.empty and len(df.columns) > 0
    except Exception:
        return False


def _normalizar_texto_coluna(valor) -> str:
    try:
        texto = str(valor if valor is not None else "").strip()
        texto = texto.replace("\n", " ").replace("\r", " ")
        while "  " in texto:
            texto = texto.replace("  ", " ")
        return texto
    except Exception:
        return ""


def _coluna_parece_generica(col) -> bool:
    texto = _normalizar_texto_coluna(col).lower()
    if texto == "" or texto.isdigit() or texto.startswith("unnamed:"):
        return True
    if texto in {"none", "nan"}:
        return True
    return False


def _linha_parece_cabecalho(valores: list) -> bool:
    try:
        if not valores:
            return False
        textos = [_normalizar_texto_coluna(v) for v in valores]
        preenchidos = [t for t in textos if t]
        if not preenchidos:
            return False
        unicos = len(set(preenchidos))
        proporcao_unicos = unicos / max(len(preenchidos), 1)
        qtd_textuais = sum(1 for t in preenchidos if not t.isdigit())
        proporcao_textual = qtd_textuais / max(len(preenchidos), 1)
        return proporcao_unicos >= 0.7 and proporcao_textual >= 0.7
    except Exception:
        return False


def _promover_primeira_linha_para_header_se_preciso(df):
    try:
        if not _safe_df(df):
            return df

        df2 = df.copy()
        colunas = list(df2.columns)

        qtd_genericas = sum(1 for c in colunas if _coluna_parece_generica(c))
        if qtd_genericas / max(len(colunas), 1) < 0.6:
            return df2

        primeira = df2.iloc[0].tolist()
        if not _linha_parece_cabecalho(primeira):
            return df2

        novos = []
        usados = set()

        for i, v in enumerate(primeira):
            nome = _normalizar_texto_coluna(v) or f"Coluna_{i+1}"
            base = nome
            c = 2
            while nome in usados:
                nome = f"{base}_{c}"
                c += 1
            usados.add(nome)
            novos.append(nome)

        df2.columns = novos
        return df2.iloc[1:].reset_index(drop=True)

    except Exception:
        return df


def _normalizar_nomes_colunas(df):
    try:
        if not _safe_df(df):
            return df

        df2 = df.copy()
        usadas = set()
        novas = []

        for i, col in enumerate(df2.columns):
            nome = _normalizar_texto_coluna(col) or f"Coluna_{i+1}"
            base = nome
            c = 2
            while nome in usadas:
                nome = f"{base}_{c}"
                c += 1
            usadas.add(nome)
            novas.append(nome)

        df2.columns = novas
        return df2
    except Exception:
        return df


def _preparar_df_para_mapeamento(df):
    df = _promover_primeira_linha_para_header_se_preciso(df)
    df = _normalizar_nomes_colunas(df)
    return df


def _get_modelo():
    if st.session_state.get("tipo_operacao_bling") == "cadastro":
        return st.session_state.get("df_modelo_cadastro")
    return st.session_state.get("df_modelo_estoque")


def _get_deposito():
    return st.session_state.get("deposito_nome", "")


def _is_coluna_preco(nome):
    nome = str(nome).lower()
    return "preco" in nome or "preço" in nome or "valor" in nome


# =========================================================
# 🔥 NOVO: PREVIEW INTELIGENTE DA COLUNA
# =========================================================
def _preview_coluna(df, coluna):
    try:
        if coluna in df.columns:
            valores = df[coluna].dropna().astype(str).head(5).tolist()
            return valores
    except Exception:
        pass
    return []


def render_origem_mapeamento():

    df_origem = st.session_state.get("df_origem")
    df_modelo = _get_modelo()

    if not _safe_df(df_origem) or not _safe_df(df_modelo):
        return

    df_origem = _preparar_df_para_mapeamento(df_origem)
    df_modelo = _preparar_df_para_mapeamento(df_modelo)

    st.markdown("## 🔗 Mapeamento de colunas")

    # =========================================================
    # 🔥 NOVO: PREVIEW FIXO DA PLANILHA FORNECEDORA
    # =========================================================
    with st.container():
        st.markdown("### 👁️ Preview da planilha fornecedora")
        st.dataframe(df_origem.head(5), use_container_width=True)

    colunas_modelo = list(df_modelo.columns)
    colunas_origem = list(df_origem.columns)

    mapping = {}

    for col_modelo in colunas_modelo:

        if _is_coluna_preco(col_modelo):
            st.text_input(col_modelo, value="Calculado automaticamente", disabled=True)
            mapping[col_modelo] = ""
            continue

        escolha = st.selectbox(col_modelo, [""] + colunas_origem)

        mapping[col_modelo] = escolha

        # =========================================================
        # 🔥 NOVO: MOSTRAR VALORES DA COLUNA SELECIONADA
        # =========================================================
        if escolha:
            valores = _preview_coluna(df_origem, escolha)

            if valores:
                st.caption(f"Exemplo: {valores}")

    # =========================================================
    # SAÍDA
    # =========================================================
    df_saida = pd.DataFrame(index=df_origem.index)

    for col in df_modelo.columns:
        origem = mapping.get(col, "")
        df_saida[col] = df_origem[origem] if origem in df_origem.columns else ""

    st.session_state["df_saida"] = df_saida
    st.session_state["df_final"] = df_saida

    st.dataframe(df_saida.head(10), use_container_width=True)
