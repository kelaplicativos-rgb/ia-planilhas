import re
import hashlib


def limpar(texto):
    if texto is None:
        return ""
    return str(texto).strip()


def valor_vazio(v):
    return v is None or str(v).strip() == ""


def gerar_codigo_fallback(base):
    base = limpar(base)

    if not base:
        base = "produto"

    h = hashlib.md5(base.encode()).hexdigest()[:12]
    return f"SKU-{h}".upper()


def normalizar_url(url, base=""):
    url = limpar(url)

    if not url:
        return ""

    if url.startswith("http"):
        return url

    if url.startswith("//"):
        return "https:" + url

    if base and url.startswith("/"):
        return base.rstrip("/") + url

    return url


def detectar_marca(nome, descricao=""):
    texto = f"{nome} {descricao}".lower()

    marcas = [
        "sony",
        "samsung",
        "lg",
        "xiaomi",
        "apple",
        "lenovo",
        "asus",
        "hp",
        "dell",
        "motorola",
    ]

    for marca in marcas:
        if marca in texto:
            return marca.upper()

    return ""


def validar_gtin(gtin):
    gtin = limpar(gtin)

    if re.fullmatch(r"\d{8,14}", gtin):
        return gtin

    return ""


def parse_preco(valor, default="0.01"):
    valor = limpar(valor)

    if not valor:
        return default

    try:
        valor = valor.replace(".", "").replace(",", ".")
        return f"{float(valor):.2f}"
    except:
        return default


def parse_estoque(valor, default=0):
    try:
        return int(float(str(valor).replace(",", ".")))
    except:
        return default
