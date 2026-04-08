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


def _get_deposito() -> str:
    for chave in ["deposito_nome", "deposito_nome_widget", "deposito_nome_manual"]:
        valor = str(st.session_state.get(chave, "") or "").strip()
        if valor:
            if chave != "deposito_nome":
                st.session_state["deposito_nome"] = valor
            return valor
    return ""


def _is_coluna_preco(nome) -> bool:
    nome = str(nome).lower()
    return any(
        p in nome
        for p in [
            "preço",
            "preco",
            "valor venda",
            "valor_venda",
            "preco venda",
            "preço venda",
            "price",
        ]
    )


def _is_coluna_deposito(nome) -> bool:
    nome = str(nome).lower()
    return "deposit" in nome or "depós" in nome or "deposito" in nome


def _preview_coluna(df, coluna):
    try:
        if coluna in df.columns:
            valores = df[coluna].dropna().astype(str).head(5).tolist()
            return valores
    except Exception:
        pass
    return []


def _get_coluna_preco_base_precificacao(df_origem: pd.DataFrame) -> str:
    try:
        coluna = str(st.session_state.get("coluna_preco_base", "") or "").strip()
        if coluna and coluna in df_origem.columns:
            return coluna
    except Exception:
        pass
    return ""


def _get_df_precificado() -> pd.DataFrame | None:
    try:
        df_precificado = st.session_state.get("df_precificado")
        if _safe_df(df_precificado):
            return df_precificado.copy()
    except Exception:
        pass
    return None


def _obter_serie_preco_para_saida(df_origem: pd.DataFrame) -> pd.Series:
    """
    Regra:
    1) Se existir df_precificado e a coluna base usada na precificação ainda existir nele,
       usa essa coluna já recalculada.
    2) Caso contrário, usa a coluna base escolhida diretamente da origem.
    3) Se nada existir, devolve coluna vazia.
    """
    try:
        coluna_preco_base = _get_coluna_preco_base_precificacao(df_origem)
        if not coluna_preco_base:
            return pd.Series([""] * len(df_origem), index=df_origem.index, dtype="object")

        df_precificado = _get_df_precificado()
        if _safe_df(df_precificado) and coluna_preco_base in df_precificado.columns:
            serie = df_precificado[coluna_preco_base]
            return serie.reindex(df_origem.index, fill_value="")

        if coluna_preco_base in df_origem.columns:
            return df_origem[coluna_preco_base].reindex(df_origem.index, fill_value="")

    except Exception:
        pass

    return pd.Series([""] * len(df_origem), index=df_origem.index, dtype="object")


def _montar_df_saida(df_origem: pd.DataFrame, df_modelo: pd.DataFrame, mapping: dict) -> pd.DataFrame:
    deposito = _get_deposito()
    serie_preco = _obter_serie_preco_para_saida(df_origem)

    df_saida = pd.DataFrame(index=df_origem.index)

    for col in df_modelo.columns:
        origem = mapping.get(col, "")

        if _is_coluna_preco(col):
            df_saida[col] = serie_preco
            continue

        if _is_coluna_deposito(col):
            df_saida[col] = deposito if deposito else ""
            continue

        if origem in df_origem.columns:
            df_saida[col] = df_origem[origem]
        else:
            df_saida[col] = ""

    return df_saida.reindex(columns=df_modelo.columns, fill_value="")


def render_origem_mapeamento():
    df_origem = st.session_state.get("df_origem")
    df_modelo = _get_modelo()

    if not _safe_df(df_origem) or not _safe_df(df_modelo):
        return

    df_origem = _preparar_df_para_mapeamento(df_origem)
    df_modelo = _preparar_df_para_mapeamento(df_modelo)

    st.session_state["df_origem"] = df_origem.copy()
    if st.session_state.get("tipo_operacao_bling") == "cadastro":
        st.session_state["df_modelo_cadastro"] = df_modelo.copy()
    else:
        st.session_state["df_modelo_estoque"] = df_modelo.copy()

    st.markdown("## 🔗 Mapeamento de colunas")

    with st.container():
        st.markdown("### 👁️ Preview da planilha fornecedora")
        st.dataframe(df_origem.head(5), use_container_width=True)

    colunas_modelo = list(df_modelo.columns)
    colunas_origem = list(df_origem.columns)

    mapping_key = f"mapeamento_manual_{str(st.session_state.get('tipo_operacao_bling', 'padrao')).lower()}"
    mapping_salvo = st.session_state.get(mapping_key, {}) or {}
    mapping = {}

    for col_modelo in colunas_modelo:
        if _is_coluna_preco(col_modelo):
            coluna_base = _get_coluna_preco_base_precificacao(df_origem)
            texto_preco = "Calculado automaticamente"
            if coluna_base:
                texto_preco = f"Calculado automaticamente ({coluna_base})"

            st.text_input(
                col_modelo,
                value=texto_preco,
                disabled=True,
                key=f"preco_fix_{col_modelo}",
            )
            mapping[col_modelo] = ""
            continue

        if _is_coluna_deposito(col_modelo):
            deposito = _get_deposito()
            st.text_input(
                col_modelo,
                value=deposito or "Depósito automático",
                disabled=True,
                key=f"deposito_fix_{col_modelo}",
            )
            mapping[col_modelo] = ""
            continue

        valor_inicial = str(mapping_salvo.get(col_modelo, "") or "")
        opcoes = [""] + colunas_origem

        if valor_inicial and valor_inicial not in opcoes:
            opcoes.append(valor_inicial)

        escolhido = st.selectbox(
            col_modelo,
            opcoes,
            index=opcoes.index(valor_inicial) if valor_inicial in opcoes else 0,
            key=f"map_{col_modelo}",
        )

        mapping[col_modelo] = escolhido

        if escolhido:
            valores = _preview_coluna(df_origem, escolhido)
            if valores:
                st.caption(f"Exemplo: {valores}")

    st.session_state[mapping_key] = mapping.copy()

    df_saida = _montar_df_saida(df_origem, df_modelo, mapping)

    st.session_state["df_saida"] = df_saida.copy()
    st.session_state["df_final"] = df_saida.copy()

    st.dataframe(df_saida.head(10), use_container_width=True)
