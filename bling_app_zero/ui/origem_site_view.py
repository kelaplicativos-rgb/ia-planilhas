from __future__ import annotations

import time

import pandas as pd
import streamlit as st

from bling_app_zero.ui.app_core_flow import set_etapa_segura
from bling_app_zero.ui.origem_site_config import MOTORES_SITE, PRESETS
from bling_app_zero.ui.origem_site_execution import executar_busca
from bling_app_zero.ui.origem_site_state import (
    limpar_busca_site,
    guardar_resultado,
    restaurar_resultado_site_travado,
)
from bling_app_zero.ui.origem_site_utils import extrair_urls, url_valida
from bling_app_zero.ui.origem_auto_map_preview import render_preview_inteligente


CHAVES_PREVIEW_SITE_MODELO_BLING = [
    "df_preview_inteligente",
    "df_auto_mapa",
    "df_preview_site_modelo_bling",
    "origem_site_preview_modelo_bling",
    "origem_site_preview_modelo_bling_linhas",
    "origem_site_preview_modelo_bling_colunas",
    "origem_site_preview_hash",
]


def _obter_df_atual_site() -> pd.DataFrame | None:
    df_preview = st.session_state.get("df_preview_site_modelo_bling")
    df_saida = st.session_state.get("df_saida")
    df_origem = st.session_state.get("df_origem")

    if isinstance(df_preview, pd.DataFrame) and not df_preview.empty:
        return df_preview.copy()

    if isinstance(df_saida, pd.DataFrame) and not df_saida.empty:
        return df_saida.copy()

    if isinstance(df_origem, pd.DataFrame) and not df_origem.empty:
        return df_origem.copy()

    restaurado = restaurar_resultado_site_travado()
    if isinstance(restaurado, pd.DataFrame) and not restaurado.empty:
        return restaurado.copy()

    return None


def _obter_df_bruto_site() -> pd.DataFrame | None:
    df_saida = st.session_state.get("df_saida")
    df_origem = st.session_state.get("df_origem")

    if isinstance(df_saida, pd.DataFrame) and not df_saida.empty:
        return df_saida.copy()

    if isinstance(df_origem, pd.DataFrame) and not df_origem.empty:
        return df_origem.copy()

    restaurado = restaurar_resultado_site_travado()
    if isinstance(restaurado, pd.DataFrame) and not restaurado.empty:
        return restaurado.copy()

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


def _limpar_preview_site_modelo_bling() -> None:
    for chave in CHAVES_PREVIEW_SITE_MODELO_BLING:
        st.session_state.pop(chave, None)


def _normalizar_preview_modelo_bling(df_preview: pd.DataFrame) -> pd.DataFrame:
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


def _usar_preview_site_como_base_do_mapeamento(df_preview: pd.DataFrame) -> bool:
    if not _df_valido(df_preview):
        st.error("Preview da busca por site inválido. Gere a captura novamente antes de continuar.")
        return False

    df_modelo = st.session_state.get("df_modelo")
    if not isinstance(df_modelo, pd.DataFrame) or len(df_modelo.columns) == 0:
        st.error("Anexe o modelo Bling antes de usar o preview da busca por site.")
        return False

    df_preview_modelo = _normalizar_preview_modelo_bling(df_preview)
    hash_preview = _hash_df_simples(df_preview_modelo)

    st.session_state["df_preview_inteligente"] = df_preview_modelo.copy()
    st.session_state["df_preview_site_modelo_bling"] = df_preview_modelo.copy()
    st.session_state["df_precificado"] = df_preview_modelo.copy()
    st.session_state["origem_site_preview_modelo_bling"] = True
    st.session_state["origem_site_preview_modelo_bling_linhas"] = len(df_preview_modelo)
    st.session_state["origem_site_preview_modelo_bling_colunas"] = len(df_preview_modelo.columns)
    st.session_state["origem_site_preview_hash"] = hash_preview
    st.session_state["mapping_hash_base"] = hash_preview
    st.session_state["mapping_hash_modelo"] = _hash_df_simples(df_modelo)
    st.session_state["mapping_manual"] = {str(col): str(col) for col in df_preview_modelo.columns.tolist()}
    st.session_state["mapping_sugerido"] = {}
    st.session_state["agent_ui_package"] = {
        "status": "preview_site_modelo_bling",
        "mensagem": "Preview da busca por site montado em cima do modelo Bling anexado.",
    }
    st.session_state["_ia_auto_mapping_executado"] = True

    st.session_state.pop("df_final", None)

    if set_etapa_segura("mapeamento", origem="origem_site_preview_modelo_bling"):
        st.rerun()
        return True

    st.error("Não foi possível avançar para o mapeamento. Confira se o modelo do Bling foi carregado corretamente.")
    return False


def _registrar_preview_site_para_continuar(df_preview: pd.DataFrame) -> None:
    """Guarda o preview de site para o botão único Continuar da tela principal.

    Não renderiza botão local para evitar duplicidade/confusão no mobile.
    """
    if not _df_valido(df_preview):
        return

    df_preview_modelo = _normalizar_preview_modelo_bling(df_preview)
    st.session_state["df_preview_inteligente"] = df_preview_modelo.copy()
    st.session_state["df_preview_site_modelo_bling"] = df_preview_modelo.copy()
    st.session_state["df_precificado"] = df_preview_modelo.copy()
    st.session_state["origem_site_preview_modelo_bling"] = True
    st.session_state["origem_site_preview_modelo_bling_linhas"] = len(df_preview_modelo)
    st.session_state["origem_site_preview_modelo_bling_colunas"] = len(df_preview_modelo.columns)
    st.session_state["origem_site_preview_hash"] = _hash_df_simples(df_preview_modelo)
    st.session_state.pop("df_final", None)


def _formatar_tempo(segundos: float) -> str:
    segundos = max(0, int(segundos or 0))
    minutos, seg = divmod(segundos, 60)
    horas, minutos = divmod(minutos, 60)
    if horas:
        return f"{horas:02d}:{minutos:02d}:{seg:02d}"
    return f"{minutos:02d}:{seg:02d}"


def _recortar_texto(texto: str, limite: int = 120) -> str:
    texto_limpo = " ".join(str(texto or "").strip().split())
    if len(texto_limpo) <= limite:
        return texto_limpo
    return texto_limpo[: limite - 3].rstrip() + "..."


def _criar_monitor_progresso(total_urls: int):
    total_urls = max(1, int(total_urls or 1))
    total_passos = max(1, total_urls * max(1, len(PRESETS)) * max(1, len(MOTORES_SITE)))
    inicio = time.time()

    st.markdown("#### 🔎 Monitor detalhado da captura")
    barra = st.progress(0, text="0% • Preparando captura...")
    resumo = st.empty()
    grade_metricas = st.empty()
    etapa_atual = st.empty()
    trilha = st.empty()
    pulso = st.empty()

    estado = {
        "passo": 0,
        "ultimo_label": "Preparando captura...",
        "eventos": [],
        "ultimo_sinal": inicio,
    }

    def _registrar_evento(texto: str, percentual_local: int, indice_url: int) -> None:
        agora = time.time()
        estado["ultimo_sinal"] = agora
        evento = {
            "hora": time.strftime("%H:%M:%S"),
            "url": indice_url or "-",
            "motor": f"{int(percentual_local or 0)}%",
            "etapa": _recortar_texto(texto, 90),
        }
        estado["eventos"].append(evento)
        estado["eventos"] = estado["eventos"][-8:]

    def atualizar(percentual_local: int, mensagem: str, indice_url: int = 0) -> None:
        agora = time.time()
        texto = str(mensagem or "Processando...").strip() or "Processando..."

        if texto != estado["ultimo_label"]:
            estado["passo"] = min(total_passos, estado["passo"] + 1)
            estado["ultimo_label"] = texto
            _registrar_evento(texto, percentual_local, indice_url)
        elif agora - float(estado.get("ultimo_sinal") or inicio) >= 1.5:
            _registrar_evento(texto, percentual_local, indice_url)

        passo = max(1, min(total_passos, int(estado["passo"] or 1)))
        progresso = min(0.99, max(0.01, passo / total_passos))
        decorrido = agora - inicio
        estimado_total = decorrido / progresso if progresso > 0 else 0
        restante = max(0, estimado_total - decorrido)
        segundos_sem_sinal = max(0, int(agora - float(estado.get("ultimo_sinal") or agora)))
        percentual_global = int(progresso * 100)

        barra.progress(
            percentual_global,
            text=f"{percentual_global}% • Trabalhando agora: {_recortar_texto(texto, 55)}",
        )

        resumo.info(
            f"🟢 Sistema trabalhando • sinal recebido há {segundos_sem_sinal}s • "
            f"etapa {passo}/{total_passos} • URL {indice_url or '-'} de {total_urls}"
        )

        with grade_metricas.container():
            col1, col2, col3 = st.columns(3)
            col1.metric("⏱️ Decorrido", _formatar_tempo(decorrido))
            col2.metric("⏳ Restante", _formatar_tempo(restante))
            col3.metric("🧩 Progresso", f"{passo}/{total_passos}")

        etapa_atual.markdown(
            "\n".join(
                [
                    "**📍 O que está acontecendo agora**",
                    f"- **URL atual:** {indice_url or '-'} de {total_urls}",
                    f"- **Motor interno:** {int(percentual_local or 0)}%",
                    f"- **Ação:** {_recortar_texto(texto, 140)}",
                ]
            )
        )

        eventos = estado.get("eventos") or []
        if eventos:
            trilha.dataframe(pd.DataFrame(eventos), hide_index=True, use_container_width=True)

        pulso.caption(
            "💓 Pulso do robô: se este número muda, o sistema não travou. "
            f"Última atualização: {time.strftime('%H:%M:%S')}"
        )

    def finalizar(total_linhas: int) -> None:
        decorrido = time.time() - inicio
        barra.progress(100, text="100% • Captura concluída")
        resumo.success(
            f"✅ Captura concluída em {_formatar_tempo(decorrido)} • "
            f"{int(total_linhas)} linhas encontradas • "
            f"{total_passos}/{total_passos} etapas finalizadas"
        )
        with grade_metricas.container():
            col1, col2, col3 = st.columns(3)
            col1.metric("⏱️ Tempo total", _formatar_tempo(decorrido))
            col2.metric("📦 Linhas", int(total_linhas))
            col3.metric("✅ Etapas", f"{total_passos}/{total_passos}")
        etapa_atual.markdown("**✅ Resultado consolidado e pronto para gerar preview baseado no modelo Bling.**")
        pulso.caption(f"Finalizado às {time.strftime('%H:%M:%S')}.")

    return atualizar, finalizar


def render_origem_site_panel() -> None:
    # Blindagem: antes de desenhar a tela, tenta restaurar a última captura por site.
    restaurar_resultado_site_travado()

    with st.container(border=True):
        st.markdown("#### 🚀 Captura por site (ULTRA automático)")

        total_travado = int(st.session_state.get("origem_site_total_produtos") or 0)
        if st.session_state.get("origem_site_resultado_travado") and total_travado > 0:
            st.success(
                f"🔒 Captura por site travada: {total_travado} produtos preservados. "
                "Você pode atualizar o navegador sem perder esta busca."
            )

        urls_texto = st.text_area("URLs", height=100)
        urls = extrair_urls(urls_texto)

        col1, col2 = st.columns(2)
        with col1:
            executar = st.button("🚀 Buscar TUDO automaticamente")
        with col2:
            limpar = st.button("🧹 Limpar")

        if limpar:
            limpar_busca_site()
            _limpar_preview_site_modelo_bling()
            st.session_state.pop("df_final", None)
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
            _limpar_preview_site_modelo_bling()
            st.session_state.pop("df_final", None)
            finalizar_progresso(len(df))
            st.success(f"{len(df)} produtos encontrados (ULTRA automático)")
            st.rerun()

    df_bruto = _obter_df_bruto_site()
    if df_bruto is not None:
        df_modelo = st.session_state.get("df_modelo")
        if isinstance(df_modelo, pd.DataFrame) and not df_modelo.empty:
            df_preview = render_preview_inteligente(
                df_bruto,
                df_modelo,
                titulo="Planilha de preview da busca por site baseada no modelo Bling anexado",
            )
            _registrar_preview_site_para_continuar(df_preview)
        else:
            st.info("Anexe o modelo Bling para gerar a planilha de preview da busca por site nas colunas corretas.")
