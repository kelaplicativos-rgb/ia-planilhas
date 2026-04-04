from typing import Dict, List

import pandas as pd
import streamlit as st

from bling_app_zero.core.mapeamento_auto import sugestao_automatica
from bling_app_zero.core.precificacao import calcular_preco_compra_automatico_df
from bling_app_zero.utils.excel import df_to_excel_bytes


MODO_CADASTRO = "Cadastro de produtos"
MODO_ESTOQUE = "Atualização de estoque"

ORIGEM_PLANILHA = "Anexar planilha"
ORIGEM_XML = "Anexar XML da nota fiscal"
ORIGEM_SITE = "Buscar em site"

OPCOES_SITUACAO = ["Ativo", "Desativado"]
OPCOES_PRECO = [
    "Usar precificação automática",
    "Selecionar coluna da planilha",
]

# Campos fixos que não devem depender da planilha do fornecedor
CAMPOS_FIXOS_CADASTRO = {
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

    df = df.copy()
    df = df.fillna("")

    # Caso o pandas tenha lido cabeçalhos como 0,1,2...
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
        try:
            df = pd.read_csv(arquivo, sep=";", dtype=str)
        except Exception:
            arquivo.seek(0)
            df = pd.read_csv(arquivo, sep="\t", dtype=str)

    return _normalizar_dataframe(df)


def _ler_excel_bytes(arquivo, nome_arquivo: str) -> pd.DataFrame:
    arquivo.seek(0)

    nome = (nome_arquivo or "").lower()
    engine = None

    if nome.endswith(".xlsx"):
        engine = "openpyxl"
    elif nome.endswith(".xls"):
        engine = None

    try:
        if engine:
            df = pd.read_excel(arquivo, dtype=str, engine=engine)
        else:
            df = pd.read_excel(arquivo, dtype=str)
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

    # fallback: tenta excel, depois csv
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
            "situacao",
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


def _montar_tabela_mapeamento_final(
    mapeamento_coluna_para_campo: Dict[str, str],
    situacao_fixa: str | None = None,
    preco_modo: str | None = None,
    preco_coluna: str | None = None,
) -> pd.DataFrame:
    linhas = []

    for coluna_fornecedor, campo_codigo in mapeamento_coluna_para_campo.items():
        if not campo_codigo:
            continue

        if campo_codigo == "preco" and preco_modo == "auto":
            linhas.append(
                {
                    "Campo do painel": _label_campo("preco"),
                    "Código interno": "preco",
                    "Origem": "PRECIFICAÇÃO AUTOMÁTICA",
                }
            )
            continue

        linhas.append(
            {
                "Campo do painel": _label_campo(campo_codigo),
                "Código interno": campo_codigo,
                "Origem": coluna_fornecedor,
            }
        )

    if preco_modo == "coluna" and preco_coluna:
        existe_preco = any(linha["Código interno"] == "preco" for linha in linhas)
        if not existe_preco:
            linhas.append(
                {
                    "Campo do painel": _label_campo("preco"),
                    "Código interno": "preco",
                    "Origem": preco_coluna,
                }
            )

    if situacao_fixa:
        linhas.append(
            {
                "Campo do painel": _label_campo("situacao"),
                "Código interno": "situacao",
                "Origem": f"VALOR FIXO: {situacao_fixa}",
            }
        )

    for campo_fixo, valor_fixo in CAMPOS_FIXOS_CADASTRO.items():
        linhas.append(
            {
                "Campo do painel": _label_campo(campo_fixo),
                "Código interno": campo_fixo,
                "Origem": f"VALOR FIXO: {valor_fixo}",
            }
        )

    if not linhas:
        return pd.DataFrame(columns=["Campo do painel", "Código interno", "Origem"])

    return (
        pd.DataFrame(linhas)
        .drop_duplicates(subset=["Código interno"], keep="first")
        .reset_index(drop=True)
    )


def _valor_exemplo(df: pd.DataFrame, coluna: str) -> str:
    if df is None or df.empty or coluna not in df.columns:
        return ""

    serie = df[coluna].fillna("").astype(str)
    for valor in serie.tolist():
        valor = valor.strip()
        if valor:
            return valor

    return ""


def _sugestoes_unicas_por_coluna(
    colunas_df: List[str],
    sugestoes: Dict[str, str],
    preco_modo: str,
) -> Dict[str, str]:
    """
    Gera sugestão automática sem repetir campo já sugerido em outra coluna.
    Mantém a primeira ocorrência encontrada.
    """
    usadas: set[str] = set()
    unicas: Dict[str, str] = {}

    for col in colunas_df:
        sugestao = sugestoes.get(col, "") or ""

        if preco_modo == "auto" and sugestao == "preco":
            sugestao = ""

        if sugestao and sugestao not in usadas:
            unicas[col] = sugestao
            usadas.add(sugestao)
        else:
            unicas[col] = ""

    return unicas


def _resolver_valor_inicial_mapeamento(
    coluna: str,
    sugestoes_unicas: Dict[str, str],
    campos_disponiveis: List[str],
    preco_modo: str,
) -> str:
    """
    Prioridade:
    1) valor salvo em session_state para a coluna
    2) sugestão automática única
    3) vazio
    """
    valor_salvo = ""
    estado = st.session_state.get("mapeamento_manual")

    if isinstance(estado, dict):
        valor_salvo = estado.get(coluna, "") or ""

    valor = valor_salvo or sugestoes_unicas.get(coluna, "") or ""

    if preco_modo == "auto" and valor == "preco":
        return ""

    if valor not in campos_disponiveis:
        return ""

    return valor


def _montar_opcoes_selectbox(
    campos_base: List[str],
    campo_atual: str,
    usados_por_outros: set[str],
    preco_modo: str,
) -> List[str]:
    opcoes = []

    for campo in campos_base:
        if preco_modo == "auto" and campo == "preco":
            continue

        if campo == "":
            opcoes.append(campo)
            continue

        if campo == campo_atual or campo not in usados_por_outros:
            opcoes.append(campo)

    if campo_atual and campo_atual not in opcoes:
        opcoes.append(campo_atual)

    return opcoes


def _render_css_mapeamento_compacto() -> None:
    st.markdown(
        """
        <style>
        .map-card {
            border: 1px solid rgba(128,128,128,0.22);
            border-radius: 10px;
            padding: 8px 8px 4px 8px;
            margin-bottom: 8px;
            background: rgba(255,255,255,0.01);
        }

        .map-card-titulo {
            font-size: 0.82rem;
            font-weight: 700;
            line-height: 1.1;
            margin-bottom: 2px;
        }

        .map-card-exemplo {
            font-size: 0.70rem;
            color: rgba(120,120,120,0.95);
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            margin-bottom: 2px;
        }

        div[data-testid="stSelectbox"] label p {
            font-size: 0.78rem !important;
        }

        div[data-testid="stSelectbox"] > div[data-baseweb="select"] > div {
            min-height: 34px !important;
            padding-top: 0 !important;
            padding-bottom: 0 !important;
        }

        @media (max-width: 1200px) {
            .map-card {
                padding: 7px 7px 3px 7px;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_mapeamento_manual_compacto(
    df: pd.DataFrame,
    campos: List[str],
    sugestoes: Dict[str, str],
    preco_modo: str,
) -> Dict[str, str]:
    st.markdown("### 🛠️ Mapeamento manual")
    st.caption("Visual compacto: 1 exemplo por coluna, sem repetir opções já escolhidas.")

    _render_css_mapeamento_compacto()

    colunas_df = list(df.columns)
    sugestoes_unicas = _sugestoes_unicas_por_coluna(colunas_df, sugestoes, preco_modo)

    # Estado base: recupera o que já estava salvo ou aplica sugestão única
    estado_base: Dict[str, str] = {}
    for coluna in colunas_df:
        estado_base[coluna] = _resolver_valor_inicial_mapeamento(
            coluna=coluna,
            sugestoes_unicas=sugestoes_unicas,
            campos_disponiveis=campos,
            preco_modo=preco_modo,
        )

    novo_mapeamento: Dict[str, str] = {}

    # 6 cards por linha
    for inicio in range(0, len(colunas_df), 6):
        grupo = colunas_df[inicio : inicio + 6]
        grid = st.columns(6)

        for idx, coluna in enumerate(grupo):
            with grid[idx]:
                valor_atual = estado_base.get(coluna, "") or ""

                usados_por_outros = {
                    valor
                    for outra_coluna, valor in estado_base.items()
                    if outra_coluna != coluna and valor
                }

                opcoes = _montar_opcoes_selectbox(
                    campos_base=campos,
                    campo_atual=valor_atual,
                    usados_por_outros=usados_por_outros,
                    preco_modo=preco_modo,
                )

                if valor_atual not in opcoes:
                    valor_atual = ""

                exemplo = _valor_exemplo(df, coluna)

                st.markdown('<div class="map-card">', unsafe_allow_html=True)
                st.markdown(
                    f'<div class="map-card-titulo">{coluna}</div>',
                    unsafe_allow_html=True,
                )
                st.markdown(
                    f'<div class="map-card-exemplo">{exemplo or "Sem exemplo"}</div>',
                    unsafe_allow_html=True,
                )

                escolha = st.selectbox(
                    label=coluna,
                    options=opcoes,
                    index=opcoes.index(valor_atual) if valor_atual in opcoes else 0,
                    key=f"map_{coluna}",
                    label_visibility="collapsed",
                    format_func=_label_campo,
                )

                st.markdown("</div>", unsafe_allow_html=True)

                novo_mapeamento[coluna] = escolha
                estado_base[coluna] = escolha

    st.session_state.mapeamento_manual = novo_mapeamento
    return novo_mapeamento


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
                    "quantidade": 1,
                    "preco": 0.0,
                    "preco_custo": 0.0,
                    "origem": "XML NF-e",
                }
            ]
        )

    else:
        texto_urls = st.text_area(
            "Cole uma URL por linha",
            height=150,
            key="origem_urls_texto",
        )
        if not texto_urls.strip():
            return

        df = carregar_entrada_urls(texto_urls)

    if df is None or df.empty:
        st.warning("Não foi possível ler a entrada.")
        return

    st.session_state.df_origem = df

    st.markdown("### Preview da entrada")
    st.dataframe(df.head(1), width="stretch", height=110)

    st.divider()

    campos = _campos_por_modo(modo)
    sugestoes = _aplicar_sugestao_automatica(df, campos)

    situacao_key = "situacao_fixa"
    situacao_fixa = st.session_state.get(situacao_key, "Ativo")

    if modo == MODO_CADASTRO:
        situacao_fixa = st.selectbox(
            "Situação",
            options=OPCOES_SITUACAO,
            index=0 if situacao_fixa == "Ativo" else 1,
            key=situacao_key,
        )

    st.markdown("### Preço")

    modo_preco_ui = st.radio(
        "Definição do preço",
        OPCOES_PRECO,
        horizontal=True,
        key="modo_preco_ui",
    )

    preco_modo = "auto"
    preco_coluna = None

    if modo_preco_ui == "Selecionar coluna da planilha":
        preco_modo = "coluna"
        preco_coluna = st.selectbox(
            "Coluna da planilha para preço",
            options=list(df.columns),
            key="preco_coluna_planilha",
        )
    else:
        preco_modo = "auto"
        try:
            preco_auto = calcular_preco_compra_automatico_df(df)
            st.info(f"Preço automático detectado: {preco_auto}")
        except Exception:
            st.info("Precificação automática habilitada.")

    st.divider()

    mapeamento = _render_mapeamento_manual_compacto(
        df=df,
        campos=campos,
        sugestoes=sugestoes,
        preco_modo=preco_modo,
    )

    tabela_mapeamento = _montar_tabela_mapeamento_final(
        mapeamento_coluna_para_campo=mapeamento,
        situacao_fixa=situacao_fixa if modo == MODO_CADASTRO else None,
        preco_modo=preco_modo,
        preco_coluna=preco_coluna,
    )

    st.session_state.mapeamento_final_tabela = tabela_mapeamento
    st.session_state.mapeamento_final = {
        linha["Campo do painel"]: linha["Origem"]
        for _, linha in tabela_mapeamento.iterrows()
    }

    st.markdown("### ✅ Mapeamento final")
    st.dataframe(tabela_mapeamento, width="stretch", hide_index=True)

    st.download_button(
        "Baixar entrada tratada",
        data=df_to_excel_bytes(df),
        file_name="entrada_tratada.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        width="stretch",
    )
