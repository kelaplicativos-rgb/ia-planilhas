import pandas as pd
import streamlit as st


# =========================
# UTIL
# =========================
def normalizar_df(df):
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    df = df.fillna("")
    return df


def carregar_planilha(file):
    nome = (getattr(file, "name", "") or "").lower()

    try:
        file.seek(0)
    except Exception:
        pass

    if nome.endswith(".xlsx") or nome.endswith(".xls"):
        try:
            df = pd.read_excel(file, dtype=str, engine="openpyxl")
            return normalizar_df(df)
        except Exception:
            try:
                file.seek(0)
            except Exception:
                pass

    try:
        df = pd.read_csv(file, dtype=str)
        return normalizar_df(df)
    except Exception:
        try:
            file.seek(0)
        except Exception:
            pass

    try:
        df = pd.read_csv(file, dtype=str, sep=";")
        return normalizar_df(df)
    except Exception:
        try:
            file.seek(0)
        except Exception:
            pass

    df = pd.read_excel(file, dtype=str, engine="openpyxl")
    return normalizar_df(df)


def _texto_preview(valor, limite=60):
    texto = str(valor or "").replace("\n", " ").replace("\r", " ").strip()
    if len(texto) <= limite:
        return texto
    return texto[:limite].rstrip() + "..."


# =========================
# MAPEAMENTO NO PRÓPRIO PREVIEW
# =========================
def render_mapeamento_preview(df):
    st.markdown("### Mapeamento")

    colunas_fornecedor = list(df.columns)

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

    if "mapeamento_manual" not in st.session_state:
        st.session_state.mapeamento_manual = {}

    for campo in campos_bling:
        st.session_state.mapeamento_manual.setdefault(campo, "— Não mapear —")

    usados_validos = {
        v
        for v in st.session_state.mapeamento_manual.values()
        if v != "— Não mapear —"
    }

    st.markdown(
        """
        <style>
        .map-inline-card {
            border: 1px solid rgba(128,128,128,0.20);
            border-radius: 8px;
            padding: 6px;
            margin-bottom: 8px;
            background: rgba(255,255,255,0.01);
        }

        .map-inline-title {
            font-size: 12px;
            font-weight: 700;
            margin-bottom: 2px;
            line-height: 1.1;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }

        .map-inline-preview {
            font-size: 10px;
            color: #777;
            margin-bottom: 4px;
            min-height: 14px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }

        div[data-testid="stSelectbox"] label {
            display: none !important;
        }

        div[data-baseweb="select"] > div {
            min-height: 34px !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    for inicio in range(0, len(campos_bling), 6):
        linha_campos = campos_bling[inicio:inicio + 6]
        cols = st.columns(len(linha_campos))

        for idx, campo in enumerate(linha_campos):
            with cols[idx]:
                valor_atual = st.session_state.mapeamento_manual.get(campo, "— Não mapear —")

                usados_por_outros = {
                    st.session_state.mapeamento_manual.get(outro, "— Não mapear —")
                    for outro in campos_bling
                    if outro != campo and st.session_state.mapeamento_manual.get(outro, "— Não mapear —") != "— Não mapear —"
                }

                opcoes = ["— Não mapear —"]
                for col in colunas_fornecedor:
                    if col == valor_atual or col not in usados_por_outros:
                        opcoes.append(col)

                if valor_atual not in opcoes:
                    valor_atual = "— Não mapear —"
                    st.session_state.mapeamento_manual[campo] = valor_atual

                exemplo = ""
                if valor_atual != "— Não mapear —" and valor_atual in df.columns and len(df) > 0:
                    exemplo = _texto_preview(df[valor_atual].iloc[0])

                st.markdown('<div class="map-inline-card">', unsafe_allow_html=True)
                st.markdown(
                    f'<div class="map-inline-title">{campo}</div>',
                    unsafe_allow_html=True,
                )
                st.markdown(
                    f'<div class="map-inline-preview">{exemplo if exemplo else "Sem exemplo"}</div>',
                    unsafe_allow_html=True,
                )

                selecionado = st.selectbox(
                    f"map_{campo}",
                    options=opcoes,
                    index=opcoes.index(valor_atual),
                    key=f"map_select_{campo}",
                    label_visibility="collapsed",
                )

                st.session_state.mapeamento_manual[campo] = selecionado
                st.markdown("</div>", unsafe_allow_html=True)

    st.session_state.mapeamento_manual = {
        campo: valor
        for campo, valor in st.session_state.mapeamento_manual.items()
        if valor != "— Não mapear —"
    }


# =========================
# MONTA PREVIEW CONFORME MAPEAMENTO
# =========================
def montar_preview_mapeado(df):
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

    mapeamento = st.session_state.get("mapeamento_manual", {}) or {}

    linha = {}
    for campo in campos_bling:
        coluna_origem = mapeamento.get(campo)

        if campo == "Situação":
            linha[campo] = "Ativo"
            continue

        if coluna_origem and coluna_origem in df.columns and len(df) > 0:
            linha[campo] = df[coluna_origem].iloc[0]
        else:
            linha[campo] = ""

    return pd.DataFrame([linha])


# =========================
# MAIN
# =========================
def render_origem_dados():
    st.subheader("Origem de Dados")

    arquivo = st.file_uploader("Anexar planilha do fornecedor", type=["xlsx", "xls", "csv"])

    if not arquivo:
        return

    df = carregar_planilha(arquivo)
    st.session_state.df_origem = df

    st.success(f"✅ Planilha carregada: {df.shape[0]} linhas")

    preview_df = montar_preview_mapeado(df)

    st.markdown("### Preview da entrada")
    st.dataframe(preview_df.head(1), width="stretch", height=120)

    render_mapeamento_preview(df)
