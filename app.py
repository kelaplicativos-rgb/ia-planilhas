import streamlit as st
import pandas as pd
import re
import random
import time

# =========================
# CONFIG
# =========================
st.set_page_config(page_title="🔥 IA Planilhas PRO", layout="wide")
st.title("🔥 IA Planilhas PRO - Bling Automação")

# =========================
# CONTROLE STOP
# =========================
if "stop" not in st.session_state:
    st.session_state.stop = False

def parar():
    st.session_state.stop = True

st.button("🛑 PARAR PROCESSAMENTO", on_click=parar)

# =========================
# IA
# =========================
client = None
IA_DISPONIVEL = False

try:
    from openai import OpenAI
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
    IA_DISPONIVEL = True
except:
    st.warning("⚠️ IA offline (modo automático ativado)")

# =========================
# LEITURA
# =========================
def ler_arquivo(arquivo):
    try:
        return pd.read_csv(arquivo, sep=None, engine="python", encoding="utf-8", on_bad_lines="skip")
    except:
        return pd.read_csv(arquivo, sep=";", engine="python", encoding="latin-1", on_bad_lines="skip")

# =========================
# GTIN
# =========================
def gerar_gtin():
    base = [random.randint(0, 9) for _ in range(12)]
    soma = sum(num * (1 if i % 2 == 0 else 3) for i, num in enumerate(base))
    digito = (10 - (soma % 10)) % 10
    return "".join(map(str, base)) + str(digito)

def validar_gtin(gtin):
    gtin = re.sub(r"\D", "", str(gtin))
    if len(gtin) != 13:
        return False
    soma = sum(int(num) * (1 if i % 2 == 0 else 3) for i, num in enumerate(gtin[:-1]))
    digito = (10 - (soma % 10)) % 10
    return digito == int(gtin[-1])

def corrigir_gtin(df):
    for col in df.columns:
        if "gtin" in col.lower() or "ean" in col.lower():
            df[col] = df[col].apply(lambda x: x if validar_gtin(x) else gerar_gtin())
    return df

# =========================
# DETECÇÃO INTELIGENTE
# =========================
def detectar_colunas(df):
    mapa = {}
    for col in df.columns:
        nome = col.lower()

        if "nome" in nome or "produto" in nome:
            mapa["nome"] = col
        elif "sku" in nome or "codigo" in nome:
            mapa["sku"] = col
        elif "preco" in nome:
            mapa["preco"] = col
        elif "estoque" in nome or "quantidade" in nome:
            mapa["estoque"] = col
        elif "marca" in nome:
            mapa["marca"] = col
        elif "categoria" in nome:
            mapa["categoria"] = col
        elif "descricao" in nome:
            mapa["descricao"] = col
        elif "ean" in nome or "gtin" in nome:
            mapa["gtin"] = col
        elif "imagem" in nome or "url" in nome:
            mapa["imagem"] = col
        elif "link" in nome:
            mapa["link"] = col

    return mapa

# =========================
# IA DESCRIÇÃO
# =========================
def gerar_descricao_ia(nome, desc_base):
    if not IA_DISPONIVEL:
        return f"{nome} de alta qualidade. Ideal para uso profissional."

    try:
        prompt = f"""
        Produto: {nome}
        Base: {desc_base}

        Gere uma descrição curta altamente persuasiva para vendas.
        """

        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=80
        )

        return resp.choices[0].message.content.strip()

    except:
        return f"{nome} de alta qualidade."

# =========================
# MONTAR BLING (CORRIGIDO)
# =========================
def montar_bling(df):

    mapa = detectar_colunas(df)

    total = len(df)
    progresso = st.progress(0)
    status = st.empty()

    inicio = time.time()

    # 🔥 MODELO PADRÃO BLING
    colunas_bling = [
        "Código", "Descrição", "Unidade", "Preço", "Situação",
        "Marca", "Descrição Curta", "URL Imagens Externas",
        "Link Externo", "GTIN/EAN"
    ]

    resultado = []

    for i, row in df.iterrows():

        if st.session_state.stop:
            st.error("⛔ Processamento interrompido")
            return pd.DataFrame()

        nome = str(row.get(mapa.get("nome", ""), ""))
        sku = row.get(mapa.get("sku", ""), "")
        preco = row.get(mapa.get("preco", ""), 0)
        marca = row.get(mapa.get("marca", ""), "")
        desc = str(row.get(mapa.get("descricao", ""), ""))
        gtin = row.get(mapa.get("gtin", ""), "")
        imagem = row.get(mapa.get("imagem", ""), "")
        link = row.get(mapa.get("link", ""), "")

        # descrição automática se vazio
        if not desc or desc == "nan":
            desc = gerar_descricao_ia(nome, "")

        # imagens formato Bling
        if isinstance(imagem, str):
            imagem = imagem.replace(",", ";")

        linha = {col: "" for col in colunas_bling}

        linha["Código"] = sku
        linha["Descrição"] = nome
        linha["Unidade"] = "UN"
        linha["Preço"] = preco
        linha["Situação"] = "Ativo"
        linha["Marca"] = marca
        linha["Descrição Curta"] = desc
        linha["URL Imagens Externas"] = imagem
        linha["Link Externo"] = link
        linha["GTIN/EAN"] = gtin

        resultado.append(linha)

        # progresso
        pct = int((i+1)/total*100)
        tempo = time.time() - inicio
        restante = (tempo/(i+1))*(total-(i+1))

        progresso.progress(pct)
        status.text(f"Processando {pct}% | ⏱ {int(restante)}s restantes")

    return pd.DataFrame(resultado)

# =========================
# UPLOAD
# =========================
arquivo = st.file_uploader("📂 Envie sua planilha", type=["csv", "xlsx"])

if arquivo:
    try:
        df = ler_arquivo(arquivo) if arquivo.name.endswith(".csv") else pd.read_excel(arquivo)

        st.success("✅ Arquivo carregado")
        st.dataframe(df.head())

        df = corrigir_gtin(df)

        df_final = montar_bling(df)

        if not df_final.empty:
            st.success("✅ Pronto para Bling")
            st.dataframe(df_final.head())

            st.download_button(
                "⬇️ Baixar planilha Bling",
                df_final.to_csv(index=False),
                "bling_import.csv",
                "text/csv"
            )

    except Exception as e:
        st.error(f"Erro: {e}")
