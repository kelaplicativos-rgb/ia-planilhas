
from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.ui.app_helpers import (
    ir_para_etapa,
    log_debug,
    safe_df_dados,
    safe_df_estrutura,
)
from bling_app_zero.ui.origem_dados_handlers import (
    consolidar_saida_da_origem,
    criar_modelo_vazio_para_operacao,
    obter_modelo_ativo,
    safe_str,
    sincronizar_estado_com_origem,
)
from bling_app_zero.ui.origem_dados_ui import (
    render_bloco_acoes_origem,
    render_origem_entrada,
)


def _safe_copy_df(df):
    try:
        return df.copy()
    except Exception:
        return df


def _normalizar_tipo_operacao(valor: str) -> tuple[str, str]:
    texto = safe_str(valor).strip().lower()

    if "estoque" in texto:
        return "Atualização de Estoque", "estoque"

    return "Cadastro de Produtos", "cadastro"


def _sincronizar_tipo_operacao(valor: str) -> None:
    label, codigo = _normalizar_tipo_operacao(valor)
    st.session_state["tipo_operacao_radio"] = label
    st.session_state["tipo_operacao"] = label
    st.session_state["tipo_operacao_bling"] = codigo


def _definir_modelo_padrao_se_necessario() -> pd.DataFrame:
    df_modelo = obter_modelo_ativo()

    if safe_df_estrutura(df_modelo):
        tipo = safe_str(st.session_state.get("tipo_operacao_bling")).lower()
        if tipo == "estoque":
            st.session_state["df_modelo_estoque"] = _safe_copy_df(df_modelo)
        else:
            st.session_state["df_modelo_cadastro"] = _safe_copy_df(df_modelo)
        return df_modelo

    df_modelo = criar_modelo_vazio_para_operacao()
    tipo = safe_str(st.session_state.get("tipo_operacao_bling")).lower()

    if tipo == "estoque":
        st.session_state["df_modelo_estoque"] = _safe_copy_df(df_modelo)
    else:
        st.session_state["df_modelo_cadastro"] = _safe_copy_df(df_modelo)

    return df_modelo


def _render_css_local() -> None:
    st.markdown(
        """
        <style>
            .blingflow-step-kicker {
                font-size: 0.82rem;
                font-weight: 700;
                opacity: 0.78;
                text-transform: uppercase;
                letter-spacing: 0.04em;
                margin-bottom: 0.25rem;
            }

            .blingflow-step-title {
                font-size: 1.35rem;
                font-weight: 700;
                margin-bottom: 0.2rem;
            }

            .blingflow-step-subtitle {
                font-size: 0.92rem;
                opacity: 0.85;
                margin-bottom: 1rem;
            }

            .blingflow-card {
                border: 1px solid rgba(120,120,120,0.16);
                border-radius: 16px;
                padding: 14px;
                margin-bottom: 12px;
            }

            .blingflow-mini {
                font-size: 0.86rem;
                opacity: 0.82;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_question(titulo: str, subtitulo: str, kicker: str = "Origem") -> None:
    st.markdown(f'<div class="blingflow-step-kicker">{kicker}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="blingflow-step-title">{titulo}</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="blingflow-step-subtitle">{subtitulo}</div>',
        unsafe_allow_html=True,
    )


def _render_operacao_clickable() -> None:
    atual = safe_str(
        st.session_state.get("tipo_operacao_radio")
        or st.session_state.get("tipo_operacao")
        or "Cadastro de Produtos"
    )
    atual, _ = _normalizar_tipo_operacao(atual)

    st.markdown('<div class="blingflow-card">', unsafe_allow_html=True)
    _render_question(
        "O que você deseja fazer?",
        "Escolha a operação principal antes de carregar a origem dos dados.",
        "Passo 1",
    )

    col1, col2 = st.columns(2, gap="small")

    with col1:
        if st.button(
            "📦 Cadastro de Produtos",
            use_container_width=True,
            key="btn_operacao_cadastro_origem",
            type="primary" if atual == "Cadastro de Produtos" else "secondary",
        ):
            _sincronizar_tipo_operacao("Cadastro de Produtos")
            st.rerun()

    with col2:
        if st.button(
            "📊 Atualização de Estoque",
            use_container_width=True,
            key="btn_operacao_estoque_origem",
            type="primary" if atual == "Atualização de Estoque" else "secondary",
        ):
            _sincronizar_tipo_operacao("Atualização de Estoque")
            st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)


def _render_bloco_modelo() -> pd.DataFrame:
    st.markdown('<div class="blingflow-card">', unsafe_allow_html=True)
    _render_question(
        "Modelo Bling",
        "O sistema mantém um modelo interno base para a operação selecionada.",
        "Passo 2",
    )

    df_modelo = _definir_modelo_padrao_se_necessario()
    tipo = safe_str(st.session_state.get("tipo_operacao_bling")).lower()

    nome_modelo = "Estoque" if tipo == "estoque" else "Cadastro"
    st.caption(f"Modelo ativo: {nome_modelo}")

    with st.expander("Preview do modelo", expanded=False):
        if safe_df_estrutura(df_modelo):
            st.dataframe(df_modelo.head(3), use_container_width=True, hide_index=True)
            st.caption(f"{len(df_modelo.columns)} coluna(s) no modelo")
        else:
            st.info("Modelo ainda sem estrutura carregada.")

    st.markdown("</div>", unsafe_allow_html=True)
    return df_modelo


def _resolver_df_origem_atual(df_origem_render: pd.DataFrame | None) -> pd.DataFrame | None:
    if safe_df_dados(df_origem_render):
        return _safe_copy_df(df_origem_render)

    df_origem = st.session_state.get("df_origem")
    if safe_df_dados(df_origem):
        return _safe_copy_df(df_origem)

    return None


def _render_resumo_curto(df_origem: pd.DataFrame | None = None) -> None:
    operacao = safe_str(
        st.session_state.get("tipo_operacao")
        or st.session_state.get("tipo_operacao_radio")
        or st.session_state.get("tipo_operacao_bling")
    ).strip()

    origem = safe_str(
        st.session_state.get("origem_dados_tipo")
        or st.session_state.get("origem_dados_radio")
    ).strip()

    linhas = 0
    if safe_df_dados(df_origem):
        try:
            linhas = int(len(df_origem))
        except Exception:
            linhas = 0

    st.markdown(
        f"""
        <div class="blingflow-card">
            <div class="blingflow-mini"><strong>Operação:</strong> {operacao or "Não definida"}</div>
            <div class="blingflow-mini"><strong>Origem:</strong> {origem or "Não definida"}</div>
            <div class="blingflow-mini"><strong>Linhas carregadas:</strong> {linhas}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_preview_origem_local(df_origem: pd.DataFrame | None) -> None:
    if not safe_df_dados(df_origem):
        return

    st.markdown('<div class="blingflow-card">', unsafe_allow_html=True)
    _render_question(
        "Preview da origem",
        "Confira rapidamente os dados antes de seguir para a precificação.",
        "Passo 4",
    )

    with st.expander("Abrir preview da origem", expanded=False):
        st.dataframe(df_origem.head(8), use_container_width=True, hide_index=True)
        st.caption(f"{len(df_origem)} linha(s) | {len(df_origem.columns)} coluna(s)")

    st.markdown("</div>", unsafe_allow_html=True)


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


def render_origem_dados() -> pd.DataFrame | None:
    _render_css_local()

    if not safe_str(st.session_state.get("tipo_operacao_radio")):
        _sincronizar_tipo_operacao(
            safe_str(st.session_state.get("tipo_operacao") or "Cadastro de Produtos")
        )

    _render_operacao_clickable()
    _render_bloco_modelo()

    st.markdown('<div class="blingflow-card">', unsafe_allow_html=True)
    _render_question(
        "Carregar origem dos dados",
        "Anexe uma planilha, XML, PDF ou busque em um site para montar a base inicial.",
        "Passo 3",
    )
    df_origem_render = render_origem_entrada()
    st.markdown("</div>", unsafe_allow_html=True)

    df_origem = _resolver_df_origem_atual(df_origem_render)
    df_saida = _persistir_origem(df_origem)

    _render_resumo_curto(df_origem)
    _render_preview_origem_local(df_origem)
    render_bloco_acoes_origem(df_origem)

    if safe_df_dados(df_saida):
        log_debug(
            f"[ORIGEM_DADOS] etapa concluída com {len(df_saida)} linha(s) prontas para precificação.",
            "INFO",
        )

    return df_saida


def continuar_para_precificacao() -> None:
    df_origem = st.session_state.get("df_origem")
    if safe_df_dados(df_origem):
        ir_para_etapa("precificacao")
