from __future__ import annotations

import hashlib

import pandas as pd
import streamlit as st

from bling_app_zero.core.precificacao import aplicar_precificacao_no_fluxo
from bling_app_zero.ui.app_helpers import log_debug
from bling_app_zero.ui.origem_dados_estado import safe_df_dados


def safe_float(valor, default: float = 0.0) -> float:
    try:
        if valor is None or valor == "":
            return default
        return float(valor)
    except Exception:
        return default


def _df_preview_seguro(df: pd.DataFrame | None):
    try:
        if not safe_df_dados(df):
            return df

        df_preview = df.copy()

        for col in df_preview.columns:
            try:
                df_preview[col] = df_preview[col].apply(
                    lambda x: "" if pd.isna(x) else str(x)
                )
            except Exception:
                try:
                    df_preview[col] = df_preview[col].astype(str)
                except Exception:
                    pass

        return df_preview.replace(
            {"nan": "", "None": "", "<NA>": "", "NaT": ""}
        )
    except Exception:
        return df


def _hash_df(df: pd.DataFrame | None) -> str:
    try:
        if not safe_df_dados(df):
            return ""

        base = f"{list(df.columns)}|{len(df)}"
        try:
            amostra = df.head(20).fillna("").astype(str).to_csv(index=False)
        except Exception:
            amostra = repr(df.head(20))

        return hashlib.md5(f"{base}|{amostra}".encode("utf-8")).hexdigest()
    except Exception:
        return ""


def _normalizar_nome_coluna(nome: str) -> str:
    try:
        return str(nome).strip().lower()
    except Exception:
        return ""


def _detectar_coluna_preco_default(colunas: list[str]) -> int:
    try:
        candidatos = [
            "preco de custo",
            "preço de custo",
            "custo",
            "valor custo",
            "preco compra",
            "preço compra",
            "preco de compra",
            "preço de compra",
            "valor unitário",
            "valor unitario",
            "preco",
            "preço",
            "valor",
        ]

        colunas_lower = [_normalizar_nome_coluna(c) for c in colunas]

        for candidato in candidatos:
            for i, nome_col in enumerate(colunas_lower):
                if candidato in nome_col:
                    return i

        return 0
    except Exception:
        return 0


def _colunas_preco_prioritarias(df: pd.DataFrame | None) -> list[str]:
    try:
        if not safe_df_dados(df):
            return []

        candidatos = []
        prioridades = [
            "preço de venda",
            "preco de venda",
            "preço venda",
            "preco venda",
            "valor de venda",
            "valor venda",
            "preço",
            "preco",
        ]

        for col in df.columns:
            nome = _normalizar_nome_coluna(col)
            for prioridade in prioridades:
                if prioridade in nome:
                    candidatos.append(str(col))
                    break

        return candidatos
    except Exception:
        return []


def _detectar_colunas_alteradas(
    df_original: pd.DataFrame | None,
    df_resultado: pd.DataFrame | None,
) -> list[str]:
    try:
        if not safe_df_dados(df_original) or not safe_df_dados(df_resultado):
            return []

        colunas_comuns = [
            col for col in df_resultado.columns
            if col in df_original.columns
        ]

        alteradas = []

        for col in colunas_comuns:
            try:
                s1 = df_original[col].fillna("").astype(str)
                s2 = df_resultado[col].fillna("").astype(str)
                if not s1.equals(s2):
                    alteradas.append(str(col))
            except Exception:
                continue

        novas = [
            str(col) for col in df_resultado.columns
            if col not in df_original.columns
        ]

        # prioriza colunas de preço
        prioridades = _colunas_preco_prioritarias(df_resultado)
        ordenadas = []

        for col in prioridades:
            if col in alteradas and col not in ordenadas:
                ordenadas.append(col)
            if col in novas and col not in ordenadas:
                ordenadas.append(col)

        for col in alteradas:
            if col not in ordenadas:
                ordenadas.append(col)

        for col in novas:
            if col not in ordenadas:
                ordenadas.append(col)

        return ordenadas
    except Exception:
        return []


def coletar_parametros_precificacao() -> dict:
    return {
        "coluna_preco": st.session_state.get("coluna_preco_base"),
        "impostos": safe_float(st.session_state.get("perc_impostos", 0)),
        "lucro": safe_float(st.session_state.get("margem_lucro", 0)),
        "custo_fixo": safe_float(st.session_state.get("custo_fixo", 0)),
        "taxa": safe_float(st.session_state.get("taxa_extra", 0)),
    }


def _garantir_base_precificacao(df_base: pd.DataFrame) -> pd.DataFrame:
    """
    Garante uma base estável para a precificação.
    Isso evita recalcular em cima de df_saida já modificado.
    """
    try:
        hash_atual = _hash_df(df_base)
        hash_salvo = st.session_state.get("_precificacao_df_base_hash", "")

        if (
            "df_base_precificacao" not in st.session_state
            or not safe_df_dados(st.session_state.get("df_base_precificacao"))
            or hash_atual != hash_salvo
        ):
            st.session_state["df_base_precificacao"] = df_base.copy()
            st.session_state["_precificacao_df_base_hash"] = hash_atual
            log_debug("Base da precificação atualizada.", "INFO")

        df_salvo = st.session_state.get("df_base_precificacao")

        if safe_df_dados(df_salvo):
            return df_salvo.copy()

        return df_base.copy()
    except Exception as e:
        log_debug(f"Erro ao garantir base da precificação: {e}", "ERRO")
        return df_base.copy()


def _aplicar_precificacao(df_base: pd.DataFrame) -> pd.DataFrame | None:
    try:
        params = coletar_parametros_precificacao()

        coluna_preco = str(params.get("coluna_preco") or "").strip()
        if not coluna_preco:
            return None

        if coluna_preco not in list(df_base.columns):
            log_debug(
                f"Coluna inválida na precificação: {coluna_preco}",
                "ERRO",
            )
            return None

        df_precificado = aplicar_precificacao_no_fluxo(df_base.copy(), params)

        if not safe_df_dados(df_precificado):
            return None

        return df_precificado

    except Exception as e:
        log_debug(f"Erro na precificação: {e}", "ERRO")
        return None


def render_precificacao(df_base):
    if not safe_df_dados(df_base):
        return

    df_base_calculo = _garantir_base_precificacao(df_base)
    colunas = list(df_base_calculo.columns)

    if not colunas:
        return

    coluna_preco_default = _detectar_coluna_preco_default(colunas)

    st.selectbox(
        "Coluna de custo",
        options=colunas,
        index=coluna_preco_default,
        key="coluna_preco_base",
    )

    col1, col2 = st.columns(2)

    with col1:
        st.number_input(
            "Margem (%)",
            min_value=0.0,
            step=0.01,
            format="%.2f",
            key="margem_lucro",
        )
        st.number_input(
            "Impostos (%)",
            min_value=0.0,
            step=0.01,
            format="%.2f",
            key="perc_impostos",
        )

    with col2:
        st.number_input(
            "Custo fixo",
            min_value=0.0,
            step=0.01,
            format="%.2f",
            key="custo_fixo",
        )
        st.number_input(
            "Taxa (%)",
            min_value=0.0,
            step=0.01,
            format="%.2f",
            key="taxa_extra",
        )

    # recalcula sempre em cima da base limpa
    df_precificado = _aplicar_precificacao(df_base_calculo)

    if safe_df_dados(df_precificado):
        st.session_state["df_saida"] = df_precificado.copy()
        st.session_state["df_final"] = df_precificado.copy()
        df_preview = df_precificado.copy()
    else:
        df_preview = df_base_calculo.copy()

    coluna_origem = str(st.session_state.get("coluna_preco_base") or "").strip()
    colunas_alteradas = _detectar_colunas_alteradas(df_base_calculo, df_precificado)

    if coluna_origem:
        if colunas_alteradas:
            destino_txt = ", ".join(colunas_alteradas[:5])
            if len(colunas_alteradas) > 5:
                destino_txt += "..."
            st.caption(
                f"Base da calculadora: **{coluna_origem}** → "
                f"refletindo no preview nas colunas: **{destino_txt}**"
            )
        else:
            st.caption(
                f"Base da calculadora: **{coluna_origem}**. "
                f"O resultado refletirá na(s) coluna(s) de preço geradas pela precificação."
            )

    if safe_df_dados(df_preview):
        with st.expander("📊 Preview da precificação", expanded=True):
            st.dataframe(
                _df_preview_seguro(df_preview).head(10),
                use_container_width=True,
                hide_index=True,
      )
