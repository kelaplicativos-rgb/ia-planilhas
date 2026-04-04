# 🔥 VERSÃO CORRIGIDA E EVOLUÍDA

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

OPCOES_MAPEAMENTO = [
    "",
    "codigo",
    "nome",
    "descricao_curta",
    "marca",
    "categoria",
    "gtin",
    "preco",
    "estoque",
    "peso_liquido",
    "altura",
    "largura",
    "comprimento",
]

CHAVE_MAPEAMENTO_PREVIEW = "mapeamento_preview_editor"


# =========================
# FUNÇÕES BASE
# =========================

def normalizar_df(df: pd.DataFrame) -> pd.DataFrame:
    df = df.fillna("")
    df.columns = [str(c).strip() for c in df.columns]

    # Corrigir cabeçalho errado
    if all(str(c).isdigit() for c in df.columns):
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


def _inicializar_mapeamento_preview(colunas: List[str]) -> Dict[str, str]:
    atual = st.session_state.get(CHAVE_MAPEAMENTO_PREVIEW, {}) or {}
    novo = {}

    for col in colunas:
        valor = atual.get(col, "")
        if valor not in OPCOES_MAPEAMENTO:
            valor = ""
        novo[col] = valor

    st.session_state[CHAVE_MAPEAMENTO_PREVIEW] = novo
    return novo


def _aplicar_sugestoes_iniciais(colunas: List[str]) -> Dict[str, str]:
    atual = _inicializar_mapeamento_preview(colunas).copy()

    usados = {v for v in atual.values() if v}

    for col in colunas:
        if atual.get(col):
            continue

        sugestao = sugestao_automatica(col)
        if sugestao in OPCOES_MAPEAMENTO and sugestao not in usados:
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


def _render_preview_com_terceira_linha(df: pd.DataFrame) -> Dict[str, str]:
    colunas = list(df.columns)
    mapeamento_atual = _aplicar_sugestoes_iniciais(colunas).copy()
    preview_rows = _get_preview_rows(df)

    st.markdown("### 👀 Preview (fixo)")

    # preview normal, com rolagem lateral nativa
    st.dataframe(
        preview_rows,
        width="stretch",
        height=140,
    )

    st.caption("Clique na linha abaixo para relacionar cada coluna do fornecedor com um campo do sistema.")

    usados = {v for v in mapeamento_atual.values() if v}

    df_relacionar = pd.DataFrame(
        [[mapeamento_atual.get(col, "") for col in colunas]],
        columns=colunas,
        index=["Relacionar"],
    )

    column_config = {}

    for col in colunas:
        valor_atual = mapeamento_atual.get(col, "")

        usados_por_outros = {
            v for chave, v in mapeamento_atual.items()
            if chave != col and v
        }

        opcoes_filtradas = [
            o for o in OPCOES_MAPEAMENTO
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

    for col in colunas:
        valor = str(linha_editada.get(col, "") or "").strip()
        if valor not in OPCOES_MAPEAMENTO:
            valor = ""
        novo_mapeamento[col] = valor

    novo_mapeamento = _resolver_duplicados(novo_mapeamento)
    st.session_state[CHAVE_MAPEAMENTO_PREVIEW] = novo_mapeamento

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
    # 🔥 PREÇO INTELIGENTE
    # =========================

    st.markdown("### 💰 Configuração de Preço")

    modo_preco = st.radio(
        "Como definir o preço?",
        OPCOES_PRECO
    )

    coluna_preco = None

    if modo_preco == OPCOES_PRECO[1]:
        coluna_preco = st.selectbox(
            "Selecione a coluna de preço",
            df.columns
        )

    else:
        preco_auto = calcular_preco_compra_automatico_df(df)
        st.success(f"Preço automático detectado: {preco_auto}")

    st.divider()

    # =========================
    # 🔥 MAPEAMENTO FINAL
    # =========================

    resultado = []

    for col, campo in mapeamento.items():
        if campo:
            resultado.append({
                "Campo painel": campo.upper(),
                "Origem": col
            })

    # adicionar fixos
    for campo, valor in CAMPOS_FIXOS.items():
        resultado.append({
            "Campo painel": campo.upper(),
            "Origem": f"FIXO: {valor}"
        })

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
    # DOWNLOAD CORRIGIDO
    # =========================

    st.download_button(
        "Baixar entrada tratada",
        data=df_to_excel_bytes(df),
        file_name="entrada.xlsx",
        width="stretch"
    )
