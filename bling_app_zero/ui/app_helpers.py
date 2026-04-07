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


# ==========================================================
# ESTADO / LOG
# ==========================================================
def garantir_estado_base() -> None:
    if "logs" not in st.session_state:
        st.session_state["logs"] = []

    if "etapa_origem" not in st.session_state or not st.session_state.get("etapa_origem"):
        st.session_state["etapa_origem"] = "upload"

    if "area_app" not in st.session_state:
        st.session_state["area_app"] = "Fluxo principal"


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
# HELPERS GERAIS
# ==========================================================
def _safe_text(value: Any) -> str:
    try:
        if value is None:
            return ""
        if pd.isna(value):
            return ""
    except Exception:
        pass
    return str(value).strip()


def _normalizar_nome_coluna(nome: Any) -> str:
    return (
        _safe_text(nome)
        .lower()
        .replace("_", " ")
        .replace("-", " ")
        .replace("  ", " ")
    )


def _colunas_possiveis_gtin(df: pd.DataFrame) -> list[str]:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return []

    candidatas: list[str] = []
    chaves = [
        "gtin",
        "ean",
        "código de barras",
        "codigo de barras",
        "cod barras",
        "cod. barras",
        "gtin/ean",
        "ean/gtin",
        "gtin tribut",
        "ean tribut",
    ]

    for col in df.columns:
        nome = _normalizar_nome_coluna(col)
        if any(chave in nome for chave in chaves):
            candidatas.append(col)

    return candidatas


def safe_df_from_state(key: str) -> pd.DataFrame | None:
    df = st.session_state.get(key)
    if isinstance(df, pd.DataFrame) and not df.empty and len(df.columns) > 0:
        return df.copy()
    return None


def get_df_fluxo() -> pd.DataFrame | None:
    """
    Ordem de prioridade do fluxo final:
    1) df_saida
    2) df_final
    3) df_precificado
    4) df_origem
    """
    for key in ["df_saida", "df_final", "df_precificado", "df_origem"]:
        df = safe_df_from_state(key)
        if df is not None:
            return df
    return None


def sincronizar_df_final() -> None:
    """
    Mantém um espelho estável em df_final sem sobrescrever incorretamente
    o melhor DataFrame do fluxo.
    """
    df_fluxo = get_df_fluxo()
    if df_fluxo is not None:
        st.session_state["df_final"] = df_fluxo.copy()


def normalizar_validacao_obrigatorios(resultado_validacao) -> bool:
    """
    Aceita bool direto ou estruturas mais complexas retornadas pelo helper.
    """
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
        return True


# ==========================================================
# EXPORTAÇÃO
# ==========================================================
def _exportar_excel_fallback(df: pd.DataFrame) -> bytes:
    df_saida = df.copy() if isinstance(df, pd.DataFrame) else pd.DataFrame()

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_saida.to_excel(writer, sheet_name="Planilha", index=False)

    output.seek(0)
    return output.getvalue()


def exportar_excel_bytes(df: pd.DataFrame) -> bytes:
    """
    Mantém compatibilidade local caso o módulo antigo
    bling_app_zero.ui.origem_dados_helpers não exista.
    """
    if _df_to_excel_bytes_utils is not None:
        try:
            retorno = _df_to_excel_bytes_utils(df)
            if isinstance(retorno, bytes):
                return retorno
            if hasattr(retorno, "getvalue"):
                return retorno.getvalue()
        except Exception as e:
            log_debug(f"Falha em _df_to_excel_bytes_utils: {e}", "ERRO")

    return _exportar_excel_fallback(df)


def exportar_download_bytes(df: pd.DataFrame) -> bytes:
    """
    Tenta primeiro um exportador robusto. Se não existir ou falhar,
    cai no exportador atual do projeto.
    """
    if _exportar_excel_robusto is not None:
        try:
            retorno = _exportar_excel_robusto(df)

            if isinstance(retorno, bytes):
                return retorno

            if hasattr(retorno, "getvalue"):
                return retorno.getvalue()
        except Exception as e:
            log_debug(f"Falha no exportador robusto: {e}", "ERRO")

    return exportar_excel_bytes(df)


# ==========================================================
# GTIN
# ==========================================================
def limpar_gtin_invalido(df: pd.DataFrame) -> pd.DataFrame:
    """
    Limpa GTIN/EAN inválido deixando vazio, sem depender do módulo ausente.
    """
    if not isinstance(df, pd.DataFrame) or df.empty:
        return df

    df_saida = df.copy()

    if aplicar_validacao_gtin_df is None:
        return df_saida

    try:
        colunas_gtin = _colunas_possiveis_gtin(df_saida)

        for col in colunas_gtin:
            try:
                df_saida, logs_gtin = aplicar_validacao_gtin_df(df_saida, col)
                for linha in logs_gtin[-20:]:
                    log_debug(str(linha), "INFO")
            except Exception as e:
                log_debug(f"Falha ao validar GTIN na coluna '{col}': {e}", "ERRO")

        return df_saida
    except Exception as e:
        log_debug(f"Erro geral ao limpar GTIN inválido: {e}", "ERRO")
        return df.copy()


# ==========================================================
# VALIDAÇÃO
# ==========================================================
def _obter_campos_faltando_de_estado() -> list[str]:
    """
    Aproveita possíveis estruturas já existentes em session_state
    sem forçar um formato único.
    """
    candidatos = [
        "campos_obrigatorios_faltando",
        "faltando_obrigatorios",
        "erros_campos_obrigatorios",
        "validacao_campos_obrigatorios",
    ]

    faltando: list[str] = []

    for chave in candidatos:
        valor = st.session_state.get(chave)

        if isinstance(valor, dict):
            for k, v in valor.items():
                if v:
                    faltando.append(str(k).strip())

        elif isinstance(valor, (list, tuple, set)):
            faltando.extend([str(x).strip() for x in valor if str(x).strip()])

        elif isinstance(valor, str) and valor.strip():
            faltando.append(valor.strip())

    # remove duplicados preservando ordem
    vistos = set()
    saida: list[str] = []
    for item in faltando:
        if item and item not in vistos:
            vistos.add(item)
            saida.append(item)

    return saida


def validar_campos_obrigatorios(df: pd.DataFrame):
    """
    Validação segura e não destrutiva.
    Retorna:
    - True quando pode seguir
    - lista/dict quando houver faltas explícitas detectadas
    """
    try:
        if not isinstance(df, pd.DataFrame) or df.empty or len(df.columns) == 0:
            return ["Nenhum dado final disponível para download."]

        faltando_estado = _obter_campos_faltando_de_estado()
        if faltando_estado:
            return faltando_estado

        # Se existir estrutura pronta de obrigatórios, respeita.
        obrigatorios = st.session_state.get("colunas_obrigatorias_download")
        if isinstance(obrigatorios, (list, tuple, set)) and obrigatorios:
            faltando: list[str] = []

            for col in obrigatorios:
                col = str(col).strip()
                if not col:
                    continue

                if col not in df.columns:
                    faltando.append(col)
                    continue

                serie = df[col]
                preenchidos = serie.astype(str).str.strip().replace(
                    {"nan": "", "None": "", "null": ""}
                )
                if (preenchidos != "").sum() == 0:
                    faltando.append(col)

            if faltando:
                return faltando

        return True
    except Exception as e:
        log_debug(f"Erro interno na validação de obrigatórios: {e}", "ERRO")
        return True


# ==========================================================
# LOG / DEBUG
# ==========================================================
def gerar_log_bytes() -> bytes:
    try:
        logs = st.session_state.get("logs", [])

        if not logs:
            return b"Nenhum log disponivel."

        conteudo = "\n".join(str(linha) for linha in logs)
        return conteudo.encode("utf-8", errors="ignore")
    except Exception as e:
        return f"Erro ao gerar log: {e}".encode("utf-8", errors="ignore")


def render_download_log_button(
    label: str,
    key: str,
    file_name: str = "debug.txt",
) -> None:
    try:
        log_bytes = gerar_log_bytes()

        st.download_button(
            label=label,
            data=log_bytes,
            file_name=file_name,
            mime="text/plain",
            use_container_width=True,
            key=key,
        )
    except Exception as e:
        log_debug(f"Erro ao preparar download do log: {e}", "ERRO")
        st.error("Nao foi possivel preparar o download do log.")


def render_debug_panel(
    download_key: str,
    file_name: str = "debug.txt",
) -> None:
    with st.expander("🔍 Debug", expanded=False):
        logs = st.session_state.get("logs", [])

        for linha in reversed(logs[-100:]):
            st.text(str(linha))

        render_download_log_button(
            label="📥 Baixar log",
            key=download_key,
            file_name=file_name,
        )


# ==========================================================
# PREVIEW FINAL
# ==========================================================
def render_preview_final() -> None:
    sincronizar_df_final()
    df_fluxo = get_df_fluxo()

    if df_fluxo is None:
        st.warning("Nenhum dado disponível para o preview final.")
        log_debug("Etapa final sem DataFrame disponível", "ERRO")
        return

    try:
        log_debug(
            f"Preview final carregado com {len(df_fluxo)} linha(s) e "
            f"{len(df_fluxo.columns)} coluna(s)"
        )
    except Exception:
        pass

    st.divider()
    st.subheader("Preview final")

    with st.expander("📦 Ver dados finais", expanded=False):
        st.dataframe(df_fluxo.head(20), use_container_width=True)

    col1, col2 = st.columns(2)

    with col1:
        if st.button(
            "⬅️ Voltar para mapeamento",
            use_container_width=True,
            key="btn_voltar_para_mapeamento_final",
        ):
            st.session_state["etapa_origem"] = "mapeamento"
            st.rerun()

    with col2:
        if st.button(
            "🔄 Atualizar preview",
            use_container_width=True,
            key="btn_atualizar_preview_final",
        ):
            st.session_state["df_final"] = df_fluxo.copy()
            st.rerun()

    try:
        df_download = limpar_gtin_invalido(df_fluxo.copy())
    except Exception as e:
        log_debug(f"Erro ao limpar GTIN inválido: {e}", "ERRO")
        df_download = df_fluxo.copy()

    validacao_ok = True
    excel_bytes = None

    try:
        validacao_ok = normalizar_validacao_obrigatorios(
            validar_campos_obrigatorios(df_download)
        )
    except Exception as e:
        log_debug(f"Erro na validação de campos obrigatórios: {e}", "ERRO")
        validacao_ok = True

    if not validacao_ok:
        st.error("Preencha os campos obrigatórios antes do download.")
    else:
        try:
            excel_bytes = exportar_download_bytes(df_download)
        except Exception as e:
            log_debug(f"Erro ao gerar Excel final: {e}", "ERRO")
            st.error("Não foi possível gerar a planilha final.")

    if isinstance(excel_bytes, bytes) and excel_bytes:
        st.download_button(
            "⬇️ Baixar planilha final",
            data=excel_bytes,
            file_name="bling_final.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            key="btn_baixar_planilha_final",
        )
    else:
        if validacao_ok:
            st.warning("A planilha final ainda não está pronta para download.")

    st.divider()
    st.subheader("Integração com Bling")
    render_bling_panel()
