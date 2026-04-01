import streamlit as st
import pandas as pd
import re
import random
import time
from concurrent.futures import ThreadPoolExecutor

# =========================
# CONFIG
# =========================
st.set_page_config(page_title="🔥 IA Planilhas PRO", layout="wide")
st.title("🔥 IA Planilhas PRO - Bling Automação")

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
    st.warning("⚠️ IA offline ativada")

# =========================
# LOG
# =========================
logs = []

def log(msg):
    logs.append(msg)

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
# DETECÇÃO
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
        elif "estoque" in nome:
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
# DESCRIÇÃO HARD (OFFLINE)
# =========================
def gerar_descricao(nome):
    return f"""
🔥 {nome}

Produto de alta qualidade com excelente custo-benefício.
Ideal para quem busca desempenho, durabilidade e praticidade.

💥 Garanta já o seu antes que acabe!
"""

# =========================
# CATEGORIA AUTOMÁTICA
# =========================
def gerar_categoria(nome):
    nome = str(nome).lower()

    if "camera" in nome:
        return "Eletrônicos"
    elif "barbeador" in nome:
        return "Beleza"
    elif "lanterna" in nome:
        return "Ferramentas"
    else:
        return "Geral"

# =========================
# FUNÇÃO SEGURA (ANTI ERRO)
# =========================
def pegar_valor(df, coluna, i):
    try:
        if coluna in df.columns:
            return str(df.iloc[i][coluna])
        return ""
    except:
        return ""

# =========================
# MONTAR BLING
# =========================
def montar_bling(df):

    mapa = detectar_colunas(df)

    total = len(df)
    progress = st.progress(0)
    status = st.empty()

    resultado = []

    inicio = time.time()

    def processar_linha(i):
        nome = pegar_valor(df, mapa.get("nome", ""), i)
        desc = pegar_valor(df, mapa.get("descricao", ""), i)
        categoria = pegar_valor(df, mapa.get("categoria", ""), i)

        # descrição IA / fallback
        if IA_DISPONIVEL and nome:
            try:
                r = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{
                        "role": "user",
                        "content": f"Crie descrição persuasiva para: {nome}"
                    }]
                )
                desc_final = r.choices[0].message.content
            except:
                desc_final = gerar_descricao(nome)
        else:
            desc_final = gerar_descricao(nome)

        # categoria automática
        if not categoria:
            categoria = gerar_categoria(nome)

        return {
            "nome": nome,
            "codigo": pegar_valor(df, mapa.get("sku", ""), i),
            "preco": pegar_valor(df, mapa.get("preco", ""), i),
            "estoque": pegar_valor(df, mapa.get("estoque", ""), i),
            "marca": pegar_valor(df, mapa.get("marca", ""), i),
            "categoria": categoria,
            "descricao_curta": desc_final,
            "gtin": pegar_valor(df, mapa.get("gtin", ""), i),
            "situacao": "Ativo",
            "unidade": "UN"
        }

    # 🚀 PARALELISMO
    with ThreadPoolExecutor(max_workers=5) as executor:
        for i, res in enumerate(executor.map(processar_linha, range(total))):
            resultado.append(res)

            progresso = (i + 1) / total
            tempo = time.time() - inicio
            restante = (tempo / (i + 1)) * (total - (i + 1))

            progress.progress(progresso)
            status.text(f"Processando {i+1}/{total} | ⏱️ {restante:.1f}s restantes")

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

        st.success("✅ Pronto para Bling!")
        st.dataframe(df_final.head())

        st.download_button(
            "⬇️ Baixar CSV Bling",
            df_final.to_csv(index=False),
            "bling_import.csv",
            "text/csv"
        )

    except Exception as e:
        st.error("❌ Erro detectado!")
        st.code(str(e))

        if logs:
            st.download_button("📥 Baixar log", "\n".join(logs), "log.txt")
