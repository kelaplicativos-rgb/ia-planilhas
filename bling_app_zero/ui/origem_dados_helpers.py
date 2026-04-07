from __future__ import annotations

import re
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
        return texto in {"", "nan", "none", "null"}
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
    """
    Valida GTIN-8 / GTIN-12 / GTIN-13 / GTIN-14.
    """
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
# VALIDAÇÃO OBRIGATÓRIA (BLOQUEIO DOWNLOAD)
# ==========================================================
def validar_campos_obrigatorios(df: pd.DataFrame) -> bool:
    try:
        if not _safe_df(df) or df.empty:
            st.error("A planilha final está vazia.")
            return False

        colunas_originais = list(df.columns)
        colunas_norm = [_normalizar_nome_coluna(c) for c in colunas_originais]

        def encontrar_coluna(candidatos: list[str]) -> str | None:
            for idx, nome in enumerate(colunas_norm):
                for candidato in candidatos:
                    if candidato in nome:
                        return colunas_originais[idx]
            return None

        coluna_descricao = encontrar_coluna(["descricao", "descrição"])
        coluna_preco = encontrar_coluna(
            [
                "preco de venda",
                "preço de venda",
                "preco",
                "preço",
                "valor",
            ]
        )

        faltantes_estrutura: list[str] = []
        if coluna_descricao is None:
            faltantes_estrutura.append("Descrição")
        if coluna_preco is None:
            faltantes_estrutura.append("Preço")

        if faltantes_estrutura:
            st.error("Campo obrigatório ausente: " + ", ".join(faltantes_estrutura))
            return False

        if coluna_descricao is not None:
            serie_desc = df[coluna_descricao]
            if serie_desc.apply(_valor_vazio).all():
                st.error("O campo obrigatório 'Descrição' está vazio.")
                return False

        if coluna_preco is not None:
            serie_preco = (
                df[coluna_preco]
                .astype(str)
                .str.replace(".", "", regex=False)
                .str.replace(",", ".", regex=False)
                .str.replace(r"[^\d\.\-]", "", regex=True)
                .str.strip()
            )
            valores_validos = pd.to_numeric(serie_preco, errors="coerce")

            if valores_validos.isna().all():
                st.error("O campo obrigatório de preço está vazio ou inválido.")
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
        elif "\t" in texto:
            sep = "\t"
        else:
            sep = ","

        novo_df = df[col].astype(str).str.split(sep, expand=True)
        if novo_df.empty:
            return df

        cabecalho = novo_df.iloc[0].fillna("").astype(str).tolist()
        novo_df.columns = cabecalho
        novo_df = novo_df[1:].reset_index(drop=True)
        novo_df = novo_df.dropna(how="all")

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
    try:
        if pd.isna(valor):
            return valor
    except Exception:
        pass

    if not isinstance(valor, str):
        return valor

    texto = valor.replace("\ufeff", "").strip()

    if _texto_parece_mojibake(texto):
        try:
            texto = texto.encode("latin1", errors="ignore").decode(
                "utf-8", errors="ignore"
            )
        except Exception:
            pass

    return re.sub(r"[ \t]+", " ", texto).strip()


def _normalizar_df_texto(df: pd.DataFrame) -> pd.DataFrame:
    try:
        df_normalizado = df.copy()
        df_normalizado.columns = [
            _normalizar_texto(str(col)) for col in df_normalizado.columns
        ]

        for col in df_normalizado.select_dtypes(include=["object"]).columns:
            df_normalizado[col] = df_normalizado[col].map(_normalizar_texto)

        return df_normalizado
    except Exception as e:
        log_debug(f"Erro normalização: {e}", "ERROR")
        return df


# ==========================================================
# CSV ROBUSTO
# ==========================================================
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
        log_debug("Falha nas tentativas de leitura CSV: " + " | ".join(erros), "ERROR")
    return None


# ==========================================================
# EXCEL ROBUSTO
# ==========================================================
def _mensagem_dependencia_excel(nome: str, erros: list[str]) -> str:
    ext = Path(nome).suffix.lower()

    if ext == ".xls":
        return (
            "Não foi possível ler o arquivo .xls. "
            "No ambiente publicado, instale a dependência 'xlrd'."
        )

    if ext == ".xlsb":
        return (
            "Não foi possível ler o arquivo .xlsb. "
            "No ambiente publicado, instale a dependência 'pyxlsb'."
        )

    if erros:
        return "Erro ao ler Excel: " + " | ".join(erros[:3])

    return "Erro ao ler Excel."


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

    for aba in abas:
        try:
            df = pd.read_excel(BytesIO(conteudo), sheet_name=aba, engine=engine)
            if isinstance(df, pd.DataFrame) and len(df.columns) > 0:
                log_debug(f"Excel OK ({engine_label}) aba='{aba}'", "SUCCESS")
                return df, erros
        except Exception as e:
            msg = f"Falha ao ler aba '{aba}' ({engine_label}) em {nome}: {e}"
            log_debug(msg, "WARNING")
            erros.append(msg)

    try:
        df = pd.read_excel(BytesIO(conteudo), engine=engine)
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


# ==========================================================
# LEITOR UNIVERSAL
# ==========================================================
def ler_planilha_segura(arquivo):
    try:
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
            log_debug(
                "Fallback acionado: conteúdo parece Excel independentemente da extensão.",
                "WARNING",
            )
            df = _ler_excel_tentativas(arquivo)

        if df is None and _arquivo_parece_csv_texto(conteudo):
            log_debug(
                "Fallback acionado: conteúdo parece CSV/texto independentemente da extensão.",
                "WARNING",
            )
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
            log_debug(f"Arquivo lido sem colunas válidas: {nome}", "ERROR")
            return None

        log_debug(f"Shape final: {df.shape}", "INFO")
        return df
    except Exception as e:
        log_debug(f"Erro leitura: {e}", "ERROR")
        st.error("Erro ao ler arquivo.")
        return None


# ==========================================================
# EXPORT
# ==========================================================
def exportar_excel_bytes(df: pd.DataFrame) -> bytes:
    try:
        if df is None:
            return b""

        df_export = df.copy()
        buffer = BytesIO()

        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df_export.to_excel(writer, index=False)

        buffer.seek(0)
        return buffer.read()
    except Exception as e:
        log_debug(f"Erro exportar excel: {e}", "ERROR")
        return b""


def safe_preview(df: pd.DataFrame, rows: int = 20) -> pd.DataFrame:
    try:
        if df is None or df.empty:
            return pd.DataFrame()

        df_preview = df.head(rows).copy()

        for col in df_preview.columns:
            try:
                df_preview[col] = df_preview[col].map(
                    lambda x: "" if pd.isna(x) else str(x)
                )
            except Exception:
                pass

        return df_preview
    except Exception as e:
        log_debug(f"Erro preview: {e}", "ERROR")
        return pd.DataFrame()
