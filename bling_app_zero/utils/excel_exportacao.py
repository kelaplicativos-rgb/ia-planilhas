from __future__ import annotations

import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any

import pandas as pd

from .excel_helpers import (
    _valor_vazio,
    limpar_gtin_invalido,
    validar_campos_obrigatorios,
)
from .excel_logs import baixar_logs_txt, log_debug

try:
    import streamlit as st
except Exception:
    st = None


def _safe_df(df: Any) -> bool:
    try:
        return isinstance(df, pd.DataFrame) and len(df.columns) > 0
    except Exception:
        return False


def _obter_modelo_ativo_sessao() -> pd.DataFrame | None:
    try:
        if st is None:
            return None

        tipo = str(st.session_state.get("tipo_operacao_bling") or "").strip().lower()

        if tipo == "cadastro":
            modelo = st.session_state.get("df_modelo_cadastro")
        elif tipo == "estoque":
            modelo = st.session_state.get("df_modelo_estoque")
        else:
            modelo = None

        if _safe_df(modelo):
            return modelo.copy()

        return None
    except Exception:
        return None


def _alinhar_df_ao_modelo(df: pd.DataFrame, modelo_df: pd.DataFrame | None = None) -> pd.DataFrame:
    try:
        if not _safe_df(df):
            return pd.DataFrame()

        modelo_ativo = modelo_df if _safe_df(modelo_df) else _obter_modelo_ativo_sessao()

        if not _safe_df(modelo_ativo):
            return df.copy()

        colunas_modelo = [str(c) for c in modelo_ativo.columns]

        df_alinhado = pd.DataFrame(index=df.index)

        for col in colunas_modelo:
            df_alinhado[col] = df[col] if col in df.columns else ""

        return df_alinhado.reindex(columns=colunas_modelo, fill_value="")

    except Exception as e:
        log_debug(f"Erro ao alinhar DataFrame ao modelo: {e}", "ERROR")
        return df.copy()


def _normalizar_valores_exportacao(df: pd.DataFrame) -> pd.DataFrame:
    try:
        df_saida = df.copy()

        for col in df_saida.columns:
            df_saida[col] = df_saida[col].apply(
                lambda v: "" if _valor_vazio(v) else v
            )

        return df_saida
    except Exception:
        return df.copy()


def _validar_df_para_exportacao(df: pd.DataFrame) -> bool:
    try:
        erros = validar_campos_obrigatorios(df)

        if erros:
            log_debug(f"Campos obrigatórios faltando: {erros}", "ERROR")

            if st:
                st.error("⚠️ Existem campos obrigatórios não preenchidos.")
                st.write(erros)

            return False

        return True
    except Exception as e:
        log_debug(f"Erro ao validar campos obrigatórios: {e}", "ERROR")
        return True


def _preparar_df_exportacao(
    df: pd.DataFrame | None,
    modelo_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    try:
        if not _safe_df(df):
            return pd.DataFrame()

        df_saida = df.copy()

        df_saida = limpar_gtin_invalido(df_saida)
        df_saida = _alinhar_df_ao_modelo(df_saida, modelo_df=modelo_df)
        df_saida = _normalizar_valores_exportacao(df_saida)

        return df_saida

    except Exception as e:
        log_debug(f"Erro ao preparar DataFrame: {e}", "ERROR")
        return pd.DataFrame()


# =========================
# EXPORTAÇÃO PRINCIPAL
# =========================
def exportar_df_exato_para_excel_bytes(
    df: pd.DataFrame,
    nome_aba: str = "Planilha",
) -> bytes:
    try:
        df_export = _preparar_df_exportacao(df)

        if not _validar_df_para_exportacao(df_export):
            return b""

        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df_export.to_excel(writer, sheet_name=nome_aba[:31], index=False)

        output.seek(0)
        return output.getvalue()

    except Exception as e:
        log_debug(f"Erro na exportação: {e}", "ERROR")
        return b""


def exportar_excel_bytes(df: pd.DataFrame, nome_aba: str = "Planilha") -> bytes:
    return exportar_df_exato_para_excel_bytes(df=df, nome_aba=nome_aba)


# 🔥 CORREÇÃO CRÍTICA: alias para compatibilidade com imports antigos
def df_to_excel_bytes(df: pd.DataFrame, nome_aba: str = "Planilha") -> bytes:
    return exportar_excel_bytes(df=df, nome_aba=nome_aba)


def exportar_dataframe_para_excel(
    df: pd.DataFrame,
    caminho_arquivo: str | Path,
    nome_aba: str = "Planilha",
) -> bool:
    try:
        df_export = _preparar_df_exportacao(df)

        if not _validar_df_para_exportacao(df_export):
            return False

        caminho = Path(caminho_arquivo)
        caminho.parent.mkdir(parents=True, exist_ok=True)

        with pd.ExcelWriter(caminho, engine="openpyxl") as writer:
            df_export.to_excel(writer, sheet_name=nome_aba[:31], index=False)

        return True

    except Exception as e:
        log_debug(f"Erro ao exportar arquivo Excel: {e}", "ERROR")
        return False


def gerar_zip_com_arquivos(arquivos: dict[str, bytes]) -> bytes:
    try:
        buffer = BytesIO()

        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for nome, conteudo in arquivos.items():
                if nome:
                    zf.writestr(nome, conteudo or b"")

        buffer.seek(0)
        return buffer.getvalue()

    except Exception as e:
        log_debug(f"Erro ao gerar ZIP: {e}", "ERROR")
        return b""


def gerar_zip_processamento(
    arquivos: dict[str, bytes] | None = None,
    incluir_logs: bool = True,
    nome_log: str = "log_processamento.txt",
) -> bytes:
    try:
        itens = dict(arquivos or {})

        if incluir_logs:
            itens[nome_log] = baixar_logs_txt()

        return gerar_zip_com_arquivos(itens)

    except Exception as e:
        log_debug(f"Erro ao gerar ZIP de processamento: {e}", "ERROR")
        return b""
