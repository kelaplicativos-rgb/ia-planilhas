from __future__ import annotations

from collections.abc import Callable

import pandas as pd
import streamlit as st

from bling_app_zero.ui.app_helpers import (
    ir_para_etapa,
    log_debug,
    safe_df_dados,
)
from bling_app_zero.ui.origem_dados_handlers import (
    consolidar_saida_da_origem,
    criar_modelo_vazio_para_operacao,
    obter_modelo_ativo,
    sincronizar_estado_com_origem,
)
from bling_app_zero.ui.origem_dados_ui import (
    render_bloco_acoes_origem,
    render_origem_entrada,
)

NavCallback = Callable[[], None] | None


def _safe_copy_df(df):
    try:
        return df.copy()
    except Exception:
        return df


def _safe_str(valor) -> str:
    try:
        if valor is None:
            return ""
        texto = str(valor).strip()
        if texto.lower() in {"none", "nan", "nat"}:
            return ""
        return texto
    except Exception:
        return ""


def _sincronizar_tipo_operacao(valor: str) -> None:
    texto = _safe_str(valor).lower()

    if "estoque" in texto:
        st.session_state["tipo_operacao_radio"] = "Atualização de Estoque"
        st.session_state["tipo_operacao"] = "Atualização de Estoque"
        st.session_state["tipo_operacao_bling"] = "estoque"
        return

    st.session_state["tipo_operacao_radio"] = "Cadastro de Produtos"
    st.session_state["tipo_operacao"] = "Cadastro de Produtos"
    st.session_state["tipo_operacao_bling"] = "cadastro"


def _resolver_tipo_operacao_atual() -> str:
    atual = _safe_str(
        st.session_state.get("tipo_operacao_radio")
        or st.session_state.get("tipo_operacao")
        or "Cadastro de Produtos"
    )
    if "estoque" in atual.lower():
        return "Atualização de Estoque"
    return "Cadastro de Produtos"


def _definir_modelo_padrao_se_necessario() -> pd.DataFrame:
    df_modelo = obter_modelo_ativo()
    if isinstance(df_modelo, pd.DataFrame) and len(df_modelo.columns) > 0:
        tipo = _safe_str(st.session_state.get("tipo_operacao_bling")).lower()
        if tipo == "estoque":
            st.session_state["df_modelo_estoque"] = _safe_copy_df(df_modelo)
        else:
            st.session_state["df_modelo_cadastro"] = _safe_copy_df(df_modelo)
        return df_modelo

    df_modelo = criar_modelo_vazio_para_operacao()
    tipo = _safe_str(st.session_state.get("tipo_operacao_bling")).lower()
    if tipo == "estoque":
        st.session_state["df_modelo_estoque"] = _safe_copy_df(df_modelo)
    else:
        st.session_state["df_modelo_cadastro"] = _safe_copy_df(df_modelo)
    return df_modelo


def _resolver_df_origem_atual(df_origem_render: pd.DataFrame | None) -> pd.DataFrame | None:
    if safe_df_dados(df_origem_render):
        return _safe_copy_df(df_origem_render)

    df_origem = st.session_state.get("df_origem")
    if safe_df_dados(df_origem):
        return _safe_copy_df(df_origem)

    for chave in ["df_saida", "df_final", "df_precificado", "df_calc_precificado"]:
        df_alt = st.session_state.get(chave)
        if safe_df_dados(df_alt):
            try:
                st.session_state["df_origem"] = df_alt.copy()
            except Exception:
                st.session_state["df_origem"] = df_alt
            return _safe_copy_df(df_alt)

    return None


def _persistir_origem(df_origem: pd.DataFrame | None) -> pd.DataFrame | None:
    if not safe_df_dados(df_origem):
        return None

    df_base = _safe_copy_df(df_origem)
    sincronizar_estado_com_origem(df_base, log_debug)

    df_saida = consolidar_saida_da_origem(df_base)

    st.session_state["df_origem"] = _safe_copy_df(df_base)
    st.session_state["df_saida"] = _safe_copy_df(df_saida)
    st.session_state["df_final"] = _safe_copy_df(df_saida)

    return df_saida


def _render_css() -> None:
    st.markdown(
        """
        <style>
            .wiz-kicker {
                font-size: 0.78rem;
                font-weight: 700;
                letter-spacing: 0.08em;
                text-transform: uppercase;
                color: #64748b;
                margin-bottom: 0.25rem;
            }

            .wiz-title {
                font-size: 2rem;
                font-weight: 800;
                line-height: 1.08;
                color: #0f172a;
                margin-bottom: 0.4rem;
            }

            .wiz-subtitle {
                font-size: 1rem;
                color: #475569;
                margin-bottom: 1rem;
            }

            .wiz-block {
                border: 1px solid #e5e7eb;
                border-radius: 22px;
                padding: 1rem;
                background: #ffffff;
                margin-bottom: 0.95rem;
            }

            .wiz-block-title {
                font-size: 1.15rem;
                font-weight: 800;
                color: #111827;
                margin-bottom: 0.2rem;
            }

            .wiz-block-subtitle {
                font-size: 0.95rem;
                color: #6b7280;
                margin-bottom: 0.85rem;
            }

            .wiz-choice-row {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 0.75rem;
            }

            .wiz-summary {
                border: 1px solid #e2e8f0;
                background: #f8fafc;
                color: #334155;
                border-radius: 18px;
                padding: 0.85rem 1rem;
                font-size: 0.94rem;
                margin-top: 0.9rem;
            }

            @media (max-width: 640px) {
                .wiz-title {
                    font-size: 1.75rem;
                }

                .wiz-choice-row {
                    grid-template-columns: 1fr;
                }

                .wiz-block {
                    border-radius: 18px;
                    padding: 0.9rem;
                }
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_header() -> None:
    st.markdown('<div class="wiz-kicker">Etapa 1</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="wiz-title">Vamos montar sua base?</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="wiz-subtitle">Responda as perguntas abaixo. O sistema monta o fluxo e só depois libera a próxima etapa.</div>',
        unsafe_allow_html=True,
    )


def _render_operacao() -> None:
    atual = _resolver_tipo_operacao_atual()

    st.markdown('<div class="wiz-block">', unsafe_allow_html=True)
    st.markdown(
        '<div class="wiz-block-title">O que você quer fazer?</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="wiz-block-subtitle">Escolha se o fluxo será de cadastro de produtos ou atualização de estoque.</div>',
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns(2, gap="small")

    with col1:
        if st.button(
            "Cadastro de Produtos",
            use_container_width=True,
            key="btn_operacao_cadastro_origem",
            type="primary" if atual == "Cadastro de Produtos" else "secondary",
        ):
            _sincronizar_tipo_operacao("Cadastro de Produtos")
            st.rerun()

    with col2:
        if st.button(
            "Atualização de Estoque",
            use_container_width=True,
            key="btn_operacao_estoque_origem",
            type="primary" if atual == "Atualização de Estoque" else "secondary",
        ):
            _sincronizar_tipo_operacao("Atualização de Estoque")
            st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)


def _render_modelo() -> pd.DataFrame:
    st.markdown('<div class="wiz-block">', unsafe_allow_html=True)
    st.markdown(
        '<div class="wiz-block-title">Qual modelo Bling será usado?</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="wiz-block-subtitle">O modelo é definido automaticamente pela operação escolhida.</div>',
        unsafe_allow_html=True,
    )

    df_modelo = _definir_modelo_padrao_se_necessario()
    tipo = _safe_str(st.session_state.get("tipo_operacao_bling")).lower()
    nome_modelo = "Estoque" if tipo == "estoque" else "Cadastro"

    st.caption(f"Modelo ativo: {nome_modelo}")

    if isinstance(df_modelo, pd.DataFrame) and len(df_modelo.columns) > 0:
        with st.expander("Preview do modelo", expanded=False):
            st.dataframe(
                df_modelo.head(3),
                use_container_width=True,
                hide_index=True,
            )

    st.markdown("</div>", unsafe_allow_html=True)
    return df_modelo


def _render_origem() -> None:
    st.markdown('<div class="wiz-block">', unsafe_allow_html=True)
    st.markdown(
        '<div class="wiz-block-title">De onde virão os dados?</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="wiz-block-subtitle">Selecione a fonte e carregue a base antes de seguir para a precificação.</div>',
        unsafe_allow_html=True,
    )

    render_origem_entrada()

    st.markdown("</div>", unsafe_allow_html=True)


def _render_resumo_curto(df_origem: pd.DataFrame | None = None) -> None:
    operacao = _safe_str(
        st.session_state.get("tipo_operacao")
        or st.session_state.get("tipo_operacao_radio")
        or st.session_state.get("tipo_operacao_bling")
    )
    origem = _safe_str(
        st.session_state.get("origem_dados_tipo")
        or st.session_state.get("origem_dados_radio")
    )

    linhas = 0
    if safe_df_dados(df_origem):
        try:
            linhas = int(len(df_origem))
        except Exception:
            linhas = 0

    st.markdown(
        (
            '<div class="wiz-summary">'
            f"<strong>Operação:</strong> {operacao or 'Não definida'}"
            f" &nbsp;&nbsp;|&nbsp;&nbsp; "
            f"<strong>Origem:</strong> {origem or 'Não definida'}"
            f" &nbsp;&nbsp;|&nbsp;&nbsp; "
            f"<strong>Linhas carregadas:</strong> {linhas}"
            "</div>"
        ),
        unsafe_allow_html=True,
    )


def _render_preview_origem(df_origem: pd.DataFrame | None) -> None:
    if not safe_df_dados(df_origem):
        return

    with st.expander("Preview da origem", expanded=False):
        st.dataframe(
            df_origem.head(8),
            use_container_width=True,
            hide_index=True,
        )
        st.caption(f"{len(df_origem)} linha(s) | {len(df_origem.columns)} coluna(s)")


def render_origem_dados() -> pd.DataFrame | None:
    if not _safe_str(st.session_state.get("tipo_operacao_radio")):
        _sincronizar_tipo_operacao(
            _safe_str(st.session_state.get("tipo_operacao") or "Cadastro de Produtos")
        )

    _render_css()
    _render_header()
    _render_operacao()
    _render_modelo()
    _render_origem()

    df_origem = _resolver_df_origem_atual(st.session_state.get("df_origem"))
    df_saida = _persistir_origem(df_origem)

    _render_resumo_curto(df_origem)
    _render_preview_origem(df_origem)

    render_bloco_acoes_origem(df_origem)

    if safe_df_dados(df_saida):
        try:
            total = len(df_saida)
        except Exception:
            total = 0

        log_debug(
            f"[ORIGEM_DADOS] etapa concluída com {total} linha(s) prontas para precificação.",
            "INFO",
        )

    return df_saida


def continuar_para_precificacao() -> None:
    df_origem = st.session_state.get("df_origem")
    if safe_df_dados(df_origem):
        ir_para_etapa("precificacao")
