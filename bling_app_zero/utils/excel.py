import io
import re
import zipfile
import unicodedata

import pandas as pd
import streamlit as st


# =========================================================
# TEXTO
# =========================================================
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
    nome = re.sub(r"[^a-z0-9]+", "_", nome)
    nome = re.sub(r"_+", "_", nome).strip("_")
    return nome or "coluna"


# =========================================================
# ZIP
# =========================================================
def _extrair_melhor_arquivo_do_zip(arquivo_zip):
    """
    Extrai em memória o melhor arquivo do zip.
    Prioridade: .xlsx -> .xls -> .csv
    Retorna: (BytesIO, nome_interno)
    """
    arquivo_zip.seek(0)

    with zipfile.ZipFile(arquivo_zip) as zf:
        nomes = [
            nome for nome in zf.namelist()
            if not nome.endswith("/") and not nome.startswith("__MACOSX/")
        ]

        if not nomes:
            raise ValueError("O arquivo ZIP está vazio.")

        prioridade = [".xlsx", ".xls", ".csv"]
        escolhidos = []

        for ext in prioridade:
            for nome in nomes:
                if nome.lower().endswith(ext):
                    escolhidos.append(nome)
            if escolhidos:
                break

        if not escolhidos:
            raise ValueError("O ZIP não contém arquivo compatível (.xlsx, .xls ou .csv).")

        # escolhe o menor caminho/nome mais simples primeiro
        escolhidos = sorted(escolhidos, key=lambda x: (x.count("/"), len(x), x.lower()))
        nome_escolhido = escolhidos[0]

        with zf.open(nome_escolhido) as f:
            conteudo = f.read()

    buffer = io.BytesIO(conteudo)
    buffer.name = nome_escolhido.split("/")[-1]
    return buffer, nome_escolhido


# =========================================================
# LEITURA ROBUSTA
# =========================================================
def _ler_excel_multiplas_formas(arquivo):
    tentativas = [
        lambda: pd.read_excel(arquivo, dtype=str),
        lambda: pd.read_excel(arquivo, dtype=str, header=None),
    ]

    ultimo_erro = None

    for tentativa in tentativas:
        try:
            arquivo.seek(0)
            df = tentativa()
            if df is not None and df.shape[1] > 0:
                return df
        except Exception as e:
            ultimo_erro = e

    raise ValueError(f"Erro ao ler Excel: {ultimo_erro}")


def _ajustar_header(df):
    """
    Detecta automaticamente uma linha provável de cabeçalho.
    """
    if df is None or df.empty:
        return df

    df = df.copy()

    for i in range(min(10, len(df))):
        linha = df.iloc[i]

        valores = [limpar_texto(v) for v in linha.tolist()]
        preenchidos = sum(1 for v in valores if v)

        if preenchidos >= 2:
            df.columns = valores
            df = df.iloc[i + 1:].reset_index(drop=True)
            break

    df.columns = [limpar_texto(c) or f"coluna_{idx+1}" for idx, c in enumerate(df.columns)]
    return df


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
    Lê .csv, .xls, .xlsx e .zip automaticamente.
    Se for zip, extrai em memória e escolhe o melhor arquivo interno.
    """
    if arquivo is None:
        return None

    nome = str(getattr(arquivo, "name", "")).lower()

    try:
        arquivo_para_ler = arquivo

        if nome.endswith(".zip"):
            arquivo_para_ler, _ = _extrair_melhor_arquivo_do_zip(arquivo)

        nome_interno = str(getattr(arquivo_para_ler, "name", "")).lower()

        if nome_interno.endswith(".csv"):
            df = _ler_csv_com_tentativas(arquivo_para_ler)
        else:
            df = _ler_excel_multiplas_formas(arquivo_para_ler)
            df = _ajustar_header(df)

        if df is None or df.empty:
            return None

        df = df.dropna(axis=0, how="all")
        df = df.fillna("")
        df = df.astype(str).reset_index(drop=True)

        # remove colunas totalmente vazias
        colunas_validas = []
        for col in df.columns:
            serie = df[col].astype(str).map(limpar_texto)
            if (serie != "").any():
                colunas_validas.append(col)

        if colunas_validas:
            df = df[colunas_validas]

        if df.empty or len(df.columns) == 0:
            return None

        return df

    except Exception as e:
        st.error(f"Erro ao ler arquivo: {e}")
        return None


# =========================================================
# LIMPEZA / NORMALIZAÇÃO
# =========================================================
def limpar_valores_vazios(df):
    if df is None or df.empty:
        return pd.DataFrame()

    df = df.copy()

    for col in df.columns:
        df[col] = df[col].apply(limpar_texto)

    df = df.fillna("")
    df = df.astype(str)

    return df


def normalizar_colunas(df):
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
    if df is None or df.empty:
        return pd.DataFrame()

    try:
        linhas = int(linhas)
    except Exception:
        linhas = 1

    if linhas <= 0:
        linhas = 1

    return df.head(linhas)


# =========================================================
# EXPORTAÇÃO
# =========================================================
def salvar_excel_bytes(df):
    buffer = io.BytesIO()

    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Dados")

    buffer.seek(0)
    return buffer.getvalue()


def salvar_txt_bytes(texto: str):
    return str(texto).encode("utf-8")


# =========================================================
# UI
# =========================================================
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
