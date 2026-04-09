from __future__ import annotations

import pandas as pd
import streamlit as st


ETAPAS_VALIDAS_ORIGEM = {"origem", "mapeamento", "final"}


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


# =========================
# 🔥 NOVO — SINCRONIZA ETAPA
# =========================
def _set_etapa(etapa: str):
    etapa = str(etapa).strip().lower()

    st.session_state["etapa_origem"] = etapa
    st.session_state["etapa"] = etapa
    st.session_state["etapa_fluxo"] = etapa


def _get_etapa() -> str:
    for chave in ["etapa_origem", "etapa", "etapa_fluxo"]:
        val = str(st.session_state.get(chave) or "").strip().lower()
        if val:
            return val
    return "origem"


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
            st.session_state["deposito_nome"] = valor
            return valor
    return ""


def _is_coluna_deposito(nome) -> bool:
    nome = str(nome).lower().strip()
    return "deposit" in nome or "deposito" in nome


def _get_df_base_mapeamento(df_origem: pd.DataFrame) -> pd.DataFrame:
    """
    Usa o DF mais atualizado possível para que a precificação
    reflita no preview final e no download.
    Prioridade:
    1) df_base
    2) df_dados
    3) df_origem
    """
    try:
        for chave in ["df_base", "df_dados", "df_origem"]:
            df = st.session_state.get(chave)
            if _safe_df(df) and len(df) == len(df_origem):
                return df.copy()
    except Exception:
        pass

    return df_origem.copy()


def _montar_df_saida(df_origem, df_modelo, mapping):
    df_base = _get_df_base_mapeamento(df_origem)
    df_saida = pd.DataFrame(index=range(len(df_base)))

    deposito_fixo = _get_deposito()

    for col in df_modelo.columns:

        if _is_coluna_deposito(col):
            df_saida[col] = deposito_fixo
            continue

        origem = mapping.get(col, "")

        if origem in df_base.columns:
            df_saida[col] = df_base[origem]
        elif origem in df_origem.columns:
            df_saida[col] = df_origem[origem]
        else:
            df_saida[col] = ""

    return df_saida


def _voltar_para_origem():
    _set_etapa("origem")
    st.rerun()


def render_origem_mapeamento():

    # 🔥 CORREÇÃO CRÍTICA AQUI
    if _get_etapa() != "mapeamento":
        return

    df_origem = st.session_state.get("df_origem")
    df_modelo = _get_modelo()

    if not _safe_df_com_linhas(df_origem) or not _safe_df(df_modelo):
        st.warning("Dados inválidos.")
        return

    df_origem = _preparar_df_origem_para_mapeamento(df_origem)
    df_modelo = _preparar_df_modelo_para_mapeamento(df_modelo)

    st.session_state["df_origem"] = df_origem
    st.session_state["df_modelo_mapeamento"] = df_modelo

    mapping_salvo = st.session_state.get("mapping_origem", {})
    if not isinstance(mapping_salvo, dict):
        mapping_salvo = {}

    mapping = {}

    st.text_input(
        "📦 Nome do Depósito (Bling)",
        key="deposito_nome_widget",
        placeholder="Ex: ifood, geral, principal",
    )

    for col_modelo in df_modelo.columns:

        if _is_coluna_deposito(col_modelo):
            continue

        opcoes = [""] + list(df_origem.columns)

        valor_atual = st.session_state.get(
            f"map_{col_modelo}",
            mapping_salvo.get(col_modelo, ""),
        )

        if valor_atual not in opcoes:
            valor_atual = ""

        indice_atual = opcoes.index(valor_atual) if valor_atual in opcoes else 0

        mapping[col_modelo] = st.selectbox(
            col_modelo,
            opcoes,
            index=indice_atual,
            key=f"map_{col_modelo}",
        )

    st.session_state["mapping_origem"] = mapping

    df_saida = _montar_df_saida(df_origem, df_modelo, mapping)

    st.dataframe(df_saida.head(), use_container_width=True)

    st.session_state["df_saida"] = df_saida.copy()
    st.session_state["df_final"] = df_saida.copy()

    col1, col2 = st.columns(2)

    with col1:
        if st.button("🚀 Avançar", use_container_width=True):
            st.session_state["df_saida"] = df_saida.copy()
            st.session_state["df_final"] = df_saida.copy()
            st.session_state["mapping_origem"] = mapping
            _set_etapa("final")
            st.rerun()

    with col2:
        if st.button("⬅️ Voltar", use_container_width=True):
            _voltar_para_origem()
