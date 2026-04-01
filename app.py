import streamlit as st
import pandas as pd
import io
from openai import OpenAI

st.set_page_config(page_title="🔥 IA Planilhas PRO", layout="wide")
st.title("🔥 IA Planilhas PRO - Automação Bling")

# =========================
# API (OPCIONAL)
# =========================
client = None
try:
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
except:
    st.warning("⚠️ IA desativada (sem API key ou sem saldo)")

# =========================
# FUNÇÃO: LER CSV SUJO
# =========================
def ler_csv_seguro(arquivo):
    try:
        return pd.read_csv(arquivo, sep=None, engine="python", encoding="utf-8", on_bad_lines="skip")
    except:
        try:
            return pd.read_csv(arquivo, sep=";", encoding="latin-1", on_bad_lines="skip")
        except:
            return pd.read_csv(arquivo, sep=",", encoding="latin-1", on_bad_lines="skip")

# =========================
# FUNÇÃO: LIMPAR DADOS
# =========================
def limpar_dados(df):
    df = df.copy()

    # Remove espaços
    df.columns = df.columns.str.strip()

    # Remove colunas vazias
    df = df.dropna(axis=1, how='all')

    # Preenche vazios
    df = df.fillna("")

    return df

# =========================
# FUNÇÃO: PADRÃO BLING
# =========================
def padronizar_bling(df):
    df = df.copy()

    # Garante colunas básicas
    colunas = {
        "codigo": "CODIGO",
        "sku": "SKU",
        "nome": "NOME",
        "preco": "PRECO",
        "descricao": "DESCRICAO"
    }

    for col in colunas:
        if col not in df.columns:
            df[col] = ""

    return df

# =========================
# UPLOAD
# =========================
arquivo = st.file_uploader("📂 Envie CSV ou Excel", type=["csv", "xlsx"])

df = None

if arquivo:
    try:
        if arquivo.name.endswith(".csv"):
            df = ler_csv_seguro(arquivo)
        else:
            df = pd.read_excel(arquivo)

        df = limpar_dados(df)
        df = padronizar_bling(df)

        st.success("✅ Planilha carregada e limpa!")
        st.dataframe(df)

    except Exception as e:
        st.error(f"Erro ao ler: {e}")

# =========================
# IA (OPCIONAL)
# =========================
if df is not None and client:
    pergunta = st.text_area("💬 Pergunte algo:")

    if st.button("🚀 Analisar com IA"):
        with st.spinner("Processando..."):
            try:
                dados = df.head(30).to_csv(index=False)

                resposta = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "Especialista em Bling e planilhas"},
                        {"role": "user", "content": f"{dados}\n\nPergunta: {pergunta}"}
                    ]
                )

                st.write(resposta.choices[0].message.content)

            except Exception as e:
                st.error(f"Erro IA: {e}")

# =========================
# DOWNLOAD
# =========================
if df is not None:
    st.download_button(
        "⬇️ Baixar planilha corrigida",
        data=df.to_csv(index=False),
        file_name="bling_corrigido.csv",
        mime="text/csv"
    )
