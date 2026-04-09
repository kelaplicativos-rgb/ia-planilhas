from __future__ import annotations

from io import BytesIO
from typing import Any
import zipfile

import pandas as pd
import streamlit as st


# ==========================================================
# LEITURA SEGURA
# ==========================================================
def ler_planilha_segura(arquivo: Any) -> pd.DataFrame:
    if arquivo is None:
        return pd.DataFrame()

    try:
        nome = getattr(arquivo, "name", "").lower()

        if nome.endswith(".xlsx") or nome.endswith(".xls"):
            df = pd.read_excel(arquivo)

        elif nome.endswith(".csv"):
            df = pd.read_csv(arquivo, sep=None, engine="python")

        elif nome.endswith(".xlsb"):
            df = pd.read_excel(arquivo, engine="pyxlsb")

        else:
            st.warning("Formato não suportado")
            return pd.DataFrame()

        df.columns = [str(c).strip() for c in df.columns]
        return df

    except Exception as e:
        st.error(f"Erro ao ler planilha: {e}")
        return pd.DataFrame()


def ler_planilha_excel(arquivo: Any) -> pd.DataFrame:
    """
    Alias mantido por compatibilidade com a base antiga.
    """
    return ler_planilha_segura(arquivo)


# ==========================================================
# SAFE DF
# ==========================================================
def safe_df_dados(df: Any) -> pd.DataFrame:
    try:
        if isinstance(df, pd.DataFrame):
            return df.copy()
        if df is None:
            return pd.DataFrame()
        return pd.DataFrame(df)
    except Exception:
        return pd.DataFrame()


# ==========================================================
# LOG
# ==========================================================
def log_debug(msg: str, nivel: str = "INFO") -> None:
    """
    Mantido por compatibilidade com imports antigos do pacote utils.
    """
    try:
        print(f"[{nivel}] {msg}")
    except Exception:
        pass


# ==========================================================
# EXPORTAÇÃO BASE
# ==========================================================
def df_to_excel_bytes(df: pd.DataFrame) -> bytes:
    try:
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df.to_excel(writer, index=False)
        return buffer.getvalue()
    except Exception:
        return b""


def exportar_excel_bytes(df: pd.DataFrame) -> bytes:
    """
    Alias compatível com o restante da base.
    """
    return df_to_excel_bytes(df)


def exportar_dataframe_para_excel(
    df: pd.DataFrame,
    nome_arquivo: str = "planilha.xlsx",
):
    try:
        excel_bytes = df_to_excel_bytes(df)

        st.download_button(
            "📥 Baixar planilha",
            data=excel_bytes,
            file_name=nome_arquivo,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    except Exception as e:
        st.error(f"Erro ao exportar: {e}")


# ==========================================================
# EXPORTAÇÃO EXATA
# ==========================================================
def exportar_df_exato_para_excel_bytes(df: pd.DataFrame) -> bytes:
    """
    Exporta o DataFrame exatamente como está.
    Criado para compatibilidade com imports do sistema.
    """
    try:
        if df is None or not isinstance(df, pd.DataFrame):
            return b""

        if len(df.columns) == 0:
            return b""

        return df_to_excel_bytes(df)

    except Exception as e:
        st.error(f"Erro exportando DF exato: {e}")
        return b""


# ==========================================================
# DOWNLOAD LOG
# ==========================================================
def baixar_logs_txt(texto: str, nome: str = "log_processamento.txt"):
    try:
        st.download_button(
            "📄 Baixar log",
            data=str(texto).encode("utf-8"),
            file_name=nome,
            mime="text/plain",
        )
    except Exception as e:
        st.error(f"Erro ao baixar log: {e}")


# ==========================================================
# GTIN
# ==========================================================
def _somente_digitos(valor: Any) -> str:
    try:
        return "".join(ch for ch in str(valor or "") if ch.isdigit())
    except Exception:
        return ""


def _gtin_valido_basico(valor: Any) -> str:
    try:
        digitos = _somente_digitos(valor)

        if not digitos:
            return ""

        if set(digitos) == {"0"}:
            return ""

        if len(digitos) in [8, 12, 13, 14]:
            return digitos

        return ""
    except Exception:
        return ""


def limpar_gtin_invalido(df: pd.DataFrame) -> pd.DataFrame:
    """
    Mantido por compatibilidade com imports antigos.
    Limpa GTIN/EAN inválido deixando vazio.
    """
    try:
        if df is None or not isinstance(df, pd.DataFrame):
            return df

        df = df.copy()

        for col in df.columns:
            nome_col = str(col).strip().lower()
            if (
                "gtin" in nome_col
                or "ean" in nome_col
                or "codigo de barras" in nome_col
                or "código de barras" in nome_col
            ):
                df[col] = df[col].apply(_gtin_valido_basico)

        return df
    except Exception:
        return df


# ==========================================================
# VALIDAÇÃO
# ==========================================================
def validar_campos_obrigatorios(
    df: pd.DataFrame,
    campos_obrigatorios: list[str] | tuple[str, ...],
) -> list[str]:
    """
    Retorna lista de campos obrigatórios ausentes no DataFrame.
    """
    faltantes: list[str] = []

    try:
        if not isinstance(df, pd.DataFrame):
            return list(campos_obrigatorios)

        colunas_df = [str(c).strip() for c in df.columns]

        for campo in campos_obrigatorios:
            campo_txt = str(campo).strip()
            if campo_txt and campo_txt not in colunas_df:
                faltantes.append(campo_txt)

        return faltantes
    except Exception:
        return [str(c).strip() for c in campos_obrigatorios if str(c).strip()]


# ==========================================================
# ZIP
# ==========================================================
def gerar_zip_com_arquivos(arquivos: dict[str, bytes]) -> bytes:
    try:
        buffer = BytesIO()

        with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            for nome_arquivo, conteudo in arquivos.items():
                nome_ok = str(nome_arquivo or "").strip() or "arquivo.bin"
                conteudo_ok = conteudo if isinstance(conteudo, (bytes, bytearray)) else b""
                zf.writestr(nome_ok, conteudo_ok)

        return buffer.getvalue()
    except Exception:
        return b""


def gerar_zip_processamento(
    arquivos: dict[str, bytes] | None = None,
    log_texto: str = "",
    nome_log: str = "log_processamento.txt",
) -> bytes:
    """
    Gera zip com arquivos diversos e opcionalmente inclui o log.
    """
    try:
        arquivos_zip: dict[str, bytes] = {}

        if isinstance(arquivos, dict):
            for nome, conteudo in arquivos.items():
                arquivos_zip[str(nome)] = (
                    conteudo if isinstance(conteudo, (bytes, bytearray)) else b""
                )

        if log_texto:
            arquivos_zip[nome_log] = str(log_texto).encode("utf-8")

        return gerar_zip_com_arquivos(arquivos_zip)
    except Exception:
        return b""


# ==========================================================
# MODELO BLING
# ==========================================================
def limpar_dados_manter_cabecalho(df: pd.DataFrame) -> pd.DataFrame:
    try:
        return df.iloc[0:0].copy()
    except Exception:
        return pd.DataFrame(columns=getattr(df, "columns", []))


def reaproveitar_modelo(
    df_modelo: pd.DataFrame,
    df_dados: pd.DataFrame,
) -> pd.DataFrame:
    try:
        if df_modelo is None or not isinstance(df_modelo, pd.DataFrame) or len(df_modelo.columns) == 0:
            return df_dados

        if df_dados is None or not isinstance(df_dados, pd.DataFrame):
            return limpar_dados_manter_cabecalho(df_modelo)

        df_saida = limpar_dados_manter_cabecalho(df_modelo)

        for col in df_modelo.columns:
            if col in df_dados.columns:
                df_saida[col] = df_dados[col]
            else:
                df_saida[col] = ""

        return df_saida

    except Exception as e:
        st.error(f"Erro ao reaproveitar modelo: {e}")
        return df_dados if isinstance(df_dados, pd.DataFrame) else pd.DataFrame()


def exportar_excel_com_modelo(
    df_final: pd.DataFrame,
    df_modelo: pd.DataFrame,
) -> bytes:
    try:
        df_saida = reaproveitar_modelo(df_modelo, df_final)
        return df_to_excel_bytes(df_saida)
    except Exception as e:
        st.error(f"Erro exportando com modelo: {e}")
        return df_to_excel_bytes(df_final) if isinstance(df_final, pd.DataFrame) else b""
