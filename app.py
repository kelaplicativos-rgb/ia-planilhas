import streamlit as st
import pandas as pd
from openai import OpenAI

# =========================
# CONFIG
# =========================
st.set_page_config(page_title="IA Planilhas PRO", layout="wide")
st.title("🔥 IA Planilhas PRO")

# =========================
# API KEY
# =========================
try:
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
except:
    st.error("⚠️ Configure sua OPENAI_API_KEY nos Secrets do Streamlit")
    st.stop()

# =========================
# FUNÇÃO DE LEITURA ROBUSTA
# =========================
def ler_arquivo(arquivo):
    try:
        # tentativa automática (melhor opção)
        df = pd.read_csv(
            arquivo,
            sep=None,
            engine="python",
            encoding="utf-8",
            on_bad_lines="skip"
        )
        return df, "utf-8 automático"
    except:
        try:
            # fallback comum (Brasil)
            df = pd.read_csv(
                arquivo,
                sep=";",
                engine="python",
                encoding="latin-1",
                on_bad_lines="skip"
            )
            return df, "latin-1 com ;"
        except Exception as e:
            return None, str(e)

# =========================
# UPLOAD
# =========================
arquivo = st.file_uploader(
    "📂 Envie sua planilha (CSV ou Excel)",
    type=["csv", "xlsx"]
)

df = None

if arquivo is not None:
    try:
        if arquivo.name.endswith(".csv"):
            df, info = ler_arquivo(arquivo)

            if df is not None:
                st.success(f"✅ CSV carregado com sucesso ({info})")
                st.warning("⚠️ Linhas inválidas podem ter sido ignoradas automaticamente")
            else:
                st.error(f"Erro ao ler CSV: {info}")

        else:
            df = pd.read_excel(arquivo)
            st.success("✅ Excel carregado com sucesso!")

        if df is not None:
            st.dataframe(df)

    except Exception as e:
        st.error(f"Erro geral ao ler arquivo: {e}")

# =========================
# PERGUNTA IA
# =========================
if df is not None:
    st.subheader("🤖 Análise com IA")

    pergunta = st.text_area("💬 Pergunte algo sobre sua planilha:")

    if st.button("🚀 Analisar com IA"):
        if pergunta.strip() == "":
            st.warning("Digite uma pergunta")
        else:
            with st.spinner("Processando com IA..."):

                try:
                    dados_texto = df.head(50).to_csv(index=False)

                    resposta = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[
                            {
                                "role": "system",
                                "content": "Você é um especialista em análise de planilhas e dados comerciais."
                            },
                            {
                                "role": "user",
                                "content": f"""
                                Analise a planilha abaixo:

                                {dados_texto}

                                Pergunta:
                                {pergunta}
                                """
                            }
                        ]
                    )

                    st.subheader("📊 Resultado:")
                    st.write(resposta.choices[0].message.content)

                except Exception as e:
                    st.error(f"Erro na IA: {e}")

# =========================
# DOWNLOAD
# =========================
if df is not None:
    st.subheader("📥 Exportar")

    st.download_button(
        "⬇️ Baixar planilha tratada (CSV)",
        data=df.to_csv(index=False),
        file_name="planilha_tratada.csv",
        mime="text/csv"
    )
