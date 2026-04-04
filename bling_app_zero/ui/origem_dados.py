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

CAMPO_LABELS = {
    "": "— Não mapear —",
    "codigo": "Código",
    "nome": "Nome",
    "descricao_curta": "Descrição curta",
    "descricao_complementar": "Descrição complementar",
    "preco": "Preço",
    "preco_custo": "Preço de custo",
    "estoque": "Estoque",
    "gtin": "GTIN / EAN",
    "marca": "Marca",
    "categoria": "Categoria",
    "ncm": "NCM",
    "cest": "CEST",
    "cfop": "CFOP",
    "unidade": "Unidade",
    "fornecedor": "Fornecedor",
    "cnpj_fornecedor": "CNPJ do fornecedor",
    "numero_nfe": "Número da NF-e",
    "data_emissao": "Data de emissão",
    "imagens": "Imagens",
    "origem": "Origem",
    "deposito_id": "Depósito / Estoque destino",
    "situacao": "Situação",
    "peso_liquido": "Peso líquido",
    "peso_bruto": "Peso bruto",
    "largura": "Largura",
    "altura": "Altura",
    "profundidade": "Profundidade",
    "comprimento": "Comprimento",
    "diametro": "Diâmetro",
    "volume": "Volume",
}

OPCOES_SITUACAO = ["Ativo", "Desativado"]


def _label_campo(codigo: str) -> str:
    return CAMPO_LABELS.get(codigo, codigo.replace("_", " ").strip().title())


def _normalizar_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()

    df = df.copy()
    df = df.fillna("")

    # Corrige casos em que o pandas leu as colunas como 0,1,2,3...
    if len(df.columns) > 0 and all(str(col).strip().isdigit() for col in df.columns):
        primeira_linha = [str(x).strip() for x in df.iloc[0].tolist()]
        if any(primeira_linha):
            df.columns = primeira_linha
            df = df.iloc[1:].reset_index(drop=True)

    df.columns = [str(col).strip() for col in df.columns]
    df = df.fillna("")

    return df


def _ler_csv_bytes(arquivo) -> pd.DataFrame:
    arquivo.seek(0)
    try:
        df = pd.read_csv(arquivo, dtype=str)
    except Exception:
        arquivo.seek(0)
        df = pd.read_csv(arquivo, sep=";", dtype=str)

    return _normalizar_dataframe(df)


def _ler_excel_bytes(arquivo) -> pd.DataFrame:
    arquivo.seek(0)

    # Primeira tentativa padrão
    df = pd.read_excel(arquivo, dtype=str)
    df = _normalizar_dataframe(df)

    # Se ainda vier esquisito, força leitura sem header e usa a primeira linha como cabeçalho
    if len(df.columns) > 0 and all(str(col).strip().isdigit() for col in df.columns):
        arquivo.seek(0)
        bruto = pd.read_excel(arquivo, dtype=str, header=None)
        bruto = bruto.fillna("")
        if not bruto.empty:
            bruto.columns = [str(x).strip() for x in bruto.iloc[0].tolist()]
            df = bruto.iloc[1:].reset_index(drop=True)
            df = _normalizar_dataframe(df)

    return df


def carregar_entrada_upload(arquivo) -> pd.DataFrame:
    nome = (arquivo.name or "").lower()

    if nome.endswith(".csv"):
        return _ler_csv_bytes(arquivo)

    if nome.endswith(".xlsx") or nome.endswith(".xls"):
        return _ler_excel_bytes(arquivo)

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
            "descricao_complementar",
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
            "situacao",
            "peso_liquido",
            "peso_bruto",
            "largura",
            "altura",
            "profundidade",
            "comprimento",
            "diametro",
            "volume",
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


def _aplicar_sugestao_automatica(df: pd.DataFrame, campos_validos: List[str]) -> Dict[str, str]:
    sugestoes: Dict[str, str] = {}

    for col in df.columns:
        sugestao = sugestao_automatica(col)
        sugestoes[col] = sugestao if sugestao in campos_validos else ""

    return sugestoes


def _montar_tabela_mapeamento_final(
    mapeamento_coluna_para_campo: Dict[str, str],
    situacao_fixa: str | None = None,
) -> pd.DataFrame:
    linhas = []

    for coluna_fornecedor, campo_codigo in mapeamento_coluna_para_campo.items():
        if not campo_codigo:
            continue

        linhas.append(
            {
                "Campo do painel": _label_campo(campo_codigo),
                "Código interno": campo_codigo,
                "Coluna do fornecedor": coluna_fornecedor,
            }
        )

    if situacao_fixa:
        linhas.append(
            {
                "Campo do painel": _label_campo("situacao"),
                "Código interno": "situacao",
                "Coluna do fornecedor": f"Valor fixo: {situacao_fixa}",
            }
        )

    if not linhas:
        return pd.DataFrame(columns=["Campo do painel", "Código interno", "Coluna do fornecedor"])

    return pd.DataFrame(linhas).sort_values(by=["Campo do painel"]).reset_index(drop=True)


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
    sugestoes = _aplicar_sugestao_automatica(df, campos)

    st.markdown("#### Mapeamento manual")

    mapeamento: Dict[str, str] = {}
    usados: List[str] = []

    situacao_key = "situacao_fixa"
    situacao_fixa = st.session_state.get(situacao_key, "Ativo")

    if modo == MODO_CADASTRO:
        situacao_fixa = st.selectbox(
            "Situação",
            options=OPCOES_SITUACAO,
            index=0 if situacao_fixa == "Ativo" else 1,
            key=situacao_key,
            help="Campo fixo do painel. Não depende da planilha do fornecedor.",
        )

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
            format_func=_label_campo,
        )

        mapeamento[col] = escolha

        if escolha and escolha != "situacao":
            usados.append(escolha)

    st.session_state.mapeamento_manual = mapeamento

    tabela_mapeamento = _montar_tabela_mapeamento_final(
        mapeamento_coluna_para_campo=mapeamento,
        situacao_fixa=situacao_fixa if modo == MODO_CADASTRO else None,
    )

    st.session_state.mapeamento_final_tabela = tabela_mapeamento
    st.session_state.mapeamento_final = {
        linha["Campo do painel"]: linha["Coluna do fornecedor"]
        for _, linha in tabela_mapeamento.iterrows()
    }

    with st.expander("Mapeamento final", expanded=False):
        if tabela_mapeamento.empty:
            st.warning("Nenhum campo foi mapeado ainda.")
        else:
            st.dataframe(tabela_mapeamento, width="stretch", hide_index=True)

    st.download_button(
        "Baixar entrada tratada",
        data=df_to_excel_bytes(df),
        file_name="entrada_tratada.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        width="stretch",
    )
