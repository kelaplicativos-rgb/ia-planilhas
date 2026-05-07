from __future__ import annotations

import re
import unicodedata
from typing import Iterable

import pandas as pd


# Sugestões conservadoras para reduzir avisos do Bling quando o NCM vier vazio.
# Não substitui revisão fiscal/contábil. Só preenche quando a classificação fiscal está vazia.
# Formato: ((termos que precisam aparecer na descrição), NCM)
NCM_SUGESTOES_POR_TERMO: tuple[tuple[tuple[str, ...], str], ...] = (
    (("mouse",), "84716053"),
    (("teclado",), "84716052"),
    (("controle gamer",), "95045000"),
    (("controle game",), "95045000"),
    (("joystick",), "95045000"),
    (("gamepad",), "95045000"),
    (("fone", "bluetooth"), "85183000"),
    (("fone", "ouvido"), "85183000"),
    (("headset",), "85183000"),
    (("microfone",), "85181090"),
    (("caixa", "som"), "85182100"),
    (("speaker",), "85182100"),
    (("carregador",), "85044010"),
    (("fonte", "alimentacao"), "85044090"),
    (("fonte", "alimentação"), "85044090"),
    (("adaptador", "tomada"), "85366990"),
    (("cabo", "usb"), "85444200"),
    (("cabo", "hdmi"), "85444200"),
    (("cabo", "tipo c"), "85444200"),
    (("cabo", "type c"), "85444200"),
    (("hub", "usb"), "84718000"),
    (("webcam",), "85258919"),
    (("camera", "wifi"), "85258919"),
    (("câmera", "wifi"), "85258919"),
    (("camera", "seguranca"), "85258919"),
    (("câmera", "segurança"), "85258919"),
    (("suporte", "celular"), "39269090"),
    (("suporte", "veicular"), "39269090"),
    (("tripé",), "96200000"),
    (("tripe",), "96200000"),
    (("ring light",), "94054200"),
    (("luminaria",), "94054200"),
    (("luminária",), "94054200"),
    (("lanterna",), "85131010"),
    (("pilha",), "85061010"),
    (("bateria", "recarregavel"), "85075000"),
    (("bateria", "recarregável"), "85075000"),
    (("power bank",), "85076000"),
    (("carregador portatil",), "85076000"),
    (("carregador portátil",), "85076000"),
    (("cartao", "memoria"), "85235110"),
    (("cartão", "memória"), "85235110"),
    (("pendrive",), "85235110"),
    (("pen drive",), "85235110"),
    (("roteador",), "85176241"),
    (("repetidor", "wifi"), "85176241"),
    (("antena",), "85291019"),
    (("relogio", "smart"), "85176299"),
    (("relógio", "smart"), "85176299"),
    (("smartwatch",), "85176299"),
    (("calculadora",), "84701000"),
)

VALORES_VAZIOS_NCM = {
    "",
    "nan",
    "none",
    "null",
    "na",
    "n a",
    "indefinido",
    "sem ncm",
    "sem classificacao fiscal",
    "sem classificação fiscal",
}


def normalizar_para_busca(valor: object) -> str:
    texto = str(valor or "").strip().lower()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(ch for ch in texto if not unicodedata.combining(ch))
    texto = re.sub(r"[^a-z0-9]+", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def valor_ncm_vazio(valor: object) -> bool:
    texto = str(valor or "").strip()
    if not texto:
        return True
    return normalizar_para_busca(texto) in {normalizar_para_busca(v) for v in VALORES_VAZIOS_NCM}


def sugerir_ncm_por_descricao(descricao: object) -> str:
    texto = normalizar_para_busca(descricao)
    if not texto:
        return ""

    for termos, ncm in NCM_SUGESTOES_POR_TERMO:
        if all(normalizar_para_busca(termo) in texto for termo in termos):
            return ncm

    return ""


def localizar_colunas_ncm(colunas: Iterable[object], normalizar_nome) -> list[str]:
    encontradas: list[str] = []
    for col in colunas:
        nome = normalizar_nome(col)
        if "ncm" in nome or "classificacao fiscal" in nome or "classificação fiscal" in nome:
            encontradas.append(str(col))
    return encontradas


def preencher_ncm_sugerido(
    df: pd.DataFrame,
    descricao_coluna: str,
    ncm_colunas: list[str],
    *,
    logger=None,
) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return df
    if not descricao_coluna or descricao_coluna not in df.columns or not ncm_colunas:
        return df

    base = df.copy().fillna("")
    total_preenchido = 0

    for idx, row in base.iterrows():
        sugestao = sugerir_ncm_por_descricao(row.get(descricao_coluna, ""))
        if not sugestao:
            continue

        for col in ncm_colunas:
            if col in base.columns and valor_ncm_vazio(row.get(col, "")):
                base.at[idx, col] = sugestao
                total_preenchido += 1

    if total_preenchido > 0 and callable(logger):
        logger(
            f"{total_preenchido} NCM(s) vazio(s) preenchido(s) por sugestão local conservadora. Revise com contador quando necessário.",
            nivel="INFO",
        )

    return base.fillna("")
