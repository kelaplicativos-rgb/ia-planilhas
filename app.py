import streamlit as st
import pandas as pd
import re
import random

# =========================
# CONFIG
# =========================
st.set_page_config(page_title="🔥 IA Planilhas PRO", layout="wide")
st.title("🔥 IA Planilhas PRO - Bling Automação TOTAL")

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
# DETECÇÃO COLUNAS
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

    return mapa

# =========================
# FALLBACK DESCRIÇÃO
# =========================
def descricao_fallback(nome):
    return f"{nome} com alta qualidade, envio rápido e excelente custo-benefício. Aproveite agora!"

# =========================
# FALLBACK CATEGORIA
# =========================
def detectar_categoria(nome):
    nome = str(nome).lower()

    if "câmera" in nome:
        return "Eletrônicos"
    elif "barbeador" in nome:
        return "Beleza e Cuidados"
    elif "lanterna" in nome:
        return "Ferramentas"
    elif "brinquedo" in nome:
        return "Brinquedos"
    elif "carro" in nome:
        return "Automotivo"
    else:
        return "Geral"

# =========================
# IA DESCRIÇÃO HARD
# =========================
def gerar_descricao_ia(nome, descricao):
    try:
        prompt = f"""
        Crie uma descrição de venda PERSUASIVA nível HARD para e-commerce.

        Produto: {nome}
        Base: {descricao}

        Regras:
        - Texto vendedor forte
        - Gatilhos mentais
        - Foco em conversão
        - Máx 3 linhas
        """

        resposta = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )

        return resposta.choices[0].message.content

    except:
        return descricao_fallback(nome)

# =========================
# MONTAR BLING
# =========================
def montar_bling(df):

    mapa = detectar_colunas(df)
    novo = pd.DataFrame()

    novo["nome"] = df.get(mapa.get("nome"), "")
    novo["codigo"] = df.get(mapa.get("sku"), "")
    novo["preco"] = df.get(mapa.get("preco"), 0)
    novo["estoque"] = df.get(mapa.get("estoque"), 0)
    novo["marca"] = df.get(mapa.get("marca"), "")

    descricoes = []
    categorias = []

    for i in range(len(df)):

        nome = str(novo["nome"][i])
        desc_original = str(df.get(mapa.get("descricao"), "")[i])

        # 🔥 DESCRIÇÃO IA OU FALLBACK
        if IA_DISPONIVEL:
            desc = gerar_descricao_ia(nome, desc_original)
        else:
            desc = descricao_fallback(nome)

        descricoes.append(desc)

        # 🔥 CATEGORIA
        cat = df.get(mapa.get("categoria"), "")
        cat_val = str(cat[i]) if mapa.get("categoria") else ""

        if cat_val.strip() == "":
            cat_val = detectar_categoria(nome)

        categorias.append(cat_val)

    novo["descricao_curta"] = descricoes
    novo["categoria"] = categorias

    novo["gtin"] = df.get(mapa.get("gtin"), "")
    novo["situacao"] = "Ativo"
    novo["unidade"] = "UN"

    return novo

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

        st.success("🔥 Planilha otimizada para vendas + Bling!")
        st.dataframe(df_final.head())

        st.download_button(
            "⬇️ Baixar planilha Bling",
            df_final.to_csv(index=False),
            "bling_import.csv",
            "text/csv"
        )

    except Exception as e:
        st.error(f"Erro: {e}")
