import streamlit as st
import pandas as pd
import re
import random
import traceback
import time

# =========================
# CONFIG
# =========================
st.set_page_config(page_title="🔥 IA Planilhas PRO MAX", layout="wide")
st.title("🔥 IA Planilhas PRO MAX (Ultra Performance)")

# =========================
# LOG
# =========================
def mostrar_erro(e):
    erro = traceback.format_exc()
    st.error("❌ Erro detectado!")
    st.code(erro)
    st.download_button("⬇️ Baixar log", erro, "erro.txt")

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
    st.warning("⚠️ IA offline (modo automático)")

# =========================
# LEITURA
# =========================
def ler_arquivo(arquivo):
    try:
        return pd.read_csv(arquivo, sep=None, engine="python", encoding="utf-8", on_bad_lines="skip")
    except:
        return pd.read_csv(arquivo, sep=";", encoding="latin-1", on_bad_lines="skip")

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
    soma = sum(int(n) * (1 if i % 2 == 0 else 3) for i, n in enumerate(gtin[:-1]))
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
# FALLBACKS
# =========================
def descricao_fallback(nome):
    return f"{nome} com alta qualidade, envio rápido e excelente custo-benefício. Aproveite agora!"

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
# IA EM LOTE 🔥
# =========================
def gerar_descricao_lote(produtos):
    try:
        texto = "\n".join([f"{p[0]} | {p[1]}" for p in produtos])

        prompt = f"""
        Crie descrições PERSUASIVAS nível HARD para cada produto.

        Retorne uma lista na mesma ordem.

        Produtos:
        {texto}
        """

        resposta = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )

        return resposta.choices[0].message.content.split("\n")

    except:
        return [descricao_fallback(p[0]) for p in produtos]

# =========================
# MONTAR BLING (ULTRA)
# =========================
def montar_bling(df):

    inicio = time.time()

    mapa = detectar_colunas(df)
    novo = pd.DataFrame()

    novo["nome"] = df.get(mapa.get("nome"), "")
    novo["codigo"] = df.get(mapa.get("sku"), "")
    novo["preco"] = df.get(mapa.get("preco"), 0)
    novo["estoque"] = df.get(mapa.get("estoque"), 0)
    novo["marca"] = df.get(mapa.get("marca"), "")

    total = len(df)
    progresso = st.progress(0)
    status = st.empty()

    descricoes = []
    categorias = []

    batch_size = 20

    for i in range(0, total, batch_size):

        lote = []
        for j in range(i, min(i + batch_size, total)):
            nome = str(novo["nome"][j])
            desc = str(df.get(mapa.get("descricao"), "")[j])
            lote.append((nome, desc))

        # IA ou fallback
        if IA_DISPONIVEL:
            descs = gerar_descricao_lote(lote)
        else:
            descs = [descricao_fallback(p[0]) for p in lote]

        for idx, j in enumerate(range(i, min(i + batch_size, total))):
            descricoes.append(descs[idx] if idx < len(descs) else descricao_fallback(lote[idx][0]))

            nome = str(novo["nome"][j])
            cat = df.get(mapa.get("categoria"), "")
            cat_val = str(cat[j]) if mapa.get("categoria") else ""

            if cat_val.strip() == "":
                cat_val = detectar_categoria(nome)

            categorias.append(cat_val)

        # progresso + tempo
        progresso_atual = min(i + batch_size, total)
        progresso.progress(progresso_atual / total)

        tempo_decorrido = time.time() - inicio
        tempo_estimado = (tempo_decorrido / progresso_atual) * total

        status.text(f"Processando {progresso_atual}/{total} | ⏱ {int(tempo_estimado - tempo_decorrido)}s restantes")

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

        st.info("🚀 Processamento inteligente iniciado...")
        df_final = montar_bling(df)

        st.success("🔥 Pronto! Planilha otimizada")
        st.dataframe(df_final.head())

        st.download_button(
            "⬇️ Baixar",
            df_final.to_csv(index=False),
            "bling_import.csv",
            "text/csv"
        )

    except Exception as e:
        mostrar_erro(e)
