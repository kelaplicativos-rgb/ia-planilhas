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


# ==========================================================
# DETECÇÃO CSV QUEBROU
# ==========================================================
def _corrigir_coluna_unica(df: pd.DataFrame) -> pd.DataFrame:
    """
    Se o CSV vier em uma única coluna, tenta reconstruir automaticamente.
    """
    try:
        if df is None or df.empty:
            return df

        if len(df.columns) > 1:
            return df

        log_debug("Detectado CSV em coluna única - tentando correção automática", "WARNING")

        col = df.columns[0]

        # tenta identificar separador
        sample = df[col].dropna().astype(str).head(5).tolist()
        texto = "\n".join(sample)

        if texto.count(";") > texto.count(","):
            sep = ";"
        elif texto.count("\t") > 0:
            sep = "\t"
        else:
            sep = ","

        log_debug(f"Reprocessando com sep='{sep}'", "INFO")

        novo_df = df[col].str.split(sep, expand=True)

        # primeira linha vira header
        novo_df.columns = novo_df.iloc[0]
        novo_df = novo_df[1:].reset_index(drop=True)

        return novo_df

    except Exception as e:
        log_debug(f"Erro ao corrigir coluna única: {e}", "ERROR")
        return df


# ==========================================================
# TEXTO / ENCODING
# ==========================================================
_MOJIBAKE_TOKENS = ("Ã", "Â", "â€™", "â€œ", "â€", "�")


def _texto_parece_mojibake(texto: str) -> bool:
    if not texto:
        return False
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

    texto = re.sub(r"[ \t]+", " ", texto).strip()
    return texto


def _normalizar_df_texto(df: pd.DataFrame) -> pd.DataFrame:
    try:
        if df is None or df.empty:
            return df

        df = df.copy()
        df.columns = [_normalizar_texto(str(col)) for col in df.columns]

        for col in df.select_dtypes(include=["object"]).columns:
            df[col] = df[col].map(_normalizar_texto)

        return df

    except Exception as e:
        log_debug(f"Erro normalização texto: {e}", "ERROR")
        return df


# ==========================================================
# CSV ROBUSTO
# ==========================================================
def _ler_csv_tentativas(arquivo) -> pd.DataFrame | None:
    conteudo = arquivo.getvalue()

    tentativas = [
        ("utf-8-sig", None),
        ("utf-8", None),
        ("cp1252", None),
        ("latin1", None),
    ]

    for encoding, _ in tentativas:
        try:
            buffer = BytesIO(conteudo)

            df = pd.read_csv(
                buffer,
                encoding=encoding,
                sep=None,           # 🔥 AUTO DETECÇÃO REAL
                engine="python",    # 🔥 ESSENCIAL
            )

            if df is not None and not df.empty:
                log_debug(f"CSV lido com sucesso ({encoding})", "SUCCESS")

                # 🔥 CORREÇÃO AUTOMÁTICA
                df = _corrigir_coluna_unica(df)

                return df

        except Exception:
            continue

    log_debug("Falha total ao ler CSV", "ERROR")
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
            log_debug("Excel lido com sucesso", "SUCCESS")

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
        log_debug(f"Erro leitura planilha: {e}", "ERROR")
        st.error("Erro ao ler arquivo")
        return None


# ==========================================================
# HELPERS
# ==========================================================
def hash_df(df: pd.DataFrame) -> str:
    return hashlib.md5(
        pd.util.hash_pandas_object(df, index=True).values.tobytes()
    ).hexdigest()


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
