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


def _normalizar_gtin(valor) -> str:
    if pd.isna(valor):
        return ""

    texto = str(valor).strip()

    if texto == "":
        return ""

    # remove .0 típico de excel
    if texto.endswith(".0"):
        texto = texto[:-2]

    # mantém só dígitos
    texto = "".join(ch for ch in texto if ch.isdigit())

    if len(texto) in (8, 12, 13, 14):
        return texto

    return ""


def _limpar_gtin(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df

    for col in df.columns:
        if "gtin" in str(col).lower() or "ean" in str(col).lower():
            df[col] = df[col].apply(_normalizar_gtin)

    return df


def _ler_csv_seguro(arquivo):
    tentativas = [
        {"sep": ",", "encoding": "utf-8"},
        {"sep": ";", "encoding": "utf-8"},
        {"sep": ";", "encoding": "latin1"},
        {"sep": ",", "encoding": "latin1"},
        {"sep": None, "engine": "python", "encoding": "utf-8", "on_bad_lines": "skip"},
        {"sep": None, "engine": "python", "encoding": "latin1", "on_bad_lines": "skip"},
    ]

    ultimo_erro = None

    for params in tentativas:
        try:
            arquivo.seek(0)
            return pd.read_csv(arquivo, **params)
        except Exception as e:
            ultimo_erro = e

    st.error(f"Erro ao ler CSV: {ultimo_erro}")
    return None


def _gerar_sugestoes(df_origem: pd.DataFrame, colunas_modelo_ativas: list[str]) -> dict:
    """
    Compatível com as duas assinaturas possíveis do core:
    - sugestao_automatica(df)
    - sugestao_automatica(df, colunas_modelo_ativas)
    """
    try:
        sugestoes = sugestao_automatica(df_origem, colunas_modelo_ativas)
        if isinstance(sugestoes, dict):
            return sugestoes
    except TypeError:
        pass
    except Exception:
        pass

    try:
        sugestoes = sugestao_automatica(df_origem)
        if isinstance(sugestoes, dict):
            return sugestoes
    except Exception:
        pass

    return {}


def _aplicar_regras_bling_basicas(df_saida: pd.DataFrame, modo: str, deposito: str) -> pd.DataFrame:
    """
    Regras mínimas para não quebrar a planilha e manter compatibilidade com o modelo.
    Não altera layout. Só preenche campos fixos quando existirem no modelo.
    """
    if df_saida is None or df_saida.empty:
        return df_saida

    colunas_lower = {str(c).strip().lower(): c for c in df_saida.columns}

    # link externo sempre vazio
    if "link externo" in colunas_lower:
        df_saida[colunas_lower["link externo"]] = ""

    # fallback simples descrição curta / descrição
    desc = colunas_lower.get("descrição")
    desc_curta = colunas_lower.get("descrição curta")

    if desc and desc_curta:
        vazios = (
            df_saida[desc_curta].isna()
            | (df_saida[desc_curta].astype(str).str.strip() == "")
        )
        df_saida.loc[vazios, desc_curta] = df_saida.loc[vazios, desc]

    # depósito somente no fluxo estoque
    if modo == "estoque":
        for nome_col in ("depósito", "deposito"):
            if nome_col in colunas_lower:
                df_saida[colunas_lower[nome_col]] = deposito
                break

    df_saida = _limpar_gtin(df_saida)

    return df_saida


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

    # =========================
    # INPUT
    # =========================
    if origem == "Planilha":
        arquivo = st.file_uploader(
            "Envie a planilha",
            type=["xlsx", "csv"],
            key="upload_planilha_origem",
        )

        if arquivo:
            try:
                if arquivo.name.lower().endswith(".csv"):
                    df_origem = _ler_csv_seguro(arquivo)
                else:
                    df_origem = pd.read_excel(arquivo)
            except Exception as e:
                st.error(f"Erro ao ler planilha: {e}")
                return

    elif origem == "XML":
        arquivo = st.file_uploader(
            "Envie o XML",
            type=["xml"],
            key="upload_xml_origem",
        )
        if arquivo:
            st.warning("Leitura de XML em processamento...")
            return

    elif origem == "Site":
        url = st.text_input("URL do site", key="url_site_origem")
        if url:
            st.info("Captura do site em processamento...")
            return

    if df_origem is None or df_origem.empty:
        return

    origem_hash = _hash_df(df_origem)

    # reset se mudar origem
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

    # =========================
    # MODELOS
    # =========================
    modelo_cadastro = None
    modelo_estoque = None

    if modo == "cadastro":
        modelo_cadastro = st.file_uploader(
            "Modelo Cadastro",
            type=["xlsx"],
            key="upload_modelo_cadastro",
        )
    else:
        modelo_estoque = st.file_uploader(
            "Modelo Estoque",
            type=["xlsx"],
            key="upload_modelo_estoque",
        )

    if modo == "cadastro" and modelo_cadastro:
        try:
            df_modelo = pd.read_excel(modelo_cadastro)
        except Exception as e:
            st.error(f"Erro ao ler modelo de cadastro: {e}")
            return
    elif modo == "estoque" and modelo_estoque:
        try:
            df_modelo = pd.read_excel(modelo_estoque)
        except Exception as e:
            st.error(f"Erro ao ler modelo de estoque: {e}")
            return
    else:
        st.warning("Anexe o modelo correspondente.")
        return

    colunas_modelo_ativas = list(df_modelo.columns)

    # =========================
    # MAPEAMENTO
    # =========================
    sugestoes = _gerar_sugestoes(df_origem, colunas_modelo_ativas)

    if (
        "mapeamento_manual" not in st.session_state
        or not st.session_state["mapeamento_manual"]
    ):
        st.session_state["mapeamento_manual"] = sugestoes or {}

    mapa = st.session_state["mapeamento_manual"]

    st.markdown("### Preview origem")
    st.dataframe(_safe_preview(df_origem), width="stretch")

    st.markdown("### Mapeamento")

    if st.button("Limpar mapeamento", width="stretch"):
        st.session_state["mapeamento_manual"] = {}
        st.rerun()

    opcoes = [""] + list(df_origem.columns)

    for col in colunas_modelo_ativas:
        valor = mapa.get(col, "")
        if valor not in opcoes:
            valor = ""

        mapa[col] = st.selectbox(
            col,
            opcoes,
            index=opcoes.index(valor),
            key=f"map_{col}",
        )

    # =========================
    # ESTOQUE
    # =========================
    deposito = ""
    if modo == "estoque":
        deposito = st.text_input(
            "Nome do depósito",
            key="nome_deposito_estoque",
        )

    # =========================
    # MONTAGEM
    # =========================
    def montar_df():
        df_saida = pd.DataFrame(index=df_origem.index)

        for col in colunas_modelo_ativas:
            origem_col = mapa.get(col)

            if origem_col and origem_col in df_origem.columns:
                df_saida[col] = df_origem[origem_col]
            else:
                df_saida[col] = ""

        if modo == "estoque" and not deposito:
            return None

        df_saida = _aplicar_regras_bling_basicas(df_saida, modo=modo, deposito=deposito)

        # garante mesma ordem do modelo
        df_saida = df_saida.reindex(columns=colunas_modelo_ativas)

        return df_saida

    st.divider()
    st.markdown("### Preview saída")

    df_preview = montar_df()

    if modo == "estoque" and not deposito:
        st.warning("Informe o nome do depósito para gerar a planilha de estoque.")
    elif df_preview is not None:
        st.dataframe(_safe_preview(df_preview), width="stretch")

    # =========================
    # DOWNLOAD
    # =========================
    df_final = montar_df()

    if df_final is not None:
        # trava o dataframe do envio sem interferir no dataframe do download
        st.session_state["df_final"] = df_final.copy()

        excel = _exportar_df_exato_para_excel_bytes(df_final)
        nome = "cadastro.xlsx" if modo == "cadastro" else "estoque.xlsx"

        st.download_button(
            "Baixar arquivo",
            data=excel,
            file_name=nome,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            width="stretch",
        )
    else:
        st.session_state["df_final"] = None
