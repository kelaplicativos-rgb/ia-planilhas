from __future__ import annotations

import io
import re
import unicodedata
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st


# =========================================================
# CONFIGURAÇÕES
# =========================================================
ENCODINGS_TENTATIVA = [
    "utf-8",
    "utf-8-sig",
    "latin-1",
    "cp1252",
]

SEPARADORES_TENTATIVA = [
    None,   # auto com engine python
    ";",
    ",",
    "\t",
    "|",
]


# =========================================================
# FUNÇÕES BÁSICAS DE TEXTO
# =========================================================
def remover_acentos(texto: str) -> str:
    if texto is None:
        return ""
    texto = str(texto)
    return "".join(
        c for c in unicodedata.normalize("NFKD", texto)
        if not unicodedata.combining(c)
    )


def normalizar_texto(texto: Any) -> str:
    if texto is None:
        return ""

    try:
        if pd.isna(texto):
            return ""
    except Exception:
        pass

    texto = str(texto)
    texto = texto.replace("\r", " ").replace("\n", " ").replace("\t", " ")
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def normalizar_nome_coluna(coluna: Any) -> str:
    coluna = normalizar_texto(coluna)
    coluna = remover_acentos(coluna).lower()
    coluna = coluna.replace("/", " ")
    coluna = coluna.replace("\\", " ")
    coluna = coluna.replace("-", " ")
    coluna = re.sub(r"[^a-z0-9 ]+", "", coluna)
    coluna = re.sub(r"\s+", " ", coluna).strip()

    if not coluna:
        coluna = "coluna"

    return coluna


def tornar_colunas_unicas(colunas: list[str]) -> list[str]:
    contagem: dict[str, int] = {}
    resultado: list[str] = []

    for nome in colunas:
        base = nome or "coluna"

        if base not in contagem:
            contagem[base] = 1
            resultado.append(base)
        else:
            contagem[base] += 1
            resultado.append(f"{base}_{contagem[base]}")

    return resultado


# =========================================================
# DETECÇÃO DE TIPO / LEITURA DE BYTES
# =========================================================
def obter_nome_arquivo(arquivo: Any) -> str:
    if hasattr(arquivo, "name"):
        return str(arquivo.name)
    return str(arquivo)


def obter_extensao_arquivo(arquivo: Any) -> str:
    nome = obter_nome_arquivo(arquivo).lower()
    return Path(nome).suffix.lower()


def ler_bytes_arquivo(arquivo: Any) -> bytes:
    if isinstance(arquivo, (str, Path)):
        with open(arquivo, "rb") as f:
            return f.read()

    if hasattr(arquivo, "getvalue"):
        return arquivo.getvalue()

    if hasattr(arquivo, "read"):
        posicao_original = None

        if hasattr(arquivo, "tell"):
            try:
                posicao_original = arquivo.tell()
            except Exception:
                posicao_original = None

        try:
            if hasattr(arquivo, "seek"):
                arquivo.seek(0)

            conteudo = arquivo.read()

            if isinstance(conteudo, str):
                conteudo = conteudo.encode("utf-8")

            return conteudo
        finally:
            if posicao_original is not None and hasattr(arquivo, "seek"):
                try:
                    arquivo.seek(posicao_original)
                except Exception:
                    pass

    raise ValueError("Não foi possível ler os bytes do arquivo enviado.")


# =========================================================
# LEITURA CSV / TXT
# =========================================================
def tentar_ler_csv_bytes(conteudo: bytes) -> tuple[pd.DataFrame, str]:
    erros: list[str] = []

    for encoding in ENCODINGS_TENTATIVA:
        for sep in SEPARADORES_TENTATIVA:
            try:
                buffer = io.BytesIO(conteudo)

                if sep is None:
                    df = pd.read_csv(
                        buffer,
                        sep=None,
                        engine="python",
                        encoding=encoding,
                        dtype=str,
                        on_bad_lines="skip",
                    )
                    metodo = f"csv automático | encoding={encoding} | separador=auto"
                else:
                    df = pd.read_csv(
                        buffer,
                        sep=sep,
                        engine="python",
                        encoding=encoding,
                        dtype=str,
                        on_bad_lines="skip",
                    )
                    metodo = f"csv manual | encoding={encoding} | separador={repr(sep)}"

                if df is not None and len(df.columns) > 0:
                    return df, metodo

            except Exception as e:
                erros.append(f"encoding={encoding}, sep={repr(sep)} -> {e}")

    raise ValueError("Falha ao ler arquivo CSV/TXT.\n" + "\n".join(erros[:10]))


# =========================================================
# LEITURA EXCEL
# =========================================================
def tentar_ler_excel_bytes(conteudo: bytes) -> tuple[pd.DataFrame, str]:
    erros: list[str] = []

    for engine in [None, "openpyxl"]:
        try:
            buffer = io.BytesIO(conteudo)
            df = pd.read_excel(
                buffer,
                dtype=str,
                engine=engine,
            )
            metodo = f"excel | engine={engine or 'auto'}"
            return df, metodo
        except Exception as e:
            erros.append(f"engine={engine or 'auto'} -> {e}")

    raise ValueError("Falha ao ler arquivo Excel.\n" + "\n".join(erros[:10]))


# =========================================================
# LIMPEZA / NORMALIZAÇÃO DE DATAFRAME
# =========================================================
def limpar_valores_vazios(df: pd.DataFrame) -> pd.DataFrame:
    if df is None:
        return pd.DataFrame()

    df = df.copy()

    for coluna in df.columns:
        df[coluna] = df[coluna].apply(normalizar_texto)

    df = df.replace("", pd.NA)
    df = df.dropna(axis=0, how="all")
    df = df.dropna(axis=1, how="all")
    df = df.fillna("")
    df = df.reset_index(drop=True)

    return df


def normalizar_colunas(df: pd.DataFrame) -> pd.DataFrame:
    if df is None:
        return pd.DataFrame()

    df = df.copy()
    df.columns = [normalizar_nome_coluna(c) for c in df.columns]
    df.columns = tornar_colunas_unicas(list(df.columns))

    colunas_validas = []
    for c in df.columns:
        c_limpa = normalizar_nome_coluna(c)
        if c_limpa.startswith("unnamed"):
            continue
        colunas_validas.append(c)

    if colunas_validas:
        df = df[colunas_validas].copy()

    return df


def limpar_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    if df is None:
        return pd.DataFrame()

    df = df.copy()
    df = normalizar_colunas(df)
    df = limpar_valores_vazios(df)
    return df


def remover_colunas_quase_vazias(
    df: pd.DataFrame,
    percentual_minimo_preenchido: float = 0.01,
) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame() if df is None else df.copy()

    total_linhas = max(len(df), 1)
    colunas_manter = []

    for coluna in df.columns:
        preenchidos = (df[coluna].astype(str).str.strip() != "").sum()
        percentual = preenchidos / total_linhas

        if percentual >= percentual_minimo_preenchido:
            colunas_manter.append(coluna)

    if not colunas_manter:
        return df.copy()

    return df[colunas_manter].copy()


# =========================================================
# FUNÇÃO PRINCIPAL DE LEITURA UNIVERSAL
# =========================================================
def ler_planilha_universal(arquivo: Any) -> dict[str, Any]:
    nome_arquivo = obter_nome_arquivo(arquivo)
    extensao = obter_extensao_arquivo(arquivo)

    try:
        conteudo = ler_bytes_arquivo(arquivo)

        if extensao in [".xlsx", ".xls"]:
            df, metodo = tentar_ler_excel_bytes(conteudo)
        elif extensao in [".csv", ".txt"]:
            df, metodo = tentar_ler_csv_bytes(conteudo)
        else:
            try:
                df, metodo = tentar_ler_excel_bytes(conteudo)
            except Exception:
                df, metodo = tentar_ler_csv_bytes(conteudo)

        df = limpar_dataframe(df)
        df = remover_colunas_quase_vazias(df, percentual_minimo_preenchido=0.01)

        preview = gerar_preview(df, limite_linhas=1)

        return {
            "sucesso": True,
            "nome_arquivo": nome_arquivo,
            "extensao": extensao,
            "metodo_leitura": metodo,
            "total_linhas": int(len(df)),
            "total_colunas": int(len(df.columns)),
            "colunas": list(df.columns),
            "df": df,
            "preview": preview,
            "erro": "",
        }

    except Exception as e:
        return {
            "sucesso": False,
            "nome_arquivo": nome_arquivo,
            "extensao": extensao,
            "metodo_leitura": "",
            "total_linhas": 0,
            "total_colunas": 0,
            "colunas": [],
            "df": pd.DataFrame(),
            "preview": pd.DataFrame(),
            "erro": str(e),
        }


# =========================================================
# COMPATIBILIDADE COM core/leitor.py
# =========================================================
def ler_planilha(arquivo: Any) -> pd.DataFrame | None:
    resultado = ler_planilha_universal(arquivo)
    if not resultado["sucesso"]:
        return None
    return resultado["df"]


# =========================================================
# PREVIEW / RESUMO
# =========================================================
def gerar_preview(df: pd.DataFrame, limite_linhas: int = 1) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()

    limite_linhas = max(1, int(limite_linhas))
    return df.head(limite_linhas).copy()


def resumo_planilha(df: pd.DataFrame) -> dict[str, Any]:
    if df is None:
        df = pd.DataFrame()

    return {
        "linhas": int(len(df)),
        "colunas": int(len(df.columns)),
        "nomes_colunas": list(df.columns),
    }


def dataframe_para_texto_seguro(df: pd.DataFrame) -> pd.DataFrame:
    if df is None:
        return pd.DataFrame()

    df = df.copy()

    for coluna in df.columns:
        df[coluna] = df[coluna].apply(normalizar_texto)

    return df


# =========================================================
# EXPORTAÇÃO
# =========================================================
def salvar_excel_bytes(
    df: pd.DataFrame,
    nome_aba: str = "Dados",
) -> bytes:
    if df is None:
        df = pd.DataFrame()

    buffer = io.BytesIO()

    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=nome_aba)

    buffer.seek(0)
    return buffer.getvalue()


# =========================================================
# HELPERS DE UI
# =========================================================
def bloco_toggle(rotulo: str, chave_estado: str) -> bool:
    if chave_estado not in st.session_state:
        st.session_state[chave_estado] = False

    texto_botao = f"👁️ Mostrar {rotulo}"
    if st.session_state[chave_estado]:
        texto_botao = f"🙈 Ocultar {rotulo}"

    if st.button(texto_botao, key=f"btn_{chave_estado}"):
        st.session_state[chave_estado] = not st.session_state[chave_estado]

    return st.session_state[chave_estado]


# =========================================================
# AUXILIARES PARA O MAPEAMENTO
# =========================================================
def listar_colunas_normalizadas(df: pd.DataFrame) -> list[str]:
    if df is None or df.empty:
        return []
    return list(df.columns)


def coluna_existe(df: pd.DataFrame, nome_coluna: str) -> bool:
    if df is None or df.empty:
        return False

    nome_coluna = normalizar_nome_coluna(nome_coluna)
    return nome_coluna in df.columns


def obter_valor_seguro(linha: pd.Series, coluna: str, padrao: str = "") -> str:
    coluna = normalizar_nome_coluna(coluna)

    if coluna not in linha.index:
        return padrao

    valor = linha[coluna]
    valor = normalizar_texto(valor)

    return valor if valor != "" else padrao
