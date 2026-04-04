from typing import Dict, List

import pandas as pd
import streamlit as st

from bling_app_zero.core.mapeamento_auto import sugestao_automatica
from bling_app_zero.core.precificacao import calcular_preco_compra_automatico_df
from bling_app_zero.utils.excel import df_to_excel_bytes


# =========================
# CONFIG FIXA DO SISTEMA
# =========================

CAMPOS_FIXOS = {
    "condicao": "NOVO",
    "frete_gratis": "NÃO",
    "volume": 1,
    "itens_caixa": 1,
    "unidade_medida": "CENTIMETROS",
    "departamento": "ADULTO UNISSEX",
    "descricao_complementar": "NÃO",
    "link_externo": "NÃO",
    "video": "NÃO",
    "observacoes": "NÃO",
}

OPCOES_PRECO = [
    "Usar precificação automática",
    "Selecionar coluna da planilha",
]

# Lista padrão ampliada.
# Se em outro ponto do sistema existir:
# - st.session_state["colunas_modelo_cadastro"]
# ou
# - st.session_state["df_modelo_cadastro"]
# essas colunas terão prioridade e aparecerão no painel fixo.
CAMPOS_CADASTRO_BLING_PADRAO = [
    "",
    "codigo",
    "nome",
    "descricao_curta",
    "descricao_complementar",
    "marca",
    "categoria",
    "subcategoria",
    "grupo_produto",
    "fornecedor",
    "fabricante",
    "modelo",
    "colecao",
    "genero",
    "linha",
    "material",
    "garantia",
    "localizacao",
    "situacao",
    "tipo",
    "origem",
    "ncm",
    "cest",
    "gtin",
    "gtin_embalagem",
    "codigo_fabricante",
    "referencia_fabricante",
    "referencia_fornecedor",
    "unidade",
    "unidade_medida",
    "preco",
    "preco_promocional",
    "preco_custo",
    "custo",
    "lucro",
    "estoque",
    "estoque_minimo",
    "estoque_maximo",
    "deposito_id",
    "peso_liquido",
    "peso_bruto",
    "altura",
    "largura",
    "comprimento",
    "diametro",
    "formato_embalagem",
    "volume",
    "itens_caixa",
    "volumes",
    "dias_preparacao",
    "dias_garantia",
    "condicao",
    "frete_gratis",
    "descricao_html",
    "descricao_completa",
    "seo_title",
    "seo_description",
    "palavras_chave",
    "slug",
    "link_externo",
    "video",
    "url_video",
    "observacoes",
    "imagem_1",
    "imagem_2",
    "imagem_3",
    "imagem_4",
    "imagem_5",
    "imagem_6",
    "imagem_7",
    "imagem_8",
    "imagem_9",
    "imagem_10",
    "variacao_nome",
    "variacao_valor",
    "tributacao",
    "classe_fiscal",
    "tipo_producao",
    "departamento",
]

CHAVE_MAPEAMENTO_PREVIEW = "mapeamento_preview_editor"
CHAVE_OPCOES_MAPEAMENTO = "opcoes_mapeamento_preview"


# =========================
# FUNÇÕES BASE
# =========================

def normalizar_df(df: pd.DataFrame) -> pd.DataFrame:
    df = df.fillna("")
    df.columns = [str(c).strip() for c in df.columns]

    # Corrigir cabeçalho errado
    if len(df.columns) > 0 and all(str(c).isdigit() for c in df.columns):
        df.columns = df.iloc[0]
        df = df.iloc[1:].reset_index(drop=True)

    return df


def carregar_planilha(file):
    nome = (getattr(file, "name", "") or "").lower()

    if nome.endswith(".csv"):
        try:
            file.seek(0)
            df = pd.read_csv(file, dtype=str)
            return normalizar_df(df)
        except Exception:
            file.seek(0)
            df = pd.read_csv(file, dtype=str, sep=";")
            return normalizar_df(df)

    file.seek(0)
    df = pd.read_excel(file, dtype=str)
    return normalizar_df(df)


def _texto_preview(valor, limite=60):
    texto = str(valor or "").replace("\n", " ").replace("\r", " ").strip()
    if len(texto) <= limite:
        return texto
    return texto[:limite].rstrip() + "..."


def _obter_campos_modelo_bling() -> List[str]:
    """
    Prioridade:
    1) st.session_state['colunas_modelo_cadastro']
    2) st.session_state['df_modelo_cadastro'].columns
    3) lista padrão ampliada
    """
    colunas_modelo = st.session_state.get("colunas_modelo_cadastro")
    if isinstance(colunas_modelo, list) and colunas_modelo:
        opcoes = [""] + [str(c).strip() for c in colunas_modelo if str(c).strip()]
        return list(dict.fromkeys(opcoes))

    df_modelo = st.session_state.get("df_modelo_cadastro")
    if isinstance(df_modelo, pd.DataFrame) and len(df_modelo.columns) > 0:
        opcoes = [""] + [str(c).strip() for c in df_modelo.columns if str(c).strip()]
        return list(dict.fromkeys(opcoes))

    return list(dict.fromkeys(CAMPOS_CADASTRO_BLING_PADRAO))


def _inicializar_mapeamento_preview(
    colunas_fornecedor: List[str],
    opcoes_mapeamento: List[str],
) -> Dict[str, str]:
    atual = st.session_state.get(CHAVE_MAPEAMENTO_PREVIEW, {}) or {}
    novo = {}

    for col in colunas_fornecedor:
        valor = str(atual.get(col, "") or "").strip()
        if valor not in opcoes_mapeamento:
            valor = ""
        novo[col] = valor

    st.session_state[CHAVE_MAPEAMENTO_PREVIEW] = novo
    st.session_state[CHAVE_OPCOES_MAPEAMENTO] = opcoes_mapeamento
    return novo


def _aplicar_sugestoes_iniciais(
    colunas_fornecedor: List[str],
    opcoes_mapeamento: List[str],
) -> Dict[str, str]:
    atual = _inicializar_mapeamento_preview(colunas_fornecedor, opcoes_mapeamento).copy()
    usados = {v for v in atual.values() if v}

    for col in colunas_fornecedor:
        if atual.get(col):
            continue

        sugestao = sugestao_automatica(col)
        if sugestao in opcoes_mapeamento and sugestao not in usados:
            atual[col] = sugestao
            usados.add(sugestao)

    st.session_state[CHAVE_MAPEAMENTO_PREVIEW] = atual
    return atual


def _resolver_duplicados(mapeamento: Dict[str, str]) -> Dict[str, str]:
    vistos = set()
    corrigido = {}

    for col, campo in mapeamento.items():
        if not campo:
            corrigido[col] = ""
            continue

        if campo in vistos:
            corrigido[col] = ""
        else:
            corrigido[col] = campo
            vistos.add(campo)

    return corrigido


def _get_preview_rows(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()

    qtd = min(2, len(df))
    preview = df.head(qtd).copy()

    for col in preview.columns:
        preview[col] = preview[col].apply(_texto_preview)

    preview.index = [f"Linha {i+1}" for i in range(len(preview))]
    return preview


def _limpar_mapeamento_preview(colunas_fornecedor: List[str]) -> None:
    st.session_state[CHAVE_MAPEAMENTO_PREVIEW] = {col: "" for col in colunas_fornecedor}
    if "editor_relacionar_preview" in st.session_state:
        del st.session_state["editor_relacionar_preview"]


def _render_preview_com_terceira_linha(df: pd.DataFrame) -> Dict[str, str]:
    colunas_fornecedor = list(df.columns)
    opcoes_mapeamento = _obter_campos_modelo_bling()
    mapeamento_atual = _aplicar_sugestoes_iniciais(colunas_fornecedor, opcoes_mapeamento).copy()
    preview_rows = _get_preview_rows(df)

    st.markdown("### Preview (fixo)")
    st.dataframe(
        preview_rows,
        width="stretch",
        height=140,
    )

    st.caption(
        "Relacione cada coluna do fornecedor diretamente na terceira linha. "
        "O painel fixo usa todas as colunas disponíveis do cadastro do Bling "
        "que estiverem disponíveis no sistema."
    )

    c1, c2, c3 = st.columns([1, 1, 1])

    with c1:
        st.info(f"Colunas do fornecedor: {len(colunas_fornecedor)}")

    with c2:
        qtd_campos_bling = len([x for x in opcoes_mapeamento if x])
        st.info(f"Campos do Bling no painel: {qtd_campos_bling}")

    with c3:
        qtd_relacionados = len([v for v in mapeamento_atual.values() if v])
        st.info(f"Mapeados: {qtd_relacionados}")

    if st.button("🧹 Limpar mapeamento", use_container_width=True):
        _limpar_mapeamento_preview(colunas_fornecedor)
        st.rerun()

    df_relacionar = pd.DataFrame(
        [[mapeamento_atual.get(col, "") for col in colunas_fornecedor]],
        columns=colunas_fornecedor,
        index=["Relacionar"],
    )

    column_config = {}
    for col in colunas_fornecedor:
        valor_atual = mapeamento_atual.get(col, "")
        usados_por_outros = {
            v for chave, v in mapeamento_atual.items()
            if chave != col and v
        }

        opcoes_filtradas = [
            o for o in opcoes_mapeamento
            if o == "" or o == valor_atual or o not in usados_por_outros
        ]

        column_config[col] = st.column_config.SelectboxColumn(
            label=col,
            options=opcoes_filtradas,
            required=False,
            width="medium",
        )

    df_relacionar_editado = st.data_editor(
        df_relacionar,
        width="stretch",
        height=90,
        hide_index=False,
        num_rows="fixed",
        column_config=column_config,
        key="editor_relacionar_preview",
    )

    novo_mapeamento = {}
    linha_editada = df_relacionar_editado.iloc[0].to_dict()

    for col in colunas_fornecedor:
        valor = str(linha_editada.get(col, "") or "").strip()
        if valor not in opcoes_mapeamento:
            valor = ""
        novo_mapeamento[col] = valor

    novo_mapeamento = _resolver_duplicados(novo_mapeamento)
    st.session_state[CHAVE_MAPEAMENTO_PREVIEW] = novo_mapeamento

    with st.expander("Ver todos os campos disponíveis do painel fixo", expanded=False):
        campos_visiveis = [campo for campo in opcoes_mapeamento if campo]
        st.write(campos_visiveis)

    return novo_mapeamento


# =========================
# UI PRINCIPAL
# =========================

def render_origem_dados():
    st.subheader("Origem dos dados")

    arquivo = st.file_uploader("Anexar planilha", type=["xlsx", "xls", "csv"])
    if not arquivo:
        return

    df = carregar_planilha(arquivo)
    st.session_state.df_origem = df

    mapeamento = _render_preview_com_terceira_linha(df)

    st.divider()

    # =========================
    # PREÇO INTELIGENTE
    # =========================
    st.markdown("### Configuração de Preço")

    modo_preco = st.radio(
        "Como definir o preço?",
        OPCOES_PRECO,
    )

    coluna_preco = None
    if modo_preco == OPCOES_PRECO[1]:
        coluna_preco = st.selectbox(
            "Selecione a coluna de preço",
            df.columns,
        )
        st.session_state["coluna_preco_manual"] = coluna_preco
    else:
        preco_auto = calcular_preco_compra_automatico_df(df)
        st.success(f"Preço automático detectado: {preco_auto}")

    st.divider()

    # =========================
    # MAPEAMENTO FINAL
    # =========================
    resultado = []

    for col, campo in mapeamento.items():
        if campo:
            resultado.append(
                {
                    "Campo painel": campo.upper(),
                    "Origem": col,
                }
            )

    for campo, valor in CAMPOS_FIXOS.items():
        resultado.append(
            {
                "Campo painel": campo.upper(),
                "Origem": f"FIXO: {valor}",
            }
        )

    df_final = pd.DataFrame(resultado)

    st.markdown("### ✅ Mapeamento final")
    st.dataframe(df_final, width="stretch")

    # compatibilidade com o restante do sistema
    st.session_state.mapeamento_manual = mapeamento
    st.session_state.mapeamento_final = {
        item["Campo painel"]: item["Origem"]
        for item in resultado
    }

    # =========================
    # DOWNLOAD
    # =========================
    st.download_button(
        "Baixar entrada tratada",
        data=df_to_excel_bytes(df),
        file_name="entrada.xlsx",
        width="stretch",
    )
