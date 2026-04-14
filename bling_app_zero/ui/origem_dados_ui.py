from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.ui.app_helpers import log_debug, safe_df_dados
from bling_app_zero.ui.origem_dados_estado import reset_site_processado, safe_int, safe_str
from bling_app_zero.ui.origem_dados_handlers import ler_planilha, nome_coluna_preco_saida

try:
    from bling_app_zero.core.site_crawler import executar_crawler
except Exception:
    executar_crawler = None


def render_header_fluxo() -> None:
    st.subheader("Origem dos dados")
    st.caption(
        "Defina se você quer cadastrar produtos ou atualizar o estoque, "
        "depois escolha a origem dos dados para o sistema preparar a base do Bling."
    )


def render_modelo_bling(operacao: str) -> None:
    st.caption(f"Modelo ativo: {operacao}")


def render_preview_origem(df_origem: pd.DataFrame) -> None:
    try:
        with st.expander("Prévia da origem", expanded=False):
            st.dataframe(df_origem.head(20), use_container_width=True)
    except Exception:
        pass


def _limpar_estado_site_carregado() -> None:
    for chave in [
        "df_origem",
        "df_saida",
        "df_final",
        "df_precificado",
        "df_calc_precificado",
        "origem_dados_fingerprint",
    ]:
        st.session_state.pop(chave, None)

    st.session_state["site_processado"] = False
    st.session_state["_origem_site_autoavancar"] = False


def _fingerprint_config_site() -> str:
    partes = [
        safe_str(st.session_state.get("site_url")),
        safe_str(st.session_state.get("site_usuario")),
        safe_str(st.session_state.get("site_senha")),
        safe_str(st.session_state.get("site_modo_sincronizacao")),
        str(bool(st.session_state.get("site_precisa_login"))),
        str(safe_int(st.session_state.get("site_delay_segundos"), 300)),
        str(safe_int(st.session_state.get("site_estoque_padrao_disponivel"), 1)),
        safe_str(st.session_state.get("tipo_operacao_bling")),
        safe_str(st.session_state.get("deposito_nome")),
    ]
    return "|".join(partes)


def _sincronizar_dirty_site() -> None:
    fp_atual = _fingerprint_config_site()
    fp_anterior = safe_str(st.session_state.get("_site_config_fingerprint"))

    if not fp_anterior:
        st.session_state["_site_config_fingerprint"] = fp_atual
        return

    if fp_anterior == fp_atual:
        return

    st.session_state["_site_config_fingerprint"] = fp_atual

    if st.session_state.get("site_processado"):
        log_debug("[ORIGEM_SITE] configuração alterada após carga. Limpando dados anteriores.", "INFO")
        _limpar_estado_site_carregado()


def _executar_busca_site() -> pd.DataFrame | None:
    url = safe_str(st.session_state.get("site_url"))
    if not url:
        st.warning("Informe a URL do site antes de executar a busca.")
        return None

    if executar_crawler is None:
        log_debug("[ORIGEM_SITE] executar_crawler indisponível no ambiente atual.", "ERROR")
        st.error("O módulo de busca do site não está disponível no momento.")
        return None

    estoque_padrao = safe_int(st.session_state.get("site_estoque_padrao_disponivel"), 1)

    try:
        log_debug(f"[ORIGEM_SITE] iniciando busca no site: {url}", "INFO")
        with st.spinner("Buscando produtos no site..."):
            df_site = executar_crawler(
                url=url,
                padrao_disponivel=estoque_padrao,
            )

        if not isinstance(df_site, pd.DataFrame) or df_site.empty or len(df_site.columns) == 0:
            st.session_state["site_processado"] = False
            st.session_state["_origem_site_autoavancar"] = False
            log_debug(f"[ORIGEM_SITE] busca concluída sem dados: {url}", "WARNING")
            st.warning("A busca foi executada, mas o site não retornou produtos válidos.")
            return None

        st.session_state["df_origem"] = df_site.copy()
        st.session_state["site_processado"] = True
        st.session_state["site_ultimo_url_processado"] = url
        st.session_state["_origem_site_autoavancar"] = True

        log_debug(
            f"[ORIGEM_SITE] busca concluída com {len(df_site)} linha(s) e {len(df_site.columns)} coluna(s)",
            "INFO",
        )
        st.success(f"Busca concluída com {len(df_site)} item(ns).")
        return df_site
    except Exception as e:
        st.session_state["site_processado"] = False
        st.session_state["_origem_site_autoavancar"] = False
        log_debug(f"[ORIGEM_SITE] erro ao executar crawler: {e}", "ERROR")
        st.error(f"Erro ao buscar dados do site: {e}")
        return None


def render_config_site() -> pd.DataFrame | None:
    st.markdown("### Busca em site")

    st.text_input(
        "URL do site ou da categoria",
        key="site_url",
        placeholder="https://exemplo.com/categoria/produtos",
        help="Informe a URL base para busca dos produtos.",
    )

    st.checkbox(
        "Este site precisa de login e senha",
        key="site_precisa_login",
        help="Ative quando o site exigir autenticação antes de exibir os produtos.",
    )

    if st.session_state.get("site_precisa_login"):
        col1, col2 = st.columns(2)

        with col1:
            st.text_input(
                "Usuário / e-mail do site",
                key="site_usuario",
                placeholder="login@site.com",
            )

        with col2:
            st.text_input(
                "Senha do site",
                key="site_senha",
                type="password",
                placeholder="••••••••",
            )

        st.info(
            "Os campos de login já ficam preparados no estado da aplicação "
            "para uso pelo crawler autenticado."
        )

    st.markdown("---")

    col1, col2 = st.columns(2)

    with col1:
        st.selectbox(
            "Modo de sincronização desejado",
            ["manual", "instantaneo", "delay"],
            key="site_modo_sincronizacao",
            help=(
                "Manual: processa quando você mandar.\n"
                "Instantâneo: pronto para envio logo após a captura.\n"
                "Delay: prepara a configuração de intervalo."
            ),
        )

    with col2:
        st.number_input(
            "Delay em segundos",
            min_value=5,
            value=safe_int(st.session_state.get("site_delay_segundos"), 300),
            step=5,
            key="site_delay_segundos",
            help="Usado quando o modo de sincronização por delay estiver ativo.",
        )

    if st.session_state.get("tipo_operacao_bling") == "estoque":
        st.number_input(
            "Estoque padrão para item disponível",
            min_value=0,
            value=safe_int(st.session_state.get("site_estoque_padrao_disponivel"), 1),
            step=1,
            key="site_estoque_padrao_disponivel",
            help="Fallback para itens disponíveis quando o site não informar o estoque real.",
        )

    st.warning(
        "Nesta tela, a configuração do site já fica preparada. "
        "A execução autenticada depende do módulo de captura/fetcher usar esses campos."
    )

    _sincronizar_dirty_site()

    col_exec_1, col_exec_2 = st.columns(2)

    with col_exec_1:
        if st.button(
            "🔎 Executar busca no site",
            use_container_width=True,
            type="primary",
            key="site_btn_executar_busca",
        ):
            df_site = _executar_busca_site()
            if safe_df_dados(df_site):
                st.rerun()

    with col_exec_2:
        if st.button(
            "🧹 Limpar busca do site",
            use_container_width=True,
            key="site_btn_limpar_busca",
        ):
            _limpar_estado_site_carregado()
            log_debug("[ORIGEM_SITE] dados do site removidos manualmente.", "INFO")
            st.rerun()

    if st.session_state.get("site_processado") and safe_df_dados(st.session_state.get("df_origem")):
        url_ok = safe_str(st.session_state.get("site_ultimo_url_processado"))
        if url_ok:
            st.success(f"Dados do site já carregados para: {url_ok}")
        else:
            st.success("Dados do site já carregados nesta sessão.")
        return st.session_state.get("df_origem")

    st.info(
        "Preencha a URL e clique em 'Executar busca no site'. "
        "Quando o crawler retornar os produtos, o fluxo será liberado automaticamente."
    )
    return st.session_state.get("df_origem")


def render_origem_entrada(on_change_callback=None):
    origem = st.radio(
        "Escolha a origem dos dados",
        ["Planilha / CSV / XML", "Buscar em site"],
        horizontal=True,
        key="origem_dados_radio",
    )

    origem_valor = "site" if "site" in origem.lower() else "planilha"
    origem_anterior = str(st.session_state.get("origem_dados_tipo") or "").strip().lower()

    st.session_state["origem_dados_tipo"] = origem_valor

    if origem_anterior != origem_valor:
        reset_site_processado()
        st.session_state["_origem_site_autoavancar"] = False
        if callable(on_change_callback):
            try:
                on_change_callback(origem_valor)
            except Exception:
                pass

    if origem_valor == "site":
        return render_config_site()

    arquivo = st.file_uploader(
        "Anexe sua planilha ou XML",
        type=["xlsx", "xls", "csv", "xml"],
        key="upload_origem_dados",
        help="Formatos aceitos: XLSX, XLS, CSV e XML.",
    )

    return ler_planilha(arquivo)


def render_precificacao(df_origem: pd.DataFrame) -> None:
    st.caption("Precificação")

    opcoes = [""] + [str(c) for c in df_origem.columns]

    coluna_custo = st.selectbox(
        "Qual coluna de origem deve ser usada como base do preço?",
        opcoes,
        key="coluna_precificacao_resultado",
        help="Escolha a coluna de custo/preço base para gerar o preço automático.",
    )

    col1, col2 = st.columns(2)

    with col1:
        st.number_input(
            "Margem (%)",
            min_value=0.0,
            value=float(st.session_state.get("margem_bling", 0.0) or 0.0),
            step=1.0,
            key="margem_bling",
        )
        st.number_input(
            "Impostos (%)",
            min_value=0.0,
            value=float(st.session_state.get("impostos_bling", 0.0) or 0.0),
            step=1.0,
            key="impostos_bling",
        )

    with col2:
        st.number_input(
            "Custo fixo",
            min_value=0.0,
            value=float(st.session_state.get("custofixo_bling", 0.0) or 0.0),
            step=1.0,
            key="custofixo_bling",
        )
        st.number_input(
            "Taxa extra",
            min_value=0.0,
            value=float(st.session_state.get("taxaextra_bling", 0.0) or 0.0),
            step=1.0,
            key="taxaextra_bling",
        )

    if coluna_custo and coluna_custo in df_origem.columns:
        st.success(
            f"Preço automático será gerado na coluna: {nome_coluna_preco_saida()}"
        )
        
