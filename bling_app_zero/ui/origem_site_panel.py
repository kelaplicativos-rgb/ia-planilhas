# bling_app_zero/ui/origem_site_panel.py

from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from bling_app_zero.core.instant_scraper.click_selector import (
    extrair_por_opcao_click,
    gerar_opcoes_click_scraper,
)
from bling_app_zero.core.instant_scraper.html_fetcher import fetch_html
from bling_app_zero.core.instant_scraper.learning_store import (
    limpar_aprendizado,
    obter_aprendizado,
    salvar_aprendizado,
)
from bling_app_zero.core.instant_scraper.runner import run_scraper


def _txt(v: Any) -> str:
    return str(v or "").strip()


def _normalizar_url(url: str) -> str:
    url = _txt(url)
    if not url:
        return ""
    if url.startswith("//"):
        url = "https:" + url
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url


def _df_ok(df: Any) -> bool:
    return isinstance(df, pd.DataFrame) and not df.empty


def _registrar_df(df: pd.DataFrame, url: str) -> None:
    st.session_state["df_origem"] = df.copy().fillna("")
    st.session_state["site_url_origem"] = url
    st.session_state["site_busca_status"] = "concluido"
    st.session_state["site_busca_total"] = len(df)


def render_origem_site_panel() -> None:
    st.markdown("#### 🔥 Ultra Scraper IA — Auto Learning")
    st.caption("Detecta estruturas, permite escolha manual e aprende o melhor padrão por domínio.")

    url_input = st.text_input(
        "URL do fornecedor ou categoria",
        value=_txt(st.session_state.get("site_url_input", "")),
        placeholder="Ex.: https://www.megacentereletronicos.com.br",
        key="site_url_input",
    )

    url = _normalizar_url(url_input)
    aprendizado = obter_aprendizado(url) if url else {}

    if aprendizado:
        st.success(f"🧠 Aprendizado encontrado: opção {aprendizado.get('opcao_id')} para este domínio.")

    col1, col2, col3 = st.columns(3)

    with col1:
        detectar = st.button("🔍 Detectar estruturas", use_container_width=True, type="primary")

    with col2:
        usar_aprendido = st.button(
            "🧠 Usar aprendizado",
            use_container_width=True,
            disabled=not bool(aprendizado),
        )

    with col3:
        if st.button("🧹 Limpar aprendizado", use_container_width=True, disabled=not bool(url)):
            limpar_aprendizado(url)
            st.success("Aprendizado limpo para este domínio.")
            st.rerun()

    if detectar:
        if not url:
            st.error("Informe uma URL válida.")
            return

        html = fetch_html(url)
        opcoes = gerar_opcoes_click_scraper(html, url)

        if not opcoes:
            st.error("Nenhuma estrutura detectada.")
            return

        st.session_state["click_html"] = html
        st.session_state["click_url"] = url
        st.session_state["click_opcoes"] = opcoes

    if usar_aprendido:
        if not url:
            st.error("Informe uma URL válida.")
            return

        opcao_id = int(aprendizado.get("opcao_id", 1) or 1)
        html = fetch_html(url)

        df = extrair_por_opcao_click(
            html=html,
            base_url=url,
            opcao_id=opcao_id,
        )

        if _df_ok(df):
            _registrar_df(df, url)
            st.success(f"✅ Aprendizado aplicado: {len(df)} produto(s).")
        else:
            st.warning("O aprendizado antigo não funcionou nesta página. Detecte novamente as estruturas.")

    opcoes = st.session_state.get("click_opcoes", [])

    if opcoes:
        st.markdown("### Estruturas detectadas")

        for opcao in opcoes:
            opcao_id = int(opcao.get("id", 0) or 0)
            score = int(opcao.get("score", 0) or 0)
            pattern = opcao.get("pattern", "")
            df_preview = opcao.get("dataframe", pd.DataFrame())

            with st.container(border=True):
                st.markdown(f"#### Opção {opcao_id} — Score {score}")

                if _df_ok(df_preview):
                    st.dataframe(df_preview.head(10), use_container_width=True)
                else:
                    st.info("Esta estrutura não gerou produtos úteis no preview.")

                c1, c2 = st.columns(2)

                with c1:
                    if st.button(f"✅ Usar opção {opcao_id}", key=f"use_click_{opcao_id}", use_container_width=True):
                        df_final = extrair_por_opcao_click(
                            html=st.session_state.get("click_html", ""),
                            base_url=st.session_state.get("click_url", ""),
                            opcao_id=opcao_id,
                        )

                        if _df_ok(df_final):
                            _registrar_df(df_final, st.session_state.get("click_url", ""))
                            st.success(f"{len(df_final)} produto(s) carregado(s).")
                        else:
                            st.error("Falha ao extrair produtos desta opção.")

                with c2:
                    if st.button(f"🧠 Aprender opção {opcao_id}", key=f"learn_click_{opcao_id}", use_container_width=True):
                        salvar_aprendizado(
                            st.session_state.get("click_url", ""),
                            opcao_id=opcao_id,
                            score=score,
                            pattern=pattern,
                        )
                        st.success(f"Aprendido: opção {opcao_id} será usada neste domínio.")

    st.markdown("---")

    if st.button("⚡ Modo automático IA", use_container_width=True):
        if not url:
            st.error("Informe uma URL válida.")
            return

        df_auto = run_scraper(url)

        if _df_ok(df_auto):
            _registrar_df(df_auto, url)
            st.success(f"✅ Automático concluído: {len(df_auto)} produto(s).")
        else:
            st.error("Modo automático não encontrou produtos úteis.")

    df_final = st.session_state.get("df_origem")

    if _df_ok(df_final):
        st.markdown("### ✅ Resultado final")
        st.dataframe(df_final.head(50), use_container_width=True)

        csv = df_final.to_csv(index=False, sep=";", encoding="utf-8-sig").encode("utf-8-sig")

        st.download_button(
            "⬇️ Baixar preview CSV",
            data=csv,
            file_name="produtos_auto_learning.csv",
            mime="text/csv",
            use_container_width=True,
        )
