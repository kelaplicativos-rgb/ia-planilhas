import re
import unicodedata
from typing import Any


# =========================================================
# LIMPEZA DE TEXTO
# =========================================================
def limpar_texto(valor: Any) -> str:
    """
    Limpa textos removendo quebras, espaços duplicados e valores nulos.
    """
    if valor is None:
        return ""

    try:
        if hasattr(valor, "isna") and valor.isna():
            return ""
    except Exception:
        pass

    texto = str(valor)

    # Remove quebras e tabs
    texto = texto.replace("\n", " ").replace("\r", " ").replace("\t", " ")

    # Remove múltiplos espaços
    texto = re.sub(r"\s+", " ", texto)

    return texto.strip()


# =========================================================
# REMOVER ACENTOS
# =========================================================
def remover_acentos(texto: str) -> str:
    """
    Remove acentos de um texto.
    """
    if not texto:
        return ""

    return "".join(
        c for c in unicodedata.normalize("NFKD", str(texto))
        if not unicodedata.combining(c)
    )


# =========================================================
# NORMALIZAR NOME DE COLUNA (SLUG)
# =========================================================
def slug_coluna(nome: str) -> str:
    """
    Normaliza nome de coluna para comparação inteligente.
    Ex: 'Descrição do Produto' -> 'descricao produto'
    """
    nome = limpar_texto(nome)

    # Remove acentos e deixa minúsculo
    nome = remover_acentos(nome).lower()

    # Substituições comuns
    nome = (
        nome.replace("/", " ")
        .replace("\\", " ")
        .replace("-", " ")
        .replace("_", " ")
    )

    # Remove caracteres especiais
    nome = re.sub(r"[^a-z0-9 ]+", "", nome)

    # Remove espaços duplicados
    nome = re.sub(r"\s+", " ", nome)

    return nome.strip()


# =========================================================
# PREVIEW SEGURO (para UI)
# =========================================================
def formatar_preview_valor(valor: Any, limite: int = 90) -> str:
    """
    Limita tamanho do texto para preview no app.
    """
    txt = limpar_texto(valor)

    if len(txt) > limite:
        return txt[: limite - 3] + "..."

    return txt


# =========================================================
# SOMENTE DÍGITOS
# =========================================================
def somente_digitos(valor: Any) -> str:
    """
    Remove tudo que não for número.
    """
    return re.sub(r"\D+", "", limpar_texto(valor))
