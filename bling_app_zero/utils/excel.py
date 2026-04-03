# bling_app_zero/utils/excel.py

from __future__ import annotations

import io
import re
import unicodedata
from pathlib import Path
from typing import Any, BinaryIO

import pandas as pd


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
    """
    Remove acentos de uma string.
    """
    if texto is None:
        return ""
    texto = str(texto)
    return "".join(
        c for c in unicodedata.normalize("NFKD", texto)
        if not unicodedata.combining(c)
    )


def normalizar_texto(texto: Any) -> str:
    """
    Normaliza textos genéricos:
    - converte para string
    - remove espaços extras
    - remove quebras de linha desnecessárias
    """
    if texto is None:
        return ""

    if pd.isna(texto):
        return ""

    texto = str(texto)
    texto = texto.replace("\r", " ").replace("\n", " ").replace("\t", " ")
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def normalizar_nome_coluna(coluna: Any) -> str:
    """
    Padroniza nomes de colunas para facilitar leitura automática.
    """
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
    """
    Garante que nomes repetidos virem únicos:
    exemplo: preco, preco_2, preco_3
    """
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
# DETECÇÃO DE TIPO
# =========================================================
def obter_nome_arquivo(arquivo: Any) -> str:
    """
    Extrai nome do arquivo de UploadedFile, path ou objeto parecido.
    """
    if hasattr(arquivo, "name"):
        return str(arquivo.name)
    return str(arquivo)


def obter_extensao_arquivo(arquivo: Any) -> str:
    nome = obter_nome_arquivo(arquivo).lower()
    return Path(nome).suffix.lower()


def ler_bytes_arquivo(arquivo: Any) -> bytes:
    """
    Lê bytes do arquivo sem quebrar UploadedFile do Streamlit.
    """
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
# LEITURA DE CSV/TXT
# =========================================================
def tentar_ler_csv_bytes(conteudo: bytes) -> tuple[pd.DataFrame, str]:
    """
    Tenta ler CSV/TXT com múltiplos encodings e separadores.
    Retorna df e descrição do método usado.
    """
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

    raise ValueError(
        "Falha ao ler arquivo CSV/TXT.\n"
        + "\n".join(erros[:10])
    )


# =========================================================
# LEITURA DE EXCEL
# =========================================================
def tentar_ler_excel_bytes(conteudo: bytes) -> tuple[pd.DataFrame, str]:
    """
    Lê Excel (.xlsx / .xls) tentando engine compatível.
    """
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

    raise ValueError(
        "Falha ao ler arquivo Excel.\n"
        + "\n".join(erros[:10])
    )


# =========================================================
# LIMPEZA DO DATAFRAME
# =========================================================
def limpar_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Limpeza geral da planilha:
    - transforma cabeçalhos em texto
    - remove linhas/colunas totalmente vazias
    - padroniza valores
    - remove colunas 'unnamed'
    """
    if df is None:
        return pd.DataFrame()

    df = df.copy()

    # Garante cabeçalhos em string
    df.columns = [normalizar_nome_coluna(c) for c in df.columns]
    df.columns = tornar_colunas_unicas(list(df.columns))

    # Remove colunas do tipo unnamed / coluna vazia fake
    colunas_validas = []
    for c in df.columns:
        c_limpa = normalizar_nome_coluna(c)
        if c_limpa.startswith("unnamed"):
            continue
        colunas_validas.append(c)

    if colunas_validas:
        df = df[colunas_validas]

    # Padroniza valores
    for coluna in df.columns:
        df[coluna] = df[coluna].apply(normalizar_texto)

    # Troca strings vazias por NA temporariamente para limpeza
    df = df.replace("", pd.NA)

    # Remove linhas e colunas totalmente vazias
    df = df.dropna(axis=0, how="all")
    df = df.dropna(axis=1, how="all")

    # Volta NA para string vazia
    df = df.fillna("")

    # Reseta índice
    df = df.reset_index(drop=True)

    return df


def remover_colunas_quase_vazias(
    df: pd.DataFrame,
    percentual_minimo_preenchido: float = 0.01,
) -> pd.DataFrame:
    """
    Remove colunas praticamente vazias.
    Ex.: uma coluna preenchida em menos de 1% das linhas.
    """
    if df.empty:
        return df.copy()

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
# FUNÇÕES PÚBLICAS PRINCIPAIS
# =========================================================
def ler_planilha_universal(arquivo: Any) -> dict[str, Any]:
    """
    Função principal do módulo.
    Lê qualquer planilha suportada e devolve estrutura padronizada.

    Retorno:
    {
        "sucesso": bool,
        "nome_arquivo": str,
        "extensao": str,
        "metodo_leitura": str,
        "total_linhas": int,
        "total_colunas": int,
        "colunas": list[str],
        "df": pd.DataFrame,
        "preview": pd.DataFrame,
        "erro": str
    }
    """
    nome_arquivo = obter_nome_arquivo(arquivo)
    extensao = obter_extensao_arquivo(arquivo)

    try:
        conteudo = ler_bytes_arquivo(arquivo)

        if extensao in [".xlsx", ".xls"]:
            df, metodo = tentar_ler_excel_bytes(conteudo)

        elif extensao in [".csv", ".txt"]:
            df, metodo = tentar_ler_csv_bytes(conteudo)

        else:
            # tenta primeiro como excel, depois csv
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


def gerar_preview(df: pd.DataFrame, limite_linhas: int = 1) -> pd.DataFrame:
    """
    Gera preview reduzido. Por sua regra, default = 1 linha.
    """
    if df is None or df.empty:
        return pd.DataFrame()

    limite_linhas = max(1, int(limite_linhas))
    return df.head(limite_linhas).copy()


def resumo_planilha(df: pd.DataFrame) -> dict[str, Any]:
    """
    Retorna resumo simples da planilha.
    """
    if df is None:
        df = pd.DataFrame()

    return {
        "linhas": int(len(df)),
        "colunas": int(len(df.columns)),
        "nomes_colunas": list(df.columns),
    }


def dataframe_para_texto_seguro(df: pd.DataFrame) -> pd.DataFrame:
    """
    Garante que todas as colunas estejam em string limpa.
    Útil antes de mapear para o Bling.
    """
    if df is None:
        return pd.DataFrame()

    df = df.copy()

    for coluna in df.columns:
        df[coluna] = df[coluna].apply(normalizar_texto)

    return df


# =========================================================
# FUNÇÕES AUXILIARES PARA O PRÓXIMO MÓDULO
# =========================================================
def listar_colunas_normalizadas(df: pd.DataFrame) -> list[str]:
    """
    Retorna as colunas já normalizadas.
    """
    if df is None or df.empty:
        return []
    return list(df.columns)


def coluna_existe(df: pd.DataFrame, nome_coluna: str) -> bool:
    """
    Verifica existência já considerando normalização.
    """
    if df is None or df.empty:
        return False

    nome_coluna = normalizar_nome_coluna(nome_coluna)
    return nome_coluna in df.columns


def obter_valor_seguro(linha: pd.Series, coluna: str, padrao: str = "") -> str:
    """
    Lê valor com segurança.
    """
    coluna = normalizar_nome_coluna(coluna)

    if coluna not in linha.index:
        return padrao

    valor = linha[coluna]
    valor = normalizar_texto(valor)

    return valor if valor != "" else padrao
