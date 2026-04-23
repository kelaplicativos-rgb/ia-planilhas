from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import random
import re
import unicodedata
from typing import Any

import pandas as pd


REGISTRY_PATH = Path("bling_app_zero/output/gtin_registry.json")
REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)

GTIN_CANDIDATE_COLUMNS = [
    "GTIN/EAN",
    "GTIN",
    "EAN",
    "GTIN/EAN tributário",
    "GTIN/EAN Tributário",
    "GTIN tributário",
    "GTIN Tributário",
    "EAN tributário",
    "EAN Tributário",
    "GTIN/EAN da Embalagem",
    "GTIN/EAN da embalagem",
    "GTIN da Embalagem",
    "GTIN da embalagem",
    "EAN da Embalagem",
    "EAN da embalagem",
    "GTIN Embalagem",
    "EAN Embalagem",
    "Código de barras",
    "Codigo de barras",
    "Código de Barras",
    "Codigo de Barras",
    "Código de barras da embalagem",
    "Codigo de barras da embalagem",
]

GTIN_PARTIAL_MATCH_TERMS = [
    "gtin",
    "ean",
    "codigo de barras",
    "codigo barras",
    "cod barras",
    "barcode",
    "embalagem",
]


@dataclass
class GtinAuditItem:
    coluna: str
    total_preenchidos: int
    total_validos: int
    total_invalidos: int
    total_vazios: int


def _remover_acentos(valor: str) -> str:
    texto = str(valor or "")
    texto = unicodedata.normalize("NFKD", texto)
    return "".join(ch for ch in texto if not unicodedata.combining(ch))


def normalizar_texto(valor: Any) -> str:
    texto = _remover_acentos(str(valor or "")).strip().lower()
    texto = re.sub(r"[\s_/|()-]+", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def somente_digitos(valor: Any) -> str:
    return re.sub(r"\D+", "", str(valor or "").strip())


def _todos_digitos_iguais(texto: str) -> bool:
    return bool(texto) and len(set(texto)) == 1


def calcular_digito_gtin(corpo: str) -> int:
    soma = 0
    peso = 3

    for digito in reversed(corpo):
        soma += int(digito) * peso
        peso = 1 if peso == 3 else 3

    return (10 - (soma % 10)) % 10


def gtin_checksum_valido(gtin: str) -> bool:
    if not gtin or not gtin.isdigit():
        return False

    if len(gtin) not in {8, 12, 13, 14}:
        return False

    corpo = gtin[:-1]
    digito_informado = int(gtin[-1])
    digito_calculado = calcular_digito_gtin(corpo)
    return digito_calculado == digito_informado


def gtin_tem_prefixo_brasil(gtin: str) -> bool:
    if len(gtin) == 13:
        return gtin.startswith(("789", "790"))

    if len(gtin) == 14:
        return gtin[1:4] in {"789", "790"}

    return True


def gtin_tem_prefixo_gs1_alocado(gtin: str) -> bool:
    if not gtin or len(gtin) not in {13, 14}:
        return True

    prefixo = int(gtin[:3] if len(gtin) == 13 else gtin[1:4])

    faixas_validas = [
        (0, 19),
        (30, 39),
        (60, 139),
        (200, 299),
        (300, 379),
        (380, 380),
        (383, 383),
        (385, 385),
        (387, 387),
        (400, 440),
        (450, 459),
        (460, 469),
        (470, 470),
        (471, 471),
        (474, 474),
        (475, 475),
        (476, 476),
        (477, 477),
        (478, 478),
        (479, 479),
        (480, 480),
        (481, 481),
        (482, 482),
        (484, 484),
        (485, 485),
        (486, 486),
        (487, 487),
        (489, 489),
        (490, 499),
        (500, 509),
        (520, 521),
        (528, 528),
        (529, 529),
        (530, 530),
        (531, 531),
        (535, 535),
        (539, 539),
        (540, 549),
        (560, 560),
        (569, 569),
        (570, 579),
        (590, 590),
        (594, 594),
        (599, 599),
        (600, 601),
        (603, 603),
        (608, 608),
        (609, 609),
        (611, 611),
        (613, 613),
        (615, 615),
        (616, 616),
        (618, 618),
        (619, 619),
        (621, 621),
        (622, 622),
        (624, 624),
        (625, 625),
        (626, 626),
        (627, 627),
        (628, 628),
        (629, 629),
        (640, 649),
        (690, 699),
        (700, 709),
        (729, 729),
        (730, 739),
        (740, 740),
        (741, 741),
        (742, 742),
        (743, 743),
        (744, 744),
        (745, 745),
        (746, 746),
        (750, 750),
        (754, 755),
        (759, 759),
        (760, 769),
        (770, 771),
        (773, 773),
        (775, 775),
        (777, 777),
        (778, 778),
        (779, 779),
        (780, 780),
        (784, 784),
        (785, 785),
        (786, 786),
        (789, 790),
        (800, 839),
        (840, 849),
        (850, 850),
        (858, 858),
        (859, 859),
        (860, 860),
        (865, 865),
        (867, 867),
        (868, 869),
        (870, 879),
        (880, 880),
        (883, 883),
        (884, 884),
        (885, 885),
        (888, 888),
        (890, 890),
        (893, 893),
        (896, 896),
        (899, 899),
        (900, 919),
        (930, 939),
        (940, 949),
        (950, 950),
        (951, 951),
        (955, 955),
        (958, 958),
        (977, 979),
    ]

    return any(inicio <= prefixo <= fim for inicio, fim in faixas_validas)


def validar_gtin(valor: Any, aceitar_apenas_prefixo_br: bool = False) -> bool:
    texto = somente_digitos(valor)

    if not texto:
        return False

    if len(texto) not in {8, 12, 13, 14}:
        return False

    if _todos_digitos_iguais(texto):
        return False

    if not gtin_checksum_valido(texto):
        return False

    if not gtin_tem_prefixo_gs1_alocado(texto):
        return False

    if aceitar_apenas_prefixo_br and not gtin_tem_prefixo_brasil(texto):
        return False

    return True


def limpar_gtin(valor: Any, aceitar_apenas_prefixo_br: bool = False) -> str:
    texto = somente_digitos(valor)
    if not texto:
        return ""

    if not validar_gtin(texto, aceitar_apenas_prefixo_br=aceitar_apenas_prefixo_br):
        return ""

    return texto


def _normalizar_colunas(df: pd.DataFrame) -> dict[str, str]:
    return {normalizar_texto(col): str(col) for col in df.columns}


def _eh_coluna_gtin(nome_coluna: Any) -> bool:
    nome = normalizar_texto(nome_coluna)
    if not nome:
        return False

    candidatos_exatos = {normalizar_texto(col) for col in GTIN_CANDIDATE_COLUMNS}
    if nome in candidatos_exatos:
        return True

    possui_gtin_ou_ean = ("gtin" in nome) or ("ean" in nome)
    possui_codigo_barras = ("codigo de barras" in nome) or ("codigo barras" in nome)

    if possui_gtin_ou_ean or possui_codigo_barras:
        return True

    return any(termo in nome for termo in GTIN_PARTIAL_MATCH_TERMS[:4]) and (
        "barra" in nome or "barras" in nome
    )


def localizar_colunas_gtin(df: pd.DataFrame) -> list[str]:
    if not isinstance(df, pd.DataFrame) or len(df.columns) == 0:
        return []

    encontradas: list[str] = []

    for col in df.columns:
        nome_real = str(col)
        if _eh_coluna_gtin(nome_real) and nome_real not in encontradas:
            encontradas.append(nome_real)

    return encontradas


def serie_texto_limpa(df: pd.DataFrame, coluna: str) -> pd.Series:
    if not isinstance(df, pd.DataFrame) or coluna not in df.columns:
        return pd.Series(dtype="object")

    return (
        df[coluna]
        .astype(str)
        .str.strip()
        .replace({"nan": "", "None": "", "none": ""})
    )


def auditar_gtins_dataframe(
    df: pd.DataFrame,
    aceitar_apenas_prefixo_br: bool = False,
) -> dict[str, Any]:
    if not isinstance(df, pd.DataFrame) or len(df.columns) == 0:
        return {
            "colunas": [],
            "itens": [],
            "total_preenchidos": 0,
            "total_validos": 0,
            "total_invalidos": 0,
            "total_vazios": 0,
        }

    colunas = localizar_colunas_gtin(df)
    itens: list[dict[str, Any]] = []
    total_preenchidos = 0
    total_validos = 0
    total_invalidos = 0
    total_vazios = 0

    for coluna in colunas:
        serie = serie_texto_limpa(df, coluna)
        total_coluna = int(len(serie))
        vazios = int(serie.eq("").sum())
        preenchidos = int(total_coluna - vazios)

        validos = int(
            serie[serie.ne("")]
            .apply(
                lambda x: validar_gtin(
                    x,
                    aceitar_apenas_prefixo_br=aceitar_apenas_prefixo_br,
                )
            )
            .sum()
        )
        invalidos = int(preenchidos - validos)

        item = GtinAuditItem(
            coluna=coluna,
            total_preenchidos=preenchidos,
            total_validos=validos,
            total_invalidos=invalidos,
            total_vazios=vazios,
        )

        itens.append(item.__dict__)
        total_preenchidos += preenchidos
        total_validos += validos
        total_invalidos += invalidos
        total_vazios += vazios

    return {
        "colunas": colunas,
        "itens": itens,
        "total_preenchidos": int(total_preenchidos),
        "total_validos": int(total_validos),
        "total_invalidos": int(total_invalidos),
        "total_vazios": int(total_vazios),
    }


def contar_gtins_invalidos_df(
    df: pd.DataFrame,
    aceitar_apenas_prefixo_br: bool = False,
) -> int:
    auditoria = auditar_gtins_dataframe(
        df=df,
        aceitar_apenas_prefixo_br=aceitar_apenas_prefixo_br,
    )
    return int(auditoria.get("total_invalidos", 0))


def limpar_gtins_invalidos_df(
    df: pd.DataFrame,
    aceitar_apenas_prefixo_br: bool = False,
) -> tuple[pd.DataFrame, int]:
    if not isinstance(df, pd.DataFrame) or len(df.columns) == 0:
        return pd.DataFrame(), 0

    base = df.copy().fillna("")
    colunas = localizar_colunas_gtin(base)
    total_limpos = 0

    for coluna in colunas:
        serie_original = base[coluna].astype(str).fillna("")
        serie_limpa = serie_original.apply(
            lambda valor: limpar_gtin(
                valor,
                aceitar_apenas_prefixo_br=aceitar_apenas_prefixo_br,
            )
        )

        removidos = int(
            (
                serie_original.str.strip()
                .replace({"nan": "", "None": "", "none": ""})
                .ne("")
                & serie_limpa.eq("")
            ).sum()
        )

        base[coluna] = serie_limpa
        total_limpos += removidos

    return base.fillna(""), int(total_limpos)


def _carregar_registry() -> dict[str, Any]:
    if not REGISTRY_PATH.exists():
        return {"usados": []}

    try:
        data = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {"usados": []}
        usados = data.get("usados", [])
        if not isinstance(usados, list):
            usados = []
        return {"usados": [somente_digitos(v) for v in usados if somente_digitos(v)]}
    except Exception:
        return {"usados": []}


def _salvar_registry(registro: dict[str, Any]) -> None:
    usados = registro.get("usados", [])
    REGISTRY_PATH.write_text(
        json.dumps({"usados": usados}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def listar_gtins_registrados() -> set[str]:
    registro = _carregar_registry()
    return set(registro.get("usados", []))


def registrar_gtins(gtins: list[str]) -> None:
    registro = _carregar_registry()
    usados = set(registro.get("usados", []))
    for gtin in gtins:
        texto = somente_digitos(gtin)
        if texto:
            usados.add(texto)

    registro["usados"] = sorted(usados)
    _salvar_registry(registro)


def _coletar_gtins_existentes_no_df(df: pd.DataFrame) -> set[str]:
    encontrados: set[str] = set()
    if not isinstance(df, pd.DataFrame) or len(df.columns) == 0:
        return encontrados

    for coluna in localizar_colunas_gtin(df):
        serie = serie_texto_limpa(df, coluna)
        for valor in serie.tolist():
            texto = somente_digitos(valor)
            if texto:
                encontrados.add(texto)

    return encontrados


def gerar_gtin13(
    prefixo_base: str = "789",
    usados: set[str] | None = None,
    tentar_aleatorio: bool = False,
) -> str:
    prefixo = somente_digitos(prefixo_base)
    if not prefixo:
        prefixo = "789"

    if len(prefixo) > 12:
        prefixo = prefixo[:12]

    usados = set(usados or set())

    corpo_len = 12
    restante = corpo_len - len(prefixo)
    if restante <= 0:
        prefixo = prefixo[:12]
        restante = 12 - len(prefixo)

    if not tentar_aleatorio:
        for numero in range(10 ** max(restante, 1)):
            sequencia = str(numero).zfill(restante)
            corpo = f"{prefixo}{sequencia}"[:12]
            digito = calcular_digito_gtin(corpo)
            gtin = f"{corpo}{digito}"
            if gtin not in usados:
                return gtin
    else:
        for _ in range(50000):
            sequencia = "".join(str(random.randint(0, 9)) for _ in range(restante))
            corpo = f"{prefixo}{sequencia}"[:12]
            digito = calcular_digito_gtin(corpo)
            gtin = f"{corpo}{digito}"
            if gtin not in usados:
                return gtin

    raise RuntimeError("Não foi possível gerar um GTIN-13 único com o prefixo informado.")


def gerar_gtins_para_dataframe(
    df: pd.DataFrame,
    colunas_alvo: list[str] | None = None,
    prefixo_base: str = "789",
    modo: str = "vazios_e_invalidos",
    aceitar_apenas_prefixo_br: bool = False,
    registrar_no_arquivo: bool = True,
) -> tuple[pd.DataFrame, int, list[str]]:
    if not isinstance(df, pd.DataFrame) or len(df.columns) == 0:
        return pd.DataFrame(), 0, []

    base = df.copy().fillna("")
    colunas = colunas_alvo or localizar_colunas_gtin(base)
    colunas = [col for col in colunas if col in base.columns]

    if not colunas:
        return base.fillna(""), 0, []

    usados = listar_gtins_registrados()
    usados.update(_coletar_gtins_existentes_no_df(base))

    gerados: list[str] = []
    total_gerados = 0

    for coluna in colunas:
        novos_valores: list[str] = []

        for valor in base[coluna].astype(str).fillna("").tolist():
            texto = somente_digitos(valor)
            valido = (
                validar_gtin(
                    texto,
                    aceitar_apenas_prefixo_br=aceitar_apenas_prefixo_br,
                )
                if texto
                else False
            )

            deve_gerar = False

            if modo == "vazios":
                deve_gerar = not texto
            elif modo == "invalidos":
                deve_gerar = bool(texto) and not valido
            elif modo == "sobrescrever_tudo":
                deve_gerar = True
            else:
                deve_gerar = (not texto) or (bool(texto) and not valido)

            if deve_gerar:
                gtin_novo = gerar_gtin13(prefixo_base=prefixo_base, usados=usados)
                usados.add(gtin_novo)
                gerados.append(gtin_novo)
                novos_valores.append(gtin_novo)
                total_gerados += 1
            else:
                novos_valores.append(texto if valido else valor)

        base[coluna] = novos_valores

    if registrar_no_arquivo and gerados:
        registrar_gtins(gerados)

    return base.fillna(""), int(total_gerados), gerados
