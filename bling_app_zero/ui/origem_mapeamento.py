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


def _is_coluna_id(nome) -> bool:
    nome = str(nome).lower().strip()
    return nome == "id" or "id produto" in nome


def _is_coluna_situacao(nome) -> bool:
    nome = str(nome).lower().strip()
    return nome in {"situação", "situacao"} or "situa" in nome


def _detectar_duplicidades(mapping: dict) -> dict[str, list[str]]:
    usados: dict[str, list[str]] = {}
    for col_modelo, col_origem in mapping.items():
        col_origem = str(col_origem or "").strip()
        if not col_origem:
            continue
        usados.setdefault(col_origem, []).append(col_modelo)
    return {k: v for k, v in usados.items() if len(v) > 1}


def _obter_df_modelo():
    candidatos = [
        st.session_state.get("df_modelo_mapeamento"),
        st.session_state.get("df_modelo_cadastro"),
        st.session_state.get("df_modelo_estoque"),
    ]
    for df in candidatos:
        if _safe_df(df):
            return df
    return None


def _colunas_ja_usadas(mapping: dict, coluna_atual: str) -> set[str]:
    usados: set[str] = set()
    for col_modelo, col_origem in mapping.items():
        if str(col_modelo) == str(coluna_atual):
            continue
        col_origem = str(col_origem or "").strip()
        if col_origem:
            usados.add(col_origem)
    return usados


def _obter_opcoes_disponiveis(df_origem: pd.DataFrame, mapping: dict, coluna_atual: str) -> list[str]:
    atual = str(mapping.get(coluna_atual, "") or "").strip()
    usados = _colunas_ja_usadas(mapping, coluna_atual)

    opcoes = [""]
    for coluna in df_origem.columns:
        nome = str(coluna)
        if nome == atual or nome not in usados:
            opcoes.append(nome)

    return opcoes


def _valor_padrao_coluna(coluna_modelo: str) -> str:
    if _is_coluna_situacao(coluna_modelo):
        return "Ativo"
    return ""


# =========================================================
# CORE
# =========================================================
def _montar_df_saida(df_origem, df_modelo, mapping):
    df_saida_base = st.session_state.get("df_saida")
    if isinstance(df_saida_base, pd.DataFrame) and len(df_saida_base) == len(df_origem):
        df_saida = df_saida_base.copy()
    else:
        df_saida = pd.DataFrame(index=range(len(df_origem)))

    deposito = str(st.session_state.get("deposito_nome", "") or "").strip()

    for col in df_modelo.columns:
        if _is_coluna_id(col):
            df_saida[col] = ""
            continue

        if _is_coluna_deposito(col):
            df_saida[col] = deposito
            continue

        origem = str(mapping.get(col, "") or "").strip()

        if origem and origem in df_origem.columns:
            df_saida[col] = df_origem[origem].reset_index(drop=True)
            continue

        if col not in df_saida.columns:
            df_saida[col] = _valor_padrao_coluna(col)
            continue

        if _is_coluna_situacao(col):
            serie_atual = df_saida[col].astype(str).fillna("").str.strip()
            if (serie_atual == "").all():
                df_saida[col] = "Ativo"

    return df_saida


# =========================================================
# RENDER
# =========================================================
def render_origem_mapeamento():
    if _get_etapa() != "mapeamento":
        return

    df_origem = st.session_state.get("df_origem")
    df_modelo = _obter_df_modelo()

    if not _safe_df_com_linhas(df_origem) or not _safe_df(df_modelo):
        st.warning("Dados inválidos.")
        return

    st.subheader("📌 Mapeamento de colunas")

    st.text_input(
        "📦 Nome do Depósito (Bling)",
        value=str(st.session_state.get("deposito_nome", "") or ""),
        key="deposito_nome",
        placeholder="Ex: ifood, geral, principal",
    )

    if "mapping_origem" not in st.session_state:
        st.session_state["mapping_origem"] = {}

    mapping = dict(st.session_state["mapping_origem"])

    for col_modelo in df_modelo.columns:
        if _is_coluna_id(col_modelo):
            st.text_input(
                col_modelo,
                value="(Automático / Bloqueado)",
                disabled=True,
                key=f"id_locked_{col_modelo}",
            )
            mapping[col_modelo] = ""
            continue

        if _is_coluna_deposito(col_modelo):
            continue

        opcoes = _obter_opcoes_disponiveis(df_origem, mapping, col_modelo)
        valor_atual = str(mapping.get(col_modelo, "") or "").strip()

        if valor_atual not in opcoes:
            valor_atual = ""

        valor = st.selectbox(
            col_modelo,
            opcoes,
            index=opcoes.index(valor_atual) if valor_atual in opcoes else 0,
            key=f"map_{col_modelo}",
        )
        mapping[col_modelo] = valor

    duplicidades = _detectar_duplicidades(mapping)
    erro = False

    if duplicidades:
        erro = True
        descricoes = []
        for coluna_origem, colunas_modelo in duplicidades.items():
            descricoes.append(
                f"'{coluna_origem}' usada em: {', '.join([str(c) for c in colunas_modelo])}"
            )
        st.error("❌ Existe coluna sendo usada mais de uma vez.\n\n" + "\n".join(descricoes))

    if not erro:
        st.session_state["mapping_origem"] = mapping

    df_saida = _montar_df_saida(df_origem, df_modelo, mapping)

    st.dataframe(df_saida.head(15), use_container_width=True)

    st.session_state["df_saida"] = df_saida.copy()
    st.session_state["df_final"] = df_saida.copy()

    col1, col2 = st.columns(2)

    with col1:
        if st.button("➡️ Avançar", use_container_width=True, disabled=erro):
            _set_etapa("final")
            st.rerun()

    with col2:
        if st.button("⬅️ Voltar", use_container_width=True):
            _set_etapa("origem")
            st.rerun()
