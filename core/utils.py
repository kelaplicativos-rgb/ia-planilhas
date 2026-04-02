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

    if url.startswith("http"):
        return url

    if base:
        return urljoin(base, url)

    return url


# =========================
# SKU
# =========================
def gerar_codigo_fallback(seed=""):
    numeros = somente_numeros(seed)

    if len(numeros) >= 8:
        return numeros[:14]

    return str(random.randint(1000000000000, 9999999999999))


# =========================
# PREÇO
# =========================
def parse_preco(valor):
    if valor is None:
        return "0.01"

    texto = limpar(valor)

    match = re.findall(r"\d{1,3}(?:\.\d{3})*,\d{2}", texto)

    if match:
        texto = match[0]

    try:
        numero = float(texto.replace(".", "").replace(",", "."))
        if numero <= 0:
            return "0.01"
        return f"{numero:.2f}"
    except:
        return "0.01"


# =========================
# ESTOQUE
# =========================
def parse_estoque(valor, padrao=0):
    if valor is None:
        return padrao

    texto = limpar(valor).lower()

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
        except:
            return padrao

    return padrao


# =========================
# GTIN (🔥 FALTAVA ESSA)
# =========================
def validar_gtin(valor):
    if valor is None:
        return ""

    numeros = somente_numeros(valor)

    if len(numeros) in [8, 12, 13, 14]:
        return numeros

    return ""


# =========================
# MARCA
# =========================
def detectar_marca(nome="", descricao=""):
    marcas = [
        "Samsung", "LG", "Philips", "Lenoxx", "Knup",
        "Motorola", "Xiaomi", "Apple", "JBL",
        "Sony", "Kaidi", "H'maston", "It-Blue", "Grasep"
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
