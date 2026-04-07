from __future__ import annotations

import re
import zipfile
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st


# ==========================================================
# LOG
# ==========================================================
def log_debug(msg: str, nivel: str = "INFO") -> None:
    try:
        if "logs" not in st.session_state:
            st.session_state["logs"] = []

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        linha = f"[{timestamp}] [{nivel}] {msg}"
        st.session_state["logs"].append(linha)
    except Exception:
        pass


def baixar_logs_txt() -> bytes:
    try:
        logs = st.session_state.get("logs", [])
        return "\n".join(logs).encode("utf-8")
    except Exception:
        return b""


# ==========================================================
# HELPERS GERAIS
# ==========================================================
def _safe_df(df: pd.DataFrame | None) -> bool:
    try:
        return isinstance(df, pd.DataFrame) and len(df.columns) > 0
    except Exception:
        return False


def _valor_vazio(valor: Any) -> bool:
    try:
        if valor is None:
            return True
        if pd.isna(valor):
            return True

        texto = str(valor).strip().lower()
        return texto in {"", "nan", "none", "null", "<na>"}
    except Exception:
        return True


def _normalizar_nome_coluna(nome: str) -> str:
    try:
        return str(nome).strip().lower()
    except Exception:
        return ""


def _extrair_bytes_arquivo(arquivo) -> bytes:
    try:
        if arquivo is None:
            return b""

        conteudo = b""

        if hasattr(arquivo, "seek"):
            try:
                arquivo.seek(0)
            except Exception:
                pass

        if hasattr(arquivo, "getvalue"):
            try:
                conteudo = arquivo.getvalue()
                if isinstance(conteudo, bytes) and conteudo:
                    return conteudo
            except Exception:
                pass

        if hasattr(arquivo, "read"):
            try:
                if hasattr(arquivo, "seek"):
                    arquivo.seek(0)
                conteudo = arquivo.read()
                if isinstance(conteudo, bytes) and conteudo:
                    return conteudo
            except Exception:
                pass

        return b""
    except Exception:
        return b""


# ==========================================================
# 🚀 SUPORTE ZIP (ADICIONADO SEM QUEBRAR NADA)
# ==========================================================
def _extrair_planilha_zip(arquivo):
    try:
        nome = str(getattr(arquivo, "name", "")).lower()

        if not nome.endswith(".zip"):
            return arquivo

        conteudo = _extrair_bytes_arquivo(arquivo)

        with zipfile.ZipFile(BytesIO(conteudo)) as z:
            arquivos = z.namelist()

            for nome_interno in arquivos:
                nome_lower = nome_interno.lower()

                if nome_lower.endswith((".xlsx", ".xls", ".csv")):
                    with z.open(nome_interno) as f:
                        bytes_file = f.read()

                        fake_file = BytesIO(bytes_file)
                        fake_file.name = nome_interno

                        log_debug(
                            f"ZIP detectado → usando: {nome_interno}",
                            "INFO",
                        )

                        return fake_file

        log_debug("ZIP sem planilha válida", "ERROR")
        return arquivo

    except Exception as e:
        log_debug(f"Erro ao processar ZIP: {e}", "ERROR")
        return arquivo


def _arquivo_parece_excel_por_assinatura(conteudo: bytes) -> bool:
    try:
        if not conteudo:
            return False

        if conteudo[:2] == b"PK":
            return True

        if conteudo[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
            return True

        return False
    except Exception:
        return False


def _arquivo_parece_csv_texto(conteudo: bytes) -> bool:
    try:
        if not conteudo:
            return False

        amostra = conteudo[:4096]

        for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin1"):
            try:
                texto = amostra.decode(encoding, errors="ignore")
                if not texto.strip():
                    continue

                if any(sep in texto for sep in [";", ",", "\t"]):
                    return True
            except Exception:
                continue

        return False
    except Exception:
        return False


# ==========================================================
# GTIN LIMPEZA (CRÍTICO PRA BLING)
# ==========================================================
def _apenas_digitos(valor) -> str:
    try:
        if _valor_vazio(valor):
            return ""
        return re.sub(r"\D+", "", str(valor))
    except Exception:
        return ""


def _ean_checksum_valido(numero: str) -> bool:
    try:
        if not numero or not numero.isdigit():
            return False

        if len(numero) not in {8, 12, 13, 14}:
            return False

        corpo = numero[:-1]
        digito_informado = int(numero[-1])

        soma = 0
        peso_tres = True
        for dig in reversed(corpo):
            soma += int(dig) * (3 if peso_tres else 1)
            peso_tres = not peso_tres

        digito_calculado = (10 - (soma % 10)) % 10
        return digito_calculado == digito_informado
    except Exception:
        return False


def limpar_gtin_invalido(df: pd.DataFrame) -> pd.DataFrame:
    try:
        if not _safe_df(df) or df.empty:
            return df

        df_limpo = df.copy()
        colunas_gtin: list[str] = []

        for col in df_limpo.columns:
            nome = _normalizar_nome_coluna(col)
            if "gtin" in nome or "ean" in nome:
                colunas_gtin.append(col)

        if not colunas_gtin:
            return df_limpo

        for col in colunas_gtin:

            def validar(v):
                numero = _apenas_digitos(v)
                if not numero:
                    return ""
                if len(numero) not in {8, 12, 13, 14}:
                    return ""
                if not _ean_checksum_valido(numero):
                    return ""
                return numero

            df_limpo[col] = df_limpo[col].apply(validar)

        log_debug(
            f"GTIN inválido limpo com sucesso em {len(colunas_gtin)} coluna(s)",
            "SUCCESS",
        )
        return df_limpo
    except Exception as e:
        log_debug(f"Erro ao limpar GTIN: {e}", "ERROR")
        return df


# ==========================================================
# LEITOR UNIVERSAL (ALTERAÇÃO MÍNIMA AQUI)
# ==========================================================
def ler_planilha_segura(arquivo):
    try:
        # 🔥 AQUI FOI A ÚNICA ALTERAÇÃO
        arquivo = _extrair_planilha_zip(arquivo)

        nome = str(getattr(arquivo, "name", "")).lower().strip()
        log_debug(f"Lendo arquivo: {nome or 'arquivo_sem_nome'}")

        if arquivo is None:
            st.error("Nenhum arquivo foi enviado.")
            return None

        conteudo = _extrair_bytes_arquivo(arquivo)
        if not conteudo:
            st.error("Arquivo vazio ou inválido.")
            log_debug("Arquivo vazio ou sem bytes.", "ERROR")
            return None

        ext = Path(nome).suffix.lower()

        df = None

        if ext == ".csv":
            df = _ler_csv_tentativas(arquivo)
        elif ext in {".xlsx", ".xls", ".xlsm", ".xlsb"}:
            df = _ler_excel_tentativas(arquivo)

        if df is None and _arquivo_parece_excel_por_assinatura(conteudo):
            df = _ler_excel_tentativas(arquivo)

        if df is None and _arquivo_parece_csv_texto(conteudo):
            df = _ler_csv_tentativas(arquivo)

        if df is None:
            st.error("Erro ao ler arquivo.")
            log_debug(f"Falha total na leitura do arquivo: {nome}", "ERROR")
            return None

        df = df.dropna(how="all")

        if len(df.columns) == 1:
            df = _corrigir_coluna_unica(df)

        df = _normalizar_df_texto(df)

        if not _safe_df(df):
            st.error("Arquivo lido sem colunas válidas.")
            return None

        log_debug(f"Shape final: {df.shape}", "INFO")
        return df

    except Exception as e:
        log_debug(f"Erro leitura: {e}", "ERROR")
        st.error("Erro ao ler arquivo.")
        return None
