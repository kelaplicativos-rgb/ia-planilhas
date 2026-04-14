from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from bling_app_zero.core.bling_api import BlingAPIClient
from bling_app_zero.core.bling_auth import BlingAuthManager
from bling_app_zero.core.bling_user_session import (
    ensure_current_user_defaults,
    get_current_user_key,
    get_current_user_label,
    set_pending_oauth_user,
)
from bling_app_zero.ui.app_helpers import log_debug


def _safe_df(df) -> bool:
    try:
        return isinstance(df, pd.DataFrame) and not df.empty and len(df.columns) > 0
    except Exception:
        return False


def _safe_copy_df(df):
    try:
        return df.copy()
    except Exception:
        return df


def _safe_str(value: Any) -> str:
    try:
        return str(value or "").strip()
    except Exception:
        return ""


def _safe_float(value: Any) -> float | None:
    try:
        if value is None:
            return None

        text = str(value).strip()
        if not text:
            return None

        text = text.replace("R$", "").replace(" ", "")
        if "," in text:
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")

        return float(text)
    except Exception:
        return None


def _get_etapa_atual() -> str:
    for chave in ("etapa_origem", "etapa", "etapa_fluxo"):
        valor = _safe_str(st.session_state.get(chave)).lower()
        if valor:
            return valor
    return ""


def _esta_na_etapa_conexao() -> bool:
    return _get_etapa_atual() == "conexao"


def _get_df_base_envio() -> pd.DataFrame | None:
    for chave in ["df_final", "df_saida"]:
        df = st.session_state.get(chave)
        if _safe_df(df):
            log_debug(f"[SEND_PANEL] base de envio carregada de '{chave}'", "INFO")
            return _safe_copy_df(df)
    return None


def _persistir_df_envio(df_envio: pd.DataFrame) -> None:
    try:
        st.session_state["df_envio"] = df_envio.copy()
    except Exception:
        st.session_state["df_envio"] = df_envio


def _get_user_key() -> str:
    ensure_current_user_defaults()

    query_bi = st.query_params.get("bi")
    if isinstance(query_bi, list):
        query_bi = query_bi[0] if query_bi else ""

    user_key = _safe_str(query_bi) or _safe_str(st.session_state.get("bling_user_key"))
    if not user_key:
        user_key = get_current_user_key()

    st.session_state["bling_user_key"] = user_key
    return user_key


def _get_auth_manager() -> BlingAuthManager:
    return BlingAuthManager(user_key=_get_user_key())


def _set_connection_state(
    connected: bool,
    message: str = "",
    *,
    source: str = "",
) -> None:
    st.session_state["bling_conectado"] = bool(connected)
    st.session_state["bling_conexao_ok"] = bool(connected)
    st.session_state["bling_connection_message"] = _safe_str(message)
    st.session_state["bling_connection_checked"] = True
    st.session_state["bling_ultimo_status"] = "conectado" if connected else "desconectado"
    st.session_state["bling_connection_source"] = _safe_str(source)


def _clear_connection_state(message: str = "") -> None:
    _set_connection_state(False, message=message, source="clear")


def _is_connected() -> tuple[bool, str]:
    persisted = bool(st.session_state.get("bling_conectado"))
    persisted_msg = _safe_str(st.session_state.get("bling_connection_message"))
    if persisted:
        return True, persisted_msg or "Conta conectada ao Bling."

    try:
        auth = _get_auth_manager()
        ok, token_or_msg = auth.get_valid_access_token()
        msg = _safe_str(token_or_msg)

        if ok:
            _set_connection_state(
                True,
                message=msg or "Conta conectada ao Bling.",
                source="auth_check",
            )
            return True, msg or "Conta conectada ao Bling."

        _clear_connection_state(msg or "Conta não conectada.")
        return False, msg or "Conta não conectada."
    except Exception as e:
        msg = f"Falha ao verificar conexão: {e}"
        _clear_connection_state(msg)
        return False, msg


def _oauth_status_key() -> str:
    return "_bling_oauth_last_status"


def _oauth_message_key() -> str:
    return "_bling_oauth_last_message"


def _set_oauth_feedback(status: str, message: str) -> None:
    st.session_state[_oauth_status_key()] = _safe_str(status)
    st.session_state[_oauth_message_key()] = _safe_str(message)


def _render_oauth_feedback() -> None:
    status = _safe_str(st.session_state.get(_oauth_status_key()))
    message = _safe_str(st.session_state.get(_oauth_message_key()))

    if not status or not message:
        return

    if status == "success":
        st.success(message)
    elif status == "warning":
        st.warning(message)
    elif status == "error":
        st.error(message)
    else:
        st.info(message)


def _clear_oauth_feedback() -> None:
    st.session_state.pop(_oauth_status_key(), None)
    st.session_state.pop(_oauth_message_key(), None)


def _resolver_auth_url(auth: BlingAuthManager) -> str:
    candidates = [
        "build_authorize_url",
        "get_authorize_url",
        "get_authorization_url",
        "get_auth_url",
        "authorize_url",
    ]
    for attr in candidates:
        fn = getattr(auth, attr, None)
        if callable(fn):
            try:
                url = _safe_str(fn())
                if url:
                    return url
            except Exception as e:
                log_debug(f"[SEND_PANEL] falha ao gerar URL OAuth via {attr}: {e}", "ERROR")
    return ""


def _render_connect_button_same_tab(auth_url: str) -> None:
    if not auth_url:
        st.error("URL de autenticação do Bling não foi gerada.")
        return

    st.link_button(
        "🔗 Conectar com Bling",
        auth_url,
        use_container_width=True,
    )


def _tipo_operacao() -> str:
    valor = _safe_str(st.session_state.get("tipo_operacao_bling")).lower()
    if valor in {"estoque", "cadastro"}:
        return valor
    return "cadastro"


def _first_existing(row: dict[str, Any], candidates: list[str]) -> Any:
    lowered = {str(k).strip().lower(): v for k, v in row.items()}
    for name in candidates:
        value = lowered.get(name.strip().lower())
        if value not in (None, ""):
            return value
    return None


def _normalize_row_for_product(row: dict[str, Any]) -> dict[str, Any]:
    codigo = _first_existing(row, ["Código", "codigo", "SKU", "sku"])
    nome = _first_existing(
        row,
        [
            "Descrição",
            "descricao",
            "Descrição Curta",
            "descricao curta",
            "Nome",
            "nome",
            "Título",
            "titulo",
        ],
    )
    situacao = _first_existing(row, ["Situação", "situacao", "Status", "status"])
    unidade = _first_existing(row, ["Unidade", "unidade"])
    preco = _first_existing(
        row,
        [
            "Preço de venda",
            "preço de venda",
            "Preco de venda",
            "preco de venda",
            "Preço",
            "preço",
            "Preco",
            "preco",
            "Preço unitário (OBRIGATÓRIO)",
            "preço unitário (obrigatório)",
        ],
    )

    return {
        "codigo": _safe_str(codigo),
        "descricao": _safe_str(nome),
        "situacao": _safe_str(situacao),
        "unidade": _safe_str(unidade),
        "preco": preco,
    }


def _normalize_row_for_stock(row: dict[str, Any]) -> dict[str, Any]:
    codigo = _first_existing(row, ["Código", "codigo", "SKU", "sku"])
    estoque = _first_existing(
        row,
        ["Estoque", "estoque", "Quantidade", "quantidade", "Saldo", "saldo"],
    )
    deposito = _first_existing(
        row,
        [
            "Depósito (OBRIGATÓRIO)",
            "depósito (obrigatório)",
            "Deposito (OBRIGATÓRIO)",
            "deposito (obrigatório)",
            "Depósito",
            "depósito",
            "Deposito",
            "deposito",
        ],
    )
    preco = _first_existing(
        row,
        [
            "Preço unitário (OBRIGATÓRIO)",
            "preço unitário (obrigatório)",
            "Preço de venda",
            "preço de venda",
            "Preco de venda",
            "preco de venda",
        ],
    )

    return {
        "codigo": _safe_str(codigo),
        "estoque": _safe_float(estoque),
        "deposito": deposito,
        "preco": _safe_float(preco),
    }


def _validar_df_para_envio(df_envio: pd.DataFrame, operacao: str) -> tuple[bool, list[str]]:
    erros: list[str] = []

    if not _safe_df(df_envio):
        erros.append("Nenhum dado válido disponível para envio.")
        return False, erros

    colunas = {str(c).strip().lower() for c in df_envio.columns}

    if "código" not in colunas and "codigo" not in colunas and "sku" not in colunas:
        erros.append("A base de envio precisa ter uma coluna de Código ou SKU.")

    if operacao == "cadastro":
        possui_nome = any(
            c in colunas
            for c in ["descrição", "descricao", "descrição curta", "descricao curta", "nome", "título", "titulo"]
        )
        if not possui_nome:
            erros.append("Para cadastro, a base precisa ter Descrição, Descrição Curta, Nome ou Título.")
    else:
        possui_estoque = any(c in colunas for c in ["estoque", "quantidade", "saldo"])
        if not possui_estoque:
            erros.append("Para estoque, a base precisa ter Estoque, Quantidade ou Saldo.")

    return len(erros) == 0, erros


def _enviar_cadastro(df_envio: pd.DataFrame, user_key: str) -> tuple[int, int, list[str]]:
    client = BlingAPIClient(user_key=user_key)
    ok_count = 0
    fail_count = 0
    erros: list[str] = []

    try:
        registros = df_envio.fillna("").to_dict(orient="records")
        for idx, row in enumerate(registros, start=1):
            payload = _normalize_row_for_product(row)

            if not payload["codigo"] or not payload["descricao"]:
                fail_count += 1
                erros.append(f"Linha {idx}: produto ignorado por falta de Código/SKU ou Descrição.")
                continue

            ok, resp = client.upsert_product(payload)
            if ok:
                ok_count += 1
            else:
                fail_count += 1
                msg = _safe_str(resp.get("erro")) or "Erro desconhecido"
                detalhes = resp.get("detalhes")
                if detalhes not in (None, "", {}):
                    msg = f"{msg} | {detalhes}"
                erros.append(f"Linha {idx} ({payload['codigo']}): {msg}")
    finally:
        try:
            client.close()
        except Exception:
            pass

    return ok_count, fail_count, erros


def _resolver_deposito_id(valor: Any) -> str | None:
    text = _safe_str(valor)
    if not text:
        return None

    if text.isdigit():
        return text

    deposito_manual_id = _safe_str(st.session_state.get("deposito_id_bling"))
    if deposito_manual_id.isdigit():
        return deposito_manual_id

    return None


def _enviar_estoque(df_envio: pd.DataFrame, user_key: str) -> tuple[int, int, list[str]]:
    client = BlingAPIClient(user_key=user_key)
    ok_count = 0
    fail_count = 0
    erros: list[str] = []

    try:
        registros = df_envio.fillna("").to_dict(orient="records")
        for idx, row in enumerate(registros, start=1):
            payload = _normalize_row_for_stock(row)

            if not payload["codigo"]:
                fail_count += 1
                erros.append(f"Linha {idx}: estoque ignorado por falta de Código/SKU.")
                continue

            estoque = payload["estoque"]
            if estoque is None:
                estoque = 0.0

            deposito_id = _resolver_deposito_id(payload["deposito"])

            ok, resp = client.update_stock(
                codigo=payload["codigo"],
                estoque=float(estoque),
                deposito_id=deposito_id,
                preco=payload["preco"],
            )
            if ok:
                ok_count += 1
            else:
                fail_count += 1
                msg = _safe_str(resp.get("erro")) or "Erro desconhecido"
                detalhes = resp.get("detalhes")
                if detalhes not in (None, "", {}):
                    msg = f"{msg} | {detalhes}"
                erros.append(f"Linha {idx} ({payload['codigo']}): {msg}")
    finally:
        try:
            client.close()
        except Exception:
            pass

    return ok_count, fail_count, erros


def _executar_envio_real(
    df_envio: pd.DataFrame,
    user_key: str,
    operacao: str,
) -> tuple[int, int, list[str]]:
    if operacao == "estoque":
        return _enviar_estoque(df_envio, user_key)
    return _enviar_cadastro(df_envio, user_key)


def render_bling_primeiro_acesso(on_skip=None, on_continue=None) -> None:
    """
    Tela de conexão SOMENTE do início do fluxo.
    """
    if not _esta_na_etapa_conexao():
        log_debug(
            f"[SEND_PANEL] render_bling_primeiro_acesso bloqueado fora da etapa conexão "
            f"(etapa atual: {_get_etapa_atual()}).",
            "INFO",
        )
        return

    _render_oauth_feedback()

    user_label = get_current_user_label()
    user_key = _get_user_key()

    st.subheader("Conectar ao Bling")
    st.caption(
        "Conecte sua conta do Bling no início do fluxo. "
        "Essa opção não será exibida novamente no final."
    )

    if user_label:
        st.caption(f"Conta atual: {user_label}")

    col1, col2 = st.columns(2)

    with col1:
        if st.button(
            "➡️ Continuar sem conectar",
            use_container_width=True,
            key="btn_bling_primeiro_acesso_pular",
        ):
            st.session_state["bling_primeiro_acesso_decidido"] = True
            st.session_state["bling_primeiro_acesso_escolha"] = "sem_conexao"
            log_debug("[SEND_PANEL] usuário escolheu continuar sem conectar.", "INFO")
            if callable(on_skip):
                on_skip()

    with col2:
        try:
            set_pending_oauth_user(user_key)
        except Exception as e:
            log_debug(f"[SEND_PANEL] falha ao preparar usuário pendente do OAuth: {e}", "ERROR")

        auth = _get_auth_manager()
        auth_url = _resolver_auth_url(auth)
        _render_connect_button_same_tab(auth_url)

    _clear_oauth_feedback()

    conectado, mensagem = _is_connected()
    if conectado:
        st.success(mensagem or "Conta conectada ao Bling.")
        st.session_state["bling_primeiro_acesso_decidido"] = True
        st.session_state["bling_primeiro_acesso_escolha"] = "conectado"
        if callable(on_continue):
            on_continue()


def render_send_panel() -> None:
    st.subheader("Envio para o Bling")

    conectado, status_msg = _is_connected()
    user_label = get_current_user_label()
    operacao = _tipo_operacao()

    if conectado:
        st.success(status_msg or "Conta conectada ao Bling.")
    else:
        st.warning(
            "Conta não conectada ao Bling. "
            "A conexão fica apenas no início do fluxo e não aparece mais aqui no final."
        )
        if status_msg:
            st.caption(status_msg)

    if user_label:
        st.caption(f"Conta atual: {user_label}")

    df_base = _get_df_base_envio()
    if not _safe_df(df_base):
        st.warning("Nenhum dado disponível para envio.")
        log_debug("[SEND_PANEL] nenhum DataFrame disponível para envio.", "ERROR")
        return

    df_envio = _safe_copy_df(df_base)
    _persistir_df_envio(df_envio)

    st.caption(
        "Os dados abaixo são apenas para envio. "
        "O download final continua separado e a conexão não é renderizada novamente nesta etapa."
    )

    with st.expander("Visualizar dados de envio", expanded=False):
        st.dataframe(df_envio.head(20), use_container_width=True)

    validacao_ok, erros_validacao = _validar_df_para_envio(df_envio, operacao)
    if not validacao_ok:
        st.error("A base de envio não está pronta.")
        with st.expander("Ver detalhes", expanded=False):
            for erro in erros_validacao:
                st.write(f"- {erro}")
        return

    col1, col2 = st.columns(2)

    with col1:
        if st.button(
            "📤 Enviar para Bling",
            use_container_width=True,
            type="primary",
            key="btn_enviar_bling_real",
            disabled=not conectado,
        ):
            try:
                user_key = _get_user_key()
                ok_count, fail_count, erros = _executar_envio_real(df_envio, user_key, operacao)

                if ok_count and not fail_count:
                    st.success(f"Envio concluído com sucesso. {ok_count} registro(s) enviado(s).")
                elif ok_count and fail_count:
                    st.warning(
                        f"Envio concluído parcialmente. "
                        f"{ok_count} registro(s) enviado(s) e {fail_count} com erro."
                    )
                else:
                    st.error("Nenhum registro foi enviado com sucesso.")

                if erros:
                    with st.expander("Ver detalhes do envio", expanded=False):
                        for erro in erros[:200]:
                            st.write(f"- {erro}")

                log_debug(
                    f"[SEND_PANEL] envio executado. operacao={operacao} "
                    f"ok={ok_count} falha={fail_count}",
                    "INFO",
                )
            except Exception as e:
                log_debug(f"[SEND_PANEL] erro no envio real: {e}", "ERROR")
                st.error(f"Erro ao enviar para o Bling: {e}")

    with col2:
        if st.button(
            "🔄 Atualizar dados de envio",
            use_container_width=True,
            key="btn_atualizar_dados_envio",
        ):
            df_base = _get_df_base_envio()
            if _safe_df(df_base):
                _persistir_df_envio(df_base)
                log_debug("[SEND_PANEL] dados de envio atualizados.", "INFO")
                st.rerun()

    if not conectado:
        st.info(
            "Para enviar de fato ao Bling, use a conexão no início do fluxo. "
            "Aqui no final o sistema apenas informa o status e evita duplicar o botão de conexão."
                )
    
