
from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.agent.agent_memory import get_agent_snapshot, reset_agent_state
from bling_app_zero.agent.agent_orchestrator import (
    IAPlanoExecucao,
    executar_fluxo_real_com_ia,
    interpretar_comando_usuario,
    plano_para_json,
    pode_ir_para_final,
    pode_ir_para_mapeamento,
    resumo_execucao_atual,
)
from bling_app_zero.ui.app_helpers import (
    dataframe_para_csv_bytes,
    log_debug,
    safe_df_dados,
    validar_df_para_download,
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


def _safe_str(valor) -> str:
    if valor is None:
        return ""
    texto = str(valor).strip()
    if texto.lower() in {"none", "nan", "nat"}:
        return ""
    return texto


def _sincronizar_etapa(etapa: str) -> None:
    st.session_state["etapa"] = etapa
    st.session_state["etapa_origem"] = etapa
    st.session_state["etapa_fluxo"] = etapa


def _render_header_modo_ia() -> None:
    st.markdown("### IA Orquestrador")
    st.success("Modo ativo: ETL completo + Bling output")
    st.caption(
        "Descreva o objetivo em linguagem natural. "
        "A IA interpreta, lê a origem, normaliza, aplica o modelo interno do Bling, "
        "valida e entrega a planilha final pronta para download."
    )


def _render_fornecedores_disponiveis() -> None:
    fornecedores = listar_fornecedores_disponiveis()
    if fornecedores:
        st.caption("Fornecedores conectados: " + ", ".join(fornecedores))
    else:
        st.caption("Nenhum conector oficial carregado no momento.")


def _render_exemplos() -> None:
    exemplos = [
        "Atualiza estoque do Mega Center no depósito iFood",
        "Cadastra produtos do Atacadum com preço original",
        "Ler XML e atualizar estoque no depósito iFood",
        "Buscar no site da Mega Center e cadastrar produtos",
        "Cadastra produtos do Oba Oba Mix",
    ]
    with st.expander("Exemplos de comandos", expanded=False):
        for ex in exemplos:
            st.caption(f"• {ex}")


def _render_objetivo_fluxo() -> None:
    with st.expander("Como a IA executa este fluxo", expanded=False):
        st.markdown("1. Lê a origem completa")
        st.markdown("2. Normaliza sem perder linhas")
        st.markdown("3. Monta o modelo interno do Bling")
        st.markdown("4. Valida a saída final")
        st.markdown("5. Libera preview e download")


def _render_plano_preview() -> None:
    plano_preview = st.session_state.get("ia_plano_preview")
    if not plano_preview:
        return

    st.markdown("#### Plano interpretado")
    try:
        plano = IAPlanoExecucao(**plano_preview)
        st.code(plano_para_json(plano), language="json")
    except Exception:
        st.json(plano_preview)


def _render_status_agente() -> None:
    resumo = resumo_execucao_atual()
    snapshot = get_agent_snapshot()

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Etapa", _safe_str(resumo.get("etapa_atual")) or "-")
    with col2:
        st.metric("Status", _safe_str(resumo.get("status_execucao")) or "-")
    with col3:
        st.metric("Operação", _safe_str(resumo.get("operacao")) or "-")
    with col4:
        st.metric("Simulação", "Aprovada" if resumo.get("simulacao_aprovada") else "Pendente")

    pendencias = snapshot.get("pendencias") or []
    avisos = snapshot.get("avisos") or []
    erros = snapshot.get("erros") or []

    if erros:
        for erro in erros:
            st.error(erro)

    if avisos:
        with st.expander("Avisos do agente", expanded=False):
            for aviso in avisos:
                st.warning(aviso)

    if pendencias:
        with st.expander("Pendências do agente", expanded=False):
            for pendencia in pendencias:
                st.info(pendencia)


def _render_resumo_base(df: pd.DataFrame) -> None:
    if not safe_df_dados(df):
        return

    resumo = resumo_execucao_atual()

    st.markdown("#### Base preparada pela IA")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Linhas preparadas", len(df))
    with col2:
        st.metric("Colunas", len(df.columns))
    with col3:
        st.metric("Operação detectada", _safe_str(resumo.get("operacao")) or "-")

    with st.expander("Ver base preparada", expanded=False):
        st.dataframe(df.head(100), use_container_width=True)


def _render_validacao_final(df_final: pd.DataFrame, operacao: str) -> tuple[bool, list[str]]:
    valido, erros = validar_df_para_download(df_final, operacao)

    st.markdown("#### Validação final")
    if valido:
        st.success("A planilha final já está no formato do Bling.")
    else:
        st.warning("A IA montou a planilha final, mas ainda existem pendências de validação.")
        for erro in erros:
            st.caption(f"• {erro}")

    return valido, erros


def _render_preview_final() -> None:
    df_final = st.session_state.get("df_final")
    if not safe_df_dados(df_final):
        return

    operacao = _safe_str(
        st.session_state.get("tipo_operacao")
        or st.session_state.get("operacao")
        or resumo_execucao_atual().get("operacao")
        or "cadastro"
    ).lower()

    st.markdown("#### Preview final pronto para Bling")
    _render_validacao_final(df_final, operacao)

    with st.expander("Ver preview final", expanded=False):
        st.dataframe(df_final.head(100), use_container_width=True)

    nome_arquivo = "bling_export_estoque.csv" if operacao == "estoque" else "bling_export_cadastro.csv"
    csv_bytes = dataframe_para_csv_bytes(df_final)

    st.download_button(
        "Baixar planilha pronta para o Bling",
        data=csv_bytes,
        file_name=nome_arquivo,
        mime="text/csv",
        use_container_width=True,
        key="ia_download_bling_final",
    )


def _render_ctas_pos_execucao() -> None:
    st.markdown("---")
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("Nova execução IA", use_container_width=True, key="ia_nova_execucao"):
            reset_agent_state(
                preserve_dataframe_keys=False,
                preserve_operacao=False,
                preserve_deposito=False,
            )
            st.session_state["ia_erro_execucao"] = ""
            st.session_state["ia_plano_preview"] = {}
            st.session_state["df_origem"] = pd.DataFrame()
            st.session_state["df_normalizado"] = pd.DataFrame()
            st.session_state["df_mapeado"] = pd.DataFrame()
            st.session_state["df_precificado"] = pd.DataFrame()
            st.session_state["df_final"] = pd.DataFrame()
            _sincronizar_etapa("ia_orquestrador")
            st.rerun()

    with col2:
        disabled_map = not pode_ir_para_mapeamento()
        if st.button(
            "Ir para mapeamento",
            use_container_width=True,
            key="ia_ir_para_mapeamento",
            disabled=disabled_map,
        ):
            _sincronizar_etapa("mapeamento")
            st.rerun()

    with col3:
        disabled_final = not pode_ir_para_final()
        if st.button(
            "Ir para preview final",
            use_container_width=True,
            key="ia_ir_para_preview_final",
            disabled=disabled_final,
        ):
            _sincronizar_etapa("final")
            st.rerun()


def _executar_fluxo(comando: str, upload_arquivo=None) -> None:
    resultado = executar_fluxo_real_com_ia(
        st_session_state=st.session_state,
        comando=comando,
        arquivo_upload=upload_arquivo,
        fetch_router_func=buscar_produtos_fornecedor,
        crawler_func=executar_crawler_site,
        xml_reader_func=converter_upload_xml_para_dataframe,
        log_func=log_debug,
    )

    plano = resultado.get("plano")
    if plano is not None:
        try:
            st.session_state["ia_plano_preview"] = plano.to_dict()
        except Exception:
            st.session_state["ia_plano_preview"] = {}

    if not resultado.get("ok"):
        st.session_state["ia_erro_execucao"] = _safe_str(
            resultado.get("mensagem") or "Falha ao executar o fluxo com IA."
        )
        return

    st.session_state["ia_erro_execucao"] = ""
    st.session_state["df_origem"] = resultado.get("df_origem", pd.DataFrame())
    st.session_state["df_mapeado"] = resultado.get("df_origem", pd.DataFrame())
    st.session_state["df_precificado"] = resultado.get("df_origem", pd.DataFrame())
    st.session_state["df_final"] = resultado.get("df_final", pd.DataFrame())

    operacao = _safe_str(getattr(plano, "operacao", "") if plano else "")
    if operacao:
        st.session_state["tipo_operacao"] = operacao
        st.session_state["operacao"] = operacao

    deposito = _safe_str(getattr(plano, "deposito", "") if plano else "")
    if deposito:
        st.session_state["deposito_nome"] = deposito

    if safe_df_dados(st.session_state["df_final"]):
        _sincronizar_etapa("final")
    elif resultado.get("validacao", {}).get("aprovado"):
        _sincronizar_etapa("final")
    else:
        _sincronizar_etapa("mapeamento")


def render_ia_panel() -> None:
    _render_header_modo_ia()
    _render_fornecedores_disponiveis()
    _render_exemplos()
    _render_objetivo_fluxo()

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

    upload_arquivo = st.file_uploader(
        "Envie planilha ou XML quando o comando exigir arquivo",
        type=["xml", "csv", "xlsx", "xls"],
        key="ia_upload_arquivo_fluxo_real",
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
        if st.button("Executar ETL + saída Bling", use_container_width=True):
            _executar_fluxo(comando=comando, upload_arquivo=upload_arquivo)
            if _safe_str(st.session_state.get("ia_erro_execucao")):
                st.rerun()
            st.success("Fluxo executado com sucesso. A planilha final já foi preparada.")
            st.rerun()

    erro = _safe_str(st.session_state.get("ia_erro_execucao"))
    if erro:
        st.error(erro)

    _render_plano_preview()
    _render_status_agente()

    df_origem = st.session_state.get("df_origem")
    if safe_df_dados(df_origem):
        _render_resumo_base(df_origem)

    _render_preview_final()

    if safe_df_dados(df_origem) or safe_df_dados(st.session_state.get("df_final")):
        _render_ctas_pos_execucao()


