from __future__ import annotations

from datetime import datetime
from io import BytesIO
from typing import Any

import pandas as pd
import streamlit as st

from bling_app_zero.ui.bling_panel import render_bling_panel

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


ETAPAS_VALIDAS_ORIGEM = {"origem", "mapeamento", "final"}


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
# DEBUG PANEL
# ==========================================================
def render_debug_panel() -> None:
    try:
        logs = st.session_state.get("logs", [])

        with st.expander("🧠 Debug / Logs", expanded=False):
            if not logs:
                st.caption("Nenhum log disponível.")
            else:
                texto = "\n".join(logs[-500:])
                st.text_area(
                    "Logs do sistema",
                    value=texto,
                    height=220,
                )

            col1, col2, col3 = st.columns(3)

            with col1:
                if st.button("🔄 Atualizar logs", use_container_width=True):
                    st.rerun()

            with col2:
                if st.button("🧹 Limpar logs", use_container_width=True):
                    st.session_state["logs"] = []
                    st.rerun()

            with col3:
                if logs:
                    log_bytes = "\n".join(logs).encode("utf-8")

                    st.download_button(
                        "📥 Baixar log",
                        data=log_bytes,
                        file_name="log_processamento.txt",
                        mime="text/plain",
                        use_container_width=True,
                    )

    except Exception as e:
        st.warning(f"Erro no debug panel: {e}")


# ==========================================================
# HELPERS
# ==========================================================
def safe_df_from_state(key: str) -> pd.DataFrame | None:
    df = st.session_state.get(key)
    if isinstance(df, pd.DataFrame) and len(df.columns) > 0:
        return df.copy()
    return None


def get_df_fluxo() -> pd.DataFrame | None:
    prioridade = ["df_final", "df_saida", "df_dados", "df_base"]

    for key in prioridade:
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
    texto = _safe_str(nome).strip().lower()
    substituicoes = {
        "á": "a",
        "à": "a",
        "ã": "a",
        "â": "a",
        "é": "e",
        "ê": "e",
        "í": "i",
        "ó": "o",
        "ô": "o",
        "õ": "o",
        "ú": "u",
        "ç": "c",
    }
    for antigo, novo in substituicoes.items():
        texto = texto.replace(antigo, novo)
    return texto


def _valor_preenchido(valor: Any) -> bool:
    try:
        if pd.isna(valor):
            return False
    except Exception:
        pass

    texto = _safe_str(valor).lower()
    return texto not in {"", "nan", "none", "null", "n/a", "na", "-"}


def _descobrir_operacao() -> str:
    candidatos = [
        st.session_state.get("tipo_operacao"),
        st.session_state.get("operacao"),
        st.session_state.get("operacao_selecionada"),
        st.session_state.get("tipo_fluxo"),
        st.session_state.get("tipo_operacao_bling"),
    ]

    for valor in candidatos:
        texto = _safe_str(valor).lower()
        if texto:
            return texto

    return ""


def _campos_obrigatorios_por_operacao(df: pd.DataFrame) -> list[str]:
    chaves_estado = [
        "campos_obrigatorios",
        "colunas_obrigatorias",
        "obrigatorios_modelo",
        "required_columns",
    ]

    for chave in chaves_estado:
        valor = st.session_state.get(chave)
        if isinstance(valor, (list, tuple, set)):
            obrigatorios = [_safe_str(x) for x in valor if _safe_str(x)]
            obrigatorios = [
                col
                for col in obrigatorios
                if "gtin" not in _normalizar_coluna(col)
                and "ean" not in _normalizar_coluna(col)
            ]
            if obrigatorios:
                return obrigatorios

    operacao = _descobrir_operacao()

    if "estoque" in operacao:
        candidatos = [
            "Código",
            "Código do produto",
            "SKU",
            "Estoque",
            "Saldo",
            "Depósito",
        ]
    else:
        candidatos = [
            "Código",
            "Nome",
            "Descrição",
            "Preço",
            "Preço de venda",
        ]

    nomes_df = list(df.columns)
    obrigatorios_reais: list[str] = []

    for candidato in candidatos:
        cand_norm = _normalizar_coluna(candidato)
        for col in nomes_df:
            col_norm = _normalizar_coluna(col)
            if cand_norm == col_norm or cand_norm in col_norm or col_norm in cand_norm:
                obrigatorios_reais.append(col)
                break

    vistos = set()
    finais = []
    for col in obrigatorios_reais:
        if col not in vistos:
            vistos.add(col)
            finais.append(col)

    return finais


def _resumo_preenchimento_coluna(serie: pd.Series) -> tuple[int, int]:
    total = int(len(serie))
    if total <= 0:
        return 0, 0

    try:
        preenchidos = int(serie.apply(_valor_preenchido).sum())
    except Exception:
        preenchidos = 0

    return preenchidos, total


def _validar_campos_obrigatorios(df: pd.DataFrame) -> tuple[bool, list[str], list[str]]:
    """
    Validação apenas informativa.
    NÃO bloqueia mais o download.
    """
    obrigatorios = _campos_obrigatorios_por_operacao(df)

    if not obrigatorios:
        return True, [], []

    faltantes_criticos: list[str] = []
    alertas: list[str] = []

    for coluna in obrigatorios:
        if coluna not in df.columns:
            faltantes_criticos.append(coluna)
            continue

        serie = df[coluna]
        if serie.empty:
            faltantes_criticos.append(coluna)
            continue

        preenchidos, total = _resumo_preenchimento_coluna(serie)

        if preenchidos <= 0:
            faltantes_criticos.append(coluna)
            continue

        if preenchidos < total:
            alertas.append(f"{coluna} ({preenchidos}/{total} preenchidos)")

    return True, faltantes_criticos, alertas


def _aplicar_tratamento_gtin(df: pd.DataFrame) -> pd.DataFrame:
    if aplicar_validacao_gtin_em_colunas_automaticas is None:
        return df

    try:
        modo = _safe_str(st.session_state.get("gtin_modo_valor") or "limpar").lower()
        if modo not in {"limpar", "gerar"}:
            modo = "limpar"

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
        log_debug(f"Falha ao aplicar tratamento de GTIN: {e}", "ERROR")
        return df


def _nome_arquivo_download() -> str:
    operacao = _descobrir_operacao()
    if "estoque" in operacao:
        return "bling_estoque_final.xlsx"
    return "bling_cadastro_final.xlsx"


def _ir_para_etapa(etapa: str) -> None:
    etapa_ok = _safe_str(etapa).lower() or "origem"
    if etapa_ok not in ETAPAS_VALIDAS_ORIGEM:
        etapa_ok = "origem"

    st.session_state["etapa_origem"] = etapa_ok
    st.session_state["etapa"] = etapa_ok
    st.session_state["etapa_fluxo"] = etapa_ok


def _obter_modelo_bling_ativo() -> pd.DataFrame | None:
    try:
        operacao = _descobrir_operacao()

        if "estoque" in operacao:
            df_modelo = st.session_state.get("df_modelo_estoque")
        else:
            df_modelo = st.session_state.get("df_modelo_cadastro")

        if isinstance(df_modelo, pd.DataFrame) and len(df_modelo.columns) > 0:
            return df_modelo.copy()

        return None
    except Exception:
        return None


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
            resultado = _df_to_excel_bytes_utils(df)
            if resultado:
                return resultado
        except Exception as e:
            log_debug(f"df_to_excel_bytes utils falhou: {e}", "ERROR")

    return _exportar_excel_fallback(df)


def exportar_download_bytes(df: pd.DataFrame) -> bytes:
    try:
        df_modelo = _obter_modelo_bling_ativo()

        if _exportar_excel_com_modelo and isinstance(df_modelo, pd.DataFrame):
            resultado = _exportar_excel_com_modelo(df, df_modelo)
            if resultado:
                log_debug("Download gerado usando modelo Bling ativo.", "SUCCESS")
                return resultado

        log_debug("Modelo Bling não disponível para exportação. Usando fallback.", "WARNING")
        return exportar_excel_bytes(df)

    except Exception as e:
        log_debug(f"Erro ao exportar download com modelo: {e}", "ERROR")
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

    if df_final.empty and len(df_final.columns) > 0:
        log_debug(
            "Preview final contém apenas estrutura de colunas sem linhas. Verificando fonte do fluxo.",
            "WARNING",
        )

    st.session_state["df_final"] = df_final.copy()
    st.session_state["df_saida"] = df_final.copy()

    st.subheader("Preview final")
    st.dataframe(df_final.head(20), use_container_width=True)

    col_voltar, col_download = st.columns([1, 3])

    with col_voltar:
        if st.button("⬅️ Voltar", use_container_width=True):
            _ir_para_etapa("mapeamento")
            st.rerun()

    valido, campos_faltantes, campos_alerta = _validar_campos_obrigatorios(df_final)

    st.session_state["preview_final_valido"] = True
    st.session_state["campos_obrigatorios_faltantes"] = campos_faltantes
    st.session_state["campos_obrigatorios_alertas"] = campos_alerta

    if campos_faltantes:
        st.warning(
            "Validação apenas informativa. Campos com ausência total detectados: "
            + ", ".join(campos_faltantes)
        )
        log_debug(
            "Validação informativa - campos ausentes: " + ", ".join(campos_faltantes),
            "WARNING",
        )
    else:
        log_debug("Validação final informativa concluída sem ausência total.", "SUCCESS")

    if campos_alerta:
        st.warning(
            "Campos com preenchimento parcial: " + ", ".join(campos_alerta)
        )
        log_debug(
            "Campos obrigatórios com preenchimento parcial: " + ", ".join(campos_alerta),
            "WARNING",
        )

    excel_bytes: bytes | None = None

    try:
        excel_bytes = exportar_download_bytes(df_final)

        if not excel_bytes:
            excel_bytes = _exportar_excel_fallback(df_final)

        if not excel_bytes:
            raise ValueError("Arquivo Excel gerado vazio.")
    except Exception as e:
        excel_bytes = None
        log_debug(f"Falha ao gerar arquivo para download: {e}", "ERROR")
        st.error(f"Erro ao preparar download: {e}")

    with col_download:
        st.download_button(
            "⬇️ Baixar planilha",
            data=excel_bytes if excel_bytes is not None else b"",
            file_name=_nome_arquivo_download(),
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            disabled=(excel_bytes is None),
        )

    render_bling_panel()
