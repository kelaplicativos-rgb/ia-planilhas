# (mantive seu código inteiro, só melhorei pontos críticos)

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
# ZIP (mantido)
# =========================================================
def _extrair_melhor_arquivo_do_zip(arquivo_zip):
    arquivo_zip.seek(0)

    with zipfile.ZipFile(arquivo_zip) as zf:
        nomes = [
            nome for nome in zf.namelist()
            if not nome.endswith("/") and not nome.startswith("__MACOSX/")
        ]

        if not nomes:
            raise ValueError("ZIP vazio")

        prioridade = [".xlsx", ".xls", ".csv"]

        for ext in prioridade:
            candidatos = [n for n in nomes if n.lower().endswith(ext)]
            if candidatos:
                nome_escolhido = sorted(candidatos)[0]
                with zf.open(nome_escolhido) as f:
                    conteudo = f.read()

                buffer = io.BytesIO(conteudo)
                buffer.name = nome_escolhido
                return buffer, nome_escolhido

    raise ValueError("ZIP sem arquivo válido")


# =========================================================
# LEITURA MELHORADA
# =========================================================
def _ler_excel_multiplas_formas(arquivo):
    tentativas = [
        lambda: pd.read_excel(arquivo, dtype=str),
        lambda: pd.read_excel(arquivo, dtype=str, header=None),
        lambda: pd.read_excel(arquivo, dtype=str, engine="openpyxl"),
    ]

    for tentativa in tentativas:
        try:
            arquivo.seek(0)
            df = tentativa()

            if df is not None and df.shape[1] > 0:
                return df
        except:
            continue

    raise ValueError("Falha total ao ler Excel")


def _ajustar_header(df):
    if df is None or df.empty:
        return df

    df = df.copy()

    # procura header nas primeiras 15 linhas (ANTES era 10)
    for i in range(min(15, len(df))):
        linha = df.iloc[i]
        valores = [limpar_texto(v) for v in linha.tolist()]

        preenchidos = sum(1 for v in valores if v)

        # precisa ter mais conteúdo pra ser header real
        if preenchidos >= 3:
            df.columns = valores
            df = df.iloc[i + 1:].reset_index(drop=True)
            break

    df.columns = [
        limpar_texto(c) or f"coluna_{i+1}"
        for i, c in enumerate(df.columns)
    ]

    return df


def _ler_csv_com_tentativas(arquivo):
    for enc in ["utf-8", "latin-1"]:
        for sep in [None, ";", ",", "\t"]:
            try:
                arquivo.seek(0)
                df = pd.read_csv(
                    arquivo,
                    sep=sep,
                    engine="python",
                    encoding=enc,
                    dtype=str,
                    on_bad_lines="skip",
                )
                if df is not None and len(df.columns) > 0:
                    return df
            except:
                continue

    raise ValueError("Falha ao ler CSV")


# =========================================================
# FUNÇÃO PRINCIPAL (AJUSTADA)
# =========================================================
def ler_planilha(arquivo):
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

        if df is None:
            raise ValueError("DataFrame vazio após leitura")

        df = df.dropna(axis=0, how="all")
        df = df.fillna("")
        df = df.astype(str).reset_index(drop=True)

        # REMOVE COLUNAS VAZIAS (corrigido)
        df = df.loc[:, (df != "").any(axis=0)]

        if df.empty or len(df.columns) == 0:
            raise ValueError("Planilha sem dados úteis")

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
        df.to_excel(writer, index=False)

    buffer.seek(0)
    return buffer.getvalue()


def salvar_txt_bytes(texto: str):
    return str(texto).encode("utf-8")


# =========================================================
# UI
# =========================================================
def bloco_toggle(nome, chave):
    estado_key = f"toggle_{chave}"

    if estado_key not in st.session_state:
        st.session_state[estado_key] = False

    if st.button(f"👁️ {nome}", key=f"btn_{chave}", use_container_width=True):
        st.session_state[estado_key] = not st.session_state[estado_key]

    return st.session_state[estado_key]
