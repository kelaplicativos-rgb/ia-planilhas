import re


def limpar(texto):
    """
    Limpa texto removendo espaços extras, quebras e normalizando.
    """
    if texto is None:
        return ""

    texto = str(texto)

    # remove múltiplos espaços
    texto = re.sub(r"\s+", " ", texto)

    return texto.strip()


def somente_numeros(texto):
    """
    Remove tudo que não for número
    """
    if texto is None:
        return ""

    return re.sub(r"\D", "", str(texto))


def normalizar_url(url, base=""):
    """
    Corrige URL relativa
    """
    if not url:
        return ""

    url = str(url).strip()

    if url.startswith("http"):
        return url

    if base:
        from urllib.parse import urljoin
        return urljoin(base, url)

    return url


def gerar_codigo_fallback(seed=""):
    """
    Gera SKU fallback confiável
    """
    numeros = somente_numeros(seed)

    if len(numeros) >= 8:
        return numeros[:14]

    import random
    return str(random.randint(1000000000000, 9999999999999))


def parse_preco(valor):
    """
    Converte preço para padrão Bling
    """
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


def parse_estoque(valor, padrao=0):
    """
    Converte estoque para inteiro confiável
    """
    if valor is None:
        return padrao

    texto = limpar(valor).lower()

    if any(x in texto for x in ["esgotado", "sem estoque", "indisponivel", "indisponível"]):
        return 0

    match = re.search(r"-?\d+", texto)

    if match:
        try:
            return int(match.group())
        except:
            return padrao

    return padrao
