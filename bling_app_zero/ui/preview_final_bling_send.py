from __future__ import annotations

import json
from typing import Any

import pandas as pd
import streamlit as st

from bling_app_zero.ui.app_helpers import log_debug
from bling_app_zero.ui.preview_final_bling_result import append_envio_log
from bling_app_zero.ui.preview_final_data import zerar_colunas_video
from bling_app_zero.ui.preview_final_state import resumo_rotina_site, safe_import_bling_sync
from bling_app_zero.services.bling.auto_sell import executar_auto_sell, AutoSellConfig


def enviar_para_bling(df_final: pd.DataFrame, tipo_operacao: str, deposito_nome: str) -> None:
    estrategia = st.session_state.get("bling_sync_strategy", "inteligente")
    auto_mode = st.session_state.get("bling_sync_auto_mode", "manual")

    # 🔥 AUTO SELL MODE
    if auto_mode in ["instantaneo", "periodico"]:
        st.warning("Modo AUTO SELL ativo (execução segura).")

        resultado = executar_auto_sell(
            df_final=df_final.copy(),
            config=AutoSellConfig(
                tipo_operacao=tipo_operacao,
                deposito_nome=deposito_nome,
                strategy=estrategia,
                auto_mode=auto_mode,
                dry_run=True,
            ),
            callback=lambda e: append_envio_log(str(e)),
        )

        st.session_state["bling_envio_resultado"] = resultado
        st.success("AUTO SELL executado em modo seguro (dry-run).")
        return

    # 🔥 MODO NORMAL (já existente)
    bling_sync = safe_import_bling_sync()
    if bling_sync is None:
        st.error("Serviço de sincronização do Bling não foi carregado.")
        return

    df_final = zerar_colunas_video(df_final)

    try:
        resultado = bling_sync.sincronizar_produtos_bling(
            df_final=df_final.copy(),
            tipo_operacao=tipo_operacao,
            deposito_nome=deposito_nome,
            strategy=estrategia,
            auto_mode=auto_mode,
            dry_run=False,
        )

        st.session_state["bling_envio_resultado"] = resultado

        if bool(resultado.get("ok", False)):
            st.success("Envio ao Bling executado com sucesso.")
        else:
            st.warning("Envio ao Bling retornou alertas.")

    except Exception as exc:
        st.session_state["bling_envio_resultado"] = {
            "ok": False,
            "modo": "erro_execucao",
            "mensagem": str(exc),
            "tipo_operacao": tipo_operacao,
            "deposito_nome": deposito_nome,
            "site_fallback": resumo_rotina_site(),
        }
        st.error(f"Falha no envio ao Bling: {exc}")
        log_debug(f"Falha no envio ao Bling: {exc}", nivel="ERRO")
