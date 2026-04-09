from __future__ import annotations

import zipfile
from io import BytesIO
from pathlib import Path

import pandas as pd
import streamlit as st

from .excel_helpers import (
    _arquivo_parece_csv_texto,
    _arquivo_parece_excel_por_assinatura,
    _corrigir_coluna_unica,
    _extrair_bytes_arquivo,
    _limpar_dataframe_lido,
    _mensagem_dependencia_excel,
    _normalizar_df_texto,
    _safe_df,
)
from .excel_logs import log_debug


def _extrair_planilha_zip(arquivo):
    try:
        nome = str(getattr(arquivo, "name", "") or "").lower().strip()

        if not nome.endswith(".zip"):
            return arquivo

        conteudo_zip = _extrair_bytes_arquivo(arquivo)
        if not conteudo_zip:
            log_debug("ZIP enviado sem conteúdo legível.", "ERROR")
            return arquivo

        with zipfile.ZipFile(BytesIO(conteudo_zip)) as zf:
            nomes_internos = zf.namelist()

            candidatos = []
            for nome_interno in nomes_internos:
                nome_interno_lower = str(nome_interno).lower().strip()
                if nome_interno_lower.endswith(
                    (".xlsx", ".xls", ".csv", ".xlsm", ".xlsb")
                ):
                    candidatos.append(nome_interno)

            if not candidatos:
                log_debug("ZIP sem planilha válida interna.", "ERROR")
                return arquivo

            nome_escolhido = candidatos[0]

            with zf.open(nome_escolhido) as arquivo_interno:
                conteudo_interno = arquivo_interno.read()

            fake_file = BytesIO(conteudo_interno)
            fake_file.name = Path(nome_escolhido).name

            log_debug(
                f"ZIP detectado. Arquivo interno usado: {fake_file.name}",
                "SUCCESS",
            )
            return fake_file

    except Exception as e:
        log_debug(f"Erro ao processar ZIP automaticamente: {e}", "ERROR")
        return arquivo


def _ler_csv_tentativas(arquivo) -> pd.DataFrame | None:
    try:
        conteudo = _extrair_bytes_arquivo(arquivo)
        if not conteudo:
            return None
    except Exception:
        return None

    erros: list[str] = []

    for encoding in ["utf-8-sig", "utf-8", "cp1252", "latin1"]:
        try:
            df = pd.read_csv(
                BytesIO(conteudo),
                encoding=encoding,
                sep=None,
                engine="python",
            )

            if df is not None:
                df = _corrigir_coluna_unica(df)
                log_debug(f"CSV OK ({encoding})", "SUCCESS")
                return df
        except Exception as e:
            erros.append(f"{encoding}: {e}")
            continue

    for encoding in ["utf-8-sig", "utf-8", "cp1252", "latin1"]:
        for sep in [";", ",", "\t", "|"]:
            try:
                df = pd.read_csv(
                    BytesIO(conteudo),
                    encoding=encoding,
                    sep=sep,
                    engine="python",
                )
                if df is not None and len(df.columns) > 0:
                    df = _corrigir_coluna_unica(df)
                    log_debug(f"CSV OK ({encoding}, sep='{sep}')", "SUCCESS")
                    return df
            except Exception as e:
                erros.append(f"{encoding}/{sep}: {e}")
                continue

    if erros:
        log_debug(
            "Falha nas tentativas de leitura CSV: " + " | ".join(erros),
            "ERROR",
        )
    return None


def _ler_excel_com_engine(
    conteudo: bytes, engine: str | None, nome: str
) -> tuple[pd.DataFrame | None, list[str]]:
    engine_label = engine or "auto"
    erros: list[str] = []

    try:
        excel_file = pd.ExcelFile(BytesIO(conteudo), engine=engine)
        abas = excel_file.sheet_names or []
    except Exception as e:
        msg = f"Falha ao abrir workbook ({engine_label}) em {nome}: {e}"
        log_debug(msg, "WARNING")
        erros.append(msg)
        return None, erros

    melhor_df = pd.DataFrame()
    melhor_score = (0, 0)

    for aba in abas:
        try:
            df = pd.read_excel(BytesIO(conteudo), sheet_name=aba, engine=engine)
            df = _limpar_dataframe_lido(df)
            score = (len(df), len(df.columns) if isinstance(df, pd.DataFrame) else 0)

            log_debug(
                f"Excel OK ({engine_label}) aba='{aba}' shape={df.shape if isinstance(df, pd.DataFrame) else (0, 0)}",
                "SUCCESS",
            )

            if (
                isinstance(df, pd.DataFrame)
                and len(df.columns) > 0
                and score > melhor_score
            ):
                melhor_score = score
                melhor_df = df
        except Exception as e:
            msg = f"Falha ao ler aba '{aba}' ({engine_label}) em {nome}: {e}"
            log_debug(msg, "WARNING")
            erros.append(msg)

        try:
            df_sem_header = pd.read_excel(
                BytesIO(conteudo),
                sheet_name=aba,
                engine=engine,
                header=None,
            )
            df_sem_header = _limpar_dataframe_lido(df_sem_header)
            score_sem_header = (
                len(df_sem_header),
                len(df_sem_header.columns)
                if isinstance(df_sem_header, pd.DataFrame)
                else 0,
            )

            if (
                isinstance(df_sem_header, pd.DataFrame)
                and len(df_sem_header.columns) > 0
                and score_sem_header > melhor_score
            ):
                melhor_score = score_sem_header
                melhor_df = df_sem_header
                log_debug(
                    f"Excel OK ({engine_label}) aba='{aba}' sem header shape={df_sem_header.shape}",
                    "SUCCESS",
                )
        except Exception:
            pass

    if _safe_df(melhor_df):
        return melhor_df, erros

    try:
        df = pd.read_excel(BytesIO(conteudo), engine=engine)
        df = _limpar_dataframe_lido(df)
        if isinstance(df, pd.DataFrame) and len(df.columns) > 0:
            log_debug(f"Excel OK ({engine_label})", "SUCCESS")
            return df, erros
    except Exception as e:
        msg = f"Falha final read_excel ({engine_label}) em {nome}: {e}"
        log_debug(msg, "WARNING")
        erros.append(msg)

    return None, erros


def _ler_excel_tentativas(arquivo) -> pd.DataFrame | None:
    nome = str(getattr(arquivo, "name", "")).lower().strip()
    conteudo = _extrair_bytes_arquivo(arquivo)

    if not conteudo:
        log_debug("Arquivo Excel vazio ou sem bytes disponíveis.", "ERROR")
        return None

    ext = Path(nome).suffix.lower()
    erros_gerais: list[str] = []

    if ext in {".xlsx", ".xlsm"}:
        engines: list[str | None] = [None, "openpyxl"]
    elif ext == ".xls":
        engines = ["xlrd", None]
    elif ext == ".xlsb":
        engines = ["pyxlsb", None]
    else:
        engines = [None, "openpyxl", "xlrd", "pyxlsb"]

    for engine in engines:
        df, erros = _ler_excel_com_engine(conteudo, engine, nome)
        erros_gerais.extend(erros)
        if _safe_df(df):
            return df

    if erros_gerais:
        st.error(_mensagem_dependencia_excel(nome, erros_gerais))

    return None


def ler_planilha_segura(arquivo) -> pd.DataFrame:
    try:
        if arquivo is None:
            log_debug("Nenhum arquivo enviado para leitura.", "WARNING")
            return pd.DataFrame()

        arquivo = _extrair_planilha_zip(arquivo)
        conteudo = _extrair_bytes_arquivo(arquivo)

        if not conteudo:
            st.error("Arquivo sem conteúdo legível.")
            log_debug("Arquivo sem conteúdo legível.", "ERROR")
            return pd.DataFrame()

        nome = str(getattr(arquivo, "name", "") or "").lower().strip()
        ext = Path(nome).suffix.lower()

        df: pd.DataFrame | None = None

        if ext == ".csv":
            df = _ler_csv_tentativas(arquivo)
        elif ext in {".xlsx", ".xls", ".xlsm", ".xlsb"}:
            df = _ler_excel_tentativas(arquivo)
        else:
            if _arquivo_parece_excel_por_assinatura(conteudo):
                df = _ler_excel_tentativas(arquivo)
            elif _arquivo_parece_csv_texto(conteudo):
                df = _ler_csv_tentativas(arquivo)

        if df is None or not isinstance(df, pd.DataFrame):
            st.error("Não foi possível ler a planilha enviada.")
            log_debug(f"Falha total na leitura do arquivo: {nome}", "ERROR")
            return pd.DataFrame()

        df = _corrigir_coluna_unica(df)
        df = _normalizar_df_texto(df)
        df = _limpar_dataframe_lido(df)

        if df.empty:
            st.error("A planilha foi lida, mas está vazia após limpeza.")
            log_debug("Planilha vazia após limpeza.", "WARNING")
            return pd.DataFrame()

        log_debug(f"Leitura segura concluída com sucesso. Shape={df.shape}", "SUCCESS")
        return df

    except Exception as e:
        st.error(f"Erro ao ler planilha: {e}")
        log_debug(f"Erro em ler_planilha_segura: {e}", "ERROR")
        return pd.DataFrame()


def ler_planilha_excel(arquivo) -> pd.DataFrame:
    return ler_planilha_segura(arquivo)

