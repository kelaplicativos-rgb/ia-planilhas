import re
import random
from urllib.parse import urljoin


# =========================
# TEXTO
# =========================
def limpar(texto):
    if texto is None:
        return ""
    texto = str(texto)
    texto = re.sub(r"\s+", " ", texto)
    return texto.strip()


def somente_numeros(texto):
    if texto is None:
        return ""
    return re.sub(r"\D", "", str(texto))


# =========================
# URL
# =========================
def normalizar_url(url, base=""):
    if not url:
        return ""

    url = str(url).strip()

    if url.startswith("http://") or url.startswith("https://"):
        return url

    if url.startswith("//"):
        return "https:" + url

    if base:
        return urljoin(base, url)

    return url


# =========================
# SKU / CÓDIGO
# =========================
def gerar_codigo_fallback(seed=""):
    numeros = somente_numeros(seed)

    if len(numeros) >= 8:
        return numeros[:14]

    return str(random.randint(1000000000000, 9999999999999))


# =========================
# PREÇO
# =========================
def parse_preco(valor, fallback="0.01"):
    if valor is None:
        return fallback

    texto = limpar(valor)

    if texto == "":
        return fallback

    match = re.findall(r"\d{1,3}(?:\.\d{3})*,\d{2}", texto)
    if match:
        texto = match[0]

    texto = texto.replace("R$", "").replace("r$", "").strip()

    try:
        numero = float(texto.replace(".", "").replace(",", "."))
        if numero <= 0:
            return fallback
        return f"{numero:.2f}"
    except Exception:
        return fallback


# =========================
# ESTOQUE
# =========================
def parse_estoque(valor, padrao=0):
    if valor is None:
        return int(padrao)

    texto = limpar(valor).lower()

    if texto == "":
        return int(padrao)

    if any(x in texto for x in [
        "esgotado",
        "sem estoque",
        "indisponivel",
        "indisponível"
    ]):
        return 0

    match = re.search(r"-?\d+", texto)

    if match:
        try:
            return int(match.group())
        except Exception:
            return int(padrao)

    return int(padrao)


# =========================
# GTIN
# =========================
def validar_gtin(valor):
    if valor is None:
        return ""

    numeros = somente_numeros(valor)

    if len(numeros) not in [8, 12, 13, 14]:
        return ""

    return numeros


# =========================
# MARCA
# =========================
def detectar_marca(nome="", descricao=""):
    marcas = [
        "Samsung",
        "LG",
        "Philips",
        "Lenoxx",
        "Knup",
        "Motorola",
        "Xiaomi",
        "Apple",
        "JBL",
        "Sony",
        "Kaidi",
        "H'maston",
        "It-Blue",
        "Grasep",
        "Awei",
        "Inova",
        "Exbom",
        "Tomate",
        "Altomex",
    ]

    base = f"{nome} {descricao}".lower()

    for marca in marcas:
        if marca.lower() in base:
            return marca

    return ""


# =========================
# VALORES VAZIOS
# =========================
def valor_vazio(valor):
    if valor is None:
        return True

    texto = limpar(valor)

    if texto == "":
        return True

    if texto.lower() in ["nan", "none", "null", "-"]:
        return True

    return False
