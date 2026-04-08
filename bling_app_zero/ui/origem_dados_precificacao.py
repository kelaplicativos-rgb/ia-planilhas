from __future__ import annotations

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


def _df_preview_seguro(df: pd.DataFrame | None) -> pd.DataFrame | None:
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


def coletar_parametros_precificacao() -> dict:
    return {
        "coluna_preco": st.session_state.get("coluna_preco_base"),
        "impostos": safe_float(st.session_state.get("perc_impostos", 0)),
        "lucro": safe_float(st.session_state.get("margem_lucro", 0)),
        "custo_fixo": safe_float(st.session_state.get("custo_fixo", 0)),
        "taxa": safe_float(st.session_state.get("taxa_extra", 0)),
    }


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

        colunas_lower = [str(c).strip().lower() for c in colunas]

        for candidato in candidatos:
            for i, nome_col in enumerate(colunas_lower):
                if candidato in nome_col:
                    return i

        return 0
    except Exception:
        return 0


def _registrar_bloqueio_preco() -> None:
    try:
        bloqueios_atuais = st.session_state.get("bloquear_campos_auto", {})
        if not isinstance(bloqueios_atuais, dict):
            bloqueios_atuais = {}

        bloqueios_atuais.update(
            {
                "preco": True,
                "preço": True,
                "preco de venda": True,
                "preço de venda": True,
                "valor": True,
                "valor de venda": True,
            }
        )

        st.session_state["bloquear_campos_auto"] = bloqueios_atuais
    except Exception:
        pass


def _sincronizar_df_precificado_no_fluxo(df_precificado: pd.DataFrame) -> None:
    """
    Sincroniza o DataFrame precificado com TODO o fluxo principal.

    Regra esperada pelo sistema:
    - a precificação precisa continuar para o mapeamento
    - o DF atualizado precisa seguir para a planilha final
    - o botão Reaplicar precisa sobrescrever o estado anterior
    """
    try:
        df_sync = df_precificado.copy()

        # Estados principais do fluxo
        st.session_state["df_precificado"] = df_sync.copy()
        st.session_state["df_dados"] = df_sync.copy()
        st.session_state["df_saida"] = df_sync.copy()
        st.session_state["df_final"] = df_sync.copy()

        # Estados auxiliares comuns no fluxo
        st.session_state["df_origem"] = df_sync.copy()
        st.session_state["df_origem_mapeamento"] = df_sync.copy()
        st.session_state["df_preview_final"] = df_sync.copy()

        # Marca que houve aplicação da calculadora
        st.session_state["precificacao_aplicada"] = True
        st.session_state["precificacao_reaplicada"] = True
        st.session_state["ultima_acao_fluxo"] = "precificacao"

        # Configuração para uso posterior no download / mapeamento
        st.session_state["config_precificacao"] = {
            "coluna_preco_base": st.session_state.get("coluna_preco_base"),
            "margem_lucro": safe_float(st.session_state.get("margem_lucro", 0)),
            "perc_impostos": safe_float(st.session_state.get("perc_impostos", 0)),
            "custo_fixo": safe_float(st.session_state.get("custo_fixo", 0)),
            "taxa_extra": safe_float(st.session_state.get("taxa_extra", 0)),
        }

        _registrar_bloqueio_preco()

        log_debug(
            "Precificação sincronizada no fluxo principal "
            "(df_dados, df_saida, df_final e mapeamento).",
            "INFO",
        )
    except Exception as e:
        log_debug(f"Erro ao sincronizar precificação no fluxo: {e}", "ERRO")


def _aplicar_precificacao(df_base: pd.DataFrame, exibir_feedback: bool = False) -> pd.DataFrame | None:
    try:
        params = coletar_parametros_precificacao()

        coluna_preco = str(params.get("coluna_preco") or "").strip()
        if not coluna_preco:
            if exibir_feedback:
                st.warning("Selecione a coluna de custo para calcular a precificação.")
            return None

        if coluna_preco not in list(df_base.columns):
            if exibir_feedback:
                st.error("A coluna de custo selecionada não existe mais na planilha.")
            log_debug(
                f"Coluna de custo inválida para precificação: {coluna_preco}",
                "ERRO",
            )
            return None

        df_precificado = aplicar_precificacao_no_fluxo(df_base.copy(), params)

        if not safe_df_dados(df_precificado):
            if exibir_feedback:
                st.warning("A precificação não gerou um DataFrame válido.")
            log_debug("Precificação retornou DataFrame inválido.", "ERRO")
            return None

        _sincronizar_df_precificado_no_fluxo(df_precificado)

        if exibir_feedback:
            st.success("Precificação aplicada e enviada para o fluxo da planilha.")

        return df_precificado

    except Exception as e:
        log_debug(f"Erro na precificação automática: {e}", "ERRO")
        if exibir_feedback:
            st.error("Erro ao aplicar a precificação.")
        return None


def render_precificacao(df_base):
    st.markdown("### 💰 Precificação")

    if not safe_df_dados(df_base):
        return

    colunas = list(df_base.columns)
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

    # Aplica automaticamente durante o fluxo para manter a prévia viva
    # e garantir que o mapeamento receba o df atualizado.
    _aplicar_precificacao(df_base, exibir_feedback=False)

    if st.button("🔁 Reaplicar", use_container_width=True):
        _aplicar_precificacao(df_base, exibir_feedback=True)

    df_precificado_state = st.session_state.get("df_precificado")

    if safe_df_dados(df_precificado_state):
        with st.expander("📊 Preview da precificação", expanded=False):
            try:
                st.dataframe(
                    _df_preview_seguro(df_precificado_state).head(10),
                    use_container_width=True,
                )
            except Exception as e:
                log_debug(f"Erro ao renderizar prévia: {e}", "ERRO")
