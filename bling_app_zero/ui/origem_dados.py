from __future__ import annotations

import hashlib
from io import BytesIO

import pandas as pd
import streamlit as st

from bling_app_zero.core.mapeamento_auto import sugestao_automatica


# ==========================================================
# HELPERS
# ==========================================================
def _hash_df(df: pd.DataFrame) -> str:
    return hashlib.md5(
        pd.util.hash_pandas_object(df, index=True).values.tobytes()
    ).hexdigest()


def _exportar_df_exato_para_excel_bytes(df: pd.DataFrame) -> bytes:
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)
    buffer.seek(0)
    return buffer.read()


def _safe_preview(df: pd.DataFrame, rows: int = 20) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    return df.head(rows)


# ==========================================================
# GTIN
# ==========================================================
def _normalizar_gtin(valor) -> str:
    if pd.isna(valor):
        return ""

    texto = str(valor).strip()

    if texto.endswith(".0"):
        texto = texto[:-2]

    texto = "".join(ch for ch in texto if ch.isdigit())

    if len(texto) in (8, 12, 13, 14):
        return texto

    return ""


def _limpar_gtin(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df

    for col in df.columns:
        nome_col = str(col).lower()
        if "gtin" in nome_col or "ean" in nome_col:
            df[col] = df[col].apply(_normalizar_gtin)
    return df


# ==========================================================
# LEITURA ROBUSTA DE ARQUIVOS
# ==========================================================
def _limpar_nomes_colunas(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df

    novas = []
    usados = {}

    for col in df.columns:
        nome = str(col).strip()

        if nome == "" or nome.lower() == "nan":
            nome = "SEM_NOME"

        base = nome
        contador = usados.get(base, 0)

        if contador > 0:
            nome = f"{base}_{contador}"

        usados[base] = contador + 1
        novas.append(nome)

    df.columns = novas
    return df


def _detectar_header(df_raw: pd.DataFrame) -> int:
    melhor_linha = 0
    maior_score = -1

    if df_raw is None or df_raw.empty:
        return 0

    limite = min(10, len(df_raw))

    for i in range(limite):
        linha = df_raw.iloc[i].astype(str).tolist()

        score = sum(
            1 for x in linha
            if str(x).strip() != "" and str(x).strip().lower() != "nan"
        )

        if score > maior_score:
            maior_score = score
            melhor_linha = i

    return melhor_linha


def _ler_excel_seguro(arquivo):
    motores = [None, "openpyxl", "xlrd"]

    for engine in motores:
        try:
            arquivo.seek(0)
            kwargs_raw = {"header": None}
            if engine:
                kwargs_raw["engine"] = engine

            df_raw = pd.read_excel(arquivo, **kwargs_raw)

            if df_raw is None or df_raw.empty:
                continue

            header = _detectar_header(df_raw)

            arquivo.seek(0)
            kwargs = {"header": header}
            if engine:
                kwargs["engine"] = engine

            df = pd.read_excel(arquivo, **kwargs)

            if df is not None and not df.empty:
                df = _limpar_nomes_colunas(df)
                return df

        except Exception:
            continue

    return None


def _ler_csv_seguro(arquivo):
    tentativas = [
        {"sep": ";", "encoding": "utf-8"},
        {"sep": ",", "encoding": "utf-8"},
        {"sep": ";", "encoding": "latin1"},
        {"sep": ",", "encoding": "latin1"},
        {"sep": None, "engine": "python", "encoding": "utf-8", "on_bad_lines": "skip"},
        {"sep": None, "engine": "python", "encoding": "latin1", "on_bad_lines": "skip"},
    ]

    for tentativa in tentativas:
        try:
            arquivo.seek(0)
            df_raw = pd.read_csv(arquivo, header=None, **tentativa)

            if df_raw is None or df_raw.empty:
                continue

            header = _detectar_header(df_raw)

            arquivo.seek(0)
            df = pd.read_csv(arquivo, header=header, **tentativa)

            if df is not None and not df.empty:
                df = _limpar_nomes_colunas(df)
                return df

        except Exception:
            continue

    return None


def _ler_planilha_segura(arquivo):
    nome = str(arquivo.name).lower()

    if nome.endswith(".csv"):
        return _ler_csv_seguro(arquivo)

    if nome.endswith(".xlsx") or nome.endswith(".xls"):
        return _ler_excel_seguro(arquivo)

    return None


# ==========================================================
# ESTOQUE / MAPEAMENTO
# ==========================================================
def _eh_coluna_estoque(nome: str) -> bool:
    nome = str(nome).lower()

    palavras = [
        "estoque",
        "saldo",
        "quantidade",
        "qtd",
        "qty",
        "disponivel",
        "disponível",
        "stock",
        "inventory",
        "balanco",
        "balanço",
    ]

    return any(p in nome for p in palavras)


def _normalizar_estoque_site(valor, padrao_disponivel=10):
    try:
        texto = str(valor).strip().lower()

        if (
            "esgotado" in texto
            or "indisponivel" in texto
            or "indisponível" in texto
            or "out of stock" in texto
        ):
            return 0

        if texto == "" or texto == "nan":
            return padrao_disponivel

        return int(float(valor))

    except Exception:
        return padrao_disponivel


def _gerar_sugestoes(df_origem, colunas_modelo):
    try:
        retorno = sugestao_automatica(df_origem, colunas_modelo)
        if isinstance(retorno, dict):
            return retorno
    except Exception:
        pass

    try:
        retorno = sugestao_automatica(df_origem)
        if isinstance(retorno, dict):
            return retorno
    except Exception:
        pass

    return {}


# ==========================================================
# MAIN UI
# ==========================================================
def render_origem_dados() -> None:
    st.subheader("Origem dos dados")

    origem = st.selectbox(
        "Selecione a origem",
        ["Planilha", "XML", "Site"],
        key="origem_tipo",
    )

    df_origem = None
    estoque_padrao_site = 10

    # =========================
    # INPUT
    # =========================
    if origem == "Planilha":
        arquivo = st.file_uploader(
            "Envie a planilha",
            type=["xlsx", "xls", "csv"],
            key="upload_planilha_origem",
        )

        if arquivo:
            df_origem = _ler_planilha_segura(arquivo)
            if df_origem is None or df_origem.empty:
                st.error("Erro ao ler a planilha.")
                return

    elif origem == "XML":
        st.warning("XML ainda em construção")
        return

    elif origem == "Site":
        url = st.text_input("URL do site", key="url_site_origem")

        estoque_padrao_site = st.number_input(
            "Estoque padrão quando disponível",
            min_value=0,
            value=10,
            step=1,
            key="estoque_padrao_site",
        )

        if url:
            st.info("Captura em andamento...")
            return

    if df_origem is None or df_origem.empty:
        return

    origem_hash = _hash_df(df_origem)

    if st.session_state.get("origem_hash") != origem_hash:
        st.session_state["origem_hash"] = origem_hash
        st.session_state["mapeamento_manual"] = {}
        st.session_state["df_final"] = None

    # =========================
    # MODO
    # =========================
    modo = st.radio(
        "Selecione a operação",
        ["cadastro", "estoque"],
        horizontal=True,
        key="modo_operacao_origem",
    )

    if modo == "cadastro":
        modelo = st.file_uploader(
            "Modelo Cadastro",
            type=["xlsx", "xls"],
            key="upload_modelo_cadastro",
        )
    else:
        modelo = st.file_uploader(
            "Modelo Estoque",
            type=["xlsx", "xls"],
            key="upload_modelo_estoque",
        )

    if not modelo:
        st.warning("Anexe o modelo correspondente.")
        return

    df_modelo = _ler_planilha_segura(modelo)

    if df_modelo is None or df_modelo.empty:
        st.error("Não foi possível ler o modelo.")
        return

    colunas_modelo = list(df_modelo.columns)

    sugestoes = _gerar_sugestoes(df_origem, colunas_modelo)

    if (
        "mapeamento_manual" not in st.session_state
        or not isinstance(st.session_state["mapeamento_manual"], dict)
        or not st.session_state["mapeamento_manual"]
    ):
        st.session_state["mapeamento_manual"] = (
            sugestoes.copy() if isinstance(sugestoes, dict) else {}
        )

    mapa = st.session_state["mapeamento_manual"]

    st.markdown("### Preview origem")
    st.dataframe(_safe_preview(df_origem), width="stretch")

    st.markdown("### Mapeamento")

    if st.button("Limpar mapeamento", width="stretch"):
        st.session_state["mapeamento_manual"] = {}
        st.rerun()

    opcoes = [""] + list(df_origem.columns)

    for col in colunas_modelo:
        valor_atual = mapa.get(col, "")
        if valor_atual not in opcoes:
            valor_atual = ""

        mapa[col] = st.selectbox(
            col,
            opcoes,
            index=opcoes.index(valor_atual),
            key=f"map_{col}",
        )

    # =========================
    # ESTOQUE
    # =========================
    deposito = ""
    if modo == "estoque":
        deposito = st.text_input(
            "Nome do depósito (OBRIGATÓRIO)",
            key="nome_deposito_estoque",
        )

    # =========================
    # MONTAGEM
    # =========================
    def montar_df():
        df_saida = pd.DataFrame(index=df_origem.index)

        for col in colunas_modelo:
            origem_col = mapa.get(col)

            if origem_col and origem_col in df_origem.columns:
                df_saida[col] = df_origem[origem_col]
            else:
                df_saida[col] = ""

        if origem == "Site":
            for col in df_saida.columns:
                if _eh_coluna_estoque(col):
                    df_saida[col] = df_saida[col].apply(
                        lambda x: _normalizar_estoque_site(x, estoque_padrao_site)
                    )

        if modo == "estoque":
            if not deposito:
                return None

            for col in df_saida.columns:
                nome_col = str(col).lower()
                if "deposito" in nome_col or "depósito" in nome_col:
                    df_saida[col] = deposito

        df_saida = _limpar_gtin(df_saida)
        return df_saida

    st.markdown("### Preview saída")

    df_preview = montar_df()

    if modo == "estoque" and not deposito:
        st.warning("Informe o depósito.")
    elif df_preview is not None:
        st.dataframe(_safe_preview(df_preview), width="stretch")

    df_final = montar_df()

    if df_final is not None:
        st.session_state["df_final"] = df_final.copy()

        excel = _exportar_df_exato_para_excel_bytes(df_final)
        nome_arquivo = "cadastro.xlsx" if modo == "cadastro" else "estoque.xlsx"

        st.download_button(
            "Baixar",
            data=excel,
            file_name=nome_arquivo,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            width="stretch",
        )
    else:
        st.session_state["df_final"] = None
