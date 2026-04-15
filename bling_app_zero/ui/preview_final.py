from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.ui.app_helpers import (
    blindar_df_para_download,
    exportar_csv_bytes,
    gerar_nome_arquivo_download,
    log_debug,
    validar_campos_obrigatorios,
)


# =========================================================
# HELPERS BASE
# =========================================================
def _safe_df(df) -> bool:
    try:
        return isinstance(df, pd.DataFrame) and not df.empty and len(df.columns) > 0
    except Exception:
        return False


def _safe_copy_df(df):
    try:
        return df.copy()
    except Exception:
        return df


def _safe_str(valor) -> str:
    try:
        if valor is None:
            return ""
        texto = str(valor).strip()
        if texto.lower() in {"none", "nan", "nat"}:
            return ""
        return texto
    except Exception:
        return ""


def _get_df_fluxo() -> pd.DataFrame | None:
    for chave in ["df_final", "df_saida", "df_precificado", "df_calc_precificado", "df_origem"]:
        df = st.session_state.get(chave)
        if _safe_df(df):
            try:
                log_debug(f"[PREVIEW_FINAL] usando DataFrame de '{chave}'", "INFO")
            except Exception:
                pass
            return _safe_copy_df(df)
    return None


def _normalizar_validacao(resultado_validacao) -> tuple[bool, list[str]]:
    try:
        if isinstance(resultado_validacao, bool):
            return resultado_validacao, []

        if resultado_validacao is None:
            return True, []

        if isinstance(resultado_validacao, dict):
            ok = bool(resultado_validacao.get("ok"))
            erros = list(
                resultado_validacao.get("alertas")
                or resultado_validacao.get("faltantes")
                or []
            )
            return ok, [str(item) for item in erros if str(item).strip()]

        if isinstance(resultado_validacao, (list, tuple, set)):
            erros = [str(item) for item in resultado_validacao if str(item).strip()]
            return len(erros) == 0, erros

        return bool(resultado_validacao), []
    except Exception:
        return False, ["Falha ao interpretar a validação dos campos obrigatórios."]


def _persistir_df_final(df_final: pd.DataFrame) -> None:
    try:
        st.session_state["df_final"] = df_final.copy()
    except Exception:
        st.session_state["df_final"] = df_final

    try:
        st.session_state["df_saida"] = df_final.copy()
    except Exception:
        st.session_state["df_saida"] = df_final


def _blindar_df_final(df_base: pd.DataFrame) -> pd.DataFrame:
    try:
        df_blindado = blindar_df_para_download(df_base.copy())
        _persistir_df_final(df_blindado)
        return df_blindado
    except Exception as e:
        log_debug(f"[PREVIEW_FINAL] erro na blindagem do DataFrame final: {e}", "ERROR")
        return _safe_copy_df(df_base)


# =========================================================
# HELPERS VISUAIS
# =========================================================
def _inject_css_preview_final() -> None:
    st.markdown(
        """
        <style>
        .final-topo-card {
            border: 1px solid rgba(128,128,128,0.16);
            border-radius: 18px;
            padding: 14px 16px;
            margin-bottom: 14px;
            background: rgba(255,255,255,0.02);
        }

        .final-kicker {
            font-size: 0.78rem;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            opacity: 0.72;
            font-weight: 700;
            margin-bottom: 6px;
        }

        .final-titulo {
            font-size: 1.16rem;
            font-weight: 700;
            line-height: 1.15;
            margin-bottom: 6px;
        }

        .final-subtitulo {
            font-size: 0.93rem;
            opacity: 0.82;
            line-height: 1.3;
        }

        .final-resumo-box {
            border: 1px solid rgba(128,128,128,0.14);
            border-radius: 14px;
            padding: 12px 14px;
            background: rgba(255,255,255,0.015);
            min-height: 82px;
        }

        .final-resumo-label {
            font-size: 0.75rem;
            opacity: 0.72;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            margin-bottom: 6px;
        }

        .final-resumo-value {
            font-size: 1rem;
            font-weight: 700;
            line-height: 1.2;
        }

        .final-bloco {
            border: 1px solid rgba(128,128,128,0.14);
            border-radius: 16px;
            padding: 14px;
            margin-bottom: 14px;
            background: rgba(255,255,255,0.015);
        }

        .final-bloco-titulo {
            font-size: 0.98rem;
            font-weight: 700;
            margin-bottom: 6px;
        }

        .final-bloco-desc {
            font-size: 0.90rem;
            opacity: 0.82;
            line-height: 1.28;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_topo_visual() -> None:
    st.markdown(
        """
        <div class="final-topo-card">
            <div class="final-kicker">Etapa 3</div>
            <div class="final-titulo">Preview final e download</div>
            <div class="final-subtitulo">
                Revise a estrutura final, valide os campos obrigatórios e baixe o arquivo
                CSV já blindado para importação.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_resumo_fluxo_visual(df_download: pd.DataFrame) -> None:
    operacao = _safe_str(
        st.session_state.get("tipo_operacao")
        or st.session_state.get("tipo_operacao_bling")
        or st.session_state.get("tipo_operacao_radio")
    )

    origem = _safe_str(
        st.session_state.get("origem_dados_tipo")
        or st.session_state.get("origem_dados_radio")
    )

    total_linhas = 0
    total_colunas = 0
    if _safe_df(df_download):
        try:
            total_linhas = int(len(df_download))
            total_colunas = int(len(df_download.columns))
        except Exception:
            pass

    c1, c2, c3 = st.columns(3, gap="small")

    with c1:
        st.markdown(
            f"""
            <div class="final-resumo-box">
                <div class="final-resumo-label">Operação</div>
                <div class="final-resumo-value">{operacao or "Não definida"}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with c2:
        st.markdown(
            f"""
            <div class="final-resumo-box">
                <div class="final-resumo-label">Origem</div>
                <div class="final-resumo-value">{origem or "Não definida"}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with c3:
        st.markdown(
            f"""
            <div class="final-resumo-box">
                <div class="final-resumo-label">Saída final</div>
                <div class="final-resumo-value">{total_linhas} linha(s) · {total_colunas} coluna(s)</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _render_bloco_info(titulo: str, descricao: str) -> None:
    st.markdown(
        f"""
        <div class="final-bloco">
            <div class="final-bloco-titulo">{titulo}</div>
            <div class="final-bloco-desc">{descricao}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_erros_validacao(erros: list[str]) -> None:
    st.error("Preencha os campos obrigatórios antes do download.")
    if not erros:
        return

    with st.expander("Ver detalhes da validação", expanded=False):
        for erro in erros:
            st.write(f"- {erro}")


def _render_preview_tabela(df_download: pd.DataFrame) -> None:
    st.markdown("### Dados finais")
    with st.expander("Visualizar preview final", expanded=True):
        st.dataframe(df_download.head(20), use_container_width=True)


def _render_acoes_finais(df_download: pd.DataFrame) -> None:
    try:
        csv_bytes = exportar_csv_bytes(df_download)
    except Exception as e:
        log_debug(f"[PREVIEW_FINAL] erro ao gerar CSV final: {e}", "ERROR")
        st.error("Não foi possível gerar a planilha final em CSV.")
        return

    if not csv_bytes:
        log_debug("[PREVIEW_FINAL] CSV final vazio ou inválido.", "ERROR")
        st.error("Não foi possível gerar a planilha final em CSV.")
        return

    st.markdown("### Ações finais")
    col1, col2 = st.columns(2, gap="small")

    with col1:
        st.download_button(
            "⬇️ Baixar planilha final",
            csv_bytes,
            gerar_nome_arquivo_download(),
            mime="text/csv",
            use_container_width=True,
            key="btn_download_preview_final_csv",
        )

    with col2:
        if st.button(
            "🔄 Atualizar preview",
            use_container_width=True,
            key="btn_atualizar_preview_final",
        ):
            _persistir_df_final(df_download)
            log_debug("[PREVIEW_FINAL] atualização manual do preview final acionada.", "INFO")
            st.rerun()


# =========================================================
# RENDER PRINCIPAL
# =========================================================
def render_preview_final() -> None:
    _inject_css_preview_final()
    _render_topo_visual()

    df_fluxo = _get_df_fluxo()
    if not _safe_df(df_fluxo):
        st.warning("Nenhum dado disponível para o preview final.")
        log_debug("[PREVIEW_FINAL] nenhum DataFrame disponível para renderização.", "ERROR")
        return

    try:
        log_debug(
            f"[PREVIEW_FINAL] preview carregado com {len(df_fluxo)} linha(s) e "
            f"{len(df_fluxo.columns)} coluna(s).",
            "INFO",
        )
    except Exception:
        pass

    df_download = _blindar_df_final(df_fluxo)

    _render_resumo_fluxo_visual(df_download)
    _render_bloco_info(
        "O que acontece nesta etapa",
        "A base final é blindada novamente antes do download, validada nos campos "
        "obrigatórios e exportada em CSV.",
    )
    _render_preview_tabela(df_download)

    try:
        validacao_ok, erros_validacao = _normalizar_validacao(
            validar_campos_obrigatorios(df_download)
        )
    except Exception as e:
        log_debug(f"[PREVIEW_FINAL] erro na validação de campos obrigatórios: {e}", "ERROR")
        validacao_ok, erros_validacao = False, ["Falha ao validar os campos obrigatórios."]

    if not validacao_ok:
        _render_erros_validacao(erros_validacao)
        return

    df_download = _blindar_df_final(df_download)
    _render_acoes_finais(df_download)
