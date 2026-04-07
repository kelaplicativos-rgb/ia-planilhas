from __future__ import annotations

import zipfile
from io import BytesIO
from pathlib import Path

import pandas as pd

from .excel_helpers import _valor_vazio, limpar_gtin_invalido
from .excel_logs import baixar_logs_txt, log_debug


def _preparar_df_exportacao(df: pd.DataFrame | None) -> pd.DataFrame:
    try:
        if df is None or not isinstance(df, pd.DataFrame):
            return pd.DataFrame()

        df_saida = df.copy()

        try:
            df_saida = limpar_gtin_invalido(df_saida)
        except Exception:
            pass

        for col in df_saida.columns:
            try:
                df_saida[col] = df_saida[col].apply(
                    lambda v: "" if _valor_vazio(v) else v
                )
            except Exception:
                pass

        return df_saida
    except Exception:
        return pd.DataFrame()


def df_to_excel_bytes(df: pd.DataFrame) -> bytes:
    try:
        df_export = _preparar_df_exportacao(df)

        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df_export.to_excel(writer, index=False)

        output.seek(0)
        return output.getvalue()
    except Exception as e:
        log_debug(f"Erro em df_to_excel_bytes: {e}", "ERROR")
        return b""


def exportar_df_exato_para_excel_bytes(
    df: pd.DataFrame,
    nome_aba: str = "Planilha",
) -> bytes:
    try:
        df_export = _preparar_df_exportacao(df)

        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df_export.to_excel(writer, sheet_name=nome_aba[:31], index=False)

        output.seek(0)
        return output.getvalue()
    except Exception as e:
        log_debug(f"Erro em exportar_df_exato_para_excel_bytes: {e}", "ERROR")
        return b""


def exportar_dataframe_para_excel(
    df: pd.DataFrame,
    caminho_arquivo: str | Path,
    nome_aba: str = "Planilha",
) -> bool:
    try:
        df_export = _preparar_df_exportacao(df)
        caminho = Path(caminho_arquivo)
        caminho.parent.mkdir(parents=True, exist_ok=True)

        with pd.ExcelWriter(caminho, engine="openpyxl") as writer:
            df_export.to_excel(writer, sheet_name=nome_aba[:31], index=False)

        log_debug(f"Arquivo Excel exportado com sucesso: {caminho}", "SUCCESS")
        return True
    except Exception as e:
        log_debug(f"Erro ao exportar arquivo Excel: {e}", "ERROR")
        return False


def exportar_excel_bytes(df: pd.DataFrame, nome_aba: str = "Planilha") -> bytes:
    """
    Mantido por compatibilidade com imports antigos do projeto.
    """
    return exportar_df_exato_para_excel_bytes(df=df, nome_aba=nome_aba)


def gerar_zip_com_arquivos(arquivos: dict[str, bytes]) -> bytes:
    try:
        buffer = BytesIO()

        with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            for nome, conteudo in arquivos.items():
                if not nome:
                    continue
                if conteudo is None:
                    conteudo = b""
                zf.writestr(str(nome), conteudo)

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
