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
    df = pd.read_excel(file, dtype=str)
    return normalizar_df(df)


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

    st.dataframe(
        df.head(5),
        height=200,
        use_container_width=True
    )

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
    # 🔥 MAPEAMENTO MANUAL
    # =========================

    st.markdown("### 🛠️ Mapeamento manual")

    usados = []
    mapeamento = {}

    for col in df.columns:

        sugestao = sugestao_automatica(col)

        opcoes = [
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

        # 🔥 BLOQUEIO DE DUPLICIDADE
        opcoes_filtradas = [
            o for o in opcoes
            if o == "" or o not in usados or o == sugestao
        ]

        escolha = st.selectbox(
            col,
            opcoes_filtradas,
            format_func=lambda x: x.upper() if x else "— NÃO MAPEAR —"
        )

        mapeamento[col] = escolha

        if escolha:
            usados.append(escolha)

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

    st.dataframe(df_final, use_container_width=True)

    # =========================
    # DOWNLOAD CORRIGIDO
    # =========================

    st.download_button(
        "Baixar entrada tratada",
        data=df_to_excel_bytes(df),  # 🔥 CORRIGIDO
        file_name="entrada.xlsx"
    )
