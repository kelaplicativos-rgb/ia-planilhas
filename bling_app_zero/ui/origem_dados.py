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
        # tentativa sem engine fixa primeiro
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
        existe_preco = any(
            linha["Código interno"] == "preco"
            for linha in linhas
        )
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

    return pd.DataFrame(linhas).drop_duplicates(subset=["Código interno"], keep="first").reset_index(drop=True)


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

    # Preview curto
    st.markdown("### 👀 Preview da entrada")
    st.dataframe(df.head(5), use_container_width=True, height=220)

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

    st.markdown("### 💰 Preço")
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

    st.markdown("### 🛠️ Mapeamento manual")

    mapeamento: Dict[str, str] = {}
    usados: List[str] = []

    # Reserva preco se ele estiver vindo da planilha por seletor próprio
    if preco_modo == "coluna":
        usados.append("preco")

    for col in df.columns:
        valor_inicial = ""

        if isinstance(st.session_state.get("mapeamento_manual"), dict):
            valor_inicial = st.session_state.mapeamento_manual.get(col, "")

        if not valor_inicial:
            valor_inicial = sugestoes.get(col, "")

        if preco_modo == "auto" and valor_inicial == "preco":
            valor_inicial = ""

        opcoes = [
            x for x in campos
            if x == "" or x == valor_inicial or x not in usados
        ]

        # preço não deve aparecer aqui se está sendo tratado pelo seletor acima
        if preco_modo == "auto":
            opcoes = [x for x in opcoes if x != "preco"]

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
        preco_modo=preco_modo,
        preco_coluna=preco_coluna,
    )

    st.session_state.mapeamento_final_tabela = tabela_mapeamento
    st.session_state.mapeamento_final = {
        linha["Campo do painel"]: linha["Origem"]
        for _, linha in tabela_mapeamento.iterrows()
    }

    st.markdown("### ✅ Mapeamento final")
    st.dataframe(tabela_mapeamento, use_container_width=True, hide_index=True)

    st.download_button(
        "Baixar entrada tratada",
        data=df_to_excel_bytes(df),
        file_name="entrada_tratada.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )
