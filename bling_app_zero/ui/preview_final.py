from __future__ import annotations

import re

import pandas as pd
import streamlit as st

from bling_app_zero.ui.app_helpers import (
    exportar_excel_bytes,
    limpar_gtin_invalido,
    log_debug,
    validar_campos_obrigatorios,
)


def _safe_df(df) -> bool:
    try:
        return isinstance(df, pd.DataFrame) and not df.empty and len(df.columns) > 0
    except Exception:
        return False


def _get_df_fluxo() -> pd.DataFrame | None:
    """
    Ordem de prioridade do fluxo final:
    1) df_final
    2) df_saida
    3) df_precificado
    4) df_calc_precificado
    5) df_origem
    """
    for chave in ["df_final", "df_saida", "df_precificado", "df_calc_precificado", "df_origem"]:
        df = st.session_state.get(chave)
        if _safe_df(df):
            return df.copy()
    return None


def _normalizar_validacao(resultado_validacao) -> bool:
    try:
        if isinstance(resultado_validacao, bool):
            return resultado_validacao
        if resultado_validacao is None:
            return True
        if isinstance(resultado_validacao, dict):
            return len(resultado_validacao) == 0
        if isinstance(resultado_validacao, (list, tuple, set)):
            return len(resultado_validacao) == 0
        return bool(resultado_validacao)
    except Exception:
        return False


def _normalizar_nome_coluna(nome) -> str:
    try:
        return str(nome).strip().lower()
    except Exception:
        return ""


def _is_coluna_imagem(nome) -> bool:
    nome = _normalizar_nome_coluna(nome)

    candidatos_exatos = {
        "url da imagem",
        "url imagem",
        "url imagens",
        "url das imagens",
        "url de imagem",
        "url de imagens",
        "imagem",
        "imagens",
        "imagem externa",
        "imagens externas",
        "url imagens externas",
        "url da imagem principal",
        "fotos",
        "foto",
    }

    if nome in candidatos_exatos:
        return True

    if "imagem" in nome or "imagens" in nome:
        return True

    if "image" in nome or "images" in nome:
        return True

    if "foto" in nome or "fotos" in nome:
        return True

    return False


def _sanitizar_texto(valor) -> str:
    try:
        if valor is None:
            return ""
        texto = str(valor).strip()
        if texto.lower() in {"nan", "none", "<na>"}:
            return ""
        return texto
    except Exception:
        return ""


def _extrair_urls_do_texto(texto: str) -> list[str]:
    try:
        texto = _sanitizar_texto(texto)
        if not texto:
            return []

        # Extrai URLs completas sem engolir o próximo separador
        urls = re.findall(r"https?://[^\s|,;\n\r]+", texto, flags=re.IGNORECASE)

        resultado: list[str] = []
        vistos: set[str] = set()

        for url in urls:
            url = _sanitizar_texto(url)
            if not url:
                continue
            if url in vistos:
                continue
            vistos.add(url)
            resultado.append(url)

        return resultado
    except Exception:
        return []


def _normalizar_urls_imagem(valor) -> str:
    try:
        if valor is None:
            return ""

        if isinstance(valor, (list, tuple, set)):
            partes_finais: list[str] = []
            vistos: set[str] = set()

            for item in valor:
                item_txt = _sanitizar_texto(item)
                if not item_txt:
                    continue

                urls_item = _extrair_urls_do_texto(item_txt)
                if urls_item:
                    for url in urls_item:
                        if url not in vistos:
                            vistos.add(url)
                            partes_finais.append(url)
                else:
                    if item_txt not in vistos:
                        vistos.add(item_txt)
                        partes_finais.append(item_txt)

            return "|".join(partes_finais)

        texto = _sanitizar_texto(valor)
        if not texto:
            return ""

        # Já veio no padrão correto
        if "|" in texto:
            partes = [_sanitizar_texto(p) for p in texto.split("|")]
            partes = [p for p in partes if p]

            partes_unicas: list[str] = []
            vistos: set[str] = set()

            for parte in partes:
                if parte not in vistos:
                    vistos.add(parte)
                    partes_unicas.append(parte)

            return "|".join(partes_unicas)

        # Se houver múltiplas URLs explícitas no mesmo texto, força pipe
        urls = _extrair_urls_do_texto(texto)
        if len(urls) >= 2:
            return "|".join(urls)

        # Fallback para textos separados por vírgula, ; ou quebra de linha
        if any(sep in texto for sep in [",", ";", "\n", "\r"]):
            partes = re.split(r"[,\n\r;]+", texto)
            partes = [_sanitizar_texto(p) for p in partes]
            partes = [p for p in partes if p]

            if len(partes) >= 2:
                partes_unicas: list[str] = []
                vistos: set[str] = set()

                for parte in partes:
                    if parte not in vistos:
                        vistos.add(parte)
                        partes_unicas.append(parte)

                return "|".join(partes_unicas)

        return texto
    except Exception:
        return _sanitizar_texto(valor)


def _blindar_colunas_imagem(df: pd.DataFrame) -> pd.DataFrame:
    try:
        if not _safe_df(df):
            return df

        df = df.copy()
        colunas_imagem = [col for col in df.columns if _is_coluna_imagem(col)]

        if not colunas_imagem:
            return df

        for col in colunas_imagem:
            try:
                df[col] = df[col].apply(_normalizar_urls_imagem)
            except Exception as e:
                log_debug(f"Erro ao normalizar coluna de imagem '{col}': {e}", "ERRO")

        try:
            log_debug(
                f"Blindagem de imagens aplicada em {len(colunas_imagem)} coluna(s): {', '.join(map(str, colunas_imagem))}"
            )
        except Exception:
            pass

        return df
    except Exception as e:
        log_debug(f"Erro geral na blindagem de colunas de imagem: {e}", "ERRO")
        return df


def render_preview_final() -> None:
    st.subheader("Preview final")

    df_fluxo = _get_df_fluxo()
    if not _safe_df(df_fluxo):
        st.warning("Nenhum dado disponível para o preview final.")
        log_debug("Preview final sem DataFrame disponível", "ERRO")
        return

    try:
        log_debug(
            f"Preview final carregado com {len(df_fluxo)} linha(s) e {len(df_fluxo.columns)} coluna(s)"
        )
    except Exception:
        pass

    try:
        # Blindagem extra antes de qualquer preview/export final
        df_fluxo = _blindar_colunas_imagem(df_fluxo.copy())
    except Exception as e:
        log_debug(f"Erro ao aplicar blindagem extra de imagens no preview final: {e}", "ERRO")

    with st.expander("Ver dados finais", expanded=False):
        st.dataframe(df_fluxo.head(20), use_container_width=True)

    try:
        df_download = limpar_gtin_invalido(df_fluxo.copy())
    except Exception as e:
        log_debug(f"Erro ao limpar GTIN inválido no preview final: {e}", "ERRO")
        df_download = df_fluxo.copy()

    try:
        # Blindagem final também no dataframe de download, após outras limpezas
        df_download = _blindar_colunas_imagem(df_download.copy())
    except Exception as e:
        log_debug(f"Erro ao reforçar blindagem de imagens no dataframe de download: {e}", "ERRO")

    try:
        validacao_ok = _normalizar_validacao(validar_campos_obrigatorios(df_download))
    except Exception as e:
        log_debug(f"Erro na validação de campos obrigatórios: {e}", "ERRO")
        validacao_ok = False

    if not validacao_ok:
        st.error("Preencha os campos obrigatórios antes do download.")
        return

    try:
        excel_bytes = exportar_excel_bytes(df_download)
    except Exception as e:
        log_debug(f"Erro ao gerar Excel final: {e}", "ERRO")
        st.error("Não foi possível gerar a planilha final.")
        return

    if not excel_bytes:
        st.error("Não foi possível gerar a planilha final.")
        return

    st.download_button(
        "⬇️ Baixar planilha final",
        excel_bytes,
        "bling_final.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

    col1, col2 = st.columns(2)

    with col1:
        if st.button(
            "⬅️ Voltar para mapeamento",
            use_container_width=True,
            key="btn_voltar_mapeamento_preview",
        ):
            st.session_state["etapa_origem"] = "mapeamento"
            st.session_state["etapa"] = "mapeamento"
            st.session_state["etapa_fluxo"] = "mapeamento"
            st.rerun()

    with col2:
        if st.button(
            "Atualizar preview",
            use_container_width=True,
            key="btn_atualizar_preview_final",
        ):
            st.session_state["df_final"] = df_fluxo.copy()
            st.rerun()
