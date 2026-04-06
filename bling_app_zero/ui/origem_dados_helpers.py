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
# TEXTO / ENCODING
# ==========================================================
_MOJIBAKE_TOKENS = (
    "Ã",
    "Â",
    "â€™",
    "â€œ",
    "â€",
    "�",
)


def _texto_parece_mojibake(texto: str) -> bool:
    if not texto:
        return False
    return any(token in texto for token in _MOJIBAKE_TOKENS)


def _df_parece_mojibake(df: pd.DataFrame) -> bool:
    try:
        if df is None or df.empty:
            return False
        amostra = df.head(20).astype(str)
        for col in amostra.columns:
            for valor in amostra[col].tolist():
                if _texto_parece_mojibake(valor):
                    return True
        return False
    except Exception:
        return False


def _normalizar_texto(valor):
    if pd.isna(valor):
        return valor
    if not isinstance(valor, str):
        return valor

    texto = valor.replace("\ufeff", "").strip()

    # Corrige mojibake clássico: "PescoÃ§o" -> "Pescoço"
    if _texto_parece_mojibake(texto):
        try:
            corrigido = texto.encode("latin1", errors="ignore").decode("utf-8", errors="ignore")
            if corrigido:
                texto = corrigido
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

        colunas_obj = df.select_dtypes(include=["object"]).columns.tolist()
        for col in colunas_obj:
            df[col] = df[col].map(_normalizar_texto)

        return df
    except Exception as e:
        log_debug(f"Erro normalização texto: {e}", "ERROR")
        return df


# ==========================================================
# CSV / EXCEL
# ==========================================================
def _ler_csv_tentativas(arquivo) -> pd.DataFrame | None:
    conteudo = arquivo.getvalue()
    tentativas = [
        ("utf-8-sig", ","),
        ("utf-8-sig", ";"),
        ("utf-8-sig", "\t"),
        ("utf-8", ","),
        ("utf-8", ";"),
        ("utf-8", "\t"),
        ("cp1252", ";"),
        ("cp1252", ","),
        ("cp1252", "\t"),
        ("latin1", ";"),
        ("latin1", ","),
        ("latin1", "\t"),
    ]

    melhor_df = None
    melhor_score = -1
    melhor_info = None

    for encoding, sep in tentativas:
        try:
            buffer = BytesIO(conteudo)
            df = pd.read_csv(buffer, encoding=encoding, sep=sep)
            if df is None:
                continue

            # score simples para escolher a melhor leitura
            score = 0
            score += len(df.columns) * 10
            score += len(df)

            # penaliza quando parece que tudo veio em uma coluna só
            if len(df.columns) == 1:
                score -= 1000

            # penaliza mojibake
            if _df_parece_mojibake(df):
                score -= 200

            # premia colunas razoáveis
            if len(df.columns) >= 3:
                score += 100

            if score > melhor_score:
                melhor_df = df
                melhor_score = score
                melhor_info = (encoding, sep)
        except Exception:
            continue

    if melhor_df is not None and melhor_info is not None:
        log_debug(
            f"CSV lido com encoding={melhor_info[0]} sep={repr(melhor_info[1])}",
            "INFO",
        )

    return melhor_df


# ==========================================================
# LEITOR UNIVERSAL (ULTRA ROBUSTO)
# ==========================================================
def ler_planilha_segura(arquivo):
    try:
        nome = arquivo.name.lower()
        log_debug(f"Lendo arquivo: {nome}")

        if nome.endswith(".csv"):
            df = _ler_csv_tentativas(arquivo)
            if df is None:
                log_debug("Falha em todas as tentativas de leitura CSV", "ERROR")
                st.error("Erro ao ler CSV")
                return None

        elif nome.endswith((".xlsx", ".xls", ".xlsm", ".xlsb")):
            df = pd.read_excel(arquivo)
            log_debug("Excel lido com sucesso", "INFO")

        else:
            log_debug("Formato não suportado", "ERROR")
            st.error("Formato não suportado")
            return None

        # limpeza estrutural
        df = df.dropna(how="all")

        # normalização textual
        df = _normalizar_df_texto(df)

        if df.empty:
            log_debug("Arquivo carregado mas vazio", "WARNING")
        else:
            log_debug(f"Arquivo carregado: {df.shape}", "SUCCESS")

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
        log_debug("Excel exportado com sucesso", "SUCCESS")
        return buffer.read()
    except Exception as e:
        log_debug(f"Erro exportar excel: {e}", "ERROR")
        st.error("Erro ao gerar Excel")
        return b""


def safe_preview(df: pd.DataFrame, rows: int = 20) -> pd.DataFrame:
    try:
        if df is None or df.empty:
            return pd.DataFrame()

        preview = df.head(rows).copy()
        preview = _normalizar_df_texto(preview)
        return preview

    except Exception as e:
        log_debug(f"Erro preview: {e}", "ERROR")
        return pd.DataFrame()
