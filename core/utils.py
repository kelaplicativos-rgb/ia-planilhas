import hashlib
import re
from urllib.parse import urljoin


def normalizar_url(url, base=""):
    if not url:
        return ""

    url = str(url).strip()
    if not url:
        return ""

    if url.startswith("//"):
        return "https:" + url

    if url.startswith("http://") or url.startswith("https://"):
        return url

    if base:
        return urljoin(base, url)

    return url


def gerar_codigo_fallback(base_texto):
    texto = str(base_texto or "").strip()
    if not texto:
        texto = "produto-sem-codigo"

    hash_curto = hashlib.md5(texto.encode("utf-8")).hexdigest()[:10].upper()
    return f"SKU-{hash_curto}"


def detectar_marca(produto, descricao=""):
    texto = f"{produto or ''} {descricao or ''}".lower()

    marcas_comuns = [
        "kaidi",
        "jbl",
        "xiaomi",
        "apple",
        "samsung",
        "lg",
        "philips",
        "multilaser",
        "lenovo",
        "motorola",
        "knup",
        "exbom",
        "havit",
        "goldentec",
        "awei",
        "b-max",
        "h'maston",
        "hmaston",
        "it-blue",
        "inova",
        "altomex",
        "tomate",
        "lelong",
        "oem",
    ]

    for marca in marcas_comuns:
        if marca in texto:
            # padroniza apresentação
            if marca == "h'maston":
                return "H'Maston"
            if marca == "hmaston":
                return "H'Maston"
            if marca == "it-blue":
                return "It-Blue"
            if marca == "b-max":
                return "B-Max"
            return marca.title()

    return ""


def parse_preco(valor, fallback="0.01"):
    if valor is None:
        return fallback

    txt = str(valor).strip()
    if not txt:
        return fallback

    txt = txt.replace("R$", "").replace("r$", "").strip()

    # mantém só números, vírgula e ponto
    txt = re.sub(r"[^0-9,.\-]", "", txt)

    # formato BR: 1.234,56
    if "," in txt:
        txt = txt.replace(".", "").replace(",", ".")
    else:
        # já em formato decimal com ponto
        pass

    try:
        num = float(txt)
        if num <= 0:
            return fallback
        return f"{num:.2f}"
    except Exception:
        return fallback


def parse_estoque(valor, fallback=0):
    if valor is None:
        return int(fallback)

    txt = str(valor).strip().lower()
    if not txt:
        return int(fallback)

    if any(x in txt for x in ["sem estoque", "esgotado", "indisponível", "indisponivel"]):
        return 0

    txt = txt.replace(",", ".")

    m = re.search(r"-?\d+(?:\.\d+)?", txt)
    if not m:
        return int(fallback)

    try:
        return int(float(m.group(0)))
    except Exception:
        return int(fallback)


def validar_gtin(gtin):
    """
    Aceita apenas GTIN/EAN com:
    - 8, 12, 13 ou 14 dígitos
    - dígito verificador correto
    Caso contrário, devolve string vazia.
    """
    if not gtin:
        return ""

    gtin = re.sub(r"\D", "", str(gtin).strip())
    if len(gtin) not in [8, 12, 13, 14]:
        return ""

    try:
        digits = [int(d) for d in gtin]
    except Exception:
        return ""

    check_digit = digits[-1]
    body = digits[:-1]

    # cálculo do dígito verificador GTIN
    total = 0
    reverse_body = body[::-1]

    for i, num in enumerate(reverse_body):
        if i % 2 == 0:
            total += num * 3
        else:
            total += num

    calc = (10 - (total % 10)) % 10

    if calc != check_digit:
        return ""

    return gtin
