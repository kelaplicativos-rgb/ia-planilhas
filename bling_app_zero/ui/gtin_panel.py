from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from bling_app_zero.core.gtin_service import (
    auditar_gtins_dataframe,
    contar_gtins_invalidos_df,
    gerar_gtins_para_dataframe,
    localizar_colunas_gtin,
    limpar_gtins_invalidos_df,
)


def _safe_df_estrutura(df: Any) -> bool:
    return isinstance(df, pd.DataFrame) and len(df.columns) > 0


def _log_debug(msg: Any, nivel: str = "INFO") -> None:
    try:
        from bling_app_zero.ui.app_helpers import log_debug
        log_debug(msg, nivel=nivel)
    except Exception:
        if "logs_debug" not in st.session_state:
            st.session_state["logs_debug"] = []
        st.session_state["logs_debug"].append(f"[{nivel}] {msg}")


def _coletar_dfs_fluxo() -> dict[str, pd.DataFrame]:
    dicionario: dict[str, pd.DataFrame] = {}

    for chave in ("df_origem", "df_precificado", "df_saida", "df_final"):
        valor = st.session_state.get(chave)
        if isinstance(valor, pd.DataFrame) and len(valor.columns) > 0:
            dicionario[chave] = valor.copy()

    return dicionario


def _aplicar_df_fluxo(chave: str, df: pd.DataFrame) -> None:
    st.session_state[chave] = df.copy().fillna("")


def _inicializar_estado_gtin_ui() -> None:
    defaults = {
        "gtin_apenas_prefixo_br": False,
        "gtin_prefixo_base": "789",
        "gtin_modo_geracao": "vazios_e_invalidos",
        "gtin_ultimo_total_invalidos": 0,
        "gtin_ultimo_total_limpos": 0,
        "gtin_ultimo_total_gerados": 0,
        "gtin_ultima_auditoria": {},
    }

    for chave, valor in defaults.items():
        if chave not in st.session_state:
            st.session_state[chave] = valor


def render_gtin_panel(df_base: pd.DataFrame | None = None) -> None:
    _inicializar_estado_gtin_ui()

    df_referencia = (
        df_base.copy()
        if isinstance(df_base, pd.DataFrame) and len(df_base.columns) > 0
        else next(iter(_coletar_dfs_fluxo().values()), pd.DataFrame())
    )

    aceitar_apenas_prefixo_br = bool(st.session_state.get("gtin_apenas_prefixo_br", False))

    auditoria = auditar_gtins_dataframe(
        df_referencia,
        aceitar_apenas_prefixo_br=aceitar_apenas_prefixo_br,
    )

    st.session_state["gtin_ultima_auditoria"] = auditoria
    st.session_state["gtin_ultimo_total_invalidos"] = int(auditoria.get("total_invalidos", 0))

    with st.expander("GTIN / EAN", expanded=False):
        st.caption(
            "Painel de GTIN com detecção, limpeza de inválidos e geração de GTIN-13 válidos."
        )

        col_cfg1, col_cfg2, col_cfg3 = st.columns([1, 1, 1])

        with col_cfg1:
            somente_br = st.checkbox(
                "Aceitar apenas prefixo BR (789/790)",
                value=bool(st.session_state.get("gtin_apenas_prefixo_br", False)),
                key="gtin_apenas_prefixo_br_panel",
            )
            st.session_state["gtin_apenas_prefixo_br"] = bool(somente_br)

        with col_cfg2:
            prefixo_base = st.text_input(
                "Prefixo para geração",
                value=str(st.session_state.get("gtin_prefixo_base", "789") or "789"),
                key="gtin_prefixo_base_panel",
                help="Usado apenas na geração de GTIN-13 válidos.",
            ).strip()
            st.session_state["gtin_prefixo_base"] = prefixo_base or "789"

        with col_cfg3:
            modo_geracao = st.selectbox(
                "Modo de geração",
                options=[
                    "vazios_e_invalidos",
                    "vazios",
                    "invalidos",
                    "sobrescrever_tudo",
                ],
                index=[
                    "vazios_e_invalidos",
                    "vazios",
                    "invalidos",
                    "sobrescrever_tudo",
                ].index(str(st.session_state.get("gtin_modo_geracao", "vazios_e_invalidos"))),
                key="gtin_modo_geracao_panel",
            )
            st.session_state["gtin_modo_geracao"] = modo_geracao

        col_metric1, col_metric2, col_metric3, col_metric4 = st.columns(4)

        with col_metric1:
            st.metric("Colunas GTIN", len(auditoria.get("colunas", [])))
        with col_metric2:
            st.metric("Inválidos", int(auditoria.get("total_invalidos", 0)))
        with col_metric3:
            st.metric("Últimos limpos", int(st.session_state.get("gtin_ultimo_total_limpos", 0)))
        with col_metric4:
            st.metric("Últimos gerados", int(st.session_state.get("gtin_ultimo_total_gerados", 0)))

        if auditoria.get("itens"):
            with st.expander("Detalhes da auditoria", expanded=False):
                st.dataframe(pd.DataFrame(auditoria["itens"]), use_container_width=True)
        else:
            st.info("Nenhuma coluna de GTIN foi encontrada no DataFrame atual.")

        col_btn1, col_btn2, col_btn3 = st.columns(3)

        with col_btn1:
            detectar = st.button(
                "🔎 Detectar GTINs",
                use_container_width=True,
                key="btn_detectar_gtins_panel",
                disabled=not _safe_df_estrutura(df_referencia),
            )

        with col_btn2:
            limpar = st.button(
                "🧹 Limpar GTINs inválidos",
                use_container_width=True,
                key="btn_limpar_gtins_panel",
                disabled=(
                    not _safe_df_estrutura(df_referencia)
                    or int(auditoria.get("total_invalidos", 0)) == 0
                ),
            )

        with col_btn3:
            gerar = st.button(
                "⚡ Gerar GTINs válidos",
                use_container_width=True,
                key="btn_gerar_gtins_panel",
                disabled=(
                    not _safe_df_estrutura(df_referencia)
                    or len(localizar_colunas_gtin(df_referencia)) == 0
                ),
            )

        if detectar:
            auditoria_atual = auditar_gtins_dataframe(
                df_referencia,
                aceitar_apenas_prefixo_br=bool(st.session_state.get("gtin_apenas_prefixo_br", False)),
            )
            st.session_state["gtin_ultima_auditoria"] = auditoria_atual
            st.session_state["gtin_ultimo_total_invalidos"] = int(auditoria_atual.get("total_invalidos", 0))

            _log_debug(
                f"Detecção de GTIN executada. Inválidos encontrados: {auditoria_atual.get('total_invalidos', 0)}",
                nivel="INFO",
            )
            st.success(
                f"Detecção concluída. Inválidos encontrados: {auditoria_atual.get('total_invalidos', 0)}"
            )
            st.rerun()

        if limpar:
            total_limpo_geral = 0

            for chave, df_fluxo in _coletar_dfs_fluxo().items():
                df_limpo, total_limpos = limpar_gtins_invalidos_df(
                    df_fluxo,
                    aceitar_apenas_prefixo_br=bool(st.session_state.get("gtin_apenas_prefixo_br", False)),
                )
                _aplicar_df_fluxo(chave, df_limpo)
                total_limpo_geral += int(total_limpos)

            st.session_state["gtin_ultimo_total_limpos"] = int(total_limpo_geral)
            st.session_state["gtin_ultimo_total_gerados"] = 0
            st.session_state["preview_download_realizado"] = False
            st.session_state["preview_validacao_ok"] = False

            _log_debug(
                f"Limpeza manual de GTIN executada. Total limpo: {total_limpo_geral}",
                nivel="INFO",
            )
            st.success(f"Limpeza concluída. Total de GTINs inválidos removidos: {total_limpo_geral}")
            st.rerun()

        if gerar:
            total_gerado_geral = 0

            for chave, df_fluxo in _coletar_dfs_fluxo().items():
                df_gerado, total_gerados, _ = gerar_gtins_para_dataframe(
                    df=df_fluxo,
                    prefixo_base=str(st.session_state.get("gtin_prefixo_base", "789") or "789"),
                    modo=str(st.session_state.get("gtin_modo_geracao", "vazios_e_invalidos")),
                    aceitar_apenas_prefixo_br=bool(st.session_state.get("gtin_apenas_prefixo_br", False)),
                    registrar_no_arquivo=True,
                )
                _aplicar_df_fluxo(chave, df_gerado)
                total_gerado_geral += int(total_gerados)

            st.session_state["gtin_ultimo_total_gerados"] = int(total_gerado_geral)
            st.session_state["preview_download_realizado"] = False
            st.session_state["preview_validacao_ok"] = False

            invalidos_restantes = 0
            for _, df_fluxo in _coletar_dfs_fluxo().items():
                invalidos_restantes = contar_gtins_invalidos_df(
                    df_fluxo,
                    aceitar_apenas_prefixo_br=bool(st.session_state.get("gtin_apenas_prefixo_br", False)),
                )
                break

            _log_debug(
                f"Geração de GTIN executada. Total gerado: {total_gerado_geral} | inválidos restantes: {invalidos_restantes}",
                nivel="INFO",
            )
            st.success(
                f"Geração concluída. Total de GTINs gerados: {total_gerado_geral}"
            )
            st.rerun()
