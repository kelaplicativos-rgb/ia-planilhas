
import json
import re


def limpar_marca(marca: str, titulo: str = "") -> str:
    if not marca:
        return ""

    marca = marca.strip()

    # ❌ remover marca genérica (nome da loja)
    bloqueadas = [
        "mega center",
        "eletrônicos",
        "eletronicos",
        "loja",
        "store",
        "shop"
    ]

    marca_lower = marca.lower()

    for b in bloqueadas:
        if b in marca_lower:
            return ""

    # ❌ evitar palavras genéricas
    genericas = [
        "fone", "cabo", "carregador", "caixa", "som",
        "produto", "acessório", "acessorio"
    ]

    if marca_lower in genericas:
        return ""

    # evitar marca gigante (provavelmente descrição)
    if len(marca) > 30:
        return ""

    return marca


def inferir_marca_do_titulo(titulo: str) -> str:
    if not titulo:
        return ""

    # pega primeira palavra forte
    palavras = titulo.split()

    if not palavras:
        return ""

    candidata = palavras[0]

    # remove caracteres estranhos
    candidata = re.sub(r"[^a-zA-Z0-9\-]", "", candidata)

    # evitar números ou palavras genéricas
    if candidata.lower() in [
        "fone", "cabo", "carregador", "caixa", "som"
    ]:
        return ""

    if len(candidata) <= 2:
        return ""

    return candidata


def extrair_produto_com_ia(html: str, url: str = ""):
    """
    Aqui você já usa GPT no seu fluxo.
    Vamos apenas reforçar pós-processamento da marca.
    """

    # ⚠️ isso simula o retorno atual do GPT
    # mantenha sua chamada real aqui
    resultado = {
        "titulo": "",
        "descricao": "",
        "preco": "",
        "marca": "",
        "gtin": "",
        "categoria": "",
        "imagens": []
    }

    try:
        # 👉 aqui entra seu código atual de GPT
        # resultado = chamada_gpt(...)

        pass
    except Exception:
        pass

    titulo = resultado.get("titulo", "")
    marca = resultado.get("marca", "")

    # 🔥 limpeza
    marca = limpar_marca(marca, titulo)

    # 🔥 fallback IA (via título)
    if not marca:
        marca = inferir_marca_do_titulo(titulo)

    resultado["marca"] = marca

    return resultado
