from typing import Dict, List, Optional

import pandas as pd
import streamlit as st

from bling_app_zero.core.mapeamento_auto import sugestao_automatica
from bling_app_zero.core.precificacao import calcular_preco_venda
from bling_app_zero.utils.excel import df_to_excel_bytes

MODO_CADASTRO = "Cadastro de produtos"
MODO_ESTOQUE = "Atualização de estoque"

ORIGEM_PLANILHA = "Anexar planilha"
ORIGEM_XML = "Anexar XML da nota fiscal"
ORIGEM_SITE = "Buscar em site"

OPCOES_PRECO = [
    "Usar calculadora da precificação",
    "Usar coluna da planilha",
]

CAMPOS_FIXOS_CADASTRO = {
    "situacao": "Ativo",
    "condicao": "NOVO",
    "frete_gratis": "NÃO",
    "volume": "1",
    "itens_caixa": "1",
    "unidade_medida": "CENTIMETROS",
    "departamento": "ADULTO UNISSEX",
    "descricao_complementar": "NÃO RELACIONAR",
    "link_externo": "NÃO",
    "videos": "NÃO",
    "observacoes": "NÃO",
}

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
    "condicao": "Condição",
    "frete_gratis": "Frete grátis",
    "itens_caixa": "Itens para caixa",
    "unidade_medida": "Unidade de medida",
    "departamento": "Departamento",
    "link_externo": "Link externo",
    "videos": "Vídeos",
    "observacoes": "Observações",
}


def _label_campo(codigo: str) -> str:
    return CAMPO_LABELS.get(codigo, codigo.replace("_", " ").strip().title())


def _normalizar_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()

    df = df.copy().fillna("")

    if len(df.columns) > 0 and all(str(col).strip().isdigit() for col in df.columns):
        primeira_linha = [str(x).strip() for x in df.iloc[0].tolist()]
        if any(primeira_linha):
            df.columns = primeira_linha
            df = df.iloc[1:].reset_index(drop=True)

    df.columns = [str(col).strip() for col in df.columns]
    return df.fillna("")


def _ler_csv_bytes(arquivo) -> pd.DataFrame:
    arquivo.seek(0)
    try:
        df = pd.read_csv(arquivo, dtype=str)
    except Exception:
        arquivo.seek(0)
        try:
            df = pd.read_csv(arquivo, sep=";", dtype=str)
        except Exception:
            arquivo.seek(0)
            df = pd.read_csv(arquivo, sep="\t", dtype=str)

    return _normalizar_dataframe(df)


def _ler_excel_bytes(arquivo, nome_arquivo: str) -> pd.DataFrame:
    arquivo.seek(0)
    nome = (nome_arquivo or "").lower()

    if nome.endswith(".xlsx"):
        try:
            df = pd.read_excel(arquivo, dtype=str, engine="openpyxl")
            return _normalizar_dataframe(df)
        except Exception:
            arquivo.seek(0)

    try:
        df = pd.read_excel(arquivo, dtype=str)
        return _normalizar_dataframe(df)
    except Exception:
        arquivo.seek(0)
        bruto = pd.read_excel(arquivo, dtype=str, header=None, engine="openpyxl")
        bruto = bruto.fillna("")
        if bruto.empty:
            return pd.DataFrame()

        bruto.columns = [str(x).strip() for x in bruto.iloc[0].tolist()]
        df = bruto.iloc[1:].reset_index(drop=True)
        return _normalizar_dataframe(df)


def carregar_planilha(file) -> pd.DataFrame:
    nome = (getattr(file, "name", "") or "").lower()

    if nome.endswith(".csv"):
        return _ler_csv_bytes(file)

    if nome.endswith(".xlsx") or nome.endswith(".xls"):
        return _ler_excel_bytes(file, nome)

    try:
        return _ler_excel_bytes(file, nome)
    except Exception:
        file.seek(0)
        return _ler_csv_bytes(file)


def carregar_entrada_urls(texto_urls: str) -> pd.DataFrame:
    linhas = [x.strip() for x in texto_urls.splitlines() if x.strip()]
    if not linhas:
        return pd.DataFrame()

    return pd.DataFrame(
        [{"url": url, "nome": "Produto do site", "origem": "Site / URLs"} for url in linhas]
    )


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
            "peso_liquido",
            "peso_bruto",
            "largura",
            "altura",
            "profundidade",
            "comprimento",
            "diametro",
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


def _serie_numerica(df: pd.DataFrame, coluna: Optional[str]) -> pd.Series:
    if not coluna or coluna not in df.columns:
        return pd.Series(dtype=float)

    serie = (
        df[coluna]
        .astype(str)
        .str.replace("R$", "", regex=False)
        .str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False)
        .str.strip()
    )
    return pd.to_numeric(serie, errors="coerce")


def _formatar_moeda_br(valor: float) -> str:
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _preview_valor_unico(coluna: pd.Series) -> str:
    if coluna.empty:
        return "-"
    valor = str(coluna.iloc[0])
    return valor if len(valor) <= 65 else f"{valor[:62]}..."


def _montar_tabela_mapeamento_final(
    mapeamento_coluna_para_campo: Dict[str, str],
    preco_modo: str,
    preco_coluna_custo: Optional[str],
    preco_coluna_saida: Optional[str],
    preco_preview: Optional[float],
) -> pd.DataFrame:
    linhas = []

    for coluna_fornecedor, campo_destino in mapeamento_coluna_para_campo.items():
        if not campo_destino or campo_destino == "preco":
            continue

        linhas.append(
            {
                "Campo do download": _label_campo(campo_destino),
                "Código interno": campo_destino,
                "Origem": coluna_fornecedor,
            }
        )

    if preco_modo == "calculadora" and preco_coluna_custo:
        origem_txt = f"Calculadora sobre coluna: {preco_coluna_custo}"
        if preco_preview is not None:
            origem_txt += f" | prévia média: {_formatar_moeda_br(preco_preview)}"

        linhas.append(
            {
                "Campo do download": _label_campo("preco"),
                "Código interno": "preco",
                "Origem": origem_txt,
            }
        )

    elif preco_modo == "coluna" and preco_coluna_saida:
        linhas.append(
            {
                "Campo do download": _label_campo("preco"),
                "Código interno": "preco",
                "Origem": preco_coluna_saida,
            }
        )

    for campo_fixo, valor_fixo in CAMPOS_FIXOS_CADASTRO.items():
        linhas.append(
            {
                "Campo do download": _label_campo(campo_fixo),
                "Código interno": campo_fixo,
                "Origem": f"Valor fixo: {valor_fixo}",
            }
        )

    if not linhas:
        return pd.DataFrame(columns=["Campo do download", "Código interno", "Origem"])

    return (
        pd.DataFrame(linhas)
        .drop_duplicates(subset=["Código interno"], keep="first")
        .reset_index(drop=True)
    )


def _injeta_css_compacto() -> None:
    st.markdown(
        """
        <style>
        div[data-testid="stSelectbox"] label p {
            font-size: 0.78rem !important;
        }

        div[data-testid="stSelectbox"] > div {
            margin-top: -2px !important;
        }

        div[data-testid="stSelectbox"] div[data-baseweb="select"] > div {
            min-height: 34px !important;
            padding-top: 0px !important;
            padding-bottom: 0px !important;
            font-size: 0.85rem !important;
        }

        .map-card-title {
            font-size: 0.95rem;
            font-weight: 700;
            margin-bottom: 0.2rem;
        }

        .map-card-preview {
            font-size: 0.78rem;
            color: #666;
            min-height: 18px;
            margin-bottom: 0.35rem;
            line-height: 1.2;
        }

        div[data-testid="stVerticalBlock"] div[data-testid="stVerticalBlockBorderWrapper"] {
            border-radius: 10px !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_card_preview_compacto(
    coluna_fornecedor: str,
    df: pd.DataFrame,
    opcoes: List[str],
    valor_inicial: str,
    key: str,
) -> str:
    with st.container(border=True):
        st.markdown(f"<div class='map-card-title'>{coluna_fornecedor}</div>", unsafe_allow_html=True)
        st.markdown(
            f"<div class='map-card-preview'>{_preview_valor_unico(df[coluna_fornecedor])}</div>",
            unsafe_allow_html=True,
        )

        return st.selectbox(
            "Relacionar com",
            options=opcoes,
            index=opcoes.index(valor_inicial) if valor_inicial in opcoes else 0,
            key=key,
            format_func=_label_campo,
            label_visibility="collapsed",
        )


def render_origem_dados() -> None:
    st.subheader("Origem dos dados")
    _injeta_css_compacto()

    st.info(
        "Melhor operação: manter a planilha fornecedora visível e relacionar cada coluna diretamente no próprio preview."
    )

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

    if origem == ORIGEM_PLANILHA:
        arquivo = st.file_uploader(
            "Anexar planilha do fornecedor",
            type=["xlsx", "xls", "csv"],
            key="uploader_planilha",
        )
        if not arquivo:
            return
        df = carregar_planilha(arquivo)

    elif origem == ORIGEM_XML:
        arquivo = st.file_uploader(
            "Anexar XML da nota fiscal",
            type=["xml"],
            key="uploader_xml",
        )
        if not arquivo:
            return

        df = pd.DataFrame(
            [
                {
                    "codigo": "",
                    "descricao_curta": "Produto vindo do XML",
                    "preco_custo": 0.0,
                    "origem": "XML NF-e",
                }
            ]
        )

    else:
        texto_urls = st.text_area(
            "Cole uma URL por linha",
            height=120,
            key="origem_urls_texto",
        )
        if not texto_urls.strip():
            return
        df = carregar_entrada_urls(texto_urls)

    if df is None or df.empty:
        st.warning("Não foi possível ler a entrada.")
        return

    st.session_state.df_origem = df

    campos_destino = _campos_por_modo(modo)
    sugestoes = _aplicar_sugestao_automatica(df, campos_destino)

    with st.expander("Definição de preço", expanded=False):
        modo_preco_ui = st.radio(
            "Como deseja formar o preço de venda?",
            OPCOES_PRECO,
            horizontal=True,
            key="modo_preco_ui",
        )

        preco_modo = "calculadora"
        preco_coluna_custo = None
        preco_coluna_saida = None
        preco_preview = None

        if modo_preco_ui == "Usar coluna da planilha":
            preco_modo = "coluna"
            preco_coluna_saida = st.selectbox(
                "Coluna fornecedora que vai virar o preço",
                options=list(df.columns),
                key="preco_coluna_planilha",
            )
        else:
            preco_modo = "calculadora"

            c1, c2, c3 = st.columns(3)

            with c1:
                preco_coluna_custo = st.selectbox(
                    "Coluna de custo base",
                    options=list(df.columns),
                    key="preco_custo_base_coluna",
                )
                percentual_impostos = st.number_input(
                    "Impostos (%)",
                    min_value=0.0,
                    value=float(st.session_state.get("percentual_impostos", 0.0)),
                    step=0.1,
                    format="%.2f",
                    key="percentual_impostos",
                )

            with c2:
                margem_lucro = st.number_input(
                    "Lucro (%)",
                    min_value=0.0,
                    value=float(st.session_state.get("margem_lucro", 0.0)),
                    step=0.1,
                    format="%.2f",
                    key="margem_lucro",
                )
                taxa_extra = st.number_input(
                    "Taxas extras (%)",
                    min_value=0.0,
                    value=float(st.session_state.get("taxa_extra", 0.0)),
                    step=0.1,
                    format="%.2f",
                    key="taxa_extra",
                )

            with c3:
                custo_fixo = st.number_input(
                    "Valores fixos (R$)",
                    min_value=0.0,
                    value=float(st.session_state.get("custo_fixo", 0.0)),
                    step=0.01,
                    format="%.2f",
                    key="custo_fixo",
                )

            serie_custo = _serie_numerica(df, preco_coluna_custo)
            custo_base_medio = float(serie_custo.dropna().mean()) if not serie_custo.dropna().empty else 0.0

            preco_preview = calcular_preco_venda(
                preco_compra=custo_base_medio,
                percentual_impostos=percentual_impostos,
                margem_lucro=margem_lucro,
                custo_fixo=custo_fixo,
                taxa_extra=taxa_extra,
            )

            st.success(f"Prévia do preço calculado: {_formatar_moeda_br(preco_preview)}")

            st.session_state.config_precificacao = {
                "modo": "calculadora",
                "coluna_custo_base": preco_coluna_custo,
                "percentual_impostos": percentual_impostos,
                "margem_lucro": margem_lucro,
                "taxa_extra": taxa_extra,
                "custo_fixo": custo_fixo,
            }

    # fallback caso o expander não tenha sido aberto ainda
    modo_preco_ui = st.session_state.get("modo_preco_ui", OPCOES_PRECO[0])
    preco_modo = "coluna" if modo_preco_ui == "Usar coluna da planilha" else "calculadora"
    preco_coluna_custo = st.session_state.get("preco_custo_base_coluna")
    preco_coluna_saida = st.session_state.get("preco_coluna_planilha")
    preco_preview = None

    if preco_modo == "calculadora":
        serie_custo = _serie_numerica(df, preco_coluna_custo)
        custo_base_medio = float(serie_custo.dropna().mean()) if not serie_custo.dropna().empty else 0.0
        preco_preview = calcular_preco_venda(
            preco_compra=custo_base_medio,
            percentual_impostos=float(st.session_state.get("percentual_impostos", 0.0)),
            margem_lucro=float(st.session_state.get("margem_lucro", 0.0)),
            custo_fixo=float(st.session_state.get("custo_fixo", 0.0)),
            taxa_extra=float(st.session_state.get("taxa_extra", 0.0)),
        )

    st.markdown("### Relacionar no próprio preview")
    st.caption("Visual compacto: 1 exemplo por coluna e seleção direta no card.")

    usados: List[str] = []
    if preco_modo in {"calculadora", "coluna"}:
        usados.append("preco")

    colunas_fornecedor = df.columns.tolist()
    mapeamento: Dict[str, str] = {}

    grade = 3
    for inicio in range(0, len(colunas_fornecedor), grade):
        linha_cols = st.columns(grade)
        trecho = colunas_fornecedor[inicio:inicio + grade]

        for idx, coluna_fornecedor in enumerate(trecho):
            valor_inicial = ""
            if isinstance(st.session_state.get("mapeamento_manual"), dict):
                valor_inicial = st.session_state.mapeamento_manual.get(coluna_fornecedor, "")

            if not valor_inicial:
                valor_inicial = sugestoes.get(coluna_fornecedor, "")

            if valor_inicial == "preco" and preco_modo in {"calculadora", "coluna"}:
                valor_inicial = ""

            opcoes = [
                campo
                for campo in campos_destino
                if campo == "" or campo == valor_inicial or campo not in usados
            ]

            if preco_modo in {"calculadora", "coluna"}:
                opcoes = [campo for campo in opcoes if campo != "preco"]

            with linha_cols[idx]:
                escolha = _render_card_preview_compacto(
                    coluna_fornecedor=coluna_fornecedor,
                    df=df,
                    opcoes=opcoes,
                    valor_inicial=valor_inicial,
                    key=f"map_preview_{coluna_fornecedor}",
                )

            mapeamento[coluna_fornecedor] = escolha
            if escolha:
                usados.append(escolha)

    st.session_state.mapeamento_manual = mapeamento

    tabela_mapeamento = _montar_tabela_mapeamento_final(
        mapeamento_coluna_para_campo=mapeamento,
        preco_modo=preco_modo,
        preco_coluna_custo=preco_coluna_custo,
        preco_coluna_saida=preco_coluna_saida,
        preco_preview=preco_preview,
    )

    st.session_state.mapeamento_final_tabela = tabela_mapeamento
    st.session_state.mapeamento_final = {
        linha["Campo do download"]: linha["Origem"]
        for _, linha in tabela_mapeamento.iterrows()
    }

    with st.expander("Mapeamento final", expanded=False):
        st.dataframe(
            tabela_mapeamento,
            width="stretch",
            hide_index=True,
        )

    st.download_button(
        "Baixar entrada tratada",
        data=df_to_excel_bytes(df),
        file_name="entrada_tratada.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        width="stretch",
    )
