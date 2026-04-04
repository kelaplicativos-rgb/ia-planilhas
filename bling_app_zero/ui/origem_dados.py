import streamlit as st
import pandas as pd


# =========================
# UTIL
# =========================
def normalizar_df(df):
    df.columns = [str(c).strip() for c in df.columns]
    return df


def carregar_planilha(file):
    try:
        df = pd.read_excel(file, dtype=str, engine="openpyxl")
    except:
        df = pd.read_csv(file, dtype=str)

    return normalizar_df(df)


# =========================
# UI MAPEAMENTO COMPACTO
# =========================
def render_mapeamento(df):

    st.markdown("### 🧠 Mapeamento Manual Inteligente")

    colunas_fornecedor = list(df.columns)

    # CAMPOS DO BLING (fixos)
    campos_bling = [
        "ID",
        "Código",
        "Descrição",
        "Unidade",
        "NCM",
        "Origem",
        "Preço",
        "Valor IPI fixo",
        "Observações",
        "Situação",
        "Estoque",
        "Preço de custo",
    ]

    # estado
    if "mapeamento_manual" not in st.session_state:
        st.session_state.mapeamento_manual = {}

    mapeamento = st.session_state.mapeamento_manual

    # =========================
    # CSS COMPACTO
    # =========================
    st.markdown("""
    <style>
    .card-mini {
        padding: 6px !important;
        border-radius: 8px;
        border: 1px solid #ddd;
        margin-bottom: 6px;
        background: #fafafa;
    }

    .card-title {
        font-size: 12px;
        font-weight: 600;
        margin-bottom: 2px;
    }

    .card-preview {
        font-size: 10px;
        color: #666;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        margin-bottom: 4px;
    }

    div[data-baseweb="select"] > div {
        min-height: 30px !important;
    }
    </style>
    """, unsafe_allow_html=True)

    # =========================
    # GRID 6 COLUNAS
    # =========================
    cols = st.columns(6)

    for i, campo in enumerate(campos_bling):

        with cols[i % 6]:

            st.markdown(f'<div class="card-mini">', unsafe_allow_html=True)
            st.markdown(f'<div class="card-title">{campo}</div>', unsafe_allow_html=True)

            # preview (1 linha só)
            if colunas_fornecedor:
                exemplo = df[colunas_fornecedor[0]].iloc[0] if len(df) > 0 else ""
                st.markdown(
                    f'<div class="card-preview">{str(exemplo)[:50]}</div>',
                    unsafe_allow_html=True
                )

            # =========================
            # BLOQUEIO DE DUPLICADOS
            # =========================
            usados = list(mapeamento.values())

            valor_atual = mapeamento.get(campo)

            opcoes = ["— Não mapear —"]

            for col in colunas_fornecedor:
                if col not in usados or col == valor_atual:
                    opcoes.append(col)

            # =========================
            # SELECT
            # =========================
            selecionado = st.selectbox(
                "",
                options=opcoes,
                index=opcoes.index(valor_atual) if valor_atual in opcoes else 0,
                key=f"map_{campo}"
            )

            if selecionado == "— Não mapear —":
                mapeamento.pop(campo, None)
            else:
                mapeamento[campo] = selecionado

            st.markdown("</div>", unsafe_allow_html=True)

    st.session_state.mapeamento_manual = mapeamento


# =========================
# MAIN
# =========================
def render_origem_dados():

    st.subheader("📥 Origem de Dados")

    arquivo = st.file_uploader("Anexar planilha", type=["xlsx", "xls", "csv"])

    if not arquivo:
        return

    df = carregar_planilha(arquivo)

    st.session_state.df_origem = df

    st.success(f"✅ Planilha carregada: {df.shape[0]} linhas")

    # preview mínimo (1 linha)
    with st.expander("👀 Preview (1 linha)", expanded=False):
        st.dataframe(df.head(1), width="stretch")

    # =========================
    # MAPEAMENTO
    # =========================
    render_mapeamento(df)

    # =========================
    # DEBUG
    # =========================
    with st.expander("📊 Mapeamento atual", expanded=False):
        st.json(st.session_state.mapeamento_manual)
