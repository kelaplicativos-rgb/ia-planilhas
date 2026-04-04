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

# Fixos fora do preview
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

    df = df.copy()
    df = df.fillna("")

    # Corrige quando a primeira linha real virou dado
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
        .str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False)
        .str.replace("R$", "", regex=False)
        .str.strip()
    )
    return pd.to_numeric(serie, errors="coerce")


def _montar_tabela_mapeamento_final(
    mapeamento_coluna_para_campo: Dict[str, str],
    preco_modo: str,
    preco_coluna_custo: Optional[str],
    preco_coluna_saida: Optional[str],
    preco_preview: Optional[float],
) -> pd.DataFrame:
    linhas = []

    # Mapeamento manual: origem = planilha fornecedora / destino = campo do Bling
    for coluna_fornecedor, campo_destino in mapeamento_coluna_para_campo.items():
        if not campo_destino:
            continue

        if campo_destino == "preco":
            continue

        linhas.append(
            {
                "Campo do download": _label_campo(campo_destino),
                "Código interno": campo_destino,
                "Coluna fornecedora": coluna_fornecedor,
            }
        )

    # Preço tratado à parte
    if preco_modo == "calculadora" and preco_coluna_custo:
        origem_txt = f"CALCULADORA sobre coluna: {preco_coluna_custo}"
        if preco_preview is not None:
            origem_txt += f" | prévia média: {preco_preview:.2f}".replace(".", ",")

        linhas.append(
            {
                "Campo do download": _label_campo("preco"),
                "Código interno": "preco",
                "Coluna fornecedora": origem_txt,
            }
        )

    elif preco_modo == "coluna" and preco_coluna_saida:
        linhas.append(
            {
                "Campo do download": _label_campo("preco"),
                "Código interno": "preco",
                "Coluna fornecedora": preco_coluna_saida,
            }
        )

    # Fixos fora do preview
    for campo_fixo, valor_fixo in CAMPOS_FIXOS_CADASTRO.items():
        linhas.append(
            {
                "Campo do download": _label_campo(campo_fixo),
                "Código interno": campo_fixo,
                "Coluna fornecedora": f"VALOR FIXO: {valor_fixo}",
            }
        )

    if not linhas:
        return pd.DataFrame(columns=["Campo do download", "Código interno", "Coluna fornecedora"])

    return (
        pd.DataFrame(linhas)
        .drop_duplicates(subset=["Código interno"], keep="first")
        .reset_index(drop=True)
    )


def render_origem_dados() -> None:
    st.subheader("Origem dos dados")

    st.info(
        "Sugestão de operação: manter os campos do download/Bling como base fixa "
        "e fazer o vínculo usando as colunas da planilha fornecedora no preview."
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

        # Estrutura mínima de preview
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

    campos_destino = _campos_por_modo(modo)
    sugestoes = _aplicar_sugestao_automatica(df, campos_destino)

    st.markdown("### Definição de preço")

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

        st.caption(
            "Aqui o preço de custo base deve ser a coluna de preços/custos da planilha "
            "fornecedora, do site ou do XML."
        )

        col_calc1, col_calc2, col_calc3 = st.columns(3)

        with col_calc1:
            preco_coluna_custo = st.selectbox(
                "Preço de custo base (coluna da planilha)",
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

        with col_calc2:
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

        with col_calc3:
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

        st.success(
            f"Prévia do preço calculado pela média da coluna {preco_coluna_custo}: "
            f"R$ {preco_preview:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        )

        st.session_state.config_precificacao = {
            "modo": "calculadora",
            "coluna_custo_base": preco_coluna_custo,
            "percentual_impostos": percentual_impostos,
            "margem_lucro": margem_lucro,
            "taxa_extra": taxa_extra,
            "custo_fixo": custo_fixo,
        }

    st.divider()

    st.markdown("### Mapeamento manual no preview")
    st.caption(
        "Colunas fixas na tela = planilha fornecedora. "
        "Em cada coluna você escolhe o campo de destino do download/Bling."
    )

    usados: List[str] = []
    if preco_modo in {"calculadora", "coluna"}:
        usados.append("preco")

    mapeamento: Dict[str, str] = {}
    colunas_fornecedor = df.columns.tolist()
    colunas_ui = st.columns(len(colunas_fornecedor)) if colunas_fornecedor else []

    for idx, coluna_fornecedor in enumerate(colunas_fornecedor):
        with colunas_ui[idx]:
            st.markdown(f"**{coluna_fornecedor}**")

            preview_vals = df[coluna_fornecedor].head(5).astype(str).tolist()
            st.caption("\n".join([f"- {v}" for v in preview_vals]) if preview_vals else "-")

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

            idx_opcao = opcoes.index(valor_inicial) if valor_inicial in opcoes else 0

            escolha = st.selectbox(
                f"Destino {coluna_fornecedor}",
                options=opcoes,
                index=idx_opcao,
                key=f"map_preview_{coluna_fornecedor}",
                format_func=_label_campo,
                label_visibility="collapsed",
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
        linha["Campo do download"]: linha["Coluna fornecedora"]
        for _, linha in tabela_mapeamento.iterrows()
    }

    st.markdown("### Mapeamento final")
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
