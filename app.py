import io
import zipfile
import random
import re
import time
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import requests
import streamlit as st
from bs4 import BeautifulSoup
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

st.set_page_config(page_title="🔥 BLING AUTO INTELIGENTE TOTAL", layout="wide")
st.title("🔥 BLING AUTO INTELIGENTE TOTAL")

# =========================
# INPUTS
# =========================
modo_coleta = st.radio(
    "📥 Fonte dos dados",
    ["Planilha + Site", "Só Planilha", "Só Site"],
    horizontal=True
)

url_base = st.text_input("🌐 Site:", "https://megacentereletronicos.com.br/")
arquivo_dados = st.file_uploader(
    "📄 Planilha de dados do fornecedor / site",
    type=["xlsx", "xls", "csv"]
)

modelo_estoque_file = st.file_uploader(
    "📦 Modelo BLING ESTOQUE",
    type=["xlsx", "xls", "csv"]
)

modelo_cadastro_file = st.file_uploader(
    "📋 Modelo BLING CADASTRO",
    type=["xlsx", "xls", "csv"]
)

filtro = st.text_input("🔎 Filtrar produto:", "")
estoque_padrao = st.number_input("📦 Estoque padrão", value=10, min_value=0)
depositos_input = st.text_input(
    "🏬 IDs / nomes dos depósitos (separados por vírgula)",
    value="14888207145"
)

depositos = [d.strip() for d in depositos_input.split(",") if d.strip()]

# =========================
# LOG
# =========================
logs: list[str] = []


def log(msg: str) -> None:
    logs.append(msg)


# =========================
# REQUEST
# =========================
session = requests.Session()


def get_headers() -> dict:
    return {
        "User-Agent": random.choice([
            "Mozilla/5.0",
            "Mozilla/5.0 (Windows NT 10.0)",
            "Mozilla/5.0 (Android)"
        ]),
        "Accept-Language": "pt-BR,pt;q=0.9",
        "Accept": "text/html,application/xhtml+xml",
        "Connection": "keep-alive",
    }


def fetch(url: str) -> str | None:
    for tentativa in range(3):
        try:
            time.sleep(random.uniform(0.4, 1.0))
            r = session.get(url, headers=get_headers(), timeout=20, verify=False)
            if r.status_code == 200:
                r.encoding = "utf-8"
                return r.text
            log(f"WARN fetch status={r.status_code} url={url}")
        except Exception as e:
            log(f"ERRO fetch tentativa={tentativa+1} url={url} detalhe={e}")
    return None


# =========================
# UTIL
# =========================
def limpar(txt) -> str:
    if txt is None:
        return ""
    return re.sub(r"\s+", " ", str(txt)).strip()


def normalizar_url(url: str, base: str = "") -> str:
    url = limpar(url)
    if not url:
        return ""
    if url.startswith("http://") or url.startswith("https://"):
        return url
    if base:
        return urljoin(base, url)
    return url


def gerar_codigo_fallback(seed: str) -> str:
    digits = re.sub(r"\D", "", limpar(seed))
    if len(digits) >= 8:
        return digits[:14]
    return str(random.randint(1000000000000, 9999999999999))


def parse_preco(valor) -> str:
    txt = limpar(valor)
    if not txt:
        return "0.01"

    achados = re.findall(r"\d{1,3}(?:\.\d{3})*,\d{2}", txt)
    if achados:
        txt = achados[0]

    try:
        num = float(txt.replace(".", "").replace(",", "."))
        if num <= 0:
            return "0.01"
        return f"{num:.2f}"
    except Exception:
        return "0.01"


def parse_estoque(valor, padrao: int) -> int:
    txt = limpar(valor)
    if not txt:
        return padrao

    if any(x in txt.lower() for x in ["esgotado", "indisponível", "indisponivel", "sem estoque"]):
        return 0

    m = re.search(r"-?\d+(?:[.,]\d+)?", txt)
    if m:
        try:
            return int(float(m.group(0).replace(",", ".")))
        except Exception:
            return padrao
    return padrao


def detectar_marca(nome: str, descricao: str) -> str:
    marcas = [
        "Samsung", "LG", "Philips", "Lenoxx", "Knup", "Motorola", "Xiaomi",
        "Apple", "JBL", "Sony", "Kaidi", "H'maston", "It-Blue", "Grasep"
    ]
    base = f"{nome} {descricao}".lower()
    for marca in marcas:
        if marca.lower() in base:
            return marca
    return ""


# =========================
# LEITURA DE PLANILHAS
# =========================
def ler_planilha(file) -> pd.DataFrame | None:
    try:
        nome = (file.name or "").lower()
        if nome.endswith(".xlsx"):
            return pd.read_excel(file, engine="openpyxl")
        if nome.endswith(".xls"):
            return pd.read_excel(file)
        if nome.endswith(".csv"):
            try:
                return pd.read_csv(file, sep=";", encoding="utf-8")
            except Exception:
                file.seek(0)
                return pd.read_csv(file, sep=None, engine="python", encoding="latin1")
        st.error("Formato de arquivo não suportado.")
        return None
    except Exception as e:
        log(f"ERRO leitura planilha arquivo={getattr(file, 'name', 'desconhecido')} detalhe={e}")
        st.error(f"Erro ao ler planilha: {e}")
        return None


# =========================
# DETECÇÃO INTELIGENTE DE COLUNAS
# =========================
def detectar_colunas_inteligente(df: pd.DataFrame) -> dict[str, str]:
    mapa: dict[str, str] = {}

    for col in df.columns:
        c = limpar(col).lower()

        if "codigo produto" in c or c == "codigo" or c == "código" or "sku" in c or "cod" in c or c == "id":
            mapa.setdefault("codigo", col)

        elif "nome" in c or "produto" in c or c == "descrição" or c == "descricao" or "titulo" in c or "title" in c:
            mapa.setdefault("produto", col)

        elif "preço" in c or "preco" in c or "valor" in c or "price" in c:
            mapa.setdefault("preco", col)

        elif "estoque" in c or "saldo" in c or "qtd" in c or "quantidade" in c or "balan" in c:
            mapa.setdefault("estoque", col)

        elif "descrição curta" in c or "descricao curta" in c or "descrição" in c or "descricao" in c or "resumo" in c:
            mapa.setdefault("descricao_curta", col)

        elif "imagem" in c or "foto" in c or "image" in c:
            mapa.setdefault("imagem", col)

        elif "link externo" in c or c == "link" or c == "url" or "site" in c:
            mapa.setdefault("link", col)

        elif "marca" in c:
            mapa.setdefault("marca", col)

    return mapa


def normalizar_planilha_entrada(df: pd.DataFrame, base_url: str, padrao_estoque: int) -> pd.DataFrame:
    mapa = detectar_colunas_inteligente(df)
    log(f"Mapa detectado planilha entrada: {mapa}")

    out = pd.DataFrame()

    if "codigo" in mapa:
        out["Código"] = df[mapa["codigo"]].apply(lambda x: gerar_codigo_fallback(str(x)))
    else:
        out["Código"] = [""] * len(df)

    if "produto" in mapa:
        out["Produto"] = df[mapa["produto"]].apply(limpar)
    else:
        out["Produto"] = [""] * len(df)

    if "preco" in mapa:
        out["Preço"] = df[mapa["preco"]].apply(parse_preco)
    else:
        out["Preço"] = ["0.01"] * len(df)

    if "estoque" in mapa:
        out["Estoque"] = df[mapa["estoque"]].apply(lambda x: parse_estoque(x, padrao_estoque))
    else:
        out["Estoque"] = [padrao_estoque] * len(df)

    if "descricao_curta" in mapa:
        out["Descrição Curta"] = df[mapa["descricao_curta"]].apply(limpar)
    else:
        out["Descrição Curta"] = [""] * len(df)

    if "imagem" in mapa:
        out["Imagem"] = df[mapa["imagem"]].apply(lambda x: normalizar_url(str(x), base_url))
    else:
        out["Imagem"] = [""] * len(df)

    if "link" in mapa:
        out["Link"] = df[mapa["link"]].apply(lambda x: normalizar_url(str(x), base_url))
    else:
        out["Link"] = [""] * len(df)

    if "marca" in mapa:
        out["Marca"] = df[mapa["marca"]].apply(limpar)
    else:
        out["Marca"] = [""] * len(df)

    out["Produto"] = out["Produto"].replace("", pd.NA).fillna("Produto sem nome")
    out["Código"] = out.apply(
        lambda r: gerar_codigo_fallback(r["Link"] or r["Produto"]) if not limpar(r["Código"]) else limpar(r["Código"]),
        axis=1
    )
    out["Descrição Curta"] = out.apply(
        lambda r: r["Descrição Curta"] if limpar(r["Descrição Curta"]) else r["Produto"],
        axis=1
    )
    out["Marca"] = out.apply(
        lambda r: r["Marca"] if limpar(r["Marca"]) else detectar_marca(r["Produto"], r["Descrição Curta"]),
        axis=1
    )

    return out


# =========================
# SCRAPING
# =========================
def extrair_imagem(soup: BeautifulSoup, link: str) -> str:
    og = soup.find("meta", property="og:image")
    if og and og.get("content"):
        return urljoin(link, og["content"])

    for img in soup.find_all("img"):
        for attr in ["data-zoom-image", "data-src", "src"]:
            src = img.get(attr)
            if src and not any(bad in src.lower() for bad in ["logo", "banner", "icon"]):
                return urljoin(link, src)

    return ""


def extrair_descricao_curta_site(soup: BeautifulSoup, nome: str) -> str:
    seletores = [
        {"name": "div", "class_": re.compile("descricao|description|product", re.I)},
        {"name": "section", "class_": re.compile("descricao|description|product", re.I)},
        {"name": "article", "class_": re.compile("descricao|description|product", re.I)},
    ]

    for sel in seletores:
        tag = soup.find(sel.get("name"), class_=sel.get("class_"))
        if tag:
            texto = limpar(tag.get_text(" ", strip=True))
            if len(texto) >= 20:
                return texto[:250]

    return nome[:250]


def extrair_site(link: str) -> dict | None:
    html = fetch(link)
    if not html:
        return None

    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    texto = soup.get_text(" ", strip=True)
    nome_tag = soup.find("h1")
    nome = limpar(nome_tag.get_text(strip=True)) if nome_tag else "Produto sem nome"

    if filtro and filtro.lower() not in nome.lower():
        return None

    return {
        "Código": extrair_codigo(texto, link),
        "Produto": nome,
        "Preço": extrair_preco(texto),
        "Descrição Curta": extrair_descricao_curta_site(soup, nome),
        "Imagem": extrair_imagem(soup, link),
        "Link": link,
        "Estoque": estoque_padrao,
        "Marca": detectar_marca(nome, texto),
    }


def extrair_codigo(texto: str, link: str) -> str:
    padroes = [
        r"C[ÓO]D[:\s]*([0-9]{8,14})",
        r"SKU[:\s]*([0-9]{8,14})",
        r"\b([0-9]{8,14})\b",
    ]
    for padrao in padroes:
        m = re.search(padrao, texto, flags=re.IGNORECASE)
        if m:
            return m.group(1)
    return gerar_codigo_fallback(link)


def extrair_preco(texto: str) -> str:
    valores = re.findall(r"\d{1,3}(?:\.\d{3})*,\d{2}", texto)
    if not valores:
        return "0.01"

    nums = []
    for v in valores:
        try:
            nums.append(float(v.replace(".", "").replace(",", ".")))
        except Exception:
            pass

    if not nums:
        return "0.01"

    preco = min(nums)
    return f"{preco:.2f}"


def coletar_links_site() -> list[str]:
    links: list[str] = []

    for p in range(1, 6):
        html = fetch(f"{url_base}?page={p}")
        if not html:
            continue

        soup = BeautifulSoup(html, "html.parser")
        for a in soup.find_all("a", href=True):
            link = urljoin(url_base, a["href"])
            if "/produto" in link:
                links.append(link)

    vistos = set()
    unicos = []
    for lnk in links:
        if lnk not in vistos:
            vistos.add(lnk)
            unicos.append(lnk)
    return unicos


# =========================
# MODELOS BLING
# =========================
def mapear_colunas_modelo(cols: list[str]) -> dict[str, str]:
    mapa: dict[str, str] = {}
    for col in cols:
        c = col.strip().lower()

        if "código produto" in c or c == "código produto":
            mapa["estoque_codigo"] = col
        elif c == "código":
            mapa["cadastro_codigo"] = col
        elif "descrição produto" in c:
            mapa["estoque_descricao"] = col
        elif c == "descrição":
            mapa["cadastro_descricao"] = col
        elif "deposito" in c or "depósito" in c:
            mapa["deposito"] = col
        elif "balanço" in c or c == "saldo" or c == "estoque":
            mapa["estoque_qtd"] = col
        elif "preço unitário" in c:
            mapa["estoque_preco"] = col
        elif c == "preço":
            mapa["cadastro_preco"] = col
        elif "unidade" in c:
            mapa["unidade"] = col
        elif "situação" in c or "situacao" in c:
            mapa["situacao"] = col
        elif c == "tipo":
            mapa["tipo"] = col
        elif "descrição curta" in c or "descricao curta" in c:
            mapa["descricao_curta"] = col
        elif "descrição complementar" in c or "descricao complementar" in c:
            mapa["descricao_complementar"] = col
        elif "url imagens" in c or "url imagem" in c:
            mapa["url_imagens"] = col
        elif "link externo" in c:
            mapa["link_externo"] = col
        elif c == "marca":
            mapa["marca"] = col
        elif c == "gtin" or "gtin/ean" in c or "código de barras" in c:
            mapa["gtin"] = col
    return mapa


def preencher_modelo_estoque(modelo: pd.DataFrame, df: pd.DataFrame) -> pd.DataFrame:
    mapa = mapear_colunas_modelo(list(modelo.columns))
    linhas = []

    for _, row in df.iterrows():
        for deposito in depositos:
            nova = {col: "" for col in modelo.columns}

            if "estoque_codigo" in mapa:
                nova[mapa["estoque_codigo"]] = row["Código"]

            if "estoque_descricao" in mapa:
                nova[mapa["estoque_descricao"]] = row["Produto"]

            if "deposito" in mapa:
                nova[mapa["deposito"]] = deposito

            if "estoque_qtd" in mapa:
                nova[mapa["estoque_qtd"]] = row["Estoque"]

            if "estoque_preco" in mapa:
                nova[mapa["estoque_preco"]] = row["Preço"]

            if "gtin" in mapa:
                nova[mapa["gtin"]] = ""

            linhas.append(nova)

    return pd.DataFrame(linhas, columns=modelo.columns)


def preencher_modelo_cadastro(modelo: pd.DataFrame, df: pd.DataFrame) -> pd.DataFrame:
    mapa = mapear_colunas_modelo(list(modelo.columns))
    linhas = []

    for _, row in df.iterrows():
        nova = {col: "" for col in modelo.columns}

        if "cadastro_codigo" in mapa:
            nova[mapa["cadastro_codigo"]] = row["Código"]

        if "cadastro_descricao" in mapa:
            nova[mapa["cadastro_descricao"]] = row["Produto"]

        if "cadastro_preco" in mapa:
            nova[mapa["cadastro_preco"]] = row["Preço"]

        if "unidade" in mapa:
            nova[mapa["unidade"]] = "UN"

        if "situacao" in mapa:
            nova[mapa["situacao"]] = "Ativo"

        if "tipo" in mapa:
            nova[mapa["tipo"]] = "Produto"

        if "descricao_curta" in mapa:
            nova[mapa["descricao_curta"]] = row["Descrição Curta"]

        if "descricao_complementar" in mapa:
            nova[mapa["descricao_complementar"]] = ""

        if "url_imagens" in mapa:
            nova[mapa["url_imagens"]] = row["Imagem"]

        if "link_externo" in mapa:
            nova[mapa["link_externo"]] = row["Link"]

        if "marca" in mapa:
            nova[mapa["marca"]] = row["Marca"]

        if "gtin" in mapa:
            nova[mapa["gtin"]] = ""

        linhas.append(nova)

    return pd.DataFrame(linhas, columns=modelo.columns)


# =========================
# MERGE INTELIGENTE
# =========================
def merge_dados(planilha_df: pd.DataFrame, site_df: pd.DataFrame) -> pd.DataFrame:
    if planilha_df.empty and site_df.empty:
        return pd.DataFrame()

    if planilha_df.empty:
        return site_df.copy()

    if site_df.empty:
        return planilha_df.copy()

    plan = planilha_df.copy()
    site = site_df.copy()

    # chave preferencial: Link, depois Código, depois Produto
    plan["_chave"] = plan.apply(
        lambda r: limpar(r["Link"]) or limpar(r["Código"]) or limpar(r["Produto"]).lower(),
        axis=1
    )
    site["_chave"] = site.apply(
        lambda r: limpar(r["Link"]) or limpar(r["Código"]) or limpar(r["Produto"]).lower(),
        axis=1
    )

    base = pd.merge(plan, site, on="_chave", how="outer", suffixes=("_plan", "_site"))

    out = pd.DataFrame()

    def escolher(row, campo: str):
        plan_v = row.get(f"{campo}_plan", "")
        site_v = row.get(f"{campo}_site", "")

        if campo == "Estoque":
            return parse_estoque(plan_v, estoque_padrao) if limpar(plan_v) else parse_estoque(site_v, estoque_padrao)

        # para cadastro prioriza site quando vier enriquecido
        return limpar(site_v) or limpar(plan_v)

    for campo in ["Código", "Produto", "Preço", "Descrição Curta", "Imagem", "Link", "Marca"]:
        out[campo] = base.apply(lambda r: escolher(r, campo), axis=1)

    out["Estoque"] = base.apply(lambda r: escolher(r, "Estoque"), axis=1)

    out["Código"] = out.apply(
        lambda r: gerar_codigo_fallback(r["Link"] or r["Produto"]) if not limpar(r["Código"]) else limpar(r["Código"]),
        axis=1
    )
    out["Produto"] = out["Produto"].replace("", pd.NA).fillna("Produto sem nome")
    out["Preço"] = out["Preço"].apply(parse_preco)
    out["Descrição Curta"] = out.apply(
        lambda r: r["Descrição Curta"] if limpar(r["Descrição Curta"]) else r["Produto"],
        axis=1
    )
    out["Marca"] = out.apply(
        lambda r: r["Marca"] if limpar(r["Marca"]) else detectar_marca(r["Produto"], r["Descrição Curta"]),
        axis=1
    )
    out["Imagem"] = out["Imagem"].apply(lambda x: normalizar_url(x, url_base))
    out["Link"] = out["Link"].apply(lambda x: normalizar_url(x, url_base))
    out["Estoque"] = out["Estoque"].apply(lambda x: parse_estoque(x, estoque_padrao))

    return out.drop_duplicates(subset=["Código", "Produto", "Link"]).reset_index(drop=True)


# =========================
# EXECUÇÃO
# =========================
if st.button("🚀 EXECUTAR AUTO INTELIGENTE TOTAL"):
    if not modelo_estoque_file or not modelo_cadastro_file:
        st.error("Envie os dois modelos do Bling: estoque e cadastro.")
        st.stop()

    modelo_est = ler_planilha(modelo_estoque_file)
    modelo_cad = ler_planilha(modelo_cadastro_file)

    if modelo_est is None or modelo_cad is None:
        st.stop()

    progress = st.progress(0)

    # 1) dados da planilha de entrada
    df_planilha = pd.DataFrame()
    if modo_coleta in ["Planilha + Site", "Só Planilha"]:
        if not arquivo_dados:
            st.error("Envie a planilha de dados para esse modo.")
            st.stop()
        entrada = ler_planilha(arquivo_dados)
        if entrada is None:
            st.stop()
        df_planilha = normalizar_planilha_entrada(entrada, url_base, estoque_padrao)
        log(f"Planilha normalizada com {len(df_planilha)} linhas")

    # 2) dados do site
    df_site = pd.DataFrame()
    if modo_coleta in ["Planilha + Site", "Só Site"]:
        links = coletar_links_site()
        st.write(f"🔗 {len(links)} produtos encontrados no site")

        if links:
            produtos_site = []
            with ThreadPoolExecutor(max_workers=10) as ex:
                futures = [ex.submit(extrair_site, link) for link in links]
                total = len(links)
                for i, future in enumerate(as_completed(futures), start=1):
                    res = future.result()
                    if res:
                        produtos_site.append(res)
                    progress.progress(i / total)

            df_site = pd.DataFrame(produtos_site)
            log(f"Site normalizado com {len(df_site)} linhas")
        elif modo_coleta == "Só Site":
   
