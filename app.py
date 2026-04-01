import streamlit as st
import pandas as pd
import re
import random

# =========================
# CONFIG
# =========================
st.set_page_config(page_title="IA Planilhas PRO", layout="wide")
st.title("🔥 IA Planilhas PRO")

# =========================
# IA (OPCIONAL)
# =========================
client = None
try:
    from openai import OpenAI
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
except:
    st.warning("⚠️ IA desativada (sem API key ou sem saldo)")

# =========================
# FUNÇÃO DE LEITURA ROBUSTA
# =========================
def ler_arquivo(arquivo):
    try:
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
# GERAR GTIN VÁLIDO (EAN-13)
# =========================
def gerar_gtin():
    base = [random.randint(0, 9) for _ in range(12)]

    soma = 0
    for i, num in enumerate(base):
        soma += num * (1 if i % 2 == 0 else 3)

    digito = (10 - (soma % 10)) % 10

    return "".join(map(str, base)) + str(digito)

# =========================
# VALIDAR GTIN
# =========================
def validar_gtin(gtin):
    gtin = str(gtin)
    gtin = re.sub(r"\D", "", gtin)

    if len(gtin) != 13:
        return False

    soma = 0
    for i, num in enumerate(gtin[:-1]):
        soma += int(num) * (1 if i % 2 == 0 else 3)

    digito = (10 - (soma % 10)) % 10

    return digito == int(gtin[-1])

# =========================
# CORRIGIR GTIN (GERAR AUTOMÁTICO)
# =========================
def corrigir_gtin(df):
    colunas_possiveis = ["gtin", "ean", "codigo_barras", "GTIN", "EAN"]

    for col in colunas_possiveis:
        if col in df.columns:
            novos = []

            for valor in df[col]:
                if validar_gtin(valor):
                    novos.append(str(valor))
                else:
                    novos.append(gerar_gtin())  # 🔥 GERA AUTOMÁTICO

            df[col] = novos

    return df

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
            # 🔥 CORREÇÃO AUTOMÁTICA DE GTIN
            df = corrigir_gtin(df)

            st.success("✅ GTINs corrigidos automaticamente!")
            st.dataframe(df)

    except Exception as e:
        st.error(f"Erro geral ao ler arquivo: {e}")

# =========================
# IA (SE DISPONÍVEL)
# =========================
if df is not None and client:
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
                                "content": f"{dados_texto}\n\nPergunta: {pergunta}"
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
