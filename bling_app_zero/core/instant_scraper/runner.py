from .ultra_detector import detectar_blocos_repetidos
from .ultra_extractor import extrair_lista

candidates = detectar_blocos_repetidos(html)

frames = []

for candidate in candidates:
    elements = candidate["elements"]

    produtos = extrair_lista(elements, url)

    if produtos:
        frames.append(pd.DataFrame(produtos))
