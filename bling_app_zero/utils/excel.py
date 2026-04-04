import io
import re
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
# LEITURA ROBUSTA
# =========================================================
def _ler_excel_multiplas_formas(arquivo):
    """
    Tenta várias formas de leitura para evitar erro no modelo do Bling
    """
    tentativas = []

    # tentativa padrão
    tentativas.append(lambda: pd.read_excel(arquivo, dtype=str))

    # sem header
    tentativas.append(lambda: pd.read_excel(arquivo, dtype=str, header=None))

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
    Detecta automaticamente a linha correta de cabeçalho
    """
    for i in range(min(10, len(df))):
        linha = df.iloc[i]

        # se tiver vários valores preenchidos → provável header
        if linha.notna().sum() > 2:
            df.columns = linha
            df = df.iloc[i + 1:]
            break

    df.columns = [str(c).strip() for c in df.columns]
    df = df.reset_index(drop=True)

    return df


def _ler_csv_com_tentativas(arquivo):
    tentativas = [
        {"sep": None, "engine": "python", "encoding": "utf-8"},
        {"sep": ";", "engine": "python", "encoding": "utf-8"},
        {"sep": ",", "engine": "python", "encoding": "utf-8"},
        {"sep": "\t", "engine": "python", "encoding": "utf-8"},
        {"sep": None, "engine": "python", "encoding": "latin-1"},
    ]

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
        except:
            continue

    raise ValueError("Erro ao ler CSV")


def ler_planilha(arquivo):
    """
    SUPER LEITOR UNIVERSAL (corrigido)
    """
    if arquivo is None:
        return None

    nome = str(getattr(arquivo, "name", "")).lower()

    try:
        # CSV
        if nome.endswith(".csv"):
            df = _ler_csv_com_tentativas(arquivo)
        else:
            df = _ler_excel_multiplas_formas(arquivo)
            df = _ajustar_header(df)

        if df is None or df.empty:
            return None

        df = df.dropna(axis=0, how="all")
        df = df.fillna("")
        df = df.astype(str)

        return df

    except Exception as e:
        st.error(f"Erro ao ler arquivo: {e}")
        return None


# =========================================================
# EXPORT
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
    estado_key = f"toggle_{chave}"
    botao_key = f"btn_{chave}"

    if estado_key not in st.session_state:
        st.session_state[estado_key] = False

    if st.button(f"👁️ {nome}", key=botao_key, use_container_width=True):
        st.session_state[estado_key] = not st.session_state[estado_key]

    return st.session_state[estado_key]
