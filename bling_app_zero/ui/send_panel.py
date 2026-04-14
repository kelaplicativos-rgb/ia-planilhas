from __future__ import annotations

import hashlib
import traceback

import pandas as pd
import streamlit as st

try:
    from bling_app_zero.core.bling_auth import BlingAuthManager
except Exception:
    BlingAuthManager = None

try:
    from bling_app_zero.services.bling.bling_sync import BlingSync
except Exception:
    try:
        from bling_app_zero.services.bling_sync import BlingSync
    except Exception:
        BlingSync = None


# ==========================================================
# HELPERS
# ==========================================================
def _safe_str(valor) -> str:
    try:
        if valor is None:
            return ""
        if pd.isna(valor):
            return ""
    except Exception:
        pass

    try:
        return str(valor).strip()
    except Exception:
        return ""


def _safe_df(df) -> bool:
    try:
        return isinstance(df, pd.DataFrame) and not df.empty and len(df.columns) > 0
    except Exception:
        return False


def _garantir_estado():
    defaults = {
        "bling_resultado": None,
        "bling_enviando": False,
        "bling_hash_enviado": "",
        "bling_deposito_id": "",
        "bling_primeiro_acesso_decidido": False,
        "bling_primeiro_acesso_escolha": "Conectar depois",
        "bling_primeiro_acesso_autoavanço_feito": False,
        "bling_modo_envio": "cadastro",
    }

    for chave, valor in defaults.items():
        if chave not in st.session_state:
            st.session_state[chave] = valor

    if _safe_str(st.session_state.get("bling_primeiro_acesso_escolha")) not in {
        "Conectar depois",
        "Conectar agora",
    }:
        st.session_state["bling_primeiro_acesso_escolha"] = "Conectar depois"


def _resolver_user_key() -> str:
    for chave in ["bling_user_key", "user_key", "bi"]:
        valor = _safe_str(st.session_state.get(chave))
        if valor:
            return valor

    try:
        qp = st.query_params
        for chave in ["bi", "user_key"]:
            valor = _safe_str(qp.get(chave))
            if valor:
                return valor
    except Exception:
        pass

    return "default"


def _obter_df_envio():
    for chave in ["df_final", "df_saida", "df_precificado", "df_calc_precificado", "df_origem"]:
        df = st.session_state.get(chave)
        if _safe_df(df):
            try:
                return df.copy()
            except Exception:
                return df
    return None


def _hash_df(df: pd.DataFrame, tipo_api: str, deposito_id: str = "") -> str:
    try:
        base = df.to_csv(index=False, sep=";", lineterminator="\n")
        assinatura = f"{tipo_api}|{deposito_id}|{base}"
        return hashlib.sha256(assinatura.encode("utf-8")).hexdigest()
    except Exception:
        return ""


def _processar_callback_oauth(auth) -> bool:
    if auth is None:
        return False

    try:
        retorno = auth.handle_oauth_callback()
    except Exception as e:
        st.error(f"Erro ao processar retorno do Bling: {e}")
        return False

    if not isinstance(retorno, dict):
        return False

    status = _safe_str(retorno.get("status")).lower()
    mensagem = _safe_str(retorno.get("message"))

    if status == "success":
        st.success(mensagem or "Conta conectada com sucesso.")
        return True

    if status == "error":
        st.error(mensagem or "Falha ao autenticar com o Bling.")
        return False

    return False


def _auth_url_segura(auth) -> str:
    if auth is None:
        return ""

    try:
        if hasattr(auth, "build_authorize_url"):
            url = auth.build_authorize_url()
            if _safe_str(url):
                return _safe_str(url)
    except Exception:
        pass

    try:
        if hasattr(auth, "generate_auth_url"):
            url = auth.generate_auth_url()
            if _safe_str(url):
                return _safe_str(url)
    except Exception:
        pass

    return ""


def _esta_conectado(auth) -> bool:
    if auth is None:
        return False

    try:
        if hasattr(auth, "has_valid_token"):
            return bool(auth.has_valid_token())
    except Exception:
        pass

    try:
        if hasattr(auth, "get_connection_status"):
            status = auth.get_connection_status()
            return bool((status or {}).get("connected"))
    except Exception:
        pass

    try:
        if hasattr(auth, "get_valid_access_token"):
            ok, _ = auth.get_valid_access_token()
            return bool(ok)
    except Exception:
        pass

    return False


def _ir_para_origem_primeiro_acesso(on_continue=None) -> None:
    st.session_state["bling_primeiro_acesso_decidido"] = True
    st.session_state["bling_primeiro_acesso_escolha"] = "Conectar agora"
    st.session_state["bling_primeiro_acesso_autoavanço_feito"] = True

    if callable(on_continue):
        on_continue()
        return

    st.session_state["etapa_origem"] = "origem"
    st.session_state["etapa"] = "origem"
    st.session_state["etapa_fluxo"] = "origem"
    st.rerun()


# ==========================================================
# ETAPA 0 - PRIMEIRO ACESSO
# ==========================================================
def render_bling_primeiro_acesso(on_skip=None, on_continue=None):
    _garantir_estado()

    st.subheader("Conexão com Bling")
    st.caption("Conecte agora ou avance e conecte depois na etapa de envio.")

    if BlingAuthManager is None:
        st.error("Classe BlingAuthManager não encontrada no projeto.")
        return

    user_key = _resolver_user_key()

    try:
        auth = BlingAuthManager(user_key=user_key)
    except Exception as e:
        st.error(f"Erro ao iniciar autenticação do Bling: {e}")
        return

    conectou_agora = _processar_callback_oauth(auth)
    conectado = _esta_conectado(auth)

    if conectou_agora:
        st.session_state["bling_primeiro_acesso_escolha"] = "Conectar agora"
        st.session_state["bling_primeiro_acesso_decidido"] = True

        if not bool(st.session_state.get("bling_primeiro_acesso_autoavanço_feito")):
            _ir_para_origem_primeiro_acesso(on_continue=on_continue)
            return

    if conectado:
        st.session_state["bling_primeiro_acesso_escolha"] = "Conectar agora"
        st.session_state["bling_primeiro_acesso_decidido"] = True
        st.success("✅ Conta conectada ao Bling.")

        col1, col2 = st.columns(2)

        with col1:
            if st.button("Continuar para origem", use_container_width=True, type="primary"):
                _ir_para_origem_primeiro_acesso(on_continue=on_continue)

        with col2:
            st.info("Conexão concluída. O próximo passo é seguir para a origem dos dados.")

        return

    st.session_state["bling_primeiro_acesso_autoavanço_feito"] = False
    st.info("ℹ️ Conta ainda não conectada.")

    opcoes = ["Conectar depois", "Conectar agora"]
    valor_atual = _safe_str(st.session_state.get("bling_primeiro_acesso_escolha"))
    if valor_atual not in opcoes:
        st.session_state["bling_primeiro_acesso_escolha"] = "Conectar depois"

    escolha = st.radio(
        "Como deseja seguir?",
        opcoes,
        horizontal=True,
        key="bling_primeiro_acesso_escolha",
    )

    st.session_state["bling_primeiro_acesso_decidido"] = True

    if escolha == "Conectar agora":
        if not auth.is_configured():
            st.error("Credenciais do Bling não configuradas em secrets.")
        else:
            url = _auth_url_segura(auth)
            if url:
                st.link_button("Conectar com Bling", url, use_container_width=True)
            else:
                st.error("Não foi possível gerar a URL de autenticação.")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Continuar", use_container_width=True, type="primary"):
            if escolha == "Conectar depois":
                if callable(on_skip):
                    on_skip()
                else:
                    st.session_state["etapa_origem"] = "origem"
                    st.session_state["etapa"] = "origem"
                    st.session_state["etapa_fluxo"] = "origem"
                    st.rerun()
            else:
                if not _esta_conectado(auth):
                    st.warning("Conclua a conexão com o Bling antes de continuar.")
                    st.stop()

                _ir_para_origem_primeiro_acesso(on_continue=on_continue)

    with col2:
        st.info("Você poderá autenticar o Bling novamente na tela final de envio.")


# ==========================================================
# CONEXÃO
# ==========================================================
def _render_conexao(auth) -> bool:
    _processar_callback_oauth(auth)
    conectado = _esta_conectado(auth)

    st.markdown("---")
    col1, col2 = st.columns(2)

    with col1:
        if conectado:
            st.success("✅ Conectado ao Bling")
        else:
            st.info("ℹ️ Não conectado")

    with col2:
        try:
            if auth and auth.is_configured():
                if not conectado:
                    url = _auth_url_segura(auth)
                    if url:
                        st.link_button("Conectar com Bling", url, use_container_width=True)
                    else:
                        st.error("Não foi possível gerar a URL de autenticação.")
                else:
                    st.success("Conta já conectada.")
            else:
                st.error("Credenciais do Bling não configuradas.")
        except Exception as e:
            st.error(f"Erro ao gerar URL: {e}")

    return conectado


# ==========================================================
# RESULTADO
# ==========================================================
def _render_resultado():
    resultado = st.session_state.get("bling_resultado")
    if not isinstance(resultado, dict):
        return

    total = int(resultado.get("total", 0) or 0)
    sucesso = int(resultado.get("sucesso", 0) or 0)
    erro = int(resultado.get("erro", 0) or 0)

    if resultado.get("ok"):
        st.success("✅ Envio concluído")
    else:
        st.error("❌ Falha no envio")

    col1, col2, col3 = st.columns(3)
    col1.metric("Total", total)
    col2.metric("Sucesso", sucesso)
    col3.metric("Erros", erro)

    detalhes = resultado.get("detalhes")
    if isinstance(detalhes, dict) and detalhes:
        with st.expander("Detalhes do processamento", expanded=False):
            st.json(detalhes)

    logs = resultado.get("erros", [])
    if logs:
        with st.expander("Logs detalhados", expanded=True):
            for item in logs:
                st.error(str(item))

    if st.button("Limpar status do envio", use_container_width=True):
        st.session_state["bling_resultado"] = None
        st.session_state["bling_enviando"] = False
        st.session_state["bling_hash_enviado"] = ""
        st.rerun()


# ==========================================================
# PAINEL DE ENVIO
# ==========================================================
def render_send_panel():
    st.subheader("Enviar para Bling")
    _garantir_estado()

    df = _obter_df_envio()
    if not _safe_df(df):
        st.warning("⚠️ Nenhum dado disponível para envio.")
        return

    if BlingAuthManager is None:
        st.error("Classe BlingAuthManager não encontrada no projeto.")
        return

    if BlingSync is None:
        st.error("Classe BlingSync não encontrada no projeto.")
        return

    user_key = _resolver_user_key()

    try:
        auth = BlingAuthManager(user_key=user_key)
    except Exception as e:
        st.error(f"Erro ao iniciar autenticação do Bling: {e}")
        return

    try:
        sync = BlingSync(user_key=user_key)
    except Exception as e:
        st.error(f"Erro ao iniciar sincronização do Bling: {e}")
        return

    conectado = _render_conexao(auth)
    if not conectado:
        st.warning("Conecte ao Bling antes de enviar.")
        return

    modos = {
        "Cadastro de Produtos": "cadastro",
        "Atualização de Estoque": "estoque",
        "Cadastro + Estoque": "catalogo_completo",
    }

    modo_atual = _safe_str(st.session_state.get("bling_modo_envio"))
    if modo_atual not in modos.values():
        st.session_state["bling_modo_envio"] = "cadastro"

    labels = list(modos.keys())
    valor_para_label = {v: k for k, v in modos.items()}
    label_default = valor_para_label.get(
        st.session_state["bling_modo_envio"],
        "Cadastro de Produtos",
    )
    index_default = labels.index(label_default) if label_default in labels else 0

    tipo = st.radio(
        "Tipo de envio:",
        labels,
        horizontal=True,
        index=index_default,
    )

    tipo_api = modos[tipo]
    st.session_state["bling_modo_envio"] = tipo_api

    deposito_id = ""
    if tipo_api in {"estoque", "catalogo_completo"}:
        deposito_id = st.text_input(
            "ID do Depósito",
            value=_safe_str(st.session_state.get("bling_deposito_id")),
            placeholder="Ex: 123456",
        )
        st.session_state["bling_deposito_id"] = deposito_id

    st.markdown("---")
    st.info(f"{len(df)} registros prontos para envio")

    with st.expander("Ver dados que serão enviados", expanded=False):
        st.dataframe(df.head(20), use_container_width=True)

    df_hash = _hash_df(df, tipo_api=tipo_api, deposito_id=deposito_id)

    botao = st.button(
        "Enviar para Bling",
        use_container_width=True,
        disabled=bool(st.session_state.get("bling_enviando")),
        type="primary",
    )

    if botao:
        if st.session_state.get("bling_enviando"):
            st.warning("⚠️ Já existe um envio em andamento.")
            return

        if not df_hash:
            st.error("Não foi possível gerar a assinatura do lote para envio.")
            return

        if st.session_state.get("bling_hash_enviado") == df_hash:
            st.warning("⚠️ Mesmo lote já enviado.\nClique em limpar para reenviar.")
            return

        if tipo_api in {"estoque", "catalogo_completo"} and not _safe_str(deposito_id):
            st.warning("Informe o ID do depósito.")
            return

        st.session_state["bling_enviando"] = True

        try:
            with st.spinner("Enviando dados para o Bling..."):
                resultado = sync.sync_dataframe(
                    df=df.copy(),
                    tipo=tipo_api,
                    deposito_id=_safe_str(deposito_id) or None,
                )

            if not isinstance(resultado, dict):
                resultado = {
                    "ok": False,
                    "total": len(df),
                    "sucesso": 0,
                    "erro": len(df),
                    "erros": ["Retorno inválido do serviço de sincronização."],
                }

            st.session_state["bling_resultado"] = resultado

            if resultado.get("ok"):
                st.session_state["bling_hash_enviado"] = df_hash

        except Exception as e:
            st.session_state["bling_resultado"] = {
                "ok": False,
                "total": len(df),
                "sucesso": 0,
                "erro": len(df),
                "erros": [str(e), traceback.format_exc()],
            }
        finally:
            st.session_state["bling_enviando"] = False
            st.rerun()

    _render_resultado()


