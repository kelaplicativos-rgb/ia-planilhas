import re
import unicodedata
from typing import List, Tuple

import pandas as pd


def limpar_texto(valor) -> str:
    if valor is None:
        return ""
    try:
        if pd.isna(valor):
            return ""
    except Exception:
        pass

    texto = str(valor)
    texto = texto.replace("\n", " ").replace("\r", " ").replace("\t", " ")
    texto = re.sub(r"\s+", " ", texto)
    return texto.strip()


def remover_acentos(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", str(texto))
        if not unicodedata.combining(c)
    )


def slug_coluna(nome: str) -> str:
    nome = limpar_texto(nome)
    nome = remover_acentos(nome).lower()
    nome = nome.replace("/", " ").replace("\\", " ").replace("-", " ").replace("_", " ")
    nome = re.sub(r"[^a-z0-9 ]+", "", nome)
    nome = re.sub(r"\s+", " ", nome).strip()
    return nome


def formatar_preview_valor(valor) -> str:
    txt = limpar_texto(valor)
    if len(txt) > 90:
        return txt[:87] + "..."
    return txt


def normalizar_valor_numerico(valor) -> float:
    if valor is None:
        return 0.0

    if isinstance(valor, (int, float)) and not pd.isna(valor):
        return float(valor)

    texto = limpar_texto(valor)
    if not texto:
        return 0.0

    texto = texto.replace("R$", "").replace("%", "").strip()

    if "," in texto and "." in texto:
        if texto.rfind(",") > texto.rfind("."):
            texto = texto.replace(".", "").replace(",", ".")
        else:
            texto = texto.replace(",", "")
    else:
        if "," in texto:
            texto = texto.replace(".", "").replace(",", ".")

    texto = re.sub(r"[^0-9.\-]", "", texto)

    try:
        return float(texto)
    except Exception:
        return 0.0


def formatar_numero_brasileiro(valor: float) -> str:
    return f"{float(valor):.2f}".replace(".", ",")


def parece_numero(valor: str) -> bool:
    texto = limpar_texto(valor)
    if not texto:
        return False

    texto_limpo = re.sub(r"[^0-9,\.\-]", "", texto)
    if not texto_limpo:
        return False

    try:
        _ = normalizar_valor_numerico(texto)
        return True
    except Exception:
        return False


def parece_url(valor: str) -> bool:
    texto = limpar_texto(valor).lower()
    return texto.startswith("http://") or texto.startswith("https://") or "www." in texto


def parece_data(valor: str) -> bool:
    texto = limpar_texto(valor)
    if not texto:
        return False

    padroes = [
        r"^\d{2}/\d{2}/\d{4}$",
        r"^\d{4}-\d{2}-\d{2}$",
        r"^\d{2}-\d{2}-\d{4}$",
    ]
    return any(re.match(p, texto) for p in padroes)


def somente_digitos(valor: str) -> str:
    return re.sub(r"\D+", "", limpar_texto(valor))


def parece_gtin(valor: str) -> bool:
    dig = somente_digitos(valor)
    return len(dig) in {8, 12, 13, 14}


def parece_ncm(valor: str) -> bool:
    dig = somente_digitos(valor)
    return len(dig) == 8


def parece_cest(valor: str) -> bool:
    dig = somente_digitos(valor)
    return len(dig) == 7


def normalizar_lista_urls_imagem(valor) -> str:
    texto = limpar_texto(valor)
    if not texto:
        return ""

    partes = re.split(r"[|,;\n\r\t]+", texto)
    urls = []
    vistos = set()

    for parte in partes:
        url = limpar_texto(parte)
        if not url:
            continue

        chave = url.lower()
        if chave in vistos:
            continue

        vistos.add(chave)
        urls.append(url)

    return "|".join(urls)


def limpar_gtin(valor) -> str:
    return somente_digitos(valor)


def validar_gtin_checksum(gtin: str) -> bool:
    if not gtin or not gtin.isdigit():
        return False

    if len(gtin) not in {8, 12, 13, 14}:
        return False

    digitos = [int(d) for d in gtin]
    check_digit = digitos[-1]
    corpo = digitos[:-1]

    soma = 0
    peso = 3
    for n in reversed(corpo):
        soma += n * peso
        peso = 1 if peso == 3 else 3

    calculado = (10 - (soma % 10)) % 10
    return calculado == check_digit


def tratar_gtin(valor) -> Tuple[str, bool]:
    gtin = limpar_gtin(valor)
    if not gtin:
        return "", False
    if validar_gtin_checksum(gtin):
        return gtin, True
    return "", False


def aplicar_validacao_gtin_df(df: pd.DataFrame, coluna: str) -> Tuple[pd.DataFrame, List[str]]:
    logs: List[str] = []

    if coluna not in df.columns:
        return df, logs

    novos = []
    total_invalidos = 0
    total_validos = 0

    for idx, valor in enumerate(df[coluna].tolist(), start=1):
        txt_original = limpar_texto(valor)

        if not txt_original:
            novos.append("")
            continue

        gtin_corrigido, valido = tratar_gtin(txt_original)
        if valido:
            novos.append(gtin_corrigido)
            total_validos += 1
        else:
            novos.append("")
            total_invalidos += 1
            logs.append(f"Linha {idx}: GTIN inválido zerado ({txt_original})")

    df[coluna] = novos
    logs.append(f"GTIN válido: {total_validos}")
    logs.append(f"GTIN inválido zerado: {total_invalidos}")
    return df, logs
