from __future__ import annotations

from typing import Any
import pandas as pd

# ==========================================================
# IMPORTS COM BLINDAGEM
# ==========================================================
try:
    from .excel_logs import log_debug
except Exception:
    def log_debug(msg: str, nivel: str = "INFO"):
        pass


# ==========================================================
# SAFE DF
# ==========================================================
def safe_df_dados(df: Any) -> bool:
    try:
        return isinstance(df, pd.DataFrame) and len(df.columns) > 0
    except Exception:
        return False


# ==========================================================
# 🔥 NOVO: APLICAR MODELO BLING
# ==========================================================
def aplicar_modelo_bling(df_final: pd.DataFrame, df_modelo: pd.DataFrame) -> pd.DataFrame:
    """
    Usa o modelo Bling como base:
    - mantém colunas do modelo
    - limpa dados antigos
    - injeta df_final respeitando colunas
    """

    try:
        if not safe_df_dados(df_modelo):
            return df_final

        df_modelo = df_modelo.copy()

        # 🔥 mantém só cabeçalho
        df_base = pd.DataFrame(columns=df_modelo.columns)

        # 🔥 garante que df_final tenha as mesmas colunas
        df_saida = pd.DataFrame(columns=df_modelo.columns)

        for col in df_modelo.columns:
            if col in df_final.columns:
                df_saida[col] = df_final[col]
            else:
                df_saida[col] = ""

        return df_saida

    except Exception as e:
        log_debug(f"Erro ao aplicar modelo Bling: {e}", "ERROR")
        return df_final


# ==========================================================
# 🔥 EXPORT CORRETO COM MODELO
# ==========================================================
def exportar_excel_com_modelo(df_final: pd.DataFrame, df_modelo: pd.DataFrame):
    """
    Exporta respeitando o modelo Bling
    """
    try:
        from io import BytesIO

        df_saida = aplicar_modelo_bling(df_final, df_modelo)

        buffer = BytesIO()
        df_saida.to_excel(buffer, index=False)

        return buffer.getvalue()

    except Exception as e:
        log_debug(f"Erro ao exportar com modelo: {e}", "ERROR")
        return b""


# ==========================================================
# FALLBACK (mantido)
# ==========================================================
def exportar_excel_bytes_seguro(df: pd.DataFrame):
    try:
        from io import BytesIO

        buffer = BytesIO()
        df.to_excel(buffer, index=False)
        return buffer.getvalue()

    except Exception:
        return b""


# ==========================================================
# EXPORTS
# ==========================================================
__all__ = [
    "log_debug",
    "safe_df_dados",
    "aplicar_modelo_bling",
    "exportar_excel_com_modelo",
    "exportar_excel_bytes_seguro",
]
