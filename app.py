# ================================
# APP COMPLETO COM PERFIL DE COLUNAS + XML NF-E
# ================================

import pandas as pd
import streamlit as st

from bling_app_zero.core.leitor import carregar_planilha
from bling_app_zero.core.perfil_colunas import (
    carregar_perfil,
    deletar_perfil,
    salvar_perfil,
    gerar_hash_colunas,
)
from bling_app_zero.utils.excel import salvar_excel_bytes

# ================================
# CONFIG
# ================================

st.set_page_config(page_title="Bling Manual PRO", layout="wide")

MODO_CADASTRO = "Cadastro de produtos"
MODO_ESTOQUE = "Atualização de estoque"

MAPEAMENTOS_CADASTRO = [
    "",
    "Código",
    "Descrição",
    "Descrição Curta",
    "Preço",
    "Preço Custo",
    "Estoque",
    "GTIN",
    "NCM",
    "CEST",
    "CFOP",
    "Unidade",
    "Fornecedor",
    "CNPJ Fornecedor",
    "Número NF",
    "Data Emissão",
    "Marca",
    "Categoria",
]

MAPEAMENTOS_ESTOQUE = [
    "",
    "Código",
    "Descrição",
    "Estoque",
    "Preço",
    "Preço Custo",
    "Depósito",
    "Fornecedor",
    "Número NF",
    "Data Emissão",
]

# ================================
# ESTADO
# ================================

def init_state():
    if "df_origem" not in st.session_state:
        st.session_state.df_origem = None

    if "mapeamento_manual" not in st.session_state:
        st.session_state.mapeamento_manual = {}

    if "sugestao_confianca" not in st.session_state:
        st.session_state.sugestao_confianca = {}

    if "perfil_id" not in st.session_state:
        st.session_state.perfil_id = ""


def detectar_tipo_visual(arquivo) -> str:
    nome = getattr(arquivo, "name", "") or ""
    nome = nome.lower().strip()

    if nome.endswith(".xml"):
        return "XML NF-e"

    if nome.endswith(".csv"):
        return "CSV"

    if nome.endswith(".xlsx") or nome.endswith(".xls"):
        return "Planilha"

    return "Arquivo"


def sugestao_automatica_para_coluna(nome_coluna: str) -> str:
    c = str(nome_coluna).strip().lower()

    mapa = {
        "codigo": "Código",
        "código": "Código",
        "cod": "Código",
        "cprod": "Código",

        "descricao": "Descrição",
        "descrição": "Descrição",
        "descricao_curta": "Descrição Curta",
        "descrição_curta": "Descrição Curta",
        "xprod": "Descrição",
        "produto": "Descrição",
        "nome": "Descrição",

        "preco": "Preço",
        "preço": "Preço",
        "vuncom": "Preço",
        "valor_unitario_tributavel": "Preço",
        "valor unitario": "Preço",

        "preco_custo": "Preço Custo",
        "preço_custo": "Preço Custo",
        "custo": "Preço Custo",

        "estoque": "Estoque",
        "quantidade": "Estoque",
        "qcom": "Estoque",
        "qtrib": "Estoque",

        "gtin": "GTIN",
        "ean": "GTIN",
        "cean": "GTIN",
        "gtin_tributavel": "GTIN",

        "ncm": "NCM",
        "cest": "CEST",
        "cfop": "CFOP",
        "unidade": "Unidade",
        "ucom": "Unidade",
        "utrib": "Unidade",

        "emitente_nome": "Fornecedor",
        "emitente_fantasia": "Fornecedor",
        "emitente_cnpj": "CNPJ Fornecedor",

        "numero_nfe": "Número NF",
        "data_emissao": "Data Emissão",
    }

    if c in mapa:
        return mapa[c]

    if "codigo" in c or "cprod" in c:
        return "Código"
    if "descricao" in c or "descrição" in c or "xprod" in c:
        return "Descrição"
    if "preco_custo" in c or "preço_custo" in c or "custo" in c:
        return "Preço Custo"
    if "preco" in c or "preço" in c or "vuncom" in c:
        return "Preço"
    if "quantidade" in c or "estoque" in c or "qcom" in c:
        return "Estoque"
    if "gtin" in c or "ean" in c:
        return "GTIN"
    if "ncm" in c:
        return "NCM"
    if "cest" in c:
        return "CEST"
    if "cfop" in c:
        return "CFOP"
    if "unidade" in c or "ucom" in c:
        return "Unidade"
    if "emitente" in c and "cnpj" in c:
        return "CNPJ Fornecedor"
    if "emitente" in c:
        return "Fornecedor"
    if "nfe" in c and "numero" in c:
        return "Número NF"
    if "data_emissao" in c:
        return "Data Emissão"

    return ""


def opcoes_por_modo(modo: str):
    if modo == MODO_CADASTRO:
        return MAPEAMENTOS_CADASTRO
    return MAPEAMENTOS_ESTOQUE


# ================================
# APP
# ================================

def main():
    init_state()

    st.title("Bling Manual PRO")
    st.caption("Agora aceitando planilha do fornecedor e XML de NF-e.")

    modo = st.radio("Modo", [MODO_CADASTRO, MODO_ESTOQUE], horizontal=True)

    arquivo = st.file_uploader(
        "Anexar planilha do fornecedor ou XML da NF-e",
        type=["xlsx", "xls", "csv", "xml"],
    )

    if arquivo:
        tipo_visual = detectar_tipo_visual(arquivo)
        st.info(f"Arquivo detectado: **{tipo_visual}**")

        df = carregar_planilha(arquivo)

        if df is None or df.empty:
            st.error("Erro ao ler arquivo.")
            return

        st.session_state.df_origem = df

        assinatura = list(df.columns)
        perfil = carregar_perfil(assinatura)

        if perfil:
            st.session_state.mapeamento_manual = perfil
            st.session_state.perfil_id = gerar_hash_colunas(assinatura)
            st.success("✅ Perfil aplicado automaticamente!")
        else:
            st.info("Nenhum perfil encontrado para essa estrutura.")

            sugestoes = {}
            for col in df.columns:
                sugestoes[col] = sugestao_automatica_para_coluna(col)

            st.session_state.mapeamento_manual = sugestoes

        with st.expander("👀 Preview da entrada", expanded=False):
            st.dataframe(df.head(20), use_container_width=True)

        st.markdown("## Mapeamento")

        opcoes = opcoes_por_modo(modo)
        mapeamento = {}

        for col in df.columns:
            valor_atual = st.session_state.mapeamento_manual.get(col, "")
            if valor_atual not in opcoes:
                valor_atual = ""

            index_inicial = opcoes.index(valor_atual) if valor_atual in opcoes else 0

            mapeamento[col] = st.selectbox(
                f"{col}",
                opcoes,
                index=index_inicial,
                key=f"map_{col}",
            )

        st.session_state.mapeamento_manual = mapeamento

        with st.expander("🧾 Mapeamento final", expanded=False):
            st.json(mapeamento)

        st.markdown("## Perfil de Colunas")

        c1, c2 = st.columns(2)

        with c1:
            if st.button("💾 Salvar Perfil", use_container_width=True):
                hash_id = salvar_perfil(list(df.columns), mapeamento)
                st.session_state.perfil_id = hash_id
                st.success(f"Perfil salvo! ID: {hash_id}")

        with c2:
            if st.button("🗑️ Excluir Perfil", use_container_width=True):
                deletado = deletar_perfil(list(df.columns))
                if deletado:
                    st.success("Perfil deletado")
                else:
                    st.warning("Nenhum perfil encontrado")

        st.markdown("## Exportação rápida")
        st.download_button(
            "⬇️ Baixar entrada tratada em Excel",
            data=salvar_excel_bytes(df),
            file_name="entrada_tratada.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )


# ================================
# RUN
# ================================

if __name__ == "__main__":
    main()
