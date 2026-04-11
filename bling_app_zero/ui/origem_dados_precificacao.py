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


def _normalizar_nome_coluna(nome: str) -> str:
    try:
        return str(nome).strip().lower()
    except Exception:
        return ""


def _copiar_coluna_com_cast(
    df_origem: pd.DataFrame,
    df_destino: pd.DataFrame,
    col_origem: str,
    col_destino: str,
) -> pd.DataFrame:
    try:
        if col_origem not in df_origem.columns or col_destino not in df_destino.columns:
            return df_destino

        serie = df_origem[col_origem].reset_index(drop=True)

        if len(df_destino.index) != len(serie.index):
            serie = serie.reindex(range(len(df_destino.index)))

        df_destino[col_destino] = serie.values
        return df_destino
    except Exception:
        return df_destino


def _is_coluna_custo(nome: str) -> bool:
    nome = _normalizar_nome_coluna(nome)
    return (
        "custo" in nome
        or "compra" in nome
        or nome in {
            "preço de custo",
            "preco de custo",
            "preço de compra",
            "preco de compra",
            "valor custo",
            "valor de custo",
        }
    )


def _is_coluna_venda(nome: str) -> bool:
    nome = _normalizar_nome_coluna(nome)

    if nome in {
        "preço de venda",
        "preco de venda",
        "valor venda",
        "valor de venda",
        "preço unitário (obrigatório)",
        "preco unitario (obrigatorio)",
        "preço unitário",
        "preco unitario",
    }:
        return True

    if "venda" in nome:
        return True

    if ("unitário" in nome or "unitario" in nome) and ("preço" in nome or "preco" in nome):
        return True

    return False


def _detectar_coluna_base_selecionada(df: pd.DataFrame) -> str | None:
    try:
        coluna = str(st.session_state.get("coluna_preco_base") or "").strip()
        if coluna and coluna in df.columns:
            return coluna
        return None
    except Exception:
        return None


def _detectar_coluna_venda_gerada(df: pd.DataFrame, coluna_base: str | None) -> str | None:
    try:
        base_norm = _normalizar_nome_coluna(coluna_base)

        prioridades = [
            "preço de venda",
            "preco de venda",
            "valor venda",
            "valor de venda",
            "preço unitário (obrigatório)",
            "preco unitario (obrigatorio)",
            "preço unitário",
            "preco unitario",
        ]

        for prioridade in prioridades:
            for col in df.columns:
                nome = _normalizar_nome_coluna(col)
                if nome == prioridade and nome != base_norm and not _is_coluna_custo(nome):
                    return col

        for col in df.columns:
            nome = _normalizar_nome_coluna(col)
            if _is_coluna_venda(nome) and nome != base_norm and not _is_coluna_custo(nome):
                return col

        return None
    except Exception:
        return None


def coletar_parametros_precificacao() -> dict:
    return {
        "coluna_preco": st.session_state.get("coluna_preco_base"),
        "impostos": safe_float(st.session_state.get("perc_impostos", 0)),
        "lucro": safe_float(st.session_state.get("margem_lucro", 0)),
        "custo_fixo": safe_float(st.session_state.get("custo_fixo", 0)),
        "taxa": safe_float(st.session_state.get("taxa_extra", 0)),
    }


def _garantir_base_precificacao(df_base: pd.DataFrame) -> pd.DataFrame:
    try:
        hash_atual = hashlib.md5(str(df_base).encode()).hexdigest()
        hash_salvo = st.session_state.get("_precificacao_df_base_hash", "")

        if hash_atual != hash_salvo:
            st.session_state["df_base_precificacao"] = df_base.copy()
            st.session_state["_precificacao_df_base_hash"] = hash_atual

        return st.session_state.get("df_base_precificacao", df_base).copy()
    except Exception:
        return df_base.copy()


def _limpar_estado_precificacao_automatica() -> None:
    try:
        st.session_state["coluna_preco_unitario_origem"] = ""
        st.session_state["coluna_preco_unitario_destino"] = ""
    except Exception:
        pass


def _salvar_bases_precificadas(
    df_calc: pd.DataFrame,
    coluna_venda: str | None,
    coluna_base: str | None,
) -> None:
    try:
        st.session_state["df_calc_precificado"] = df_calc.copy()
        st.session_state["df_precificado"] = df_calc.copy()

        if (
            coluna_venda
            and coluna_venda in df_calc.columns
            and str(coluna_venda).strip() != str(coluna_base or "").strip()
        ):
            st.session_state["coluna_preco_unitario_origem"] = coluna_venda
            st.session_state["coluna_preco_unitario_destino"] = coluna_venda
            log_debug(
                f"Precificação salva para mapeamento com coluna automática '{coluna_venda}'.",
                "INFO",
            )
        else:
            _limpar_estado_precificacao_automatica()
            log_debug(
                "Precificação calculada sem coluna automática válida; mapeamento seguirá manual.",
                "INFO",
            )
    except Exception as e:
        log_debug(f"Erro ao salvar bases precificadas: {e}", "ERROR")


def _aplicar_precificacao(
    df_base_origem: pd.DataFrame,
    df_fluxo_destino: pd.DataFrame,
) -> tuple[pd.DataFrame | None, pd.DataFrame | None]:
    try:
        if not safe_df_dados(df_base_origem):
            return None, None

        if not isinstance(df_fluxo_destino, pd.DataFrame):
            return None, None

        params = coletar_parametros_precificacao()
        coluna_preco_base = _detectar_coluna_base_selecionada(df_base_origem)

        if not coluna_preco_base or coluna_preco_base not in df_base_origem.columns:
            _limpar_estado_precificacao_automatica()
            return None, None

        df_calc_origem = aplicar_precificacao_no_fluxo(df_base_origem.copy(), params)
        if not safe_df_dados(df_calc_origem):
            _limpar_estado_precificacao_automatica()
            return None, None

        col_venda_origem = _detectar_coluna_venda_gerada(df_calc_origem, coluna_preco_base)

        _salvar_bases_precificadas(
            df_calc=df_calc_origem,
            coluna_venda=col_venda_origem,
            coluna_base=coluna_preco_base,
        )

        df_preview = df_calc_origem.copy()
        df_destino = df_fluxo_destino.copy()

        if (
            col_venda_origem
            and col_venda_origem in df_calc_origem.columns
            and isinstance(df_destino, pd.DataFrame)
        ):
            col_venda_destino = _detectar_coluna_venda_gerada(df_destino, coluna_preco_base)

            if col_venda_destino and col_venda_destino in df_destino.columns:
                df_destino = _copiar_coluna_com_cast(
                    df_origem=df_calc_origem,
                    df_destino=df_destino,
                    col_origem=col_venda_origem,
                    col_destino=col_venda_destino,
                )
                st.session_state["coluna_preco_unitario_destino"] = col_venda_destino
            else:
                st.session_state["coluna_preco_unitario_destino"] = col_venda_origem

        return df_destino, df_preview

    except Exception as e:
        log_debug(f"Erro na precificação: {e}", "ERROR")
        _limpar_estado_precificacao_automatica()
        return None, None


def render_precificacao(df_base):
    if not safe_df_dados(df_base):
        return

    df_base_calc = _garantir_base_precificacao(df_base)
    colunas = list(df_base_calc.columns)

    if not colunas:
        return

    st.markdown("### Precificação")

    st.selectbox(
        "Coluna de custo",
        options=colunas,
        key="coluna_preco_base",
    )

    col1, col2 = st.columns(2)

    with col1:
        st.number_input("Margem (%)", min_value=0.0, key="margem_lucro")
        st.number_input("Impostos (%)", min_value=0.0, key="perc_impostos")

    with col2:
        st.number_input("Custo fixo", min_value=0.0, key="custo_fixo")
        st.number_input("Taxa (%)", min_value=0.0, key="taxa_extra")

    df_fluxo_atual = st.session_state.get("df_saida")
    if not isinstance(df_fluxo_atual, pd.DataFrame):
        df_fluxo_atual = df_base_calc.copy()

    df_precificado_fluxo, df_preview = _aplicar_precificacao(
        df_base_origem=df_base_calc.copy(),
        df_fluxo_destino=df_fluxo_atual.copy(),
    )

    if safe_df_dados(df_precificado_fluxo):
        st.session_state["df_saida"] = df_precificado_fluxo.copy()
        st.session_state["df_final"] = df_precificado_fluxo.copy()

    with st.expander("Preview da precificação", expanded=True):
        if safe_df_dados(df_preview):
            st.dataframe(
                df_preview.head(10),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.dataframe(
                df_base_calc.head(10),
                use_container_width=True,
                hide_index=True,
            )
