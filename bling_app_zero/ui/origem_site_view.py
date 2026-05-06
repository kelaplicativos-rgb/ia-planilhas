from __future__ import annotations

import re
import time

import pandas as pd
import streamlit as st

from bling_app_zero.core.product_image_extractor import normalize_image_urls
from bling_app_zero.ui.origem_site_config import MOTORES_SITE, PRESETS
from bling_app_zero.ui.origem_site_execution import executar_busca
from bling_app_zero.ui.origem_site_state import (
    limpar_busca_site,
    guardar_resultado,
    restaurar_resultado_site_travado,
)
from bling_app_zero.ui.origem_site_utils import extrair_urls, url_valida


CHAVES_PREVIEW_SITE = [
    "df_preview_inteligente",
    "df_auto_mapa",
    "df_preview_site_modelo_bling",
    "df_preview_origem",
    "origem_site_preview_modelo_bling",
    "origem_site_preview_modelo_bling_linhas",
    "origem_site_preview_modelo_bling_colunas",
    "origem_site_preview_hash",
]

URL_RE = re.compile(r"https?://[^\s\"'<>|,;]+|www\.[^\s\"'<>|,;]+", re.IGNORECASE)
IMAGEM_COLUNA_RE = re.compile(r"(url\s*)?(imagem|imagens|image|images|foto|fotos|img|gallery|galeria|thumbnail)", re.IGNORECASE)


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


def _limpar_preview_site() -> None:
    for chave in CHAVES_PREVIEW_SITE:
        st.session_state.pop(chave, None)


def _obter_df_bruto_site() -> pd.DataFrame | None:
    for chave in ("df_origem", "df_saida", "df_origem_site", "df_capturado_site"):
        df = st.session_state.get(chave)
        if isinstance(df, pd.DataFrame) and not df.empty:
            return df.copy()

    restaurado = restaurar_resultado_site_travado()
    if isinstance(restaurado, pd.DataFrame) and not restaurado.empty:
        return restaurado.copy()

    return None


def _normalizar_nome_coluna(nome: object) -> str:
    return str(nome or "").strip().lower().replace("í", "i").replace("é", "e").replace("á", "a").replace("ã", "a").replace("ç", "c")


def _coluna_eh_imagem(nome: object) -> bool:
    normalizado = _normalizar_nome_coluna(nome)
    if "video" in normalizado or "youtube" in normalizado:
        return False
    return bool(IMAGEM_COLUNA_RE.search(normalizado)) or normalizado in {
        "url imagens externas",
        "url_imagens_externas",
        "image_urls",
        "image_url",
        "main_image",
    }


def _normalizar_urls(valor: object) -> str:
    """Normaliza imagens capturadas antes do mapeamento.

    A versão anterior usava um regex genérico de URL e deixava passar trechos como:
    `https://megacentereletronicos.com.br/produto/image":"https:/...jpg`.
    Agora a limpeza usa o normalizador central, que só aceita URL real de arquivo
    de imagem e devolve tudo separado por `|`.
    """
    texto = str(valor or "").strip().replace("\\/", "/")
    if not texto:
        return ""
    return normalize_image_urls(texto, max_images=20)


def _consolidar_coluna_imagens(df: pd.DataFrame) -> pd.DataFrame:
    """Mantém todos os dados brutos e cria/normaliza uma coluna padrão de imagens limpa."""
    if not _df_valido(df):
        return pd.DataFrame()

    base = df.copy().fillna("")
    base.columns = [str(c).strip() for c in base.columns]
    colunas_imagem = [col for col in base.columns if _coluna_eh_imagem(col)]

    if not colunas_imagem:
        return base

    valores_finais: list[str] = []
    for _, row in base.iterrows():
        urls_linha: list[str] = []
        for coluna in colunas_imagem:
            normalizado = _normalizar_urls(row.get(coluna, ""))
            if normalizado:
                urls_linha.extend([u for u in normalizado.split("|") if u.strip()])

        vistos: set[str] = set()
        unicos: list[str] = []
        for url in urls_linha:
            if url not in vistos:
                vistos.add(url)
                unicos.append(url)
        valores_finais.append("|".join(unicos))

    if "URL Imagens Externas" not in base.columns:
        base["URL Imagens Externas"] = valores_finais
    else:
        atuais = base["URL Imagens Externas"].astype(str).tolist()
        base["URL Imagens Externas"] = [
            _normalizar_urls(atual) or novo
            for atual, novo in zip(atuais, valores_finais)
        ]

    return base.fillna("")


def _registrar_dados_brutos_para_mapeamento(df_bruto: pd.DataFrame) -> None:
    if not _df_valido(df_bruto):
        return

    df_map = _consolidar_coluna_imagens(df_bruto)
    st.session_state["df_origem"] = df_map.copy()
    st.session_state["df_saida"] = df_map.copy()
    st.session_state["df_precificado"] = df_map.copy()
    st.session_state["origem_site_preview_modelo_bling"] = False
    st.session_state["origem_site_preview_hash"] = _hash_df_simples(df_map)

    # Remove qualquer sobra do preview antigo da origem/modelo.
    st.session_state.pop("df_preview_origem", None)
    st.session_state.pop("df_preview_inteligente", None)
    st.session_state.pop("df_preview_site_modelo_bling", None)
    st.session_state.pop("df_auto_mapa", None)
    st.session_state.pop("df_final", None)


def _render_status_captura_sem_preview(df_bruto: pd.DataFrame) -> None:
    """Mostra só status compacto; não renderiza preview/tabela da origem."""
    if not _df_valido(df_bruto):
        return

    df_map = _consolidar_coluna_imagens(df_bruto)
    _registrar_dados_brutos_para_mapeamento(df_map)

    total_com_imagem = 0
    if "URL Imagens Externas" in df_map.columns:
        total_com_imagem = int(df_map["URL Imagens Externas"].astype(str).str.strip().ne("").sum())

    st.success(
        f"✅ Captura pronta para mapeamento: {len(df_map)} produtos, "
        f"{len(df_map.columns)} colunas extraídas, {total_com_imagem} com imagem."
    )
    st.caption("O preview da origem foi removido. A conferência acontece no mapeamento, com a 1ª linha em vermelho abaixo de cada campo.")


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
        etapa_atual.markdown("**✅ Resultado preservado. Siga para o mapeamento para revisar campo por campo.**")
        pulso.caption(f"Finalizado às {time.strftime('%H:%M:%S')}.")

    return atualizar, finalizar


def render_origem_site_panel() -> None:
    restaurar_resultado_site_travado()

    with st.container(border=True):
        st.markdown("#### 🚀 Captura por site")
        st.caption("O robô extrai os dados e envia direto para o mapeamento. O preview da origem foi removido.")

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
            _limpar_preview_site()
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

            df_bruto = _consolidar_coluna_imagens(df)
            guardar_resultado(df_bruto, urls, None, "AUTO_TOTAL")
            _registrar_dados_brutos_para_mapeamento(df_bruto)
            finalizar_progresso(len(df_bruto))
            st.success(f"{len(df_bruto)} produtos encontrados. Siga para o mapeamento para revisar os campos.")
            st.rerun()

    df_bruto = _obter_df_bruto_site()
    if df_bruto is not None:
        _render_status_captura_sem_preview(df_bruto)
