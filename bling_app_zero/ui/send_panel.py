from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from bling_app_zero.core.bling_api import BlingAPIClient
from bling_app_zero.core.bling_auth import BlingAuthManager
from bling_app_zero.core.bling_user_session import (
    clear_pending_oauth_user,
    ensure_current_user_defaults,
    get_current_user_key,
    get_current_user_label,
    set_pending_oauth_user,
)
from bling_app_zero.ui.app_helpers import log_debug


# ==========================================================
# HELPERS BASE
# ==========================================================


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


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except Exception:
        return int(default)


def _get_df_base_envio() -> pd.DataFrame | None:
    """
    Nunca modificar df_final ou df_saida direto.
    Sempre trabalhar com cópia isolada.
    """
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


def _is_connected() -> tuple[bool, str]:
    try:
        auth = _get_auth_manager()
        ok, token_or_msg = auth.get_valid_access_token()
        if ok:
            return True, "Conta conectada ao Bling."
        return False, _safe_str(token_or_msg) or "Conta não conectada."
    except Exception as e:
        return False, f"Falha ao verificar conexão: {e}"


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


def _processar_callback_oauth(on_continue=None) -> None:
    try:
        auth = _get_auth_manager()
        callback = auth.handle_oauth_callback()
        status = _safe_str(callback.get("status"))
        message = _safe_str(callback.get("message"))

        if status == "idle":
            return

        if status == "success":
            clear_pending_oauth_user()
            _set_oauth_feedback("success", message or "Conta conectada com sucesso.")
            log_debug("[SEND_PANEL] callback OAuth concluído com sucesso.", "INFO")

            st.session_state["bling_conectado"] = True
            st.session_state["bling_conexao_ok"] = True
            st.session_state["bling_ultimo_status"] = "conectado"

            if callable(on_continue):
                on_continue()
            else:
                st.rerun()
            return

        _set_oauth_feedback("error", message or "Falha ao concluir a conexão com o Bling.")
        log_debug(f"[SEND_PANEL] callback OAuth falhou: {message}", "ERROR")
        st.session_state["bling_conectado"] = False
        st.session_state["bling_conexao_ok"] = False
    except Exception as e:
        _set_oauth_feedback("error", f"Erro ao processar o retorno do Bling: {e}")
        log_debug(f"[SEND_PANEL] erro no callback OAuth: {e}", "ERROR")


def _render_connect_button_same_tab(auth_url: str) -> None:
    st.markdown(
        f"""
        <a href="{auth_url}" target="_self" style="
            display:block;
            width:100%;
            text-align:center;
            padding:0.75rem 1rem;
            border-radius:0.5rem;
            text-decoration:none;
            font-weight:600;
            background:#ff4b4b;
            color:white;
            border:none;
            box-sizing:border-box;
        ">🔌 Conectar com Bling</a>
        """,
        unsafe_allow_html=True,
    )


# ==========================================================
# HELPERS DE ENVIO REAL
# ==========================================================


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
        [
            "Estoque",
            "estoque",
            "Quantidade",
            "quantidade",
            "Saldo",
            "saldo",
        ],
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

    if "código".lower() not in colunas and "codigo" not in colunas and "sku" not in colunas:
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
        for idx, row in df_envio.fillna("").to_dict(orient="records"):
            pass
    except Exception:
        pass

    try:
        registros = df_envio.fillna("").to_dict(orient="records")

        for idx, row in enumerate(registros, start=1):
            payload = _normalize_row_for_product(row)

            if not payload["codigo"] or not payload["descricao"]:
                fail_count += 1
                erros.append(
                    f"Linha {idx}: produto ignorado por falta de Código/SKU ou Descrição."
                )
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


def _executar_envio_real(df_envio: pd.DataFrame, user_key: str, operacao: str) -> tuple[int, int, list[str]]:
    if operacao == "estoque":
        return _enviar_estoque(df_envio, user_key)
    return _enviar_cadastro(df_envio, user_key)


# ==========================================================
# UI DE ENVIO
# ==========================================================


def render_send_panel() -> None:
    st.subheader("Envio para o Bling")

    conectado, status_msg = _is_connected()
    user_label = get_current_user_label()
    operacao = _tipo_operacao()

    if conectado:
        st.success(f"Conta conectada ao Bling. Operação atual: {user_label}")
    else:
        st.warning(f"Bling não conectado. {status_msg}")

    df_base = _get_df_base_envio()

    if not _safe_df(df_base):
        st.warning("Nenhum dado disponível para envio.")
        log_debug("[SEND_PANEL] nenhum DataFrame disponível para envio.", "ERROR")
        return

    df_envio = _safe_copy_df(df_base)
    _persistir_df_envio(df_envio)

    st.caption("Os dados abaixo são apenas para envio. O download não será afetado.")

    with st.expander("Visualizar dados de envio", expanded=False):
        st.dataframe(df_envio.head(20), use_container_width=True)

    st.markdown("---")

    valido, erros_validacao = _validar_df_para_envio(df_envio, operacao)

    if not valido:
        st.error("A base ainda não está pronta para envio ao Bling.")
        for erro in erros_validacao:
            st.write(f"- {erro}")
        return

    if operacao == "estoque":
        st.text_input(
            "ID do depósito no Bling (opcional, usado quando a planilha não tiver ID numérico)",
            key="deposito_id_bling",
            placeholder="Ex.: 123456",
            help="Se a planilha estiver com nome do depósito e não com ID, você pode informar o ID aqui.",
        )

    col1, col2 = st.columns(2)

    with col1:
        enviar = st.button(
            "📤 Enviar para Bling",
            use_container_width=True,
            type="primary",
            disabled=not conectado,
            key="btn_enviar_bling_real",
        )

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
        st.info("Conecte o Bling primeiro para liberar o envio real.")
        return

    if enviar:
        try:
            total = len(df_envio)
            log_debug(
                f"[SEND_PANEL] envio real iniciado com {total} registro(s) em modo '{operacao}'.",
                "INFO",
            )

            with st.spinner("Enviando dados para o Bling..."):
                ok_count, fail_count, erros = _executar_envio_real(
                    df_envio=df_envio,
                    user_key=_get_user_key(),
                    operacao=operacao,
                )

            if ok_count > 0:
                st.success(f"Envio concluído. Sucesso: {ok_count} registro(s).")

            if fail_count > 0:
                st.warning(f"Alguns registros falharam: {fail_count}.")

            if erros:
                with st.expander("Ver erros do envio", expanded=False):
                    for erro in erros[:200]:
                        st.write(f"- {erro}")

            log_debug(
                f"[SEND_PANEL] envio finalizado. sucesso={ok_count}, falha={fail_count}",
                "INFO",
            )
        except Exception as e:
            log_debug(f"[SEND_PANEL] erro no envio real: {e}", "ERROR")
            st.error(f"Erro ao enviar para o Bling: {e}")

    st.markdown("---")
    st.info("⚠️ O envio utiliza uma cópia dos dados. O download final permanece intacto.")


# ==========================================================
# PRIMEIRO ACESSO / CONEXÃO
# ==========================================================


def render_bling_primeiro_acesso(
    on_skip=None,
    on_continue=None,
) -> None:
    ensure_current_user_defaults()
    _processar_callback_oauth(on_continue=on_continue)

    st.subheader("Conectar ao Bling")
    st.caption("Conecte sua conta Bling para envio automático ou continue sem integração.")

    _render_oauth_feedback()

    user_key = _get_user_key()
    user_label = get_current_user_label()
    auth = _get_auth_manager()

    conectado, status_msg = _is_connected()

    if conectado:
        st.success(f"Conta conectada com sucesso. Operação atual: {user_label}")
        col_a, col_b = st.columns(2)

        with col_a:
            if st.button(
                "➡️ Continuar",
                use_container_width=True,
                type="primary",
                key="btn_bling_conectado_continuar",
            ):
                log_debug("[SEND_PANEL] usuário continuou após conexão válida.", "INFO")
                if callable(on_continue):
                    on_continue()

        with col_b:
            if st.button(
                "🔄 Revalidar conexão",
                use_container_width=True,
                key="btn_bling_revalidar_conexao",
            ):
                log_debug("[SEND_PANEL] revalidação manual da conexão.", "INFO")
                st.rerun()

        return

    if not auth.is_configured():
        st.error(
            "Bling não configurado no ambiente. Verifique client_id, client_secret e redirect_uri no secrets.toml."
        )
        log_debug("[SEND_PANEL] configuração OAuth do Bling ausente ou incompleta.", "ERROR")

        if st.button(
            "➡️ Continuar sem conectar",
            use_container_width=True,
            key="btn_continuar_sem_conectar_sem_config",
        ):
            log_debug("[SEND_PANEL] usuário continuou sem conexão por falta de configuração.", "WARNING")
            if callable(on_skip):
                on_skip()
        return

    st.warning(status_msg)

    auth_url = ""
    try:
        set_pending_oauth_user(user_key, user_label)
        auth_url = auth.generate_auth_url()
    except Exception as e:
        log_debug(f"[SEND_PANEL] erro ao gerar URL OAuth: {e}", "ERROR")
        st.error(f"Não foi possível iniciar a conexão com o Bling: {e}")

    col1, col2 = st.columns(2)

    with col1:
        if auth_url:
            _render_connect_button_same_tab(auth_url)
            st.caption("A conexão será aberta na mesma aba e o retorno será tratado aqui automaticamente.")

    with col2:
        if st.button(
            "➡️ Continuar sem conectar",
            use_container_width=True,
            key="btn_continuar_sem_conectar",
        ):
            _clear_oauth_feedback()
            log_debug("[SEND_PANEL] usuário optou por continuar sem conexão.", "INFO")
            if callable(on_skip):
                on_skip()
