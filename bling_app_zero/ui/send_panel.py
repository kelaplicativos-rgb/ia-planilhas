from __future__ import annotations

import inspect
import json
from typing import Any, Callable

import pandas as pd
import streamlit as st

try:
    from bling_app_zero.core.bling_auth import BlingAuthManager  # type: ignore
except Exception:  # pragma: no cover
    BlingAuthManager = None  # type: ignore

try:
    from bling_app_zero.core.bling_auth import obter_resumo_conexao  # type: ignore
except Exception:  # pragma: no cover
    obter_resumo_conexao = None  # type: ignore

try:
    from bling_app_zero.core.bling_auth import render_conectar_bling  # type: ignore
except Exception:  # pragma: no cover
    render_conectar_bling = None  # type: ignore

from bling_app_zero.ui.app_helpers import (
    blindar_df_para_bling,
    log_debug,
    normalizar_texto,
    safe_df_estrutura,
    validar_df_para_download,
)


# ============================================================
# HELPERS BÁSICOS
# ============================================================

def _safe_str(value: Any) -> str:
    try:
        return str(value or "").strip()
    except Exception:
        return ""


def _resolver_user_key() -> str:
    try:
        qp_user = st.query_params.get("bi")
        if isinstance(qp_user, list):
            qp_user = qp_user[0] if qp_user else ""
        return _safe_str(qp_user) or "default"
    except Exception:
        return "default"


def _safe_import_bling_sync():
    try:
        from bling_app_zero.services.bling import bling_sync  # type: ignore
        return bling_sync
    except Exception:
        return None


def _obter_df_final() -> pd.DataFrame:
    df = st.session_state.get("df_final")
    if safe_df_estrutura(df):
        return df.copy()
    return pd.DataFrame()


def _obter_tipo_operacao() -> str:
    return normalizar_texto(st.session_state.get("tipo_operacao") or "cadastro") or "cadastro"


def _obter_deposito_nome() -> str:
    return _safe_str(st.session_state.get("deposito_nome", ""))


def _origem_site_ativa() -> bool:
    modo_origem = normalizar_texto(st.session_state.get("modo_origem", ""))
    origem_tipo = normalizar_texto(st.session_state.get("origem_upload_tipo", ""))
    origem_nome = normalizar_texto(st.session_state.get("origem_upload_nome", ""))
    return (
        "site" in modo_origem
        or "site_gpt" in origem_tipo
        or "varredura_site_" in origem_nome
    )


def _varredura_site_concluida() -> bool:
    if not _origem_site_ativa():
        return True
    df_origem = st.session_state.get("df_origem")
    return isinstance(df_origem, pd.DataFrame) and not df_origem.empty


def _download_confirmado() -> bool:
    return bool(st.session_state.get("preview_download_realizado", False))


# ============================================================
# CONEXÃO BLING
# ============================================================

def _obter_status_conexao(user_key: str) -> tuple[bool, dict]:
    try:
        if callable(obter_resumo_conexao):
            resumo = obter_resumo_conexao(user_key=user_key)
            if isinstance(resumo, dict):
                conectado = bool(resumo.get("conectado") or resumo.get("connected"))
                return conectado, resumo

        if BlingAuthManager is not None:
            auth = BlingAuthManager(user_key=user_key)
            if hasattr(auth, "get_connection_status"):
                resumo = auth.get_connection_status()
                if isinstance(resumo, dict):
                    conectado = bool(resumo.get("conectado") or resumo.get("connected"))
                    return conectado, resumo

    except Exception as exc:
        log_debug(f"Falha ao obter resumo da conexão Bling: {exc}", nivel="ERRO")

    return False, {}


def _render_status_conexao(resumo: dict) -> None:
    conectado = bool(resumo.get("conectado") or resumo.get("connected"))
    company_name = _safe_str(resumo.get("company_name"))
    expires_at = _safe_str(resumo.get("expires_at"))
    last_auth_at = _safe_str(resumo.get("last_auth_at"))
    status = _safe_str(resumo.get("status")) or ("Conectado" if conectado else "Desconectado")

    if conectado:
        st.success(f"✅ Conexão ativa com o Bling. Status: {status}")
        if company_name:
            st.caption(f"Conta: {company_name}")
        if last_auth_at:
            st.caption(f"Última autenticação: {last_auth_at}")
        if expires_at:
            st.caption(f"Expira em: {expires_at}")
    else:
        st.info(f"Status da conexão: {status}")


def _render_conectar_bling_compat(user_key: str, titulo: str) -> None:
    if not callable(render_conectar_bling):
        st.warning("Função de conexão com o Bling não disponível no ambiente atual.")
        return

    try:
        assinatura = inspect.signature(render_conectar_bling)
        parametros = assinatura.parameters

        if "user_key" in parametros and "titulo" in parametros:
            render_conectar_bling(user_key=user_key, titulo=titulo)
        elif "user_key" in parametros:
            render_conectar_bling(user_key=user_key)
        else:
            render_conectar_bling()
    except Exception as exc:
        st.error(f"Falha ao renderizar botão de conexão com o Bling: {exc}")
        log_debug(f"Falha ao renderizar botão de conexão com o Bling: {exc}", nivel="ERRO")


# ============================================================
# VALIDAÇÃO
# ============================================================

def _validar_pronto_para_envio(df_final: pd.DataFrame, tipo_operacao: str) -> tuple[bool, list[str]]:
    erros: list[str] = []

    if not safe_df_estrutura(df_final):
        erros.append("O df_final ainda não foi gerado.")
    else:
        valido_df, erros_df = validar_df_para_download(df_final, tipo_operacao)
        if not valido_df:
            erros.extend(erros_df)

    if not _download_confirmado():
        erros.append("Confirme primeiro o download no preview final.")

    if not _varredura_site_concluida():
        erros.append("Finalize a varredura do site antes do envio ao Bling.")

    return len(erros) == 0, erros


# ============================================================
# UI DE PROGRESSO
# ============================================================

def _criar_progress_callback(total_itens: int) -> Callable[[dict], None]:
    st.markdown("#### Progresso do envio")

    progresso_bar = st.progress(0, text="Preparando envio...")
    status_area = st.empty()
    metricas_area = st.empty()
    log_area = st.empty()

    logs: list[str] = []

    def _callback(payload: dict) -> None:
        processados = int(payload.get("processados", 0) or 0)
        total = int(payload.get("total", total_itens) or total_itens or 1)
        percentual = int((processados / max(total, 1)) * 100)

        codigo = _safe_str(payload.get("codigo"))
        descricao = _safe_str(payload.get("descricao"))
        status = _safe_str(payload.get("status"))
        mensagem = _safe_str(payload.get("mensagem"))

        criados = int(payload.get("total_criados", 0) or 0)
        atualizados = int(payload.get("total_atualizados", 0) or 0)
        ignorados = int(payload.get("total_ignorados", 0) or 0)
        erros = int(payload.get("total_erros", 0) or 0)

        texto_status = f"Processando {processados}/{total}"
        if codigo:
            texto_status += f" | código: {codigo}"
        if descricao:
            texto_status += f" | {descricao[:80]}"

        progresso_bar.progress(percentual, text=texto_status)
        status_area.info(texto_status)

        c1, c2, c3, c4 = metricas_area.columns(4)
        c1.metric("Criados", criados)
        c2.metric("Atualizados", atualizados)
        c3.metric("Ignorados", ignorados)
        c4.metric("Erros", erros)

        prefixo = {
            "criado": "✅",
            "atualizado": "♻️",
            "ignorado": "⏭️",
            "simulado": "🧪",
            "erro": "❌",
        }.get(status, "•")

        linha_log = " ".join(
            p for p in [
                prefixo,
                f"[{processados}/{total}]",
                codigo,
                f"- {descricao[:60]}" if descricao else "",
                f"({mensagem})" if mensagem else "",
            ] if p
        ).strip()

        if linha_log:
            logs.append(linha_log)

        log_area.code("\n".join(logs[-15:]) if logs else "Aguardando primeiros itens...")

    return _callback


# ============================================================
# ENVIO
# ============================================================

def _enviar_para_bling(
    df_final: pd.DataFrame,
    tipo_operacao: str,
    deposito_nome: str,
) -> dict:
    estrategia = st.session_state.get("bling_sync_strategy", "inteligente")
    auto_mode = st.session_state.get("bling_sync_auto_mode", "manual")
    interval_value = st.session_state.get("bling_sync_interval_value", 15)
    interval_unit = st.session_state.get("bling_sync_interval_unit", "minutos")
    progress_update_every = int(st.session_state.get("bling_sync_progress_update_every", 1) or 1)

    bling_sync = _safe_import_bling_sync()

    log_debug(
        f"Painel de envio acionado | strategy={estrategia} | auto_mode={auto_mode} | "
        f"interval={interval_value} {interval_unit} | linhas={len(df_final)} | "
        f"progress_update_every={progress_update_every}",
        nivel="INFO",
    )

    if bling_sync is not None:
        try:
            progress_callback = _criar_progress_callback(len(df_final))

            if hasattr(bling_sync, "sincronizar_produtos_bling"):
                resultado = bling_sync.sincronizar_produtos_bling(
                    df_final=df_final.copy(),
                    tipo_operacao=tipo_operacao,
                    deposito_nome=deposito_nome,
                    strategy=estrategia,
                    auto_mode=auto_mode,
                    interval_value=interval_value,
                    interval_unit=interval_unit,
                    dry_run=False,
                    progress_callback=progress_callback,
                    progress_update_every=progress_update_every,
                )
                return resultado if isinstance(resultado, dict) else {
                    "ok": False,
                    "mensagem": "Serviço retornou formato inesperado.",
                }

            if hasattr(bling_sync, "enviar_produtos"):
                resultado = bling_sync.enviar_produtos(
                    df_final=df_final.copy(),
                    tipo_operacao=tipo_operacao,
                    deposito_nome=deposito_nome,
                    strategy=estrategia,
                    progress_callback=progress_callback,
                    progress_update_every=progress_update_every,
                )
                return resultado if isinstance(resultado, dict) else {
                    "ok": True,
                    "mensagem": "Envio executado.",
                }

        except Exception as exc:
            log_debug(f"Falha no envio real ao Bling: {exc}", nivel="ERRO")
            return {
                "ok": False,
                "modo": "erro_envio",
                "mensagem": f"Falha no envio ao Bling: {exc}",
                "tipo_operacao": tipo_operacao,
                "deposito_nome": deposito_nome,
            }

    return {
        "ok": False,
        "modo": "simulacao_local",
        "mensagem": "Serviço real de sincronização ainda não está disponível.",
        "tipo_operacao": tipo_operacao,
        "deposito_nome": deposito_nome,
        "strategy": estrategia,
        "auto_mode": auto_mode,
        "interval_value": interval_value,
        "interval_unit": interval_unit,
        "total_itens": int(len(df_final)),
    }


def _render_resultado_visual(resultado: dict) -> None:
    st.markdown("#### Resultado do envio")

    ok = bool(resultado.get("ok", False))
    total = int(resultado.get("total_itens", 0) or 0)
    criados = int(resultado.get("total_criados", 0) or 0)
    atualizados = int(resultado.get("total_atualizados", 0) or 0)
    ignorados = int(resultado.get("total_ignorados", 0) or 0)
    erros = int(resultado.get("total_erros", 0) or 0)
    mensagem = _safe_str(resultado.get("mensagem"))

    if ok:
        st.success(mensagem or "Envio ao Bling executado com sucesso.")
    else:
        st.warning(mensagem or "O envio retornou alertas ou falhou.")

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total", total)
    c2.metric("Criados", criados)
    c3.metric("Atualizados", atualizados)
    c4.metric("Ignorados", ignorados)
    c5.metric("Erros", erros)

    resultados = resultado.get("resultados") if isinstance(resultado.get("resultados"), list) else []
    if resultados:
        linhas = []
        for item in resultados[-30:]:
            linhas.append({
                "Linha": item.get("linha"),
                "Código": item.get("codigo"),
                "Descrição": item.get("descricao"),
                "Ação": item.get("acao"),
                "Status": item.get("status"),
                "Mensagem": item.get("mensagem"),
                "Produto ID": item.get("produto_id"),
            })
        st.dataframe(pd.DataFrame(linhas), use_container_width=True)

    with st.expander("Ver JSON completo do retorno", expanded=False):
        st.code(json.dumps(resultado, ensure_ascii=False, indent=2), language="json")


# ============================================================
# RENDERIZAÇÃO
# ============================================================

def render_bling_primeiro_acesso(*args, **kwargs) -> None:
    st.markdown("### Conexão com Bling")
    user_key = _resolver_user_key()
    conectado, resumo = _obter_status_conexao(user_key=user_key)

    if conectado:
        st.success("✅ Conta já conectada ao Bling.")
        if resumo.get("company_name"):
            st.caption(f"Conta: {resumo['company_name']}")
        if resumo.get("expires_at"):
            st.caption(f"Expira em: {resumo['expires_at']}")
        return

    _render_conectar_bling_compat(user_key=user_key, titulo="Conectar conta Bling")


def render_send_panel(*args, **kwargs) -> None:
    st.markdown("### Envio para o Bling")

    user_key = _resolver_user_key()

    if BlingAuthManager is None:
        st.warning("Integração OAuth do Bling não disponível no ambiente atual.")
        return

    auth = BlingAuthManager(user_key=user_key)

    if not auth.is_configured():
        st.warning("Integração OAuth do Bling ainda não configurada em `.streamlit/secrets.toml`.")
        return

    df_final = _obter_df_final()
    tipo_operacao = _obter_tipo_operacao()
    deposito_nome = _obter_deposito_nome()

    if safe_df_estrutura(df_final):
        df_final = blindar_df_para_bling(
            df=df_final,
            tipo_operacao_bling=tipo_operacao,
            deposito_nome=deposito_nome,
        )
        st.session_state["df_final"] = df_final

    pronto_envio, erros_fluxo = _validar_pronto_para_envio(df_final, tipo_operacao)
    conectado, resumo = _obter_status_conexao(user_key=user_key)

    _render_status_conexao(resumo)

    if not conectado:
        st.info("Conecte sua conta do Bling para liberar o envio.")
        _render_conectar_bling_compat(user_key=user_key, titulo="Conectar com Bling")

    st.markdown("#### Pré-validação do envio")
    c1, c2, c3 = st.columns(3)
    c1.metric("DF final", "OK" if safe_df_estrutura(df_final) else "Pendente")
    c2.metric("Download confirmado", "OK" if _download_confirmado() else "Pendente")
    c3.metric("Origem site", "OK" if _varredura_site_concluida() else "Pendente")

    if erros_fluxo:
        st.warning("Ainda existem bloqueios antes do envio.")
        for erro in erros_fluxo:
            st.write(f"- {erro}")

    st.markdown("#### Estratégia de sincronização")
    st.radio(
        "Como deseja enviar os produtos?",
        options=["inteligente", "cadastrar_novos", "atualizar_existentes"],
        format_func=lambda x: {
            "inteligente": "Cadastrar novos e atualizar existentes",
            "cadastrar_novos": "Cadastrar apenas novos",
            "atualizar_existentes": "Atualizar apenas existentes",
        }.get(x, x),
        key="bling_sync_strategy",
    )

    st.markdown("#### Atualização automática")
    modo_auto = st.radio(
        "Modo de atualização",
        options=["manual", "instantaneo", "periodico"],
        format_func=lambda x: {
            "manual": "Manual",
            "instantaneo": "Instantânea",
            "periodico": "Periódica",
        }.get(x, x),
        horizontal=True,
        key="bling_sync_auto_mode",
    )

    if modo_auto == "periodico":
        col1, col2 = st.columns(2)
        with col1:
            st.number_input(
                "Intervalo",
                min_value=1,
                step=1,
                key="bling_sync_interval_value",
            )
        with col2:
            st.selectbox(
                "Unidade",
                options=["minutos", "horas", "dias"],
                key="bling_sync_interval_unit",
            )

    st.markdown("#### Performance do painel")
    st.selectbox(
        "Atualizar progresso visual a cada",
        options=[1, 2, 5, 10, 20],
        index=2,
        key="bling_sync_progress_update_every",
        help="Valores maiores deixam a interface mais leve em envios grandes.",
    )

    liberar_botao = bool(conectado and pronto_envio)

    if st.button(
        "🚀 Enviar produtos ao Bling",
        use_container_width=True,
        disabled=not liberar_botao,
        key="btn_send_panel_enviar_bling",
    ):
        resultado = _enviar_para_bling(
            df_final=df_final.copy(),
            tipo_operacao=tipo_operacao,
            deposito_nome=deposito_nome,
        )
        st.session_state["bling_envio_resultado"] = resultado

        if bool(resultado.get("ok", False)):
            log_debug("Envio ao Bling executado com sucesso pelo send_panel.", nivel="INFO")
        else:
            log_debug(
                f"Envio ao Bling com alerta/falha pelo send_panel: {json.dumps(resultado, ensure_ascii=False)}",
                nivel="ERRO",
            )

    resultado = st.session_state.get("bling_envio_resultado")
    if isinstance(resultado, dict) and resultado:
        _render_resultado_visual(resultado)

    if not liberar_botao:
        st.caption(
            "O botão de envio só é liberado quando existir df_final válido, "
            "o download tiver sido confirmado, a origem por site estiver concluída "
            "e a conexão com o Bling estiver ativa."
        )
