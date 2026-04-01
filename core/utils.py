import re
import random

def limpar(txt):
    if txt is None:
        return ""
    return re.sub(r"\s+", " ", str(txt)).strip()

def gerar_codigo_fallback(seed):
    digits = re.sub(r"\D", "", limpar(seed))
    if len(digits) >= 8:
        return digits[:14]
    return str(random.randint(1000000000000, 9999999999999))

def parse_preco(valor):
    txt = limpar(valor)
    if not txt:
        return "0.01"
    try:
        return str(float(txt.replace(".", "").replace(",", ".")))
    except:
        return "0.01"

def parse_estoque(valor, padrao):
    txt = limpar(valor)
    if not txt:
        return padrao
    m = re.search(r"\d+", txt)
    return int(m.group()) if m else padrao
