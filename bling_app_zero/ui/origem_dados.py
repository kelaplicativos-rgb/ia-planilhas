from typing import Dict, List

import pandas as pd
import streamlit as st

from bling_app_zero.core.mapeamento_auto import sugestao_automatica
from bling_app_zero.core.precificacao import calcular_preco_compra_automatico_df
from bling_app_zero.utils.excel import df_to_excel_bytes
from bling_app_zero.utils.numeros import format_money

MODO_CADASTRO = "Cadastro de produtos"
MODO_ESTOQUE = "Atualização de estoque"

ORIGEM_PLANILHA = "Anexar planilha"
ORIGEM_XML = "Anexar XML da nota fiscal"
ORIGEM_SITE = "Buscar em site"


def _ler_csv_bytes(arquivo) -> pd.DataFrame:
    try:
        return pd.read_csv(arquivo)
    except Exception:
        arquivo.seek(0)
        return pd.read_csv(arquivo, sep=";")


def carregar_entrada_upload(arquivo) -> pd.DataFrame:
    nome = (arquivo.name or "").lower()

    if nome.endswith(".csv"):
        return _ler_csv_bytes(arquivo)

    if nome.endswith(".xlsx") or nome.endswith(".xls"):
        return pd.read_excel(arquivo)

    if nome.endswith(".xml"):
        return pd.DataFrame(
            [
                {
                    "codigo": "",
                    "descricao_curta": "Produto vindo do XML",
                    "quantidade": 1,
                    "preco": 0.0,
                    "preco_custo": 0.0,
                    "origem": "XML NF-e",
                }
            ]
        )

    return pd.DataFrame()


def carregar_entrada_urls(texto_urls: str) -> pd.DataFrame:
    linhas = [x.strip() for x in texto_urls.splitlines() if x.strip()]
    if not linhas:
        return pd.DataFrame()

    return pd.DataFrame(
        [{"url": url, "nome": "Produto do site", "origem": "Site / URLs"} for url in linhas]
    )


def detectar_modo_visual_por_upload(arquivo) -> str:
    nome = (arquivo.name or "").lower()

    if nome.endswith(".xml"):
        return "XML NF-e"

    if nome.endswith(".csv") or nome.endswith(".xlsx") or nome.endswith(".xls"):
        return "Planilha"

    return "Arquivo"


def _campos_por_modo(modo: str) -> List[str]:
    if modo == MODO_CADASTRO:
        return [
            "",
            "codigo",
            "nome",
            "descricao_curta",
            "preco",
            "preco_custo",
            "estoque",
            "gtin",
            "marca",
            "categoria",
            "ncm",
            "cest",
            "cfop",
            "unidade",
            "fornecedor",
            "cnpj_fornecedor",
            "numero_nfe",
            "data_emissao",
            "imagens",
            "origem",
        ]

    return [
        "",
        "codigo",
        "estoque",
        "preco",
        "preco_custo",
        "deposito_id",
        "origem",
    ]


def _aplicar_sugestao_automatica(df: pd.DataFrame) -> Dict[str, str]:
    sugestoes = {}
    for col in df.columns:
        sugestoes[col] = sugestao_automatica(col)
    return sugestoes


def render_origem_dados() -> None:
    st.subheader("Origem dos dados")

    modo = st.radio(
        "Modo de operação",
        [MODO_CADASTRO, MODO_ESTOQUE],
        horizontal=True,
    )
    st.session_state.modo_operacao = modo

    origem = st.radio(
        "Escolha a origem",
        [ORIGEM_PLANILHA, ORIGEM_XML, ORIGEM_SITE],
        horizontal=True,
    )

    df = None
    tipo_visual = ""

    if origem == ORIGEM_PLANILHA:
        arquivo = st.file_uploader(
            "Anexar planilha do fornecedor",
            type=["xlsx", "xls", "csv"],
            key="uploader_planilha",
        )
        if arquivo is None:
            st.info("Envie uma planilha para continuar.")
            return

        tipo_visual = detectar_modo_visual_por_upload(arquivo)
        df = carregar_entrada_upload(arquivo)

    elif origem == ORIGEM_XML:
        arquivo = st.file_uploader(
            "Anexar XML da nota fiscal",
            type=["xml"],
            key="uploader_xml",
        )
        if arquivo is None:
            st.info("Envie um XML para continuar.")
            return

        tipo_visual = detectar_modo_visual_por_upload(arquivo)
        df = carregar_entrada_upload(arquivo)

    else:
        texto_urls = st.text_area(
            "Cole uma URL por linha",
            height=180,
            key="origem_urls_texto",
            placeholder="https://site.com/produto-1\nhttps://site.com/produto-2",
        )
        if not texto_urls.strip():
            st.info("Cole uma ou mais URLs para continuar.")
            return

        df = carregar_entrada_urls(texto_urls)
        tipo_visual = "Site / URLs"

    if df is None or df.empty:
        st.error("Não foi possível gerar dados de entrada.")
        return

    st.session_state.df_origem = df
    st.session_state.origem_atual = tipo_visual

    if tipo_visual == "XML NF-e":
        preco_auto = calcular_preco_compra_automatico_df(df)
        st.session_state.preco_compra_modulo_precificacao = preco_auto
        st.success(f"Preço de compra automático detectado: {format_money(preco_auto)}")
    else:
        st.session_state.preco_compra_modulo_precificacao = 0.0

    st.info(f"Origem atual: **{tipo_visual}**")

    with st.expander("Preview da entrada", expanded=False):
        st.dataframe(df.head(30), width="stretch")

    campos = _campos_por_modo(modo)
    sugestoes = _aplicar_sugestao_automatica(df)

    st.markdown("#### Mapeamento manual")

    mapeamento: Dict[str, str] = {}
    usados: List[str] = []

    for col in df.columns:
        valor_inicial = ""
        if isinstance(st.session_state.get("mapeamento_manual"), dict):
            valor_inicial = st.session_state.mapeamento_manual.get(col, "")

        if not valor_inicial:
            valor_inicial = sugestoes.get(col, "")

        opcoes = [x for x in campos if x == "" or x == valor_inicial or x not in usados]
        idx = opcoes.index(valor_inicial) if valor_inicial in opcoes else 0

        escolha = st.selectbox(
            label=col,
            options=opcoes,
            index=idx,
            key=f"map_{col}",
        )

        mapeamento[col] = escolha
        if escolha:
            usados.append(escolha)

    st.session_state.mapeamento_manual = mapeamento

    with st.expander("Mapeamento final", expanded=False):
        st.json(mapeamento)

    st.download_button(
        "Baixar entrada tratada",
        data=df_to_excel_bytes(df, "entrada_tratada"),
        file_name="entrada_tratada.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        width="stretch",
    )
