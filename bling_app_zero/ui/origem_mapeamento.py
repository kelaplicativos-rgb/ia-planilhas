from __future__ import annotations

import pandas as pd
import streamlit as st


ETAPAS_VALIDAS_ORIGEM = {"origem", "mapeamento"}


def _safe_df(df) -> bool:
    try:
        return isinstance(df, pd.DataFrame) and len(df.columns) > 0
    except Exception:
        return False


def _safe_df_com_linhas(df) -> bool:
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
        if not _safe_df_com_linhas(df):
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
            nome = _normalizar_texto_coluna(v) or f"Coluna_{i + 1}"
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
            nome = _normalizar_texto_coluna(col) or f"Coluna_{i + 1}"
            base = nome
            c = 2
            while nome in usadas:
                nome = f"{base}_{c}"
                c += 1
            usadas.add(nome)
            novas.append(nome)

        df2.columns = novas
        return df2.reset_index(drop=True)
    except Exception:
        return df


def _preparar_df_origem_para_mapeamento(df):
    df = _promover_primeira_linha_para_header_se_preciso(df)
    df = _normalizar_nomes_colunas(df)
    return df


def _preparar_df_modelo_para_mapeamento(df):
    return _normalizar_nomes_colunas(df)


def _get_modelo():
    if st.session_state.get("tipo_operacao_bling") == "cadastro":
        return st.session_state.get("df_modelo_cadastro")
    return st.session_state.get("df_modelo_estoque")


def _get_deposito() -> str:
    for chave in ["deposito_nome", "deposito_nome_widget", "deposito_nome_manual"]:
        valor = str(st.session_state.get(chave, "") or "").strip()
        if valor:
            if chave != "deposito_nome":
                st.session_state["deposito_nome"] = valor
            return valor
    return ""


def _is_coluna_preco(nome) -> bool:
    nome = str(nome).lower().strip()
    return any(
        p in nome
        for p in ["preço", "preco", "valor venda", "preco venda", "price"]
    )


def _is_coluna_deposito(nome) -> bool:
    nome = str(nome).lower().strip()
    return "deposit" in nome or "deposito" in nome


def _preview_coluna(df, coluna):
    try:
        if coluna in df.columns:
            return df[coluna].fillna("").astype(str).head(5).tolist()
    except Exception:
        pass
    return []


def _montar_df_saida(df_origem, df_modelo, mapping):
    df_saida = pd.DataFrame(index=range(len(df_origem)))

    for col in df_modelo.columns:
        origem = mapping.get(col, "")

        if origem in df_origem.columns:
            df_saida[col] = df_origem[origem]
        else:
            df_saida[col] = ""

    return df_saida


def _voltar_para_origem():
    st.session_state["etapa_origem"] = "origem"
    st.rerun()


def render_origem_mapeamento():
    if st.session_state.get("etapa_origem") != "mapeamento":
        return

    df_origem = st.session_state.get("df_origem")
    df_modelo = _get_modelo()

    if not _safe_df_com_linhas(df_origem) or not _safe_df(df_modelo):
        st.warning("Dados inválidos.")
        return

    df_origem = _preparar_df_origem_para_mapeamento(df_origem)
    df_modelo = _preparar_df_modelo_para_mapeamento(df_modelo)

    mapping = {}

    for col_modelo in df_modelo.columns:
        mapping[col_modelo] = st.selectbox(
            col_modelo,
            [""] + list(df_origem.columns),
            key=f"map_{col_modelo}",
        )

    df_saida = _montar_df_saida(df_origem, df_modelo, mapping)

    st.dataframe(df_saida.head())

    st.session_state["df_saida"] = df_saida
    st.session_state["df_final"] = df_saida

    # 🔥 CORREÇÃO PRINCIPAL AQUI
    if st.button("🚀 Avançar"):
        st.session_state["etapa_origem"] = "final"
        st.rerun()

    if st.button("⬅️ Voltar"):
        _voltar_para_origem()
