
from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.core.ia_orchestrator import (
    IAPlanoExecucao,
    executar_fluxo_real_com_ia,
    interpretar_comando_usuario,
    plano_para_json,
)
from bling_app_zero.ui.app_helpers import (
    log_debug,
    safe_df_dados,
)

try:
    from bling_app_zero.core.site_crawler import executar_crawler_site
except Exception:
    executar_crawler_site = None

try:
    from bling_app_zero.core.xml_nfe import converter_upload_xml_para_dataframe
except Exception:
    converter_upload_xml_para_dataframe = None

try:
    from bling_app_zero.core.fetch_router import (
        buscar_produtos_fornecedor,
        listar_fornecedores_disponiveis,
    )
except Exception:
    buscar_produtos_fornecedor = None

    def listar_fornecedores_disponiveis() -> list[str]:
        return []


# ============================================================
# HELPERS
# ============================================================

def _safe_str(valor) -> str:
    if valor is None:
        return ""
    texto = str(valor).strip()
    if texto.lower() in {"none", "nan", "nat"}:
        return ""
    return texto


def _render_resumo_base(df: pd.DataFrame) -> None:
    if not safe_df_dados(df):
        return

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Linhas preparadas", len(df))
    with col2:
        st.metric("Colunas", len(df.columns))
    with col3:
        etapa = _safe_str(st.session_state.get("etapa") or "-")
        st.metric("Próxima etapa", etapa)

    with st.expander("Preview da base preparada pela IA", expanded=False):
        st.dataframe(df.head(100), use_container_width=True)


def _render_exemplos() -> None:
    exemplos = [
        "Atualiza estoque do Mega Center no depósito iFood",
        "Cadastra produtos do Atacadum com preço original",
        "Ler XML e atualizar estoque no depósito iFood",
        "Buscar no site com margem 20",
        "Cadastra produtos do Oba Oba Mix",
    ]
    with st.expander("Exemplos de comandos", expanded=False):
        for ex in exemplos:
            st.caption(f"• {ex}")


# ============================================================
# RENDER
# ============================================================

def render_ia_panel() -> None:
    st.markdown("### IA Orquestrador")
    st.caption(
        "Descreva em linguagem natural o que deseja fazer. "
        "A IA interpreta, busca os dados e prepara o fluxo automaticamente."
    )

    fornecedores = listar_fornecedores_disponiveis()
    if fornecedores:
        st.caption("Fornecedores conectados: " + ", ".join(fornecedores))
    else:
        st.caption("Nenhum conector oficial carregado no momento.")

    _render_exemplos()

    comando_inicial = _safe_str(
        st.session_state.get(
            "ia_comando_usuario",
            "Atualiza estoque do Mega Center no depósito iFood",
        )
    )

    comando = st.text_area(
        "Digite seu comando",
        value=comando_inicial,
        height=120,
        key="ia_comando_usuario",
        placeholder=(
            "Ex.: Atualiza estoque do Mega Center no depósito iFood\n"
            "Ex.: Cadastra produtos do Atacadum com preço original\n"
            "Ex.: Ler XML e atualizar estoque"
        ),
    )

    upload_xml = st.file_uploader(
        "Se o comando envolver XML, envie o arquivo aqui",
        type=["xml"],
        key="ia_upload_xml_fluxo_real",
    )

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Interpretar comando", use_container_width=True):
            plano = interpretar_comando_usuario(comando)
            st.session_state["ia_plano_preview"] = plano.to_dict()
            st.session_state["ia_erro_execucao"] = ""
            log_debug(f"Plano IA interpretado: {plano.observacoes}", "INFO")
            st.rerun()

    with col2:
        if st.button("Executar fluxo com IA", use_container_width=True):
            resultado = executar_fluxo_real_com_ia(
                st_session_state=st.session_state,
                comando=comando,
                arquivo_upload=upload_xml,
                fetch_router_func=buscar_produtos_fornecedor,
                crawler_func=executar_crawler_site,
                xml_reader_func=converter_upload_xml_para_dataframe,
                log_func=log_debug,
            )

            st.session_state["ia_plano_preview"] = resultado["plano"].to_dict()

            if not resultado["ok"]:
                st.session_state["ia_erro_execucao"] = resultado["mensagem"]
                st.rerun()

            st.session_state["ia_erro_execucao"] = ""
            st.success("Fluxo executado com sucesso. A base já está pronta para continuar.")
            st.rerun()

    plano_preview = st.session_state.get("ia_plano_preview")
    if plano_preview:
        st.markdown("#### Plano interpretado")
        try:
            plano = IAPlanoExecucao(**plano_preview)
            st.code(plano_para_json(plano), language="json")
        except Exception:
            st.json(plano_preview)

    erro = _safe_str(st.session_state.get("ia_erro_execucao"))
    if erro:
        st.error(erro)

    df_origem = st.session_state.get("df_origem")
    if safe_df_dados(df_origem):
        _render_resumo_base(df_origem)

        st.markdown("---")
        st.info(
            "A base foi preparada pela IA. Agora você pode seguir direto para mapeamento "
            "ou ir ao preview final, se o fluxo já estiver fechado."
        )

        col3, col4 = st.columns(2)

        with col3:
            if st.button(
                "Ir para mapeamento",
                use_container_width=True,
                key="ia_ir_para_mapeamento",
            ):
                st.session_state["etapa"] = "mapeamento"
                st.session_state["etapa_origem"] = "mapeamento"
                st.rerun()

        with col4:
            if st.button(
                "Ir para preview final",
                use_container_width=True,
                key="ia_ir_para_preview_final",
            ):
                st.session_state["etapa"] = "final"
                st.session_state["etapa_origem"] = "final"
                st.rerun()
