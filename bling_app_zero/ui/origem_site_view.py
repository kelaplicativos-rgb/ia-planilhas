from __future__ import annotations

import time

import pandas as pd
import streamlit as st

from bling_app_zero.ui.origem_site_config import MOTORES_SITE, PRESETS
from bling_app_zero.ui.origem_site_execution import executar_busca
from bling_app_zero.ui.origem_site_state import limpar_busca_site, guardar_resultado
from bling_app_zero.ui.origem_site_utils import extrair_urls, url_valida
from bling_app_zero.ui.origem_site_visual import render_origem_site_visual_preview
from bling_app_zero.ui.origem_auto_map_preview import render_preview_inteligente


def _obter_df_atual_site() -> pd.DataFrame | None:
    df_saida = st.session_state.get("df_saida")
    df_origem = st.session_state.get("df_origem")

    if isinstance(df_saida, pd.DataFrame) and not df_saida.empty:
        return df_saida

    if isinstance(df_origem, pd.DataFrame) and not df_origem.empty:
        return df_origem

    return None


def _formatar_tempo(segundos: float) -> str:
    segundos = max(0, int(segundos or 0))
    minutos, seg = divmod(segundos, 60)
    horas, minutos = divmod(minutos, 60)
    if horas:
        return f"{horas:02d}:{minutos:02d}:{seg:02d}"
    return f"{minutos:02d}:{seg:02d}"


def _criar_monitor_progresso(total_urls: int):
    total_passos = max(1, int(total_urls) * max(1, len(PRESETS)) * max(1, len(MOTORES_SITE)))
    inicio = time.time()

    barra = st.progress(0, text="Preparando captura...")
    status = st.empty()
    detalhe = st.empty()

    estado = {
        "passo": 0,
        "ultimo_label": "Preparando captura...",
    }

    def atualizar(percentual_local: int, mensagem: str, indice_url: int = 0) -> None:
        agora = time.time()
        texto = str(mensagem or "Processando...").strip() or "Processando..."

        if texto != estado["ultimo_label"]:
            estado["passo"] = min(total_passos, estado["passo"] + 1)
            estado["ultimo_label"] = texto

        passo = max(1, estado["passo"])
        progresso = min(0.99, passo / total_passos)
        decorrido = agora - inicio
        estimado_total = decorrido / progresso if progresso > 0 else 0
        restante = max(0, estimado_total - decorrido)

        barra.progress(
            int(progresso * 100),
            text=f"{int(progresso * 100)}% • {texto}",
        )
        status.info(
            f"⏱️ Decorrido: {_formatar_tempo(decorrido)} | "
            f"⏳ Estimado restante: {_formatar_tempo(restante)} | "
            f"🧩 Progresso real: {passo}/{total_passos} etapas"
        )
        detalhe.caption(
            f"URL atual: {indice_url or '-'} de {total_urls} • "
            f"Sinal interno do motor: {int(percentual_local or 0)}%"
        )

    def finalizar(total_linhas: int) -> None:
        decorrido = time.time() - inicio
        barra.progress(100, text="100% • Captura concluída")
        status.success(
            f"✅ Concluído em {_formatar_tempo(decorrido)} • "
            f"{int(total_linhas)} linhas encontradas • "
            f"{total_passos}/{total_passos} etapas finalizadas"
        )
        detalhe.caption("Resultado consolidado e pronto para preview/mapeamento.")

    return atualizar, finalizar


def render_origem_site_panel() -> None:
    with st.container(border=True):
        st.markdown("#### 🚀 Captura por site (ULTRA automático)")

        urls_texto = st.text_area("URLs", height=100)
        urls = extrair_urls(urls_texto)

        col1, col2 = st.columns(2)
        with col1:
            executar = st.button("🚀 Buscar TUDO automaticamente")
        with col2:
            limpar = st.button("🧹 Limpar")

        if limpar:
            limpar_busca_site()
            st.rerun()

        if executar:
            if not urls:
                st.error("Informe URLs")
                return

            invalidas = [u for u in urls if not url_valida(u)]
            if invalidas:
                st.error("URLs inválidas")
                return

            atualizar_progresso, finalizar_progresso = _criar_monitor_progresso(len(urls))
            df = executar_busca(urls, None, "AUTO_TOTAL", progress_callback=atualizar_progresso)

            if df.empty:
                finalizar_progresso(0)
                st.warning("Nada encontrado")
                return

            guardar_resultado(df, urls, None, "AUTO_TOTAL")
            finalizar_progresso(len(df))
            st.success(f"{len(df)} produtos encontrados (ULTRA automático)")
            st.rerun()

    df_atual = _obter_df_atual_site()
    if df_atual is not None:
        render_origem_site_visual_preview(df_atual)

        # 🔥 NOVO: PREVIEW INTELIGENTE baseado no modelo do Bling
        df_modelo = st.session_state.get("df_modelo")
        if isinstance(df_modelo, pd.DataFrame) and not df_modelo.empty:
            render_preview_inteligente(df_atual, df_modelo)
