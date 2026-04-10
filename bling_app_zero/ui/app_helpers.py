from __future__ import annotations

from datetime import datetime
from io import BytesIO
from typing import Any

import pandas as pd
import streamlit as st

from bling_app_zero.core.modelos_bling import carregar_modelo_por_operacao

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
# HELPERS GERAIS
# ==========================================================
def _safe_str(valor: Any) -> str:
    try:
        texto = str(valor or "").strip()
        if texto.lower() in {"none", "nan", "<na>", "nat"}:
            return ""
        return texto
    except Exception:
        return ""


def _normalizar_coluna(nome: Any) -> str:
    return _safe_str(nome).lower()


def _sincronizar_etapa_global(etapa: str) -> str:
    etapa_norm = _safe_str(etapa).lower() or "origem"
    if etapa_norm not in ETAPAS_VALIDAS_ORIGEM:
        etapa_norm = "origem"

    st.session_state["etapa_origem"] = etapa_norm
    st.session_state["etapa"] = etapa_norm
    st.session_state["etapa_fluxo"] = etapa_norm
    return etapa_norm


def safe_df_from_state(key: str) -> pd.DataFrame | None:
    df = st.session_state.get(key)
    if isinstance(df, pd.DataFrame) and len(df.columns) > 0:
        return df.copy()
    return None


def _safe_df(df: Any) -> bool:
    try:
        return isinstance(df, pd.DataFrame) and len(df.columns) > 0
    except Exception:
        return False


def _safe_df_com_linhas(df: Any) -> bool:
    try:
        return isinstance(df, pd.DataFrame) and len(df.columns) > 0 and not df.empty
    except Exception:
        return False


# ==========================================================
# ESTADO / LOG
# ==========================================================
def garantir_estado_base() -> None:
    try:
        if "logs" not in st.session_state or not isinstance(st.session_state.get("logs"), list):
            st.session_state["logs"] = []

        etapa_atual = _safe_str(st.session_state.get("etapa_origem")).lower()
        if etapa_atual not in ETAPAS_VALIDAS_ORIGEM:
            etapa_atual = "origem"

        _sincronizar_etapa_global(etapa_atual)

        defaults = {
            "area_app": "Fluxo principal",
            "bloquear_campos_auto": {},
            "gtin_modo_valor": "limpar",
            "gtin_modo_label": "Deixar vazio",
            "preview_final_valido": True,
            "campos_obrigatorios_faltantes": [],
            "campos_obrigatorios_alertas": [],
            "debug_open": False,
        }

        for chave, valor in defaults.items():
            if chave not in st.session_state:
                st.session_state[chave] = valor
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
        if "logs" not in st.session_state or not isinstance(st.session_state.get("logs"), list):
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
                "📋 Log debug" if not debug_aberto else "❌ Fechar log debug",
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
# FLUXO / DF
# ==========================================================
def get_df_fluxo() -> pd.DataFrame | None:
    for key in ["df_final", "df_saida", "df_precificado", "df_calc_precificado", "df_dados", "df_base"]:
        df = safe_df_from_state(key)
        if df is not None:
            return df
    return None


def sincronizar_df_final() -> None:
    """
    Corrigido:
    - prioriza df_saida como base real do fluxo final;
    - só cai para outros DFs quando df_saida não existir.
    """
    df_saida = safe_df_from_state("df_saida")
    if df_saida is not None:
        st.session_state["df_final"] = df_saida.copy()
        return

    df_fluxo = get_df_fluxo()
    if df_fluxo is not None:
        st.session_state["df_final"] = df_fluxo.copy()


# ==========================================================
# GTIN
# ==========================================================
def _tem_coluna_gtin(df: pd.DataFrame) -> bool:
    return any(
        "gtin" in _normalizar_coluna(col) or "ean" in _normalizar_coluna(col)
        for col in df.columns
    )


def _validar_gtin(valor: Any) -> str:
    try:
        if valor is None:
            return ""

        texto = str(valor).strip()
        if not texto or texto.lower() in {"none", "nan"}:
            return ""

        if not texto.isdigit():
            return ""

        if len(texto) not in {8, 12, 13, 14}:
            return ""

        return texto
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


def _obter_modelo_exportacao() -> pd.DataFrame | None:
    try:
        tipo_operacao = _safe_str(st.session_state.get("tipo_operacao_bling")).lower()

        if tipo_operacao in {"cadastro", "estoque"}:
            state_key = "df_modelo_cadastro" if tipo_operacao == "cadastro" else "df_modelo_estoque"
            df_modelo = st.session_state.get(state_key)

            if isinstance(df_modelo, pd.DataFrame) and len(df_modelo.columns) > 0:
                return df_modelo.copy()

            df_modelo = carregar_modelo_por_operacao(tipo_operacao)
            if isinstance(df_modelo, pd.DataFrame) and len(df_modelo.columns) > 0:
                st.session_state[state_key] = df_modelo.copy()
                return df_modelo.copy()

        for fallback_key in ["df_modelo_cadastro", "df_modelo_estoque"]:
            df_modelo = st.session_state.get(fallback_key)
            if isinstance(df_modelo, pd.DataFrame) and len(df_modelo.columns) > 0:
                return df_modelo.copy()

        return None
    except Exception as e:
        log_debug(f"Erro ao obter modelo de exportação: {e}", "ERROR")
        return None


def exportar_download_bytes(df: pd.DataFrame) -> bytes:
    try:
        df_modelo = _obter_modelo_exportacao()

        if _exportar_excel_com_modelo and isinstance(df_modelo, pd.DataFrame):
            return _exportar_excel_com_modelo(df, df_modelo)

        return exportar_excel_bytes(df)
    except Exception as e:
        log_debug(f"Erro exportar_download_bytes: {e}", "ERROR")
        return exportar_excel_bytes(df)


# ==========================================================
# PREVIEW FINAL
# ==========================================================
def _render_alertas_preview() -> None:
    alertas = st.session_state.get("campos_obrigatorios_alertas", [])
    if isinstance(alertas, list):
        for alerta in alertas:
            st.warning(str(alerta))


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

    validar_campos_obrigatorios(df_final)

    st.subheader("Preview final")
    _render_alertas_preview()
    st.dataframe(df_final.head(20), use_container_width=True)

    col_voltar, col_download = st.columns([1, 3])

    with col_voltar:
        if st.button("⬅️ Voltar", use_container_width=True, key="btn_preview_voltar"):
            _sincronizar_etapa_global("mapeamento")
            st.rerun()

    excel_bytes: bytes | None = None
    try:
        excel_bytes = exportar_download_bytes(df_final)
        if not excel_bytes:
            raise ValueError("Arquivo vazio")
    except Exception as e:
        log_debug(f"Erro download: {e}", "ERROR")
        st.error(f"Erro ao gerar arquivo: {e}")

    tipo_operacao = _safe_str(st.session_state.get("tipo_operacao_bling")).lower()
    nome_arquivo = (
        "bling_export_estoque.xlsx"
        if tipo_operacao == "estoque"
        else "bling_export_cadastro.xlsx"
    )

    with col_download:
        st.download_button(
            "⬇️ Baixar planilha",
            data=excel_bytes,
            file_name=nome_arquivo,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            disabled=(excel_bytes is None),
            key="btn_preview_download_excel",
        )

    # Mantido compatível com a base atual.
    try:
        render_bling_panel()
    except Exception as e:
        log_debug(f"Painel do Bling indisponível no preview final: {e}", "WARNING")
