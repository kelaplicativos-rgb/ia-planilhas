import random
import re
from urllib.parse import urljoin


def limpar(txt) -> str:
    if txt is None:
        return ""
    txt = str(txt)
    txt = re.sub(r"\s+", " ", txt)
    return txt.strip()


def normalizar_url(url: str, base: str = "") -> str:
    url = limpar(url)

    if not url or url.lower() in ["nan", "none", "null"]:
        return ""

    if url.startswith("http://") or url.startswith("https://"):
        return url

    if base:
        return urljoin(base, url)

    return url


def gerar_codigo_fallback(seed: str) -> str:
    seed = limpar(seed)

    digits = re.sub(r"\D", "", seed)
    if len(digits) >= 8:
        return digits[:14]

    return str(random.randint(1000000000000, 9999999999999))


def parse_preco(valor) -> str:
    txt = limpar(valor)

    if not txt or txt.lower() in ["nan", "none", "null"]:
        return "0.01"

    # tenta achar um valor em formato brasileiro
    achados = re.findall(r"\d{1,3}(?:\.\d{3})*,\d{2}", txt)
    if achados:
        txt = achados[0]
        try:
            num = float(txt.replace(".", "").replace(",", "."))
            if num <= 0:
                return "0.01"
            return f"{num:.2f}"
        except Exception:
            pass

    # tenta formato internacional
    achados = re.findall(r"\d+(?:\.\d{2})", txt)
    if achados:
        txt = achados[0]
        try:
            num = float(txt)
            if num <= 0:
                return "0.01"
            return f"{num:.2f}"
        except Exception:
            pass

    # fallback: extrai qualquer número
    m = re.search(r"\d+(?:[.,]\d+)?", txt)
    if m:
        bruto = m.group(0).replace(",", ".")
        try:
            num = float(bruto)
            if num <= 0:
                return "0.01"
            return f"{num:.2f}"
        except Exception:
            pass

    return "0.01"


def parse_estoque(valor, padrao: int) -> int:
    txt = limpar(valor)

    if not txt or txt.lower() in ["nan", "none", "null"]:
        return int(padrao)

    if any(x in txt.lower() for x in ["esgotado", "indisponível", "indisponivel", "sem estoque"]):
        return 0

    m = re.search(r"-?\d+(?:[.,]\d+)?", txt)
    if m:
        try:
            num = float(m.group(0).replace(",", "."))
            return int(num)
        except Exception:
            return int(padrao)

    return int(padrao)


def detectar_marca(nome: str, descricao: str) -> str:
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
        "Multilaser",
        "Intelbras",
        "Aiwa",
        "Mondial",
        "Britânia",
        "Britania",
        "Exbom",
        "Tomate",
    ]

    base = f"{limpar(nome)} {limpar(descricao)}".lower()

    for marca in marcas:
        if marca.lower() in base:
            return marca

    return ""
