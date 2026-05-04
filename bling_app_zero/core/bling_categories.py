from __future__ import annotations

import re
from typing import Iterable, Any


def _safe_str(valor: Any) -> str:
    if valor is None:
        return ""
    texto = str(valor).replace("\ufeff", "").replace("\x00", "").strip()
    if texto.lower() in {"nan", "none", "null"}:
        return ""
    return texto


def _limpar_parte_categoria(valor: Any) -> str:
    texto = _safe_str(valor)
    if not texto:
        return ""
    texto = re.sub(r"\s+", " ", texto)
    texto = texto.strip(" >|/\\-\t\r\n")
    return texto.strip()


def normalizar_categoria_bling(valor: Any) -> str:
    """
    Normaliza categorias para o formato aceito na planilha do Bling.

    O Bling não cria categoria nova automaticamente pela importação de produtos;
    a planilha apenas vincula o produto a uma categoria já existente. Para
    subcategorias, o padrão usado no modelo é Categoria>>Subcategoria.
    """
    texto = _safe_str(valor)
    if not texto:
        return ""

    texto = texto.replace("&gt;", ">").replace("›", ">").replace("»", ">").replace("→", ">")
    texto = texto.replace("/", ">").replace("|", ">")
    texto = re.sub(r"\s*>\s*", ">", texto)
    partes = [_limpar_parte_categoria(p) for p in texto.split(">")]
    partes = [p for p in partes if p and p.lower() not in {"home", "início", "inicio", "todos", "produtos"}]

    vistas: set[str] = set()
    unicas: list[str] = []
    for parte in partes:
        chave = parte.casefold()
        if chave in vistas:
            continue
        vistas.add(chave)
        unicas.append(parte)

    return ">>".join(unicas)


def primeira_categoria_valida(valores: Iterable[Any]) -> str:
    for valor in valores:
        categoria = normalizar_categoria_bling(valor)
        if categoria:
            return categoria
    return ""


def nome_coluna_categoria(nome: Any) -> bool:
    texto = _safe_str(nome).casefold()
    texto = texto.replace("á", "a").replace("à", "a").replace("â", "a").replace("ã", "a")
    texto = texto.replace("é", "e").replace("ê", "e").replace("í", "i").replace("ó", "o").replace("ô", "o").replace("õ", "o").replace("ú", "u").replace("ç", "c")
    return any(token in texto for token in ["categoria", "category", "breadcrumb", "departamento", "secao", "seção"])


def coluna_categoria_bling_existente(colunas: Iterable[Any]) -> str:
    alvos = ["Categoria do sistema", "Categoria", "categoria", "category", "breadcrumb"]
    mapa = {str(c).strip().casefold(): str(c) for c in colunas}
    for alvo in alvos:
        achado = mapa.get(alvo.casefold())
        if achado:
            return achado
    for col in colunas:
        if nome_coluna_categoria(col):
            return str(col)
    return ""
