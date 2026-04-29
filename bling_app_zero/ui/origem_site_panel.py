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


def _limpar_estado_busca_site() -> None:
    for chave in [
        "click_html",
        "click_url",
        "click_opcoes",
        "site_busca_status",
        "site_busca_total",
        "site_busca_erro",
    ]:
        st.session_state.pop(chave, None)


def _registrar_df(df: pd.DataFrame, url: str) -> None:
    base = df.copy().fillna("")

    st.session_state["df_origem"] = base
    st.session_state["site_url_origem"] = url
    st.session_state["site_busca_status"] = "concluido"
    st.session_state["site_busca_total"] = len(base)
    st.session_state["site_busca_erro"] = ""


def _registrar_erro(msg: str) -> None:
    st.session_state["site_busca_status"] = "erro"
    st.session_state["site_busca_erro"] = msg


def _buscar_html_com_feedback(url: str) -> str:
    barra = st.progress(0)
    status = st.empty()

    try:
        status.info("Conectando ao site...")
        barra.progress(20)

        html = fetch_html(url)

        barra.progress(70)
        status.info("Página carregada. Analisando HTML...")

        if not _txt(html):
            barra.progress(100)
            status.error("O site não retornou HTML útil.")
            return ""

        barra.progress(100)
        status.success("HTML carregado com sucesso.")
        return html

    except Exception as exc:
        barra.progress(100)
        status.error(f"Falha ao carregar o site: {exc}")
        return ""


def _detectar_estruturas(url: str) -> None:
    if not url:
        st.error("Informe uma URL válida.")
        return

    st.session_state["site_busca_status"] = "detectando"
    st.session_state["site_busca_erro"] = ""

    html = _buscar_html_com_feedback(url)

    if not html:
        _registrar_erro("Não foi possível carregar HTML útil da URL informada.")
        return

    barra = st.progress(0)
    status = st.empty()

    try:
        status.info("Detectando estruturas semelhantes a produtos...")
        barra.progress(40)

        opcoes = gerar_opcoes_click_scraper(html, url)

        barra.progress(85)

        if not opcoes:
            barra.progress(100)
            _registrar_erro("Nenhuma estrutura detectada.")
            st.error("Nenhuma estrutura detectada.")
            return

        st.session_state["click_html"] = html
        st.session_state["click_url"] = url
        st.session_state["click_opcoes"] = opcoes
        st.session_state["site_busca_status"] = "estruturas_detectadas"
        st.session_state["site_busca_total"] = len(opcoes)

        barra.progress(100)
        status.success(f"{len(opcoes)} estrutura(s) detectada(s).")

    except Exception as exc:
        barra.progress(100)
        _registrar_erro(f"Erro ao detectar estruturas: {exc}")
        st.error(f"Erro ao detectar estruturas: {exc}")


def _usar_aprendizado(url: str, aprendizado: dict[str, Any]) -> None:
    if not url:
        st.error("Informe uma URL válida.")
        return

    if not aprendizado:
        st.warning("Nenhum aprendizado encontrado para este domínio.")
        return

    st.session_state["site_busca_status"] = "usando_aprendizado"
    st.session_state["site_busca_erro"] = ""

    opcao_id = int(aprendizado.get("opcao_id", 1) or 1)
    html = _buscar_html_com_feedback(url)

    if not html:
        _registrar_erro("Não foi possível carregar HTML útil para aplicar o aprendizado.")
        return

    try:
        with st.spinner("Aplicando aprendizado salvo..."):
            df = extrair_por_opcao_click(
                html=html,
                base_url=url,
                opcao_id=opcao_id,
            )

        if _df_ok(df):
            _registrar_df(df, url)
            st.success(f"✅ Aprendizado aplicado: {len(df)} produto(s).")
        else:
            _registrar_erro("O aprendizado antigo não funcionou nesta página.")
            st.warning("O aprendizado antigo não funcionou nesta página. Detecte novamente as estruturas.")

    except Exception as exc:
        _registrar_erro(f"Erro ao usar aprendizado: {exc}")
        st.error(f"Erro ao usar aprendizado: {exc}")


def _modo_automatico(url: str) -> None:
    if not url:
        st.error("Informe uma URL válida.")
        return

    st.session_state["site_busca_status"] = "automatico"
    st.session_state["site_busca_erro"] = ""

    barra = st.progress(0)
    status = st.empty()

    try:
        status.info("Executando modo automático IA...")
        barra.progress(25)

        df_auto = run_scraper(url)

        barra.progress(85)

        if _df_ok(df_auto):
            _registrar_df(df_auto, url)
            barra.progress(100)
            status.success(f"✅ Automático concluído: {len(df_auto)} produto(s).")
        else:
            barra.progress(100)
            _registrar_erro("Modo automático não encontrou produtos úteis.")
            status.error("Modo automático não encontrou produtos úteis.")

    except Exception as exc:
        barra.progress(100)
        _registrar_erro(f"Erro no modo automático: {exc}")
        status.error(f"Erro no modo automático: {exc}")


def _render_status() -> None:
    status = _txt(st.session_state.get("site_busca_status", ""))
    total = int(st.session_state.get("site_busca_total", 0) or 0)
    erro = _txt(st.session_state.get("site_busca_erro", ""))

    if status == "concluido":
        st.success(f"Busca concluída. {total} registro(s) carregado(s).")
    elif status == "estruturas_detectadas":
        st.info(f"{total} estrutura(s) detectada(s). Escolha uma opção abaixo.")
    elif status == "erro" and erro:
        st.error(erro)


def _render_opcoes_detectadas() -> None:
    opcoes = st.session_state.get("click_opcoes", [])

    if not opcoes:
        return

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
                if st.button(
                    f"✅ Usar opção {opcao_id}",
                    key=f"use_click_{opcao_id}",
                    use_container_width=True,
                ):
                    try:
                        with st.spinner("Extraindo produtos da estrutura escolhida..."):
                            df_final = extrair_por_opcao_click(
                                html=st.session_state.get("click_html", ""),
                                base_url=st.session_state.get("click_url", ""),
                                opcao_id=opcao_id,
                            )

                        if _df_ok(df_final):
                            _registrar_df(df_final, st.session_state.get("click_url", ""))
                            st.success(f"{len(df_final)} produto(s) carregado(s).")
                        else:
                            _registrar_erro("Falha ao extrair produtos desta opção.")
                            st.error("Falha ao extrair produtos desta opção.")

                    except Exception as exc:
                        _registrar_erro(f"Erro ao usar opção {opcao_id}: {exc}")
                        st.error(f"Erro ao usar opção {opcao_id}: {exc}")

            with c2:
                if st.button(
                    f"🧠 Aprender opção {opcao_id}",
                    key=f"learn_click_{opcao_id}",
                    use_container_width=True,
                ):
                    salvar_aprendizado(
                        st.session_state.get("click_url", ""),
                        opcao_id=opcao_id,
                        score=score,
                        pattern=pattern,
                    )
                    st.success(f"Aprendido: opção {opcao_id} será usada neste domínio.")


def _render_resultado_final() -> None:
    df_final = st.session_state.get("df_origem")

    if not _df_ok(df_final):
        return

    st.markdown("### ✅ Resultado final")
    st.dataframe(df_final.head(50), use_container_width=True)

    csv = df_final.to_csv(index=False, sep=";", encoding="utf-8-sig").encode("utf-8-sig")

    st.download_button(
        "⬇️ Baixar preview CSV",
        data=csv,
        file_name="produtos_busca_site.csv",
        mime="text/csv",
        use_container_width=True,
    )


def render_origem_site_panel() -> None:
    st.markdown("#### 🔥 Busca por site — Ultra Scraper IA")
    st.caption("Detecta estruturas, permite escolha manual e aprende o melhor padrão por domínio.")

    url_input = st.text_input(
        "URL do fornecedor ou categoria",
        value=_txt(st.session_state.get("site_url_input", "")),
        placeholder="Ex.: https://www.megacentereletronicos.com.br",
        key="site_url_input",
    )

    url = _normalizar_url(url_input)

    url_anterior = _txt(st.session_state.get("_site_url_normalizada_anterior", ""))
    if url and url_anterior and url != url_anterior:
        _limpar_estado_busca_site()

    if url:
        st.session_state["_site_url_normalizada_anterior"] = url

    aprendizado = obter_aprendizado(url) if url else {}

    if aprendizado:
        st.success(f"🧠 Aprendizado encontrado: opção {aprendizado.get('opcao_id')} para este domínio.")

    _render_status()

    col1, col2, col3 = st.columns(3)

    with col1:
        detectar = st.button(
            "🔍 Detectar estruturas",
            use_container_width=True,
            type="primary",
            disabled=not bool(url),
        )

    with col2:
        usar_aprendido = st.button(
            "🧠 Usar aprendizado",
            use_container_width=True,
            disabled=not bool(aprendizado) or not bool(url),
        )

    with col3:
        limpar = st.button(
            "🧹 Limpar busca",
            use_container_width=True,
            disabled=not bool(url),
        )

    if limpar:
        _limpar_estado_busca_site()
        st.success("Busca limpa. Informe a URL e execute novamente.")

    if detectar:
        _detectar_estruturas(url)

    if usar_aprendido:
        _usar_aprendizado(url, aprendizado)

    if url and aprendizado:
        if st.button("🧹 Limpar aprendizado deste domínio", use_container_width=True):
            limpar_aprendizado(url)
            st.success("Aprendizado limpo para este domínio.")

    _render_opcoes_detectadas()

    st.markdown("---")

    if st.button(
        "⚡ Modo automático IA",
        use_container_width=True,
        disabled=not bool(url),
    ):
        _modo_automatico(url)

    _render_resultado_final()

