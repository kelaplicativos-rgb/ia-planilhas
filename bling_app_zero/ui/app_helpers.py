from __future__ import annotations

from datetime import datetime
from io import BytesIO
from typing import Any

import pandas as pd
import streamlit as st

# ==========================================================
# BLING PANEL (BLINDADO)
# ==========================================================
try:
    from bling_app_zero.ui.bling_panel import render_bling_panel
except Exception:
    def render_bling_panel():
        st.warning("Painel do Bling indisponível no momento.")


# ==========================================================
# IMPORTS OPCIONAIS / BLINDAGEM
# ==========================================================
try:
    from bling_app_zero.utils.excel import (
        exportar_dataframe_para_excel as _exportar_excel_robusto,
    )
except Exception:
    _exportar_excel_robusto = None

try:
    from bling_app_zero.utils.excel import (
        df_to_excel_bytes as _df_to_excel_bytes_utils,
    )
except Exception:
    _df_to_excel_bytes_utils = None

try:
    from bling_app_zero.utils.excel import (
        exportar_excel_com_modelo as _exportar_excel_com_modelo,
    )
except Exception:
    _exportar_excel_com_modelo = None

try:
    from bling_app_zero.utils.gtin import aplicar_validacao_gtin_em_colunas_automaticas
except Exception:
    aplicar_validacao_gtin_em_colunas_automaticas = None


ETAPAS_VALIDAS_ORIGEM = {"origem", "mapeamento", "final", "envio"}


# ==========================================================
# ESTADO / LOG
# ==========================================================
def garantir_estado_base() -> None:
    try:
        if "logs" not in st.session_state or not isinstance(
            st.session_state.get("logs"), list
        ):
            st.session_state["logs"] = []

        etapa_atual = str(st.session_state.get("etapa_origem", "") or "").strip().lower()

        if etapa_atual not in ETAPAS_VALIDAS_ORIGEM:
            st.session_state["etapa_origem"] = "origem"

        if "etapa" not in st.session_state:
            st.session_state["etapa"] = st.session_state.get("etapa_origem", "origem")

        if "etapa_fluxo" not in st.session_state:
            st.session_state["etapa_fluxo"] = st.session_state.get("etapa_origem", "origem")

        if "area_app" not in st.session_state:
            st.session_state["area_app"] = "Fluxo principal"

        if "bloquear_campos_auto" not in st.session_state:
            st.session_state["bloquear_campos_auto"] = {}

        if "gtin_modo_valor" not in st.session_state:
            st.session_state["gtin_modo_valor"] = "limpar"

        if "gtin_modo_label" not in st.session_state:
            st.session_state["gtin_modo_label"] = "Deixar vazio"

        if "preview_final_valido" not in st.session_state:
            st.session_state["preview_final_valido"] = True

        if "campos_obrigatorios_faltantes" not in st.session_state:
            st.session_state["campos_obrigatorios_faltantes"] = []

        if "campos_obrigatorios_alertas" not in st.session_state:
            st.session_state["campos_obrigatorios_alertas"] = []

        if "debug_open" not in st.session_state:
            st.session_state["debug_open"] = False

    except Exception:
        st.session_state["logs"] = []
        st.session_state["etapa_origem"] = "origem"
        st.session_state["etapa"] = "origem"
        st.session_state["etapa_fluxo"] = "origem"
        st.session_state["area_app"] = "Fluxo principal"
        st.session_state["bloquear_campos_auto"] = {}
        st.session_state["gtin_modo_valor"] = "limpar"
        st.session_state["gtin_modo_label"] = "Deixar vazio"
        st.session_state["preview_final_valido"] = True
        st.session_state["campos_obrigatorios_faltantes"] = []
        st.session_state["campos_obrigatorios_alertas"] = []
        st.session_state["debug_open"] = False


def log_debug(msg: str, nivel: str = "INFO") -> None:
    try:
        if "logs" not in st.session_state:
            st.session_state["logs"] = []

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        linha = f"[{timestamp}] [{nivel}] {msg}"
        st.session_state["logs"].append(linha)
    except Exception:
        pass


# ==========================================================
# PAINEL DEBUG FIXO
# ==========================================================
def render_debug_panel() -> None:
    try:
        garantir_estado_base()

        with st.sidebar:
            st.markdown("---")
            st.caption("Debug do sistema")

            debug_aberto = bool(st.session_state.get("debug_open", False))

            if st.button(
                "🪵 Log debug" if not debug_aberto else "❌ Fechar log debug",
                key="btn_toggle_debug_global",
                use_container_width=True,
            ):
                st.session_state["debug_open"] = not debug_aberto
                st.rerun()

            if st.session_state.get("debug_open", False):
                etapa_origem = st.session_state.get("etapa_origem", "")
                etapa = st.session_state.get("etapa", "")
                etapa_fluxo = st.session_state.get("etapa_fluxo", "")
                area_app = st.session_state.get("area_app", "")

                st.text_input("Área", value=str(area_app), disabled=True)
                st.text_input("Etapa origem", value=str(etapa_origem), disabled=True)
                st.text_input("Etapa", value=str(etapa), disabled=True)
                st.text_input("Etapa fluxo", value=str(etapa_fluxo), disabled=True)

                logs = st.session_state.get("logs", [])
                if isinstance(logs, list) and logs:
                    conteudo_logs = "\n".join(str(l) for l in logs[-300:])
                else:
                    conteudo_logs = "Sem logs no momento."

                st.text_area(
                    "Logs",
                    value=conteudo_logs,
                    height=320,
                    disabled=True,
                    key="debug_logs_area",
                )

                col1, col2 = st.columns(2)

                with col1:
                    if st.button(
                        "🧹 Limpar logs",
                        key="btn_limpar_logs_global",
                        use_container_width=True,
                    ):
                        st.session_state["logs"] = []
                        log_debug("Logs limpos manualmente.", "INFO")
                        st.rerun()

                with col2:
                    st.download_button(
                        "⬇️ Baixar log",
                        data=conteudo_logs.encode("utf-8"),
                        file_name="log_debug_bling.txt",
                        mime="text/plain",
                        key="btn_baixar_logs_global",
                        use_container_width=True,
                    )

    except Exception as e:
        try:
            st.sidebar.warning(f"Debug indisponível: {e}")
        except Exception:
            pass


# ==========================================================
# HELPERS
# ==========================================================
def safe_df_from_state(key: str) -> pd.DataFrame | None:
    df = st.session_state.get(key)
    if isinstance(df, pd.DataFrame) and len(df.columns) > 0:
        return df.copy()
    return None


def get_df_fluxo() -> pd.DataFrame | None:
    for key in ["df_final", "df_saida", "df_dados", "df_base"]:
        df = safe_df_from_state(key)
        if df is not None:
            return df
    return None


def sincronizar_df_final() -> None:
    df_fluxo = get_df_fluxo()
    if df_fluxo is not None:
        st.session_state["df_final"] = df_fluxo.copy()


def _safe_str(valor: Any) -> str:
    try:
        return str(valor or "").strip()
    except Exception:
        return ""


def _normalizar_coluna(nome: Any) -> str:
    return _safe_str(nome).lower()


def _tem_coluna_gtin(df: pd.DataFrame) -> bool:
    return any(
        "gtin" in _normalizar_coluna(col) or "ean" in _normalizar_coluna(col)
        for col in df.columns
    )


# ==========================================================
# GTIN
# ==========================================================
def _validar_gtin(valor: Any) -> str:
    try:
        if valor is None:
            return ""

        valor = str(valor).strip()

        if not valor or valor.lower() in {"none", "nan"}:
            return ""

        if not valor.isdigit():
            return ""

        if len(valor) not in {8, 12, 13, 14}:
            return ""

        return valor
    except Exception:
        return ""


def limpar_gtin_invalido(df: pd.DataFrame) -> pd.DataFrame:
    try:
        df = df.copy()

        for col in df.columns:
            nome = _normalizar_coluna(col)
            if "gtin" in nome or "ean" in nome:
                df[col] = df[col].apply(_validar_gtin)

        return df

    except Exception as e:
        log_debug(f"Erro limpar GTIN: {e}", "ERROR")
        return df


def _aplicar_tratamento_gtin(df: pd.DataFrame) -> pd.DataFrame:
    if aplicar_validacao_gtin_em_colunas_automaticas is None:
        return df

    if not _tem_coluna_gtin(df):
        return df

    try:
        modo = _safe_str(st.session_state.get("gtin_modo_valor") or "limpar").lower()

        df_tratado, logs = aplicar_validacao_gtin_em_colunas_automaticas(
            df.copy(),
            preservar_coluna_original=False,
            modo=modo,
            tamanho_gerado=13,
        )

        for linha in logs[:50]:
            log_debug(linha, "INFO")

        return df_tratado

    except Exception as e:
        log_debug(f"Falha GTIN: {e}", "ERROR")
        return df


# ==========================================================
# VALIDAÇÃO
# ==========================================================
def validar_campos_obrigatorios(df: pd.DataFrame):
    try:
        if not isinstance(df, pd.DataFrame) or df.empty:
            st.session_state["preview_final_valido"] = False
            st.session_state["campos_obrigatorios_faltantes"] = ["DataFrame vazio"]
            st.session_state["campos_obrigatorios_alertas"] = ["Nenhum dado disponível para validar."]
            return False

        faltantes: list[str] = []
        alertas: list[str] = []

        candidatos = {
            "Descrição": ["descrição", "descricao"],
        }

        colunas_normalizadas = {str(col): _normalizar_coluna(col) for col in df.columns}

        for nome_campo, aliases in candidatos.items():
            col_encontrada = None

            for col_real, col_norm in colunas_normalizadas.items():
                if any(alias in col_norm for alias in aliases):
                    col_encontrada = col_real
                    break

            if col_encontrada is None:
                faltantes.append(nome_campo)
                alertas.append(f"Coluna obrigatória ausente: {nome_campo}")
                continue

            serie = df[col_encontrada].copy()
            serie = serie.replace({None: ""}).fillna("").astype(str).str.strip()

            if serie.eq("").all():
                faltantes.append(nome_campo)
                alertas.append(f"Coluna obrigatória sem dados: {col_encontrada}")

        st.session_state["campos_obrigatorios_faltantes"] = faltantes
        st.session_state["campos_obrigatorios_alertas"] = alertas
        st.session_state["preview_final_valido"] = len(faltantes) == 0

        if alertas:
            for alerta in alertas:
                log_debug(alerta, "WARNING")

        return len(faltantes) == 0

    except Exception as e:
        log_debug(f"Erro validar campos obrigatórios: {e}", "ERROR")
        st.session_state["preview_final_valido"] = False
        st.session_state["campos_obrigatorios_faltantes"] = ["Erro na validação"]
        st.session_state["campos_obrigatorios_alertas"] = [str(e)]
        return False


# ==========================================================
# EXPORTAÇÃO
# ==========================================================
def _exportar_excel_fallback(df: pd.DataFrame) -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)
    output.seek(0)
    return output.getvalue()


def exportar_excel_bytes(df: pd.DataFrame) -> bytes:
    if _df_to_excel_bytes_utils:
        try:
            return _df_to_excel_bytes_utils(df)
        except Exception:
            pass

    if _exportar_excel_robusto:
        try:
            return _exportar_excel_robusto(df)
        except Exception:
            pass

    return _exportar_excel_fallback(df)


def exportar_download_bytes(df: pd.DataFrame) -> bytes:
    try:
        df_modelo = st.session_state.get("df_modelo_cadastro")
        if not isinstance(df_modelo, pd.DataFrame):
            df_modelo = st.session_state.get("df_modelo_estoque")

        if _exportar_excel_com_modelo and isinstance(df_modelo, pd.DataFrame):
            return _exportar_excel_com_modelo(df, df_modelo)

        return exportar_excel_bytes(df)

    except Exception:
        return exportar_excel_bytes(df)


# ==========================================================
# PREVIEW FINAL
# ==========================================================
def render_preview_final() -> None:
    sincronizar_df_final()
    df = get_df_fluxo()

    if df is None:
        st.warning("Nenhum dado disponível.")
        return

    df_final = _aplicar_tratamento_gtin(df.copy())
    df_final = limpar_gtin_invalido(df_final)

    st.session_state["df_final"] = df_final.copy()
    st.session_state["df_saida"] = df_final.copy()

    st.subheader("Preview final")
    st.dataframe(df_final.head(20), use_container_width=True)

    col_voltar, col_download = st.columns([1, 3])

    with col_voltar:
        if st.button("⬅️ Voltar", use_container_width=True):
            st.session_state["etapa_origem"] = "mapeamento"
            st.rerun()

    excel_bytes = None

    try:
        excel_bytes = exportar_download_bytes(df_final)
        if not excel_bytes:
            raise ValueError("Arquivo vazio")
    except Exception as e:
        log_debug(f"Erro download: {e}", "ERROR")
        st.error(f"Erro ao gerar arquivo: {e}")

    with col_download:
        st.download_button(
            "⬇️ Baixar planilha",
            data=excel_bytes,
            file_name="bling_export.xlsx",
            use_container_width=True,
            disabled=(excel_bytes is None),
        )

    render_bling_panel()
