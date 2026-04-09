from __future__ import annotations

import pandas as pd
import streamlit as st


ETAPAS_VALIDAS_ORIGEM = {"origem", "mapeamento", "final"}


# =========================================================
# HELPERS
# =========================================================
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


def _is_coluna_deposito(nome) -> bool:
    nome = str(nome).lower().strip()
    return "deposit" in nome


# 🔒 BLOQUEIO REAL ID (regra Bling)
def _is_coluna_id(nome) -> bool:
    nome = str(nome).lower().strip()
    return nome == "id" or "id produto" in nome


def _detectar_duplicidades(mapping: dict) -> dict[str, list[str]]:
    usados: dict[str, list[str]] = {}
    for col_modelo, col_origem in mapping.items():
        col_origem = str(col_origem or "").strip()
        if not col_origem:
            continue
        usados.setdefault(col_origem, []).append(col_modelo)

    return {k: v for k, v in usados.items() if len(v) > 1}


# =========================================================
# CORE
# =========================================================
def _montar_df_saida(df_origem, df_modelo, mapping):
    df_saida = pd.DataFrame(index=range(len(df_origem)))

    deposito = str(st.session_state.get("deposito_nome", "") or "")

    for col in df_modelo.columns:

        # 🔒 ID nunca é preenchido
        if _is_coluna_id(col):
            df_saida[col] = ""
            continue

        # 🏬 Depósito fixo
        if _is_coluna_deposito(col):
            df_saida[col] = deposito
            continue

        origem = str(mapping.get(col, "") or "").strip()

        if origem and origem in df_origem.columns:
            df_saida[col] = df_origem[origem].reset_index(drop=True)
        else:
            df_saida[col] = ""

    return df_saida


# =========================================================
# RENDER
# =========================================================
def render_origem_mapeamento():
    if _get_etapa() != "mapeamento":
        return

    df_origem = st.session_state.get("df_origem")
    df_modelo = st.session_state.get("df_modelo_mapeamento")

    if not _safe_df_com_linhas(df_origem) or not _safe_df(df_modelo):
        st.warning("Dados inválidos.")
        return

    st.subheader("🧠 Mapeamento de colunas")

    # 🔥 manter valor persistente
    deposito = st.text_input(
        "📦 Nome do Depósito (Bling)",
        value=str(st.session_state.get("deposito_nome", "") or ""),
        key="deposito_nome",
        placeholder="Ex: ifood, geral, principal",
    )

    # 🔥 PERSISTÊNCIA REAL DO MAPPING
    if "mapping_origem" not in st.session_state:
        st.session_state["mapping_origem"] = {}

    mapping = st.session_state["mapping_origem"]

    usadas = set()

    for col_modelo in df_modelo.columns:

        # 🔒 ID BLOQUEADO
        if _is_coluna_id(col_modelo):
            st.text_input(
                col_modelo,
                value="(Automático / Bloqueado)",
                disabled=True,
            )
            mapping[col_modelo] = ""
            continue

        # ignora deposito (já tratado)
        if _is_coluna_deposito(col_modelo):
            continue

        # 🔥 evita duplicação
        opcoes = [""] + list(df_origem.columns)

        valor_atual = mapping.get(col_modelo, "")

        valor = st.selectbox(
            col_modelo,
            opcoes,
            index=opcoes.index(valor_atual) if valor_atual in opcoes else 0,
            key=f"map_{col_modelo}",
        )

        if valor:
            usadas.add(valor)

        mapping[col_modelo] = valor

    # 🔥 valida duplicidade
    duplicidades = _detectar_duplicidades(mapping)

    erro = False

    if duplicidades:
        erro = True
        st.error("❌ Existe coluna sendo usada mais de uma vez.")

    # 🔥 salva estado corretamente
    st.session_state["mapping_origem"] = mapping

    # 🔥 gera preview SEM QUEBRAR
    df_saida = _montar_df_saida(df_origem, df_modelo, mapping)

    st.dataframe(df_saida.head(20), use_container_width=True)

    # 🔥 não sobrescreve se já existir edição futura
    st.session_state["df_saida"] = df_saida.copy()

    if "df_final" not in st.session_state:
        st.session_state["df_final"] = df_saida.copy()

    col1, col2 = st.columns(2)

    with col1:
        if st.button("🚀 Avançar", use_container_width=True, disabled=erro):
            _set_etapa("final")
            st.rerun()

    with col2:
        if st.button("⬅️ Voltar", use_container_width=True):
            _set_etapa("origem")
            st.rerun()
