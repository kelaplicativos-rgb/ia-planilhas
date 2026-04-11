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


def _normalizar_nome_coluna(nome) -> str:
    try:
        return str(nome).strip().lower()
    except Exception:
        return ""


def _is_coluna_preco_venda(nome) -> bool:
    nome = _normalizar_nome_coluna(nome)

    prioridades_exatas = {
        "preço de venda",
        "preco de venda",
        "valor venda",
        "preço unitário",
        "preco unitario",
        "preço unitário (obrigatório)",
        "preco unitario (obrigatorio)",
    }
    if nome in prioridades_exatas:
        return True

    if "venda" in nome and ("preço" in nome or "preco" in nome or "valor" in nome):
        return True

    if ("unitário" in nome or "unitario" in nome) and ("preço" in nome or "preco" in nome):
        return True

    return False


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


def _obter_df_fonte():
    candidatos = [
        st.session_state.get("df_calc_precificado"),
        st.session_state.get("df_precificado"),
        st.session_state.get("df_origem"),
    ]

    for df in candidatos:
        if _safe_df_com_linhas(df):
            return df

    return None


def _sanitizar_valor(valor):
    try:
        if valor is None:
            return ""

        valor = str(valor)
        valor = valor.replace("⚠️", "").strip()

        if valor.lower() in ["none", "nan"]:
            return ""

        return valor
    except Exception:
        return ""


def _normalizar_situacao(valor):
    try:
        valor = str(valor).strip().lower()
        if valor in ["ativo", "1", "true"]:
            return "Ativo"
        return "Inativo"
    except Exception:
        return "Inativo"


def _aplicar_mapeamento_automatico_preco(
    mapping: dict,
    df_modelo: pd.DataFrame,
    df_fonte: pd.DataFrame,
) -> dict:
    try:
        col_preco_origem = str(
            st.session_state.get("coluna_preco_unitario_origem") or ""
        ).strip()

        if not col_preco_origem or col_preco_origem not in df_fonte.columns:
            return mapping

        novo_mapping = dict(mapping)

        for col_modelo in df_modelo.columns:
            if _is_coluna_preco_venda(col_modelo) and not str(
                novo_mapping.get(col_modelo, "") or ""
            ).strip():
                novo_mapping[col_modelo] = col_preco_origem

        return novo_mapping
    except Exception:
        return mapping


# =========================================================
# CORE
# =========================================================
def _montar_df_saida(df_fonte, df_modelo, mapping):
    df_saida_base = st.session_state.get("df_saida")

    if (
        isinstance(df_saida_base, pd.DataFrame)
        and len(df_saida_base) == len(df_fonte)
        and list(df_saida_base.columns) == list(df_modelo.columns)
    ):
        df_saida = df_saida_base.copy()
    else:
        df_saida = pd.DataFrame(index=range(len(df_fonte)), columns=df_modelo.columns)

    deposito = str(st.session_state.get("deposito_nome", "") or "")

    for col in df_modelo.columns:
        if _is_coluna_id(col):
            df_saida[col] = ""
            continue

        if _is_coluna_deposito(col):
            df_saida[col] = deposito
            continue

        origem = str(mapping.get(col, "") or "").strip()

        if origem and origem in df_fonte.columns:
            serie = df_fonte[origem].reset_index(drop=True)
            serie = serie.apply(_sanitizar_valor)
            df_saida[col] = serie
        else:
            if col not in df_saida.columns:
                df_saida[col] = ""
            else:
                df_saida[col] = df_saida[col].fillna("")

        if "situa" in str(col).lower():
            df_saida[col] = df_saida[col].apply(_normalizar_situacao)

    return df_saida


# =========================================================
# RENDER
# =========================================================
def render_origem_mapeamento():
    if _get_etapa() != "mapeamento":
        return

    df_fonte = _obter_df_fonte()
    df_modelo = _obter_df_modelo()

    if not _safe_df_com_linhas(df_fonte) or not _safe_df(df_modelo):
        st.warning("Dados inválidos.")
        return

    st.subheader("Mapeamento de colunas")

    st.text_input(
        "Nome do Depósito (Bling)",
        value=str(st.session_state.get("deposito_nome", "") or ""),
        key="deposito_nome",
        placeholder="Ex: ifood, geral, principal",
    )

    if "mapping_origem" not in st.session_state:
        st.session_state["mapping_origem"] = {}

    mapping = dict(st.session_state["mapping_origem"])
    mapping = _aplicar_mapeamento_automatico_preco(mapping, df_modelo, df_fonte)

    for col_modelo in df_modelo.columns:
        if _is_coluna_id(col_modelo):
            st.text_input(
                col_modelo,
                value="(Automático / Bloqueado)",
                disabled=True,
            )
            mapping[col_modelo] = ""
            continue

        if _is_coluna_deposito(col_modelo):
            continue

        opcoes = [""] + list(df_fonte.columns)
        valor_atual = mapping.get(col_modelo, "")

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
        st.error("❌ Existe coluna sendo usada mais de uma vez.")

    if not erro:
        st.session_state["mapping_origem"] = mapping

    df_saida = _montar_df_saida(df_fonte, df_modelo, mapping)

    st.dataframe(df_saida.head(15), use_container_width=True)

    st.session_state["df_saida"] = df_saida.copy()
    st.session_state["df_final"] = df_saida.copy()

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Avançar", use_container_width=True, disabled=erro):
            _set_etapa("final")
            st.rerun()

    with col2:
        if st.button("⬅️ Voltar", use_container_width=True):
            _set_etapa("origem")
            st.rerun()
