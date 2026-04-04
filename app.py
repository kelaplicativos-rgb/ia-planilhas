# ================================
# APP COMPLETO COM PERFIL DE COLUNAS + BLING OAUTH
# ================================

import streamlit as st

from bling_app_zero.core.leitor import carregar_planilha
from bling_app_zero.core.perfil_colunas import (
    carregar_perfil,
    deletar_perfil,
    salvar_perfil,
)
from bling_app_zero.core.bling_auth import BlingAuthManager
from bling_app_zero.core.bling_api import BlingAPIClient

st.set_page_config(page_title="Bling Manual PRO", layout="wide")

MODO_CADASTRO = "Cadastro de produtos"
MODO_ESTOQUE = "Atualização de estoque"


def init_state():
    if "df_origem" not in st.session_state:
        st.session_state.df_origem = None
    if "mapeamento_manual" not in st.session_state:
        st.session_state.mapeamento_manual = {}
    if "sugestao_confianca" not in st.session_state:
        st.session_state.sugestao_confianca = {}
    if "perfil_id" not in st.session_state:
        st.session_state.perfil_id = ""


def render_bling_panel() -> None:
    st.markdown("## Integração Bling")

    auth = BlingAuthManager()
    callback_result = auth.handle_oauth_callback()

    if callback_result["status"] == "success":
        st.success(callback_result["message"])
    elif callback_result["status"] == "error":
        st.error(callback_result["message"])

    status = auth.get_connection_status()

    col1, col2, col3 = st.columns([1.2, 1, 1])

    with col1:
        st.write(f"**Status:** {'Conectado' if status['connected'] else 'Desconectado'}")
        st.write(f"**Empresa conectada:** {status['company_name'] or '-'}")
        st.write(f"**Última autenticação:** {status['last_auth_at'] or '-'}")

    with col2:
        if not status["connected"]:
            auth_url = auth.build_authorize_url()
            st.link_button("Conectar com Bling", auth_url, use_container_width=True)
        else:
            reconnect_url = auth.build_authorize_url(force_reauth=True)
            st.link_button("Reconectar", reconnect_url, use_container_width=True)

    with col3:
        if status["connected"]:
            if st.button("Desconectar", use_container_width=True):
                ok, msg = auth.disconnect()
                if ok:
                    st.success(msg)
                    st.rerun()
                st.error(msg)

    with st.expander("Configuração da integração"):
        st.code(
            "\n".join(
                [
                    "[bling]",
                    'client_id = "SEU_CLIENT_ID"',
                    'client_secret = "SEU_CLIENT_SECRET"',
                    'redirect_uri = "https://SEU-APP.streamlit.app"',
                    'authorize_url = "https://api.bling.com.br/Api/v3/oauth/authorize"',
                    'token_url = "https://api.bling.com.br/Api/v3/oauth/token"',
                    'revoke_url = "https://api.bling.com.br/Api/v3/oauth/revoke"',
                    'api_base_url = "https://api.bling.com.br/Api/v3"',
                    'token_store_path = "bling_app_zero/output/bling_tokens.json"',
                ]
            ),
            language="toml",
        )

    if status["connected"]:
        with st.expander("Teste rápido da API do Bling"):
            if st.button("Testar conexão agora"):
                client = BlingAPIClient()
                ok, payload = client.test_connection()
                if ok:
                    st.success("Conexão com o Bling funcionando.")
                    st.json(payload)
                else:
                    st.error(payload)


def render_mapping_app() -> None:
    modo = st.radio("Modo", [MODO_CADASTRO, MODO_ESTOQUE], horizontal=True)

    arquivo = st.file_uploader(
        "Planilha fornecedor",
        type=["xlsx", "xls", "csv"],
    )

    if not arquivo:
        return

    df = carregar_planilha(arquivo)
    if df is None or df.empty:
        st.error("Erro ao ler planilha")
        return

    st.session_state.df_origem = df

    assinatura = list(df.columns)
    perfil = carregar_perfil(assinatura)

    if perfil:
        st.session_state.mapeamento_manual = perfil
        st.success("Perfil aplicado automaticamente.")
    else:
        st.info("Nenhum perfil encontrado para essa planilha.")

    with st.expander("Preview da planilha carregada", expanded=False):
        st.dataframe(df.head(20), use_container_width=True)

    st.markdown("## Mapeamento")
    opcoes_cadastro = ["", "Código", "Descrição", "Preço", "Estoque", "GTIN", "Marca", "Categoria"]
    opcoes_estoque = ["", "Código", "Estoque", "Depósito", "Preço"]

    opcoes = opcoes_cadastro if modo == MODO_CADASTRO else opcoes_estoque

    mapeamento = {}
    for col in df.columns:
        valor_inicial = ""
        if isinstance(st.session_state.mapeamento_manual, dict):
            valor_inicial = st.session_state.mapeamento_manual.get(col, "")
        try:
            idx = opcoes.index(valor_inicial) if valor_inicial in opcoes else 0
        except Exception:
            idx = 0

        mapeamento[col] = st.selectbox(
            label=col,
            options=opcoes,
            index=idx,
            key=f"map_{col}",
        )

    st.session_state.mapeamento_manual = mapeamento

    st.markdown("## Perfil de Colunas")
    c1, c2 = st.columns(2)

    with c1:
        if st.button("Salvar Perfil", use_container_width=True):
            salvar_perfil(list(df.columns), mapeamento)
            st.success("Perfil salvo!")

    with c2:
        if st.button("Excluir Perfil", use_container_width=True):
            deletado = deletar_perfil(list(df.columns))
            if deletado:
                st.success("Perfil deletado.")
            else:
                st.warning("Nenhum perfil encontrado.")

    with st.expander("Mapeamento final", expanded=False):
        st.json(mapeamento)


def main():
    init_state()
    st.title("Bling Manual PRO")

    render_bling_panel()
    st.divider()
    render_mapping_app()


if __name__ == "__main__":
    main()
