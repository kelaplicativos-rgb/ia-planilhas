from __future__ import annotations

import hashlib
import re
from datetime import datetime
from io import BytesIO

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
# GTIN LIMPEZA (🔥 CRÍTICO PRA BLING)
# ==========================================================
def limpar_gtin_invalido(df: pd.DataFrame) -> pd.DataFrame:
    try:
        if df is None or df.empty:
            return df

        df = df.copy()

        for col in df.columns:
            nome = str(col).lower()

            if "gtin" in nome or "ean" in nome:

                def validar(v):
                    v = str(v).strip()

                    if not v or v.lower() in ["nan", "none"]:
                        return ""

                    if not v.isdigit():
                        return ""

                    if len(v) not in [8, 12, 13, 14]:
                        return ""

                    return v

                df[col] = df[col].apply(validar)

        log_debug("GTIN inválido limpo com sucesso", "SUCCESS")
        return df

    except Exception as e:
        log_debug(f"Erro ao limpar GTIN: {e}", "ERROR")
        return df


# ==========================================================
# VALIDAÇÃO OBRIGATÓRIA (🔥 BLOQUEIO DOWNLOAD)
# ==========================================================
def validar_campos_obrigatorios(df: pd.DataFrame) -> bool:
    try:
        if df is None or df.empty:
            return False

        obrigatorios = ["descricao", "preco"]

        colunas = [str(c).lower() for c in df.columns]

        for campo in obrigatorios:
            if not any(campo in c for c in colunas):
                st.error(f"Campo obrigatório ausente: {campo}")
                return False

        return True

    except Exception as e:
        log_debug(f"Erro validação: {e}", "ERROR")
        return False


# ==========================================================
# DETECÇÃO CSV QUEBROU
# ==========================================================
def _corrigir_coluna_unica(df: pd.DataFrame) -> pd.DataFrame:
    try:
        if df is None or df.empty:
            return df

        if len(df.columns) > 1:
            return df

        log_debug("CSV em coluna única detectado", "WARNING")

        col = df.columns[0]

        sample = df[col].dropna().astype(str).head(5).tolist()
        texto = "\n".join(sample)

        if texto.count(";") > texto.count(","):
            sep = ";"
        elif texto.count("\t") > 0:
            sep = "\t"
        else:
            sep = ","

        novo_df = df[col].str.split(sep, expand=True)
        novo_df.columns = novo_df.iloc[0]
        novo_df = novo_df[1:].reset_index(drop=True)

        return novo_df

    except Exception as e:
        log_debug(f"Erro CSV coluna única: {e}", "ERROR")
        return df


# ==========================================================
# TEXTO
# ==========================================================
_MOJIBAKE_TOKENS = ("Ã", "Â", "â€™", "â€œ", "â€", "�")


def _texto_parece_mojibake(texto: str) -> bool:
    return any(token in texto for token in _MOJIBAKE_TOKENS)


def _normalizar_texto(valor):
    if pd.isna(valor):
        return valor
    if not isinstance(valor, str):
        return valor

    texto = valor.replace("\ufeff", "").strip()

    if _texto_parece_mojibake(texto):
        try:
            texto = texto.encode("latin1", errors="ignore").decode("utf-8", errors="ignore")
        except Exception:
            pass

    return re.sub(r"[ \t]+", " ", texto).strip()


def _normalizar_df_texto(df: pd.DataFrame) -> pd.DataFrame:
    try:
        df = df.copy()

        df.columns = [_normalizar_texto(str(col)) for col in df.columns]

        for col in df.select_dtypes(include=["object"]).columns:
            df[col] = df[col].map(_normalizar_texto)

        return df

    except Exception as e:
        log_debug(f"Erro normalização: {e}", "ERROR")
        return df


# ==========================================================
# CSV ROBUSTO
# ==========================================================
def _ler_csv_tentativas(arquivo) -> pd.DataFrame | None:
    conteudo = arquivo.getvalue()

    for encoding in ["utf-8-sig", "utf-8", "cp1252", "latin1"]:
        try:
            df = pd.read_csv(
                BytesIO(conteudo),
                encoding=encoding,
                sep=None,
                engine="python",
            )

            if df is not None and not df.empty:
                log_debug(f"CSV OK ({encoding})", "SUCCESS")
                return _corrigir_coluna_unica(df)

        except Exception:
            continue

    return None


# ==========================================================
# LEITOR UNIVERSAL
# ==========================================================
def ler_planilha_segura(arquivo):
    try:
        nome = arquivo.name.lower()
        log_debug(f"Lendo arquivo: {nome}")

        if nome.endswith(".csv"):
            df = _ler_csv_tentativas(arquivo)

        elif nome.endswith((".xlsx", ".xls", ".xlsm", ".xlsb")):
            df = pd.read_excel(arquivo)
            log_debug("Excel OK", "SUCCESS")

        else:
            st.error("Formato não suportado")
            return None

        if df is None:
            st.error("Erro ao ler arquivo")
            return None

        df = df.dropna(how="all")
        df = _normalizar_df_texto(df)

        log_debug(f"Shape final: {df.shape}", "INFO")

        return df

    except Exception as e:
        log_debug(f"Erro leitura: {e}", "ERROR")
        st.error("Erro ao ler arquivo")
        return None


# ==========================================================
# EXPORT
# ==========================================================
def exportar_excel_bytes(df: pd.DataFrame) -> bytes:
    try:
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df.to_excel(writer, index=False)
        buffer.seek(0)
        return buffer.read()
    except Exception as e:
        log_debug(f"Erro exportar excel: {e}", "ERROR")
        return b""


def safe_preview(df: pd.DataFrame, rows: int = 20) -> pd.DataFrame:
    try:
        if df is None or df.empty:
            return pd.DataFrame()
        return df.head(rows)
    except Exception as e:
        log_debug(f"Erro preview: {e}", "ERROR")
        return pd.DataFrame()
