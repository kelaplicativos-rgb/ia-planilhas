from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.ui.app_helpers import safe_df_dados
from bling_app_zero.ui.origem_dados_estado import (
    reset_site_processado,
    safe_int,
    safe_str,
)
from bling_app_zero.ui.origem_dados_handlers import (
    ler_planilha,
    nome_coluna_preco_saida,
)


def _normalizar_alias_origem(valor: str) -> str:
    texto = safe_str(valor).strip().lower()

    mapa = {
        "buscar em site": "site",
        "busca em site": "site",
        "site": "site",
        "planilha / csv / xml": "planilha",
        "planilha/csv/xml": "planilha",
        "planilha": "planilha",
        "arquivo": "planilha",
        "upload": "planilha",
    }

    if texto in mapa:
        return mapa[texto]

    if "site" in texto:
        return "site"

    return "planilha"


def _label_origem_por_alias(alias: str) -> str:
    return "Buscar em site" if alias == "site" else "Planilha / CSV / XML"


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


def render_config_site() -> None:
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


def render_origem_entrada(on_change_callback=None):
    alias_atual = _normalizar_alias_origem(
        st.session_state.get("origem_dados_tipo")
        or st.session_state.get("origem_dados")
        or st.session_state.get("origem_dados_radio")
        or "planilha"
    )
    label_atual = _label_origem_por_alias(alias_atual)

    opcoes = ["Planilha / CSV / XML", "Buscar em site"]

    if "origem_dados_radio" not in st.session_state:
        st.session_state["origem_dados_radio"] = label_atual

    origem_label = st.radio(
        "Escolha a origem dos dados",
        opcoes,
        horizontal=True,
        key="origem_dados_radio",
    )

    origem_alias = _normalizar_alias_origem(origem_label)
    origem_anterior = _normalizar_alias_origem(
        st.session_state.get("_origem_anterior_origem_dados")
        or st.session_state.get("origem_dados_tipo")
    )

    # IMPORTANTE:
    # não reatribuir st.session_state["origem_dados_radio"] aqui.
    # Essa chave pertence ao widget acima.
    st.session_state["origem_dados_tipo"] = origem_alias
    st.session_state["origem_dados"] = origem_alias

    if origem_anterior != origem_alias:
        reset_site_processado()

        if callable(on_change_callback):
            try:
                on_change_callback(origem_alias)
            except Exception:
                pass

    if origem_alias == "site":
        render_config_site()

        df_origem = st.session_state.get("df_origem")
        if st.session_state.get("site_processado") and safe_df_dados(df_origem):
            st.success("Dados do site já carregados nesta sessão.")
            return df_origem

        st.info(
            "Configure a URL do site acima. "
            "Após a busca do crawler, os dados carregados aparecerão aqui automaticamente."
        )
        return df_origem

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
