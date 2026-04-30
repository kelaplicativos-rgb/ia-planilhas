from __future__ import annotations

import time

import pandas as pd
import streamlit as st

from bling_app_zero.ui.app_core_flow import set_etapa_segura
from bling_app_zero.ui.origem_site_config import MOTORES_SITE, PRESETS
from bling_app_zero.ui.origem_site_execution import executar_busca
from bling_app_zero.ui.origem_site_state import limpar_busca_site, guardar_resultado
from bling_app_zero.ui.origem_site_utils import extrair_urls, url_valida
from bling_app_zero.ui.origem_site_visual import render_origem_site_visual_preview
from bling_app_zero.ui.origem_auto_map_preview import render_preview_inteligente


CHAVES_PREVIEW_OFICIAL_SITE = [
    "df_preview_inteligente",
    "df_auto_mapa",
    "df_precificado",
    "df_final",
    "origem_site_preview_oficial",
    "origem_site_preview_oficial_linhas",
    "origem_site_preview_oficial_colunas",
    "origem_site_preview_hash",
]


def _obter_df_atual_site() -> pd.DataFrame | None:
    df_saida = st.session_state.get("df_saida")
    df_origem = st.session_state.get("df_origem")

    if isinstance(df_saida, pd.DataFrame) and not df_saida.empty:
        return df_saida

    if isinstance(df_origem, pd.DataFrame) and not df_origem.empty:
        return df_origem

    return None


def _df_valido(df: object) -> bool:
    return isinstance(df, pd.DataFrame) and len(df.columns) > 0 and not df.empty


def _hash_df_simples(df: pd.DataFrame) -> str:
    if not isinstance(df, pd.DataFrame):
        return ""
    try:
        partes = ["|".join([str(c) for c in df.columns.tolist()])]
        amostra = df.head(30).fillna("").astype(str)
        for _, row in amostra.iterrows():
            partes.append("|".join(row.tolist()))
        return str(hash("\n".join(partes)))
    except Exception:
        return ""


def _limpar_preview_oficial_site() -> None:
    for chave in CHAVES_PREVIEW_OFICIAL_SITE:
        st.session_state.pop(chave, None)


def _normalizar_preview_oficial(df_preview: pd.DataFrame) -> pd.DataFrame:
    base = df_preview.copy().fillna("")
    base.columns = [str(c).strip() for c in base.columns]

    deposito_nome = str(st.session_state.get("deposito_nome", "") or "").strip()
    operacao = str(st.session_state.get("tipo_operacao", "cadastro") or "cadastro").strip().lower()

    if operacao == "estoque" and deposito_nome:
        for coluna in base.columns:
            nome = str(coluna).strip().lower()
            if "deposito" in nome or "depósito" in nome:
                base[coluna] = deposito_nome

    for coluna in base.columns:
        nome = str(coluna).strip().lower()
        if "video" in nome or "vídeo" in nome or "youtube" in nome:
            base[coluna] = ""

    return base.fillna("")


def _promover_preview_inteligente_para_fluxo(df_preview: pd.DataFrame) -> bool:
    if not _df_valido(df_preview):
        st.error("Preview inteligente inválido. Gere a captura novamente antes de continuar.")
        return False

    df_oficial = _normalizar_preview_oficial(df_preview)
    hash_oficial = _hash_df_simples(df_oficial)

    st.session_state["df_preview_inteligente"] = df_oficial.copy()
    st.session_state["df_precificado"] = df_oficial.copy()
    st.session_state["df_final"] = df_oficial.copy()
    st.session_state["origem_site_preview_oficial"] = True
    st.session_state["origem_site_preview_oficial_linhas"] = len(df_oficial)
    st.session_state["origem_site_preview_oficial_colunas"] = len(df_oficial.columns)
    st.session_state["origem_site_preview_hash"] = hash_oficial
    st.session_state["mapping_hash_base"] = hash_oficial
    st.session_state["mapping_hash_modelo"] = _hash_df_simples(st.session_state.get("df_modelo", pd.DataFrame()))
    st.session_state["mapping_manual"] = {str(col): str(col) for col in df_oficial.columns.tolist()}
    st.session_state["mapping_sugerido"] = {}
    st.session_state["agent_ui_package"] = {
        "status": "preview_site_oficial",
        "mensagem": "Preview inteligente da captura por site promovido como base oficial do fluxo.",
    }
    st.session_state["_ia_auto_mapping_executado"] = True

    if set_etapa_segura("mapeamento", origem="origem_site_preview_oficial"):
        st.rerun()
        return True

    st.error("Não foi possível avançar para o mapeamento. Confira se o modelo do Bling foi carregado corretamente.")
    return False


def _render_acao_preview_oficial(df_preview: pd.DataFrame) -> None:
    if not _df_valido(df_preview):
        return

    st.markdown("#### ✅ Usar preview no fluxo oficial")
    st.caption(
        "Este botão transforma o preview inteligente abaixo na base oficial do mapeamento, "
        "do preview final e do download. Assim a captura por site passa a seguir exatamente "
        "as colunas do modelo Bling anexado."
    )

    col1, col2 = st.columns([2, 1])
    with col1:
        usar_preview = st.button(
            "✅ Usar este preview no modelo Bling e continuar",
            key="btn_usar_preview_site_oficial",
            use_container_width=True,
        )
    with col2:
        st.metric("Linhas prontas", len(df_preview))

    if usar_preview:
        _promover_preview_inteligente_para_fluxo(df_preview)


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
            _limpar_preview_oficial_site()
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
            _limpar_preview_oficial_site()
            finalizar_progresso(len(df))
            st.success(f"{len(df)} produtos encontrados (ULTRA automático)")
            st.rerun()

    df_atual = _obter_df_atual_site()
    if df_atual is not None:
        st.markdown("#### 📦 Preview bruto da captura")
        st.caption("Este é o resultado extraído do site antes de encaixar no modelo Bling.")
        render_origem_site_visual_preview(df_atual)

        df_modelo = st.session_state.get("df_modelo")
        if isinstance(df_modelo, pd.DataFrame) and not df_modelo.empty:
            st.markdown("---")
            df_preview = render_preview_inteligente(
                df_atual,
                df_modelo,
                titulo="Preview convertido para o modelo do Bling",
            )
            _render_acao_preview_oficial(df_preview)
        else:
            st.info("Envie o modelo do Bling para gerar o preview oficial nas colunas corretas.")
