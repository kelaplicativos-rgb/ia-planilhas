import json
from io import BytesIO
from typing import Dict, List, Optional

import pandas as pd
import streamlit as st

from bling_app_zero.core.leitor import carregar_planilha
from bling_app_zero.core.perfil_colunas import (
    carregar_perfil,
    deletar_perfil,
    salvar_perfil,
)
from bling_app_zero.core.bling_auth import BlingAuthManager
from bling_app_zero.core.bling_sync import BlingSyncService


st.set_page_config(page_title="Bling Manual PRO", layout="wide")

MODO_CADASTRO = "Cadastro de produtos"
MODO_ESTOQUE = "Atualização de estoque"


# =========================================================
# HELPERS
# =========================================================
def df_to_excel_bytes(df: pd.DataFrame, sheet_name: str = "dados") -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    output.seek(0)
    return output.getvalue()


def normalize_value(value):
    if pd.isna(value):
        return None
    if isinstance(value, str):
        value = value.strip()
        return value if value else None
    return value


def safe_float(value) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        txt = str(value).strip().replace(".", "").replace(",", ".")
        return float(txt)
    except Exception:
        try:
            return float(value)
        except Exception:
            return None


def safe_int(value) -> Optional[int]:
    f = safe_float(value)
    if f is None:
        return None
    try:
        return int(round(f))
    except Exception:
        return None


def init_state():
    defaults = {
        "df_origem": None,
        "mapeamento_manual": {},
        "perfil_id": "",
        "bling_produtos_df": None,
        "bling_estoque_df": None,
        "ultimo_log_envio": [],
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


# =========================================================
# BLING PANEL
# =========================================================
def render_bling_panel() -> None:
    st.subheader("Integração com Bling")

    auth = BlingAuthManager()
    callback_result = auth.handle_oauth_callback()
    if callback_result["status"] == "success":
        st.success(callback_result["message"])
    elif callback_result["status"] == "error":
        st.error(callback_result["message"])

    status = auth.get_connection_status()
    configured = auth.is_configured()

    c1, c2, c3 = st.columns([1.2, 1, 1])

    with c1:
        st.write(f"**Configuração OAuth:** {'OK' if configured else 'Pendente'}")
        st.write(f"**Status:** {'Conectado' if status['connected'] else 'Desconectado'}")
        st.write(f"**Empresa/conta:** {status.get('company_name') or '-'}")
        st.write(f"**Última autenticação:** {status.get('last_auth_at') or '-'}")
        st.write(f"**Expira em:** {status.get('expires_at') or '-'}")

    with c2:
        if configured and not status["connected"]:
            auth_url = auth.build_authorize_url()
            if auth_url:
                st.link_button("Conectar com Bling", auth_url, use_container_width=True)
        elif not configured:
            st.button("Conectar com Bling", disabled=True, use_container_width=True)

    with c3:
        if configured and status["connected"]:
            reconnect_url = auth.build_authorize_url(force_reauth=True)
            if reconnect_url:
                st.link_button("Reconectar", reconnect_url, use_container_width=True)
            if st.button("Desconectar", use_container_width=True):
                ok, msg = auth.disconnect()
                if ok:
                    st.success(msg)
                    st.rerun()
                st.error(msg)
        else:
            st.button("Reconectar", disabled=True, use_container_width=True)

    if not configured:
        st.warning(
            "A integração do Bling ainda não está configurada. "
            "Preencha as credenciais em `.streamlit/secrets.toml` ou em `App Settings > Secrets` no Streamlit Cloud."
        )
        with st.expander("Exemplo de secrets.toml", expanded=False):
            st.code(
                """[bling]
client_id = "SEU_CLIENT_ID"
client_secret = "SEU_CLIENT_SECRET"
redirect_uri = "https://SEU-APP.streamlit.app"
authorize_url = "https://www.bling.com.br/Api/v3/oauth/authorize"
token_url = "https://www.bling.com.br/Api/v3/oauth/token"
revoke_url = "https://www.bling.com.br/Api/v3/oauth/revoke"
api_base_url = "https://api.bling.com.br/Api/v3"
token_store_path = "bling_app_zero/output/bling_tokens.json"
stock_write_path = "/estoques"
""",
                language="toml",
            )
        return

    if configured and status["connected"]:
        service = BlingSyncService()
        with st.expander("Teste rápido da conexão", expanded=False):
            if st.button("Testar conexão com a API"):
                ok, payload = service.test_connection()
                if ok:
                    st.success("Conexão OK.")
                    st.json(payload)
                else:
                    st.error(payload)


# =========================================================
# IMPORTAÇÃO DO BLING
# =========================================================
def render_bling_import_panel() -> None:
    st.subheader("Importar dados do Bling")

    auth = BlingAuthManager()
    if not auth.is_configured():
        st.info("Configure o Bling para liberar a importação.")
        return

    if not auth.get_connection_status()["connected"]:
        st.info("Conecte sua conta do Bling para importar dados.")
        return

    service = BlingSyncService()

    tab1, tab2 = st.tabs(["Produtos", "Estoque"])

    with tab1:
        c1, c2 = st.columns([1, 1])
        with c1:
            pagina_produtos = st.number_input("Página de produtos", min_value=1, value=1, step=1)
        with c2:
            limite_produtos = st.number_input("Limite de produtos", min_value=1, max_value=100, value=50, step=1)

        if st.button("Puxar produtos do Bling", use_container_width=True):
            ok, payload = service.importar_produtos(pagina=int(pagina_produtos), limite=int(limite_produtos))
            if ok:
                df = pd.DataFrame(payload)
                st.session_state.bling_produtos_df = df
                st.success(f"{len(df)} produto(s) carregado(s).")
            else:
                st.error(payload)

        df_prod = st.session_state.get("bling_produtos_df")
        if isinstance(df_prod, pd.DataFrame) and not df_prod.empty:
            st.dataframe(df_prod, use_container_width=True, height=320)
            st.download_button(
                "Baixar produtos do Bling em Excel",
                data=df_to_excel_bytes(df_prod, "produtos_bling"),
                file_name="produtos_bling.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )

    with tab2:
        c1, c2, c3 = st.columns([1, 1, 1])
        with c1:
            pagina_estoque = st.number_input("Página de estoque", min_value=1, value=1, step=1)
        with c2:
            limite_estoque = st.number_input("Limite de estoque", min_value=1, max_value=100, value=50, step=1)
        with c3:
            id_deposito = st.text_input("ID depósito (opcional)", value="").strip()

        if st.button("Puxar estoque do Bling", use_container_width=True):
            ok, payload = service.importar_estoques(
                pagina=int(pagina_estoque),
                limite=int(limite_estoque),
                id_deposito=id_deposito or None,
            )
            if ok:
                df = pd.DataFrame(payload)
                st.session_state.bling_estoque_df = df
                st.success(f"{len(df)} registro(s) de estoque carregado(s).")
            else:
                st.error(payload)

        df_est = st.session_state.get("bling_estoque_df")
        if isinstance(df_est, pd.DataFrame) and not df_est.empty:
            st.dataframe(df_est, use_container_width=True, height=320)
            st.download_button(
                "Baixar estoque do Bling em Excel",
                data=df_to_excel_bytes(df_est, "estoque_bling"),
                file_name="estoque_bling.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )


# =========================================================
# PLANILHA DO FORNECEDOR + MAPEAMENTO
# =========================================================
def render_mapping_panel() -> None:
    st.subheader("Planilha do fornecedor")

    modo = st.radio("Modo de operação", [MODO_CADASTRO, MODO_ESTOQUE], horizontal=True)

    arquivo = st.file_uploader("Anexar planilha do fornecedor", type=["xlsx", "xls", "csv"])

    if not arquivo:
        return

    df = carregar_planilha(arquivo)
    if df is None or df.empty:
        st.error("Erro ao ler a planilha.")
        return

    st.session_state.df_origem = df

    assinatura = list(df.columns)
    perfil = carregar_perfil(assinatura)

    if perfil:
        st.session_state.mapeamento_manual = perfil
        st.success("Perfil de colunas carregado automaticamente.")
    else:
        if not isinstance(st.session_state.mapeamento_manual, dict):
            st.session_state.mapeamento_manual = {}
        st.info("Nenhum perfil salvo encontrado para esta estrutura.")

    with st.expander("Preview da planilha", expanded=False):
        st.dataframe(df.head(30), use_container_width=True)

    if modo == MODO_CADASTRO:
        campos = [
            "",
            "codigo",
            "nome",
            "descricao_curta",
            "preco",
            "preco_custo",
            "estoque",
            "gtin",
            "marca",
            "categoria",
        ]
    else:
        campos = [
            "",
            "codigo",
            "estoque",
            "preco",
            "deposito_id",
        ]

    st.markdown("#### Mapeamento manual")
    mapeamento: Dict[str, str] = {}
    usados: List[str] = []

    for col in df.columns:
        valor_inicial = ""
        if isinstance(st.session_state.mapeamento_manual, dict):
            valor_inicial = st.session_state.mapeamento_manual.get(col, "")

        opcoes = [x for x in campos if x == "" or x == valor_inicial or x not in usados]
        idx = opcoes.index(valor_inicial) if valor_inicial in opcoes else 0

        escolha = st.selectbox(
            label=col,
            options=opcoes,
            index=idx,
            key=f"map_{col}",
        )
        mapeamento[col] = escolha
        if escolha:
            usados.append(escolha)

    st.session_state.mapeamento_manual = mapeamento

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Salvar perfil de colunas", use_container_width=True):
            salvar_perfil(list(df.columns), mapeamento)
            st.success("Perfil salvo com sucesso.")
    with c2:
        if st.button("Excluir perfil de colunas", use_container_width=True):
            apagou = deletar_perfil(list(df.columns))
            if apagou:
                st.success("Perfil excluído.")
            else:
                st.warning("Nenhum perfil salvo para esta estrutura.")

    with st.expander("Mapeamento final", expanded=False):
        st.json(mapeamento)


# =========================================================
# ENVIO PARA O BLING
# =========================================================
def get_column_by_mapped_name(df: pd.DataFrame, mapeamento: Dict[str, str], nome_mapeado: str) -> Optional[str]:
    for col_origem, destino in mapeamento.items():
        if destino == nome_mapeado and col_origem in df.columns:
            return col_origem
    return None


def build_product_rows(df: pd.DataFrame, mapeamento: Dict[str, str]) -> List[Dict]:
    codigo_col = get_column_by_mapped_name(df, mapeamento, "codigo")
    nome_col = get_column_by_mapped_name(df, mapeamento, "nome")
    desc_col = get_column_by_mapped_name(df, mapeamento, "descricao_curta")
    preco_col = get_column_by_mapped_name(df, mapeamento, "preco")
    custo_col = get_column_by_mapped_name(df, mapeamento, "preco_custo")
    estoque_col = get_column_by_mapped_name(df, mapeamento, "estoque")
    gtin_col = get_column_by_mapped_name(df, mapeamento, "gtin")
    marca_col = get_column_by_mapped_name(df, mapeamento, "marca")
    categoria_col = get_column_by_mapped_name(df, mapeamento, "categoria")

    rows = []
    for _, row in df.iterrows():
        payload = {
            "codigo": normalize_value(row[codigo_col]) if codigo_col else None,
            "nome": normalize_value(row[nome_col]) if nome_col else None,
            "descricao_curta": normalize_value(row[desc_col]) if desc_col else None,
            "preco": safe_float(row[preco_col]) if preco_col else None,
            "preco_custo": safe_float(row[custo_col]) if custo_col else None,
            "estoque": safe_float(row[estoque_col]) if estoque_col else None,
            "gtin": normalize_value(row[gtin_col]) if gtin_col else None,
            "marca": normalize_value(row[marca_col]) if marca_col else None,
            "categoria": normalize_value(row[categoria_col]) if categoria_col else None,
        }
        rows.append(payload)
    return rows


def build_stock_rows(df: pd.DataFrame, mapeamento: Dict[str, str]) -> List[Dict]:
    codigo_col = get_column_by_mapped_name(df, mapeamento, "codigo")
    estoque_col = get_column_by_mapped_name(df, mapeamento, "estoque")
    preco_col = get_column_by_mapped_name(df, mapeamento, "preco")
    deposito_col = get_column_by_mapped_name(df, mapeamento, "deposito_id")

    rows = []
    for _, row in df.iterrows():
        payload = {
            "codigo": normalize_value(row[codigo_col]) if codigo_col else None,
            "estoque": safe_float(row[estoque_col]) if estoque_col else None,
            "preco": safe_float(row[preco_col]) if preco_col else None,
            "deposito_id": normalize_value(row[deposito_col]) if deposito_col else None,
        }
        rows.append(payload)
    return rows


def render_send_panel() -> None:
    st.subheader("Enviar dados para o Bling")

    auth = BlingAuthManager()
    if not auth.is_configured():
        st.info("Configure o Bling para liberar o envio.")
        return

    if not auth.get_connection_status()["connected"]:
        st.info("Conecte sua conta do Bling para enviar dados.")
        return

    df = st.session_state.get("df_origem")
    mapeamento = st.session_state.get("mapeamento_manual") or {}

    if not isinstance(df, pd.DataFrame) or df.empty:
        st.info("Anexe primeiro a planilha do fornecedor.")
        return

    service = BlingSyncService()

    tab1, tab2 = st.tabs(["Enviar cadastro", "Enviar estoque"])

    with tab1:
        rows = build_product_rows(df, mapeamento)
        st.write(f"Linhas preparadas para cadastro: **{len(rows)}**")
        somente_validar = st.checkbox("Somente validar cadastro", value=True)

        if st.button("Enviar cadastro ao Bling", use_container_width=True):
            ok, resultado = service.enviar_cadastros(rows, dry_run=somente_validar)
            st.session_state.ultimo_log_envio = resultado if isinstance(resultado, list) else []
            if ok:
                st.success("Processo de cadastro concluído.")
            else:
                st.error("O envio teve falhas. Veja o log abaixo.")

    with tab2:
        rows = build_stock_rows(df, mapeamento)
        st.write(f"Linhas preparadas para estoque: **{len(rows)}**")
        deposito_fixo = st.text_input("ID depósito fixo (opcional, sobrescreve a planilha)", value="").strip()
        somente_validar_estoque = st.checkbox("Somente validar estoque", value=True)

        if st.button("Enviar estoque ao Bling", use_container_width=True):
            if deposito_fixo:
                for item in rows:
                    item["deposito_id"] = deposito_fixo

            ok, resultado = service.enviar_estoques(rows, dry_run=somente_validar_estoque)
            st.session_state.ultimo_log_envio = resultado if isinstance(resultado, list) else []
            if ok:
                st.success("Processo de estoque concluído.")
            else:
                st.error("O envio teve falhas. Veja o log abaixo.")

    logs = st.session_state.get("ultimo_log_envio") or []
    if logs:
        with st.expander("Log do último envio", expanded=True):
            log_df = pd.DataFrame(logs)
            st.dataframe(log_df, use_container_width=True, height=320)
            st.download_button(
                "Baixar log do envio",
                data=df_to_excel_bytes(log_df, "log_envio"),
                file_name="log_envio_bling.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )


# =========================================================
# MAIN
# =========================================================
def main():
    init_state()
    st.title("Bling Manual PRO")

    render_bling_panel()
    st.divider()
    render_bling_import_panel()
    st.divider()
    render_mapping_panel()
    st.divider()
    render_send_panel()


if __name__ == "__main__":
    main()
