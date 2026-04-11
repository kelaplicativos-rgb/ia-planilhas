from __future__ import annotations

import io
import re
from dataclasses import dataclass
from typing import Any

import pandas as pd
from pypdf import PdfReader


# ==========================================================
# MODELO
# ==========================================================
@dataclass
class ProdutoPDF:
    categoria: str = ""
    descricao: str = ""
    codigo: str = ""
    gtin: str = ""
    preco_original: float | str = ""
    preco_atual: float | str = ""


# ==========================================================
# HELPERS DE TEXTO
# ==========================================================
def _texto(v: Any) -> str:
    try:
        return str(v or "").strip()
    except Exception:
        return ""


def _limpar_linha(linha: str) -> str:
    linha = _texto(linha)

    substituicoes = {
        "\u00a0": " ",
        "\ufb01": "fi",
        "\ufb02": "fl",
        "\u2019": "'",
        "\u2018": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2013": "-",
        "\u2014": "-",
        "\u2022": "•",
        "\u00ad": "",
        "\ufffe": "",
    }

    for origem, destino in substituicoes.items():
        linha = linha.replace(origem, destino)

    linha = re.sub(r"\s+", " ", linha).strip()
    return linha


def _eh_linha_ignorar(linha: str) -> bool:
    texto = _limpar_linha(linha).lower()

    if not texto:
        return True

    lixos_prefixo = (
        "https://",
        "http://",
        "+55",
        "@www.",
        "@mega",
        "gerado em ",
        "página ",
    )
    if texto.startswith(lixos_prefixo):
        return True

    lixos_exatos = {
        "sem imagem",
    }
    if texto in lixos_exatos:
        return True

    return False


def _eh_codigo(linha: str) -> bool:
    return bool(re.search(r"^c[oó]d:\s*", _limpar_linha(linha), flags=re.IGNORECASE))


def _extrair_codigo(linha: str) -> str:
    texto = _limpar_linha(linha)
    m = re.search(r"c[oó]d:\s*([0-9A-Za-z\-\./]+)", texto, flags=re.IGNORECASE)
    return _texto(m.group(1)) if m else ""


def _eh_preco(linha: str) -> bool:
    return bool(re.search(r"R\$\s*\d", _limpar_linha(linha), flags=re.IGNORECASE))


def _extrair_preco(linha: str) -> float | str:
    texto = _limpar_linha(linha)
    m = re.search(r"R\$\s*([\d\.\,]+)", texto, flags=re.IGNORECASE)
    if not m:
        return ""

    bruto = _texto(m.group(1))
    try:
        return float(bruto.replace(".", "").replace(",", "."))
    except Exception:
        return ""


def _eh_categoria_candidata(linha: str) -> bool:
    texto = _limpar_linha(linha)
    texto_lower = texto.lower()

    if not texto:
        return False
    if _eh_codigo(texto) or _eh_preco(texto):
        return False
    if re.search(r"\d", texto):
        return False
    if len(texto) > 60:
        return False
    if texto_lower.startswith(("https://", "gerado em", "@", "+55")):
        return False

    return True


def _normalizar_nome_produto(nome: str) -> str:
    nome = _limpar_linha(nome)
    nome = re.sub(r"\s+\-\s*$", "", nome).strip()
    return nome


def _linhas_significativas(texto: str) -> list[str]:
    saida: list[str] = []

    for linha in _texto(texto).splitlines():
        linha_limpa = _limpar_linha(linha)
        if _eh_linha_ignorar(linha_limpa):
            continue
        saida.append(linha_limpa)

    return saida


# ==========================================================
# LEITURA PDF
# ==========================================================
def ler_texto_pdf_upload(arquivo_pdf) -> str:
    try:
        arquivo_pdf.seek(0)
        conteudo = arquivo_pdf.read()
        reader = PdfReader(io.BytesIO(conteudo))

        paginas: list[str] = []
        for page in reader.pages:
            try:
                txt = page.extract_text() or ""
            except Exception:
                txt = ""
            if _texto(txt):
                paginas.append(txt)

        return "\n".join(paginas).strip()
    except Exception:
        return ""


# ==========================================================
# PARSER
# ==========================================================
def extrair_dataframe_pdf_catalogo(texto_pdf: str) -> pd.DataFrame:
    linhas = _linhas_significativas(texto_pdf)
    if not linhas:
        return pd.DataFrame()

    produtos: list[ProdutoPDF] = []

    categoria_atual = ""
    nome_partes: list[str] = []
    codigo_atual = ""
    precos_atuais: list[float | str] = []

    def finalizar_produto() -> None:
        nonlocal nome_partes, codigo_atual, precos_atuais

        nome = _normalizar_nome_produto(" ".join(nome_partes))
        if not nome or not codigo_atual or not precos_atuais:
            nome_partes = []
            codigo_atual = ""
            precos_atuais = []
            return

        preco_original = precos_atuais[0] if len(precos_atuais) >= 1 else ""
        preco_atual = precos_atuais[-1] if len(precos_atuais) >= 1 else ""

        produtos.append(
            ProdutoPDF(
                categoria=categoria_atual,
                descricao=nome,
                codigo=codigo_atual,
                gtin=codigo_atual,
                preco_original=preco_original,
                preco_atual=preco_atual,
            )
        )

        nome_partes = []
        codigo_atual = ""
        precos_atuais = []

    for i, linha in enumerate(linhas):
        prox = linhas[i + 1] if i + 1 < len(linhas) else ""
        ant = linhas[i - 1] if i - 1 >= 0 else ""

        if _eh_codigo(linha):
            codigo_atual = _extrair_codigo(linha)
            continue

        if _eh_preco(linha):
            valor = _extrair_preco(linha)
            if valor != "":
                precos_atuais.append(valor)

            prox_eh_nome = bool(prox) and not _eh_codigo(prox) and not _eh_preco(prox) and not _eh_categoria_candidata(prox)
            prox_eh_categoria = _eh_categoria_candidata(prox)

            if not prox_eh_nome or prox_eh_categoria:
                finalizar_produto()
            continue

        # categoria nova: curta, sem números, fora de produto aberto
        if _eh_categoria_candidata(linha):
            if not nome_partes and not codigo_atual and not precos_atuais:
                categoria_atual = linha
                continue

            # se já há produto em construção e entrou uma linha curta logo após preço/código,
            # fecha o produto anterior e trata como categoria
            if codigo_atual and precos_atuais:
                finalizar_produto()
                categoria_atual = linha
                continue

            # evita perder nomes curtos de produto
            if ant and _eh_categoria_candidata(ant) and not codigo_atual:
                nome_partes.append(linha)
                continue

        # se já houve código + preço e chegou outra linha comum, provavelmente começa novo produto
        if codigo_atual and precos_atuais:
            finalizar_produto()

        nome_partes.append(linha)

    finalizar_produto()

    if not produtos:
        return pd.DataFrame()

    df = pd.DataFrame(
        [
            {
                "Categoria PDF": p.categoria,
                "Descrição": p.descricao,
                "Código": p.codigo,
                "GTIN": p.gtin,
                "Preço original": p.preco_original,
                "Preço atual": p.preco_atual,
                "Preço de custo": p.preco_atual,
                "Preço de venda": p.preco_atual,
                "Marca": "",
                "Categoria": "",
                "Estoque": "",
            }
            for p in produtos
        ]
    )

    # limpeza final
    if not df.empty:
        df = df.drop_duplicates(subset=["Código", "Descrição"], keep="first").reset_index(drop=True)

    return df


def converter_upload_pdf_para_dataframe(arquivo_pdf) -> pd.DataFrame:
    texto_pdf = ler_texto_pdf_upload(arquivo_pdf)
    if not _texto(texto_pdf):
        return pd.DataFrame()

    return extrair_dataframe_pdf_catalogo(texto_pdf)
