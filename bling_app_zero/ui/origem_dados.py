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


def _texto_preview(valor, limite=80):
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


def _montar_df_preview(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()

    linha_preview = df.head(1).copy()

    for col in linha_preview.columns:
        linha_preview[col] = linha_preview[col].apply(_texto_preview)

    linha_preview.index = ["Preview"]
    return linha_preview


def _montar_df_mapeamento(colunas: List[str]) -> pd.DataFrame:
    mapeamento = _aplicar_sugestoes_iniciais(colunas)
    df_map = pd.DataFrame([mapeamento], index=["Relacionar"])
    return df_map


def _extrair_mapeamento(df_editado: pd.DataFrame) -> Dict[str, str]:
    linha = df_editado.iloc[0].to_dict()
    mapeamento = {}

    for col, valor in linha.items():
        valor = str(valor or "").strip()
        if valor not in OPCOES_MAPEAMENTO:
            valor = ""
        mapeamento[col] = valor

    mapeamento = _resolver_duplicados(mapeamento)
    st.session_state[CHAVE_MAPEAMENTO_PREVIEW] = mapeamento
    return mapeamento


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

    # =========================
    # 🔥 PREVIEW FIXO NO TOPO
    # =========================

    st.markdown("### 👀 Preview (fixo)")

    preview_df = _montar_df_preview(df)

    st.data_editor(
        preview_df,
        height=140,
        width="stretch",
        disabled=True,
        hide_index=False,
        key="preview_fornecedor_visual"
    )

    st.caption("Na linha abaixo, relacione cada coluna do fornecedor com um campo do sistema.")

    # linha de relacionamento no próprio preview
    df_mapeamento = _montar_df_mapeamento(list(df.columns))

    column_config = {
        col: st.column_config.SelectboxColumn(
            label=col,
            options=OPCOES_MAPEAMENTO,
            required=False,
            width="medium",
        )
        for col in df.columns
    }

    df_mapeamento_editado = st.data_editor(
        df_mapeamento,
        height=120,
        width="stretch",
        hide_index=False,
        num_rows="fixed",
        column_config=column_config,
        key="editor_mapeamento_no_preview"
    )

    mapeamento = _extrair_mapeamento(df_mapeamento_editado)

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
        data=df_to_excel_bytes(df),  # 🔥 CORRIGIDO
        file_name="entrada.xlsx",
        width="stretch"
    )
