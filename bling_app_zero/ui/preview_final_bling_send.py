from __future__ import annotations

import json
from typing import Any

import pandas as pd
import streamlit as st

from bling_app_zero.ui.app_helpers import log_debug
from bling_app_zero.ui.preview_final_bling_result import append_envio_log
from bling_app_zero.ui.preview_final_data import zerar_colunas_video
from bling_app_zero.ui.preview_final_state import resumo_rotina_site, safe_import_bling_sync


def enviar_para_bling(df_final: pd.DataFrame, tipo_operacao: str, deposito_nome: str) -> None:
    estrategia = st.session_state.get("bling_sync_strategy", "inteligente")
    auto_mode = st.session_state.get("bling_sync_auto_mode", "manual")
    interval_value = st.session_state.get("bling_sync_interval_value", 15)
    interval_unit = st.session_state.get("bling_sync_interval_unit", "minutos")

    bling_sync = safe_import_bling_sync()
    if bling_sync is None:
        st.error("Serviço de sincronização do Bling não foi carregado.")
        return

    df_final = zerar_colunas_video(df_final)

    st.session_state["preview_envio_em_execucao"] = True
    st.session_state["bling_envio_resultado"] = None
    st.session_state["preview_envio_resumo"] = {
        "total": int(len(df_final)),
        "processados": 0,
        "criados": 0,
        "atualizados": 0,
        "ignorados": 0,
        "erros": 0,
        "status_texto": "Preparando envio...",
    }
    st.session_state["preview_envio_logs"] = []

    box_status = st.empty()
    box_metricas = st.empty()
    box_log = st.empty()
    progress = st.progress(0)

    def _render_metricas() -> None:
        resumo = st.session_state.get("preview_envio_resumo", {})
        with box_metricas.container():
            c1, c2, c3, c4, c5 = st.columns(5)
            with c1:
                st.metric("Total", int(resumo.get("total", 0) or 0))
            with c2:
                st.metric("Processados", int(resumo.get("processados", 0) or 0))
            with c3:
                st.metric("Criados", int(resumo.get("criados", 0) or 0))
            with c4:
                st.metric("Atualizados", int(resumo.get("atualizados", 0) or 0))
            with c5:
                st.metric("Erros", int(resumo.get("erros", 0) or 0))

    def _render_logs() -> None:
        logs = list(st.session_state.get("preview_envio_logs", []))
        if logs:
            box_log.code("\n".join(logs[-12:]), language="text")

    def _status_callback(evento: dict[str, Any]) -> None:
        fase = str(evento.get("phase", "") or "")
        resumo = dict(st.session_state.get("preview_envio_resumo", {}))
        total = int(evento.get("total", resumo.get("total", 0) or 0))
        processados = int(evento.get("processed", resumo.get("processados", 0) or 0))

        resumo["total"] = total or resumo.get("total", 0)
        resumo["processados"] = processados
        resumo["criados"] = int(evento.get("total_criados", resumo.get("criados", 0) or 0))
        resumo["atualizados"] = int(evento.get("total_atualizados", resumo.get("atualizados", 0) or 0))
        resumo["ignorados"] = int(evento.get("total_ignorados", resumo.get("ignorados", 0) or 0))
        resumo["erros"] = int(evento.get("total_erros", resumo.get("erros", 0) or 0))

        if fase == "start":
            resumo["status_texto"] = "Iniciando envio real ao Bling..."
            box_status.info(resumo["status_texto"])
            progress.progress(0)

        elif fase == "item_start":
            codigo = str(evento.get("codigo", "") or "").strip()
            descricao = str(evento.get("descricao", "") or "").strip()
            resumo["status_texto"] = (
                f"Enviando {int(evento.get('index', 0))}/{total} • "
                f"{codigo or descricao or 'item sem identificação'}"
            )
            box_status.info(resumo["status_texto"])
            percentual = int(((max(processados, 0)) / max(total, 1)) * 100)
            progress.progress(min(percentual, 100))

        elif fase == "item_result":
            item = evento.get("item", {}) or {}
            status_item = str(item.get("status", "") or "").strip().upper()
            codigo = str(item.get("codigo", "") or "").strip()
            mensagem = str(item.get("mensagem", "") or "").strip()
            resumo["status_texto"] = f"Processado {processados}/{total}"
            box_status.info(resumo["status_texto"])
            percentual = int((processados / max(total, 1)) * 100)
            progress.progress(min(percentual, 100))
            append_envio_log(f"[{status_item}] {codigo or 'SEM-CODIGO'} - {mensagem}")

        elif fase == "finish":
            summary = evento.get("summary", {}) or {}
            resumo["status_texto"] = str(summary.get("mensagem", "") or "Envio finalizado.")
            resumo["processados"] = int(summary.get("total_processados", resumo.get("processados", 0) or 0))
            resumo["criados"] = int(summary.get("total_criados", resumo.get("criados", 0) or 0))
            resumo["atualizados"] = int(summary.get("total_atualizados", resumo.get("atualizados", 0) or 0))
            resumo["ignorados"] = int(summary.get("total_ignorados", resumo.get("ignorados", 0) or 0))
            resumo["erros"] = int(summary.get("total_erros", resumo.get("erros", 0) or 0))
            progress.progress(100)

            if str(summary.get("modo", "") or "") == "real":
                if bool(summary.get("ok", False)):
                    box_status.success(resumo["status_texto"])
                else:
                    box_status.warning(resumo["status_texto"])
            else:
                box_status.error("Envio não foi real. O sistema caiu em simulação.")

        st.session_state["preview_envio_resumo"] = resumo
        _render_metricas()
        _render_logs()

    try:
        resultado = bling_sync.sincronizar_produtos_bling(
            df_final=df_final.copy(),
            tipo_operacao=tipo_operacao,
            deposito_nome=deposito_nome,
            strategy=estrategia,
            auto_mode=auto_mode,
            interval_value=interval_value,
            interval_unit=interval_unit,
            dry_run=False,
            status_callback=_status_callback,
        )
        st.session_state["bling_envio_resultado"] = resultado
        st.session_state["preview_envio_em_execucao"] = False

        if bool(resultado.get("ok", False)) and str(resultado.get("modo", "")) == "real":
            st.success("Envio real ao Bling executado com sucesso.")
            log_debug("Envio real ao Bling executado com sucesso.", nivel="INFO")
        elif str(resultado.get("modo", "")) != "real":
            st.error("O envio terminou em simulação. Verifique a conexão OAuth/token antes de reenviar.")
            log_debug(
                f"Envio terminou em simulação: {json.dumps(resultado, ensure_ascii=False)}",
                nivel="ERRO",
            )
        else:
            st.warning("O envio foi executado, mas retornou alertas ou erros.")
            log_debug(
                f"Envio ao Bling retornou alertas/erros: {json.dumps(resultado, ensure_ascii=False)}",
                nivel="ERRO",
            )
    except Exception as exc:
        st.session_state["preview_envio_em_execucao"] = False
        st.session_state["bling_envio_resultado"] = {
            "ok": False,
            "modo": "erro_execucao",
            "mensagem": str(exc),
            "tipo_operacao": tipo_operacao,
            "deposito_nome": deposito_nome,
            "site_fallback": resumo_rotina_site(),
        }
        box_status.error(f"Falha no envio ao Bling: {exc}")
        log_debug(f"Falha no envio ao Bling: {exc}", nivel="ERRO")
