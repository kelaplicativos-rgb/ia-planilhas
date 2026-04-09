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
    from bling_app_zero.utils.gtin import aplicar_validacao_gtin_df
except Exception:
    aplicar_validacao_gtin_df = None


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

        if "area_app" not in st.session_state:
            st.session_state["area_app"] = "Fluxo principal"

        if "bloquear_campos_auto" not in st.session_state:
            st.session_state["bloquear_campos_auto"] = {}

    except Exception:
        st.session_state["logs"] = []
        st.session_state["etapa_origem"] = "origem"
        st.session_state["area_app"] = "Fluxo principal"
        st.session_state["bloquear_campos_auto"] = {}


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
    return _safe_str(nome).strip().lower()


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
    ]

    for valor in candidatos:
        texto = _safe_str(valor).lower()
        if texto:
            return texto

    return ""


def _campos_obrigatorios_por_operacao(df: pd.DataFrame) -> list[str]:
    """
    Mantém a validação conservadora e fiel ao fluxo:
    - prioriza lista já existente no session_state, se houver
    - se não houver, usa defaults mínimos por operação
    """
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
            if obrigatorios:
                return obrigatorios

    operacao = _descobrir_operacao()

    # Defaults mínimos e seguros
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
            if cand_norm == _normalizar_coluna(col):
                obrigatorios_reais.append(col)
                break

    return obrigatorios_reais


def _validar_campos_obrigatorios(df: pd.DataFrame) -> tuple[bool, list[str]]:
    obrigatorios = _campos_obrigatorios_por_operacao(df)

    if not obrigatorios:
        return True, []

    faltantes: list[str] = []

    for coluna in obrigatorios:
        if coluna not in df.columns:
            faltantes.append(coluna)
            continue

        serie = df[coluna]

        if serie.empty:
            faltantes.append(coluna)
            continue

        preenchidos = serie.apply(_valor_preenchido)
        if not bool(preenchidos.all()):
            faltantes.append(coluna)

    return len(faltantes) == 0, faltantes


def _aplicar_limpeza_gtin_se_disponivel(df: pd.DataFrame) -> pd.DataFrame:
    if aplicar_validacao_gtin_df is None:
        return df

    try:
        df_limpo = aplicar_validacao_gtin_df(df.copy())
        if isinstance(df_limpo, pd.DataFrame):
            return df_limpo
        return df
    except Exception as e:
        log_debug(f"Falha ao aplicar limpeza de GTIN: {e}", "ERROR")
        return df


def _nome_arquivo_download() -> str:
    operacao = _descobrir_operacao()
    if "estoque" in operacao:
        return "bling_estoque_final.xlsx"
    return "bling_cadastro_final.xlsx"


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
        except Exception as e:
            log_debug(f"df_to_excel_bytes utils falhou: {e}", "ERROR")

    if _exportar_excel_robusto:
        try:
            return _exportar_excel_robusto(df)
        except Exception as e:
            log_debug(f"exportar_dataframe_para_excel falhou: {e}", "ERROR")

    return _exportar_excel_fallback(df)


def exportar_download_bytes(df: pd.DataFrame) -> bytes:
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

    # mantém o df final sempre sincronizado e já com eventual limpeza de GTIN
    df_final = _aplicar_limpeza_gtin_se_disponivel(df.copy())
    st.session_state["df_final"] = df_final.copy()

    st.subheader("Preview final")
    st.dataframe(df_final.head(20), use_container_width=True)

    col_voltar, col_download = st.columns([1, 3])

    with col_voltar:
        if st.button("⬅️ Voltar", use_container_width=True):
            st.session_state["etapa_origem"] = "mapeamento"
            st.rerun()

    valido, campos_faltantes = _validar_campos_obrigatorios(df_final)

    # guarda no estado para outras telas usarem sem renderizar True/False perdido
    st.session_state["preview_final_valido"] = bool(valido)
    st.session_state["campos_obrigatorios_faltantes"] = campos_faltantes

    if not valido:
        texto_campos = ", ".join(campos_faltantes)
        st.error("⚠️ Existem campos obrigatórios não preenchidos.")
        if texto_campos:
            st.caption(f"Campos pendentes: {texto_campos}")
        log_debug(
            f"Campos obrigatórios faltando: {campos_faltantes if campos_faltantes else True}",
            "ERROR",
        )
    else:
        log_debug("Validação final concluída sem campos obrigatórios faltando.", "SUCCESS")

    excel_bytes: bytes | None = None
    if valido:
        try:
            excel_bytes = exportar_download_bytes(df_final)
        except Exception as e:
            log_debug(f"Falha ao gerar arquivo para download: {e}", "ERROR")
            st.error(f"Erro ao preparar download: {e}")

    with col_download:
        st.download_button(
            "⬇️ Baixar planilha",
            data=excel_bytes if excel_bytes is not None else b"",
            file_name=_nome_arquivo_download(),
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            disabled=(not valido or excel_bytes is None),
        )

    # integraçao com bling
    if not st.session_state.get("_bling_renderizado"):
        st.session_state["_bling_renderizado"] = True
        st.subheader("Integração com Bling")
        render_bling_panel()
