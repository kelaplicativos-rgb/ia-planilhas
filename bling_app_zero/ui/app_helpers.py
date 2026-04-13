from __future__ import annotations

import csv
from datetime import datetime
from io import BytesIO
from typing import Any

import pandas as pd
import streamlit as st


ETAPAS_VALIDAS_ORIGEM = {"conexao", "origem", "mapeamento", "final", "envio"}


# ==========================================================
# IMPORTS OPCIONAIS
# ==========================================================
try:
    from bling_app_zero.ui.bling_panel import render_bling_panel as _render_bling_panel_real
except Exception:
    _render_bling_panel_real = None

try:
    from bling_app_zero.utils.gtin import aplicar_validacao_gtin_em_colunas_automaticas
except Exception:
    aplicar_validacao_gtin_em_colunas_automaticas = None


# ==========================================================
# ESTADO / LOG
# ==========================================================
def garantir_estado_base() -> None:
    try:
        if "logs" not in st.session_state or not isinstance(st.session_state.get("logs"), list):
            st.session_state["logs"] = []

        etapa_origem = str(st.session_state.get("etapa_origem") or "").strip().lower()
        if etapa_origem not in ETAPAS_VALIDAS_ORIGEM:
            etapa_origem = "conexao"

        etapa = str(st.session_state.get("etapa") or "").strip().lower()
        if etapa not in ETAPAS_VALIDAS_ORIGEM:
            etapa = etapa_origem

        etapa_fluxo = str(st.session_state.get("etapa_fluxo") or "").strip().lower()
        if etapa_fluxo not in ETAPAS_VALIDAS_ORIGEM:
            etapa_fluxo = etapa_origem

        st.session_state["etapa_origem"] = etapa_origem
        st.session_state["etapa"] = etapa
        st.session_state["etapa_fluxo"] = etapa_fluxo

        if "area_app" not in st.session_state:
            st.session_state["area_app"] = "Fluxo principal"

        if "debug_open" not in st.session_state:
            st.session_state["debug_open"] = False

        if "preview_final_valido" not in st.session_state:
            st.session_state["preview_final_valido"] = True

        if "campos_obrigatorios_faltantes" not in st.session_state:
            st.session_state["campos_obrigatorios_faltantes"] = []

        if "campos_obrigatorios_alertas" not in st.session_state:
            st.session_state["campos_obrigatorios_alertas"] = []

        if "gtin_modo_valor" not in st.session_state:
            st.session_state["gtin_modo_valor"] = "limpar"

        if "gtin_modo_label" not in st.session_state:
            st.session_state["gtin_modo_label"] = "Deixar vazio"

    except Exception:
        st.session_state["logs"] = []
        st.session_state["etapa_origem"] = "conexao"
        st.session_state["etapa"] = "conexao"
        st.session_state["etapa_fluxo"] = "conexao"
        st.session_state["area_app"] = "Fluxo principal"
        st.session_state["debug_open"] = False
        st.session_state["preview_final_valido"] = True
        st.session_state["campos_obrigatorios_faltantes"] = []
        st.session_state["campos_obrigatorios_alertas"] = []
        st.session_state["gtin_modo_valor"] = "limpar"
        st.session_state["gtin_modo_label"] = "Deixar vazio"


def log_debug(msg: str, nivel: str = "INFO") -> None:
    try:
        if "logs" not in st.session_state or not isinstance(st.session_state.get("logs"), list):
            st.session_state["logs"] = []

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        linha = f"[{timestamp}] [{nivel}] {msg}"
        st.session_state["logs"].append(linha)
    except Exception:
        pass


# ==========================================================
# DEBUG PANEL
# ==========================================================
def render_debug_panel() -> None:
    try:
        garantir_estado_base()

        with st.sidebar:
            st.markdown("---")
            st.caption("Debug do sistema")

            debug_aberto = bool(st.session_state.get("debug_open", False))

            if st.button(
                "📋 Log debug" if not debug_aberto else "❌ Fechar log debug",
                key="btn_toggle_debug_global",
                use_container_width=True,
            ):
                st.session_state["debug_open"] = not debug_aberto
                st.rerun()

            if st.session_state.get("debug_open", False):
                st.text_input(
                    "Área",
                    value=str(st.session_state.get("area_app", "")),
                    disabled=True,
                )
                st.text_input(
                    "Etapa origem",
                    value=str(st.session_state.get("etapa_origem", "")),
                    disabled=True,
                )
                st.text_input(
                    "Etapa",
                    value=str(st.session_state.get("etapa", "")),
                    disabled=True,
                )
                st.text_input(
                    "Etapa fluxo",
                    value=str(st.session_state.get("etapa_fluxo", "")),
                    disabled=True,
                )

                logs = st.session_state.get("logs", [])
                conteudo_logs = "\n".join(str(l) for l in logs[-300:]) if logs else "Sem logs no momento."

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
# HELPERS DF
# ==========================================================
def _safe_df(df: Any) -> bool:
    try:
        return isinstance(df, pd.DataFrame) and len(df.columns) > 0 and not df.empty
    except Exception:
        return False


def safe_df_from_state(key: str) -> pd.DataFrame | None:
    try:
        df = st.session_state.get(key)
        if isinstance(df, pd.DataFrame) and len(df.columns) > 0:
            return df.copy()
    except Exception:
        pass
    return None


def get_df_fluxo() -> pd.DataFrame | None:
    for key in [
        "df_final",
        "df_saida",
        "df_dados",
        "df_base",
        "df_precificado",
        "df_calc_precificado",
        "df_origem",
    ]:
        df = safe_df_from_state(key)
        if df is not None:
            return df
    return None


def sincronizar_df_final() -> None:
    try:
        df_fluxo = get_df_fluxo()
        if df_fluxo is not None:
            st.session_state["df_final"] = df_fluxo.copy()
    except Exception:
        pass


def _safe_str(valor: Any) -> str:
    try:
        return str(valor or "").strip()
    except Exception:
        return ""


def _normalizar_coluna(nome: Any) -> str:
    return _safe_str(nome).lower()


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

    try:
        tem_gtin = any(
            "gtin" in _normalizar_coluna(col) or "ean" in _normalizar_coluna(col)
            for col in df.columns
        )
        if not tem_gtin:
            return df

        modo = _safe_str(st.session_state.get("gtin_modo_valor") or "limpar").lower()

        df_tratado, logs = aplicar_validacao_gtin_em_colunas_automaticas(
            df.copy(),
            preservar_coluna_original=False,
            modo=modo,
            tamanho_gerado=13,
        )

        if isinstance(logs, list):
            for linha in logs[:50]:
                log_debug(str(linha), "INFO")

        return df_tratado
    except Exception as e:
        log_debug(f"Falha GTIN: {e}", "ERROR")
        return df


# ==========================================================
# VALIDAÇÃO
# ==========================================================
def validar_campos_obrigatorios(df: pd.DataFrame) -> bool:
    try:
        if not isinstance(df, pd.DataFrame) or df.empty:
            st.session_state["preview_final_valido"] = False
            st.session_state["campos_obrigatorios_faltantes"] = ["DataFrame vazio"]
            st.session_state["campos_obrigatorios_alertas"] = [
                "Nenhum dado disponível para validar."
            ]
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

            serie = df[col_encontrada].replace({None: ""}).fillna("").astype(str).str.strip()
            if serie.eq("").all():
                faltantes.append(nome_campo)
                alertas.append(f"Coluna obrigatória sem dados: {col_encontrada}")

        st.session_state["campos_obrigatorios_faltantes"] = faltantes
        st.session_state["campos_obrigatorios_alertas"] = alertas
        st.session_state["preview_final_valido"] = len(faltantes) == 0

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
def _sanitizar_df_para_csv(df: pd.DataFrame) -> pd.DataFrame:
    try:
        df = df.copy()

        for col in df.columns:
            if pd.api.types.is_object_dtype(df[col]) or pd.api.types.is_string_dtype(df[col]):
                df[col] = (
                    df[col]
                    .replace({None: ""})
                    .fillna("")
                    .astype(str)
                    .str.replace("\ufeff", "", regex=False)
                    .str.replace("\x00", "", regex=False)
                    .str.replace("\r\n", " ", regex=False)
                    .str.replace("\r", " ", regex=False)
                    .str.replace("\n", " ", regex=False)
                    .str.strip()
                )

        return df
    except Exception as e:
        log_debug(f"Erro ao sanitizar DataFrame para CSV: {e}", "ERROR")
        return df


def blindar_df_para_download(df: pd.DataFrame) -> pd.DataFrame:
    try:
        if not isinstance(df, pd.DataFrame):
            return pd.DataFrame()

        df_blindado = df.copy()
        df_blindado = _aplicar_tratamento_gtin(df_blindado)
        df_blindado = limpar_gtin_invalido(df_blindado)
        df_blindado = df_blindado.replace({None: ""}).fillna("")
        df_blindado = _sanitizar_df_para_csv(df_blindado)

        return df_blindado
    except Exception as e:
        log_debug(f"Erro em blindar_df_para_download: {e}", "ERROR")
        if isinstance(df, pd.DataFrame):
            return df.copy()
        return pd.DataFrame()


def exportar_excel_bytes(df: pd.DataFrame) -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)
    output.seek(0)
    return output.getvalue()


def exportar_csv_bytes(df: pd.DataFrame) -> bytes:
    try:
        df_download = blindar_df_para_download(df)

        if not isinstance(df_download, pd.DataFrame) or len(df_download.columns) == 0:
            return b""

        csv_texto = df_download.to_csv(
            index=False,
            sep=";",
            encoding="utf-8-sig",
            lineterminator="\r\n",
            quoting=csv.QUOTE_MINIMAL,
        )

        return csv_texto.encode("utf-8-sig")
    except Exception as e:
        log_debug(f"Erro ao exportar CSV: {e}", "ERROR")
        return b""


def gerar_nome_arquivo_download() -> str:
    tipo_operacao = _safe_str(st.session_state.get("tipo_operacao_bling")).lower()

    if tipo_operacao == "estoque":
        return "bling_export_estoque.csv"

    if tipo_operacao == "cadastro":
        return "bling_export_cadastro.csv"

    return "bling_export.csv"


# ==========================================================
# BLING PANEL
# ==========================================================
def render_bling_panel() -> None:
    if callable(_render_bling_panel_real):
        try:
            _render_bling_panel_real()
            return
        except Exception as e:
            log_debug(f"Erro ao renderizar painel do Bling: {e}", "ERROR")

    st.info("Painel do Bling indisponível no momento.")


# ==========================================================
# PREVIEW FINAL
# ==========================================================
def render_preview_final() -> None:
    sincronizar_df_final()

    df = get_df_fluxo()
    if df is None:
        st.warning("Nenhum dado disponível.")
        return

    df_final = blindar_df_para_download(df.copy())

    st.session_state["df_final"] = df_final.copy()
    st.session_state["df_saida"] = df_final.copy()

    st.subheader("Preview final")
    st.dataframe(df_final.head(20), use_container_width=True)

    col_voltar, col_download = st.columns([1, 3])

    with col_voltar:
        if st.button("⬅️ Voltar", use_container_width=True):
            st.session_state["etapa_origem"] = "mapeamento"
            st.session_state["etapa"] = "mapeamento"
            st.session_state["etapa_fluxo"] = "mapeamento"
            st.rerun()

    csv_bytes = None
    try:
        csv_bytes = exportar_csv_bytes(df_final)
        if not csv_bytes:
            raise ValueError("Arquivo CSV vazio")
    except Exception as e:
        log_debug(f"Erro download CSV: {e}", "ERROR")
        st.error(f"Erro ao gerar arquivo CSV: {e}")

    with col_download:
        st.download_button(
            "⬇️ Baixar planilha",
            data=csv_bytes,
            file_name=gerar_nome_arquivo_download(),
            mime="text/csv",
            use_container_width=True,
            disabled=(csv_bytes is None),
            key="btn_download_planilha_final_csv",
        )

    render_bling_panel()
