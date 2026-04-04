import io
import re
import unicodedata

import pandas as pd
import streamlit as st


def remover_acentos(texto: str) -> str:
    if texto is None:
        return ""

    texto = str(texto)
    texto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in texto if not unicodedata.combining(c))


def limpar_texto(valor) -> str:
    if valor is None:
        return ""

    try:
        if pd.isna(valor):
            return ""
    except Exception:
        pass

    texto = str(valor)
    texto = texto.replace("\ufeff", " ")
    texto = texto.replace("\u200b", " ")
    texto = texto.replace("\xa0", " ")
    texto = texto.replace("\n", " ").replace("\r", " ").replace("\t", " ")
    texto = re.sub(r"\s+", " ", texto)

    return texto.strip()


def slug_coluna(nome: str) -> str:
    nome = limpar_texto(nome)
    nome = remover_acentos(nome).lower()
    nome = nome.replace("/", " ")
    nome = nome.replace("\\", " ")
    nome = nome.replace("-", " ")
    nome = re.sub(r"[^a-z0-9 ]+", "", nome)
    nome = re.sub(r"\s+", "_", nome).strip("_")

    if not nome:
        nome = "coluna"

    return nome


def _ler_csv_com_tentativas(arquivo):
    tentativas = [
        {"sep": None, "engine": "python", "encoding": "utf-8"},
        {"sep": ";", "engine": "python", "encoding": "utf-8"},
        {"sep": ",", "engine": "python", "encoding": "utf-8"},
        {"sep": "\t", "engine": "python", "encoding": "utf-8"},
        {"sep": None, "engine": "python", "encoding": "latin-1"},
        {"sep": ";", "engine": "python", "encoding": "latin-1"},
        {"sep": ",", "engine": "python", "encoding": "latin-1"},
        {"sep": "\t", "engine": "python", "encoding": "latin-1"},
    ]

    ultimo_erro = None

    for tentativa in tentativas:
        try:
            arquivo.seek(0)
            df = pd.read_csv(
                arquivo,
                sep=tentativa["sep"],
                engine=tentativa["engine"],
                encoding=tentativa["encoding"],
                dtype=str,
                on_bad_lines="skip",
            )
            if df is not None and len(df.columns) > 0:
                return df
        except Exception as e:
            ultimo_erro = e

    raise ValueError(f"Erro ao ler CSV: {ultimo_erro}")


def ler_planilha(arquivo):
    """
    Lê CSV, XLS ou XLSX com fallback robusto.
    Retorna DataFrame ou None em caso de falha.
    """
    if arquivo is None:
        return None

    nome = str(getattr(arquivo, "name", "")).lower()

    try:
        if nome.endswith(".csv"):
            return _ler_csv_com_tentativas(arquivo)

        arquivo.seek(0)
        return pd.read_excel(arquivo, dtype=str)
    except Exception:
        return None


def limpar_valores_vazios(df):
    """
    Limpa células vazias e normaliza todas como texto.
    """
    if df is None or df.empty:
        return pd.DataFrame()

    df = df.copy()

    for col in df.columns:
        df[col] = df[col].apply(limpar_texto)

    df = df.fillna("")
    df = df.astype(str)

    return df


def normalizar_colunas(df):
    """
    Normaliza nomes de colunas e evita duplicadas.
    """
    if df is None or df.empty:
        return pd.DataFrame()

    df = df.copy()

    novas_colunas = []
    usados = {}

    for c in df.columns:
        base = slug_coluna(c)

        if base not in usados:
            usados[base] = 1
            novas_colunas.append(base)
        else:
            usados[base] += 1
            novas_colunas.append(f"{base}_{usados[base]}")

    df.columns = novas_colunas
    return df


def gerar_preview(df, linhas=1):
    """
    Gera preview enxuto.
    """
    if df is None or df.empty:
        return pd.DataFrame()

    try:
        linhas = int(linhas)
    except Exception:
        linhas = 1

    if linhas <= 0:
        linhas = 1

    return df.head(linhas)


def salvar_excel_bytes(df):
    """
    Exporta DataFrame para bytes Excel.
    """
    buffer = io.BytesIO()

    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Dados")

    buffer.seek(0)
    return buffer.getvalue()


def salvar_txt_bytes(texto: str):
    """
    Exporta texto simples para bytes.
    """
    return str(texto).encode("utf-8")


def bloco_toggle(nome, chave):
    """
    Botão toggle persistente no session_state.
    Começa sempre fechado por padrão.
    """
    estado_key = f"toggle_{chave}"
    botao_key = f"btn_{chave}"

    if estado_key not in st.session_state:
        st.session_state[estado_key] = False

    if st.button(f"👁️ {nome}", key=botao_key, use_container_width=True):
        st.session_state[estado_key] = not st.session_state[estado_key]

    return st.session_state[estado_key]
