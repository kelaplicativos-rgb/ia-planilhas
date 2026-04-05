import csv
import hashlib
import io
import re
import unicodedata
import xml.etree.ElementTree as ET
from typing import Dict, List, Tuple

import pandas as pd
import streamlit as st
from openpyxl.styles import numbers
from pandas.errors import ParserError

from bling_app_zero.scrapers.site_crawler import extrair_produtos_de_site


OPERACOES = {
    "cadastro": {
        "label": "Cadastro / atualização de produtos",
        "arquivo_saida": "bling_cadastro.xlsx",
    },
    "estoque": {
        "label": "Atualização de estoque",
        "arquivo_saida": "bling_estoque.xlsx",
    },
}


# ==========================================================
# LOG
# ==========================================================
def _log(msg: str) -> None:
    if "logs" not in st.session_state:
        st.session_state["logs"] = []
    st.session_state["logs"].append(str(msg))


# ==========================================================
# TEXTO / NOME DE COLUNAS
# ==========================================================
def _normalizar_texto(texto: str) -> str:
    texto = str(texto or "").strip().lower()
    texto = unicodedata.normalize("NFKD", texto)
    texto = texto.encode("ascii", "ignore").decode("utf-8")
    texto = re.sub(r"[^a-z0-9]+", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def _normalizar_colunas(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(col).strip() for col in df.columns]
    return df


def _mapa_colunas_normalizadas(colunas: List[str]) -> Dict[str, str]:
    return {_normalizar_texto(col): col for col in colunas}


def _render_lista_colunas_simples(colunas: List[str]) -> None:
    if not colunas:
        st.caption("Sem colunas para exibir.")
        return

    st.code("\n".join(str(c) for c in colunas if str(c).strip()), language=None)


# ==========================================================
# HASH / ESTADO
# ==========================================================
def _gerar_hash_texto(texto: str) -> str:
    return hashlib.md5(texto.encode("utf-8")).hexdigest()


def _limpar_estado_geracao(modo: str | None = None) -> None:
    for chave in [
        "df_saida",
        "df_saida_preview_hash",
        "excel_saida_bytes",
        "excel_saida_nome",
        "df_origem_hash",
        "coluna_preco_base_widget",
        "coluna_preco_destino_widget",
        "deposito_nome_widget",
        "calc_margem_lucro",
        "calc_impostos",
        "calc_taxa_extra",
        "calc_custo_fixo",
        "validacao_erros_saida",
        "validacao_avisos_saida",
        "logs_gtin_saida",
    ]:
        st.session_state.pop(chave, None)

    if modo:
        st.session_state.pop(f"mapeamento_manual_{modo}", None)


# ==========================================================
# CONVERSORES
# ==========================================================
def _to_text(valor) -> str:
    if valor is None:
        return ""
    try:
        if pd.isna(valor):
            return ""
    except Exception:
        pass
    texto = str(valor).strip()
    return "" if texto.lower() == "nan" else texto


def _to_float(valor) -> float:
    if valor is None:
        return 0.0

    try:
        if pd.isna(valor):
            return 0.0
    except Exception:
        pass

    texto = str(valor).strip()
    if not texto:
        return 0.0

    texto = (
        texto.replace("R$", "")
        .replace("r$", "")
        .replace("\u00a0", "")
        .replace(" ", "")
    )

    if "," in texto and "." in texto:
        if texto.rfind(",") > texto.rfind("."):
            texto = texto.replace(".", "").replace(",", ".")
        else:
            texto = texto.replace(",", "")
    elif "," in texto:
        texto = texto.replace(".", "").replace(",", ".")

    try:
        return float(texto)
    except Exception:
        return 0.0


def _serie_texto(df: pd.DataFrame, coluna: str) -> pd.Series:
    if coluna not in df.columns:
        return pd.Series([""] * len(df), index=df.index, dtype="string")

    return (
        df[coluna]
        .apply(_to_text)
        .astype("string")
        .fillna("")
        .str.strip()
    )


def _serie_float(df: pd.DataFrame, coluna: str, default: float = 0.0) -> pd.Series:
    if coluna not in df.columns:
        return pd.Series([default] * len(df), index=df.index, dtype="float64")

    serie = df[coluna].apply(_to_float)
    serie = pd.to_numeric(serie, errors="coerce").fillna(default).astype("float64")
    return serie


# ==========================================================
# LEITURA XML
# ==========================================================
def _local_name(tag: str) -> str:
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def _find_child_text(element: ET.Element, child_name: str) -> str:
    for child in list(element):
        if _local_name(child.tag) == child_name:
            return (child.text or "").strip()
    return ""


def _parse_nfe_xml_produtos(xml_bytes: bytes) -> pd.DataFrame:
    root = ET.fromstring(xml_bytes)
    itens = []

    for det in root.iter():
        if _local_name(det.tag) != "det":
            continue

        prod = None
        for child in list(det):
            if _local_name(child.tag) == "prod":
                prod = child
                break

        if prod is None:
            continue

        itens.append(
            {
                "codigo": _find_child_text(prod, "cProd"),
                "gtin": _find_child_text(prod, "cEAN"),
                "descricao": _find_child_text(prod, "xProd"),
                "ncm": _find_child_text(prod, "NCM"),
                "unidade": _find_child_text(prod, "uCom"),
                "quantidade": _find_child_text(prod, "qCom"),
                "preco_custo": _find_child_text(prod, "vUnCom"),
                "valor_total": _find_child_text(prod, "vProd"),
            }
        )

    if not itens:
        raise ValueError("Nenhum produto foi encontrado no XML da NF-e.")

    return _normalizar_colunas(pd.DataFrame(itens))


# ==========================================================
# LEITURA CSV ROBUSTA
# ==========================================================
def _detectar_encoding(raw_bytes: bytes) -> str:
    for enc in ["utf-8-sig", "utf-8", "cp1252", "latin1"]:
        try:
            raw_bytes.decode(enc)
            return enc
        except UnicodeDecodeError:
            continue
    return "latin1"


def _detectar_separador(texto: str) -> str | None:
    amostra = "\n".join(texto.splitlines()[:20]).strip()
    if not amostra:
        return None

    try:
        dialect = csv.Sniffer().sniff(amostra, delimiters=[",", ";", "\t", "|"])
        return dialect.delimiter
    except Exception:
        pass

    contagens = {
        ";": amostra.count(";"),
        ",": amostra.count(","),
        "\t": amostra.count("\t"),
        "|": amostra.count("|"),
    }
    melhor = max(contagens, key=contagens.get)
    return melhor if contagens[melhor] > 0 else None


def _tentar_ler_csv_com_config(texto: str, sep: str | None, tolerante: bool = False) -> pd.DataFrame:
    kwargs = {
        "engine": "python",
        "dtype": str,
        "keep_default_na": False,
    }

    kwargs["sep"] = sep if sep else None

    if tolerante:
        kwargs["on_bad_lines"] = "skip"

    return pd.read_csv(io.StringIO(texto), **kwargs)


def _ler_csv_robusto(arquivo) -> Tuple[pd.DataFrame, str]:
    raw_bytes = arquivo.getvalue()
    encoding = _detectar_encoding(raw_bytes)
    texto = raw_bytes.decode(encoding, errors="replace")
    separador = _detectar_separador(texto)

    configuracoes = [
        {"sep": separador, "tolerante": False, "rotulo": "detecção automática"},
        {"sep": ";", "tolerante": False, "rotulo": "separador ;"},
        {"sep": ",", "tolerante": False, "rotulo": "separador ,"},
        {"sep": "\t", "tolerante": False, "rotulo": "separador TAB"},
        {"sep": "|", "tolerante": False, "rotulo": "separador |"},
        {"sep": separador, "tolerante": True, "rotulo": "modo tolerante"},
        {"sep": ";", "tolerante": True, "rotulo": "modo tolerante ;"},
        {"sep": ",", "tolerante": True, "rotulo": "modo tolerante ,"},
    ]

    melhor_df = None
    melhor_rotulo = ""

    for cfg in configuracoes:
        try:
            df = _tentar_ler_csv_com_config(
                texto=texto,
                sep=cfg["sep"],
                tolerante=cfg["tolerante"],
            )
            df = _normalizar_colunas(df)
            if df is not None and not df.empty and len(df.columns) >= 2:
                melhor_df = df
                melhor_rotulo = cfg["rotulo"]
                break
        except ParserError:
            continue
        except Exception:
            continue

    if melhor_df is None or melhor_df.empty:
        raise ValueError("Não foi possível ler o CSV.")

    _log(
        f"CSV lido com encoding {encoding} e estratégia {melhor_rotulo}"
        + (f" | separador detectado: {repr(separador)}" if separador else "")
    )

    return melhor_df, f"CSV ({encoding})"


# ==========================================================
# LEITURA GERAL
# ==========================================================
def _ler_arquivo_upload(arquivo) -> Tuple[pd.DataFrame, str]:
    nome_arquivo = str(getattr(arquivo, "name", "")).lower()

    if nome_arquivo.endswith(".xml"):
        xml_bytes = arquivo.getvalue()
        try:
            return _parse_nfe_xml_produtos(xml_bytes), "XML NF-e"
        except Exception:
            arquivo.seek(0)
            try:
                return _normalizar_colunas(pd.read_xml(io.BytesIO(xml_bytes))), "XML genérico"
            except Exception as e:
                raise ValueError(f"Não foi possível ler o XML: {e}") from e

    if nome_arquivo.endswith(".csv"):
        return _ler_csv_robusto(arquivo)

    return _normalizar_colunas(pd.read_excel(arquivo, dtype=str)), "Planilha"


def _ler_planilha_modelo(upload_modelo, modo: str) -> Tuple[pd.DataFrame | None, List[str], str]:
    if not upload_modelo:
        return None, [], ""

    try:
        df_modelo, origem_modelo = _ler_arquivo_upload(upload_modelo)
        colunas_modelo = [str(c).strip() for c in df_modelo.columns if str(c).strip()]
        return df_modelo, colunas_modelo, origem_modelo
    except Exception as e:
        st.warning(f"Não foi possível ler a planilha modelo de {OPERACOES[modo]['label']}: {e}")
        _log(f"Falha ao ler modelo {modo}: {e}")
        return None, [], ""


# ==========================================================
# GTIN
# ==========================================================
GS1_PREFIXOS_VALIDOS: tuple[tuple[int, int], ...] = (
    (0, 19),
    (30, 39),
    (40, 49),
    (50, 59),
    (60, 99),
    (100, 139),
    (200, 299),
    (300, 379),
    (380, 380),
    (383, 383),
    (385, 385),
    (387, 387),
    (389, 389),
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
    (488, 488),
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
    (620, 620),
    (621, 621),
    (622, 622),
    (623, 623),
    (624, 624),
    (625, 625),
    (626, 626),
    (627, 627),
    (628, 628),
    (629, 629),
    (630, 630),
    (631, 631),
    (640, 649),
    (680, 681),
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
    (778, 779),
    (780, 780),
    (784, 784),
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
    (950, 951),
    (955, 955),
    (958, 958),
    (960, 969),
    (977, 977),
    (978, 979),
    (980, 980),
    (981, 984),
    (990, 999),
)

GS1_PREFIXOS_BLOQUEADOS: set[int] = {
    20, 21, 22, 23, 24, 25, 26, 27, 28, 29,
    952,
}


def _somente_digitos(valor: str) -> str:
    return re.sub(r"\D", "", str(valor or ""))


def _gtin_checksum_valido(gtin: str) -> bool:
    if len(gtin) not in (8, 12, 13, 14):
        return False
    if not gtin.isdigit():
        return False
    if set(gtin) == {"0"}:
        return False

    digitos = [int(c) for c in gtin]
    check = digitos[-1]
    corpo = digitos[:-1]

    soma = 0
    peso = 3
    for n in reversed(corpo):
        soma += n * peso
        peso = 1 if peso == 3 else 3

    calculado = (10 - (soma % 10)) % 10
    return calculado == check


def _gtin_sequencial_ou_repetitivo(gtin: str) -> bool:
    if not gtin:
        return True

    if len(set(gtin)) == 1:
        return True

    crescente = "012345678901234567890123456789"
    decrescente = "987654321098765432109876543210"

    corpo = gtin[:-1]
    if corpo and (corpo in crescente or corpo in decrescente):
        return True

    return False


def _prefixo_gs1_valido(gtin: str) -> bool:
    if len(gtin) == 8:
        return True

    if len(gtin) == 12:
        prefixo = int(gtin[:1])
        return 0 <= prefixo <= 9

    prefixo = int(gtin[:3])
    if prefixo in GS1_PREFIXOS_BLOQUEADOS:
        return False

    for inicio, fim in GS1_PREFIXOS_VALIDOS:
        if inicio <= prefixo <= fim:
            return True
    return False


def _gtin_estruturalmente_valido(gtin: str) -> bool:
    if not gtin:
        return False
    if len(gtin) not in (8, 12, 13, 14):
        return False
    if _gtin_sequencial_ou_repetitivo(gtin):
        return False
    if not _gtin_checksum_valido(gtin):
        return False
    if not _prefixo_gs1_valido(gtin):
        return False
    return True


def _limpar_gtin_invalido_serie(serie: pd.Series) -> pd.Series:
    def _limpar(valor: str) -> str:
        codigo = _somente_digitos(valor)
        if not codigo:
            return ""
        if _gtin_estruturalmente_valido(codigo):
            return codigo
        return ""

    return serie.apply(_limpar).astype("string")


def _coluna_parece_gtin_ou_ean(nome_coluna: str) -> bool:
    nome = _normalizar_texto(nome_coluna)
    if not nome:
        return False

    termos = {
        "gtin",
        "ean",
        "codigo de barras",
        "codigo barras",
        "cod barras",
        "cod de barras",
        "barcode",
        "cean",
        "ceantrib",
        "ean tributario",
        "gtin tributario",
    }

    if nome in termos:
        return True

    return any(termo in nome for termo in termos)


def _gerar_logs_limpeza_gtin(df_antes: pd.DataFrame, df_depois: pd.DataFrame) -> List[str]:
    logs: List[str] = []

    for col in df_depois.columns:
        if not _coluna_parece_gtin_ou_ean(col):
            continue

        antes = _serie_texto(df_antes, col)
        depois = _serie_texto(df_depois, col)
        qtd = int(((antes != "") & (depois == "")).sum())
        if qtd > 0:
            logs.append(f"Coluna '{col}': {qtd} GTIN/EAN inválido(s) foram deixados em branco.")

    return logs


# ==========================================================
# SUGESTÕES / MAPEAMENTO
# ==========================================================
def _sugerir_por_nome_modelo(colunas_origem: List[str], colunas_modelo: List[str]) -> Dict[str, str]:
    mapa_origem = _mapa_colunas_normalizadas(colunas_origem)
    resultado: Dict[str, str] = {}

    sinonimos = {
        "codigo": ["codigo", "código", "sku", "referencia", "ref"],
        "descricao": ["descricao", "descrição", "nome", "produto", "titulo"],
        "unidade": ["unidade", "un", "und"],
        "ncm": ["ncm"],
        "marca": ["marca", "fabricante"],
        "categoria": ["categoria", "departamento", "grupo"],
        "gtin": ["gtin", "ean", "codigo barras", "codigo de barras", "cean", "ceantrib"],
        "preco unitario": ["preco", "preço", "valor", "valor venda", "preco venda", "preco de venda"],
        "preco de custo": ["custo", "preco custo", "preço custo", "valor custo", "preco de custo"],
        "balanco": ["estoque", "quantidade", "qtd", "saldo", "balanco", "balanço"],
        "deposito": ["deposito", "depósito"],
        "peso": ["peso", "peso liquido", "peso líquido", "peso bruto"],
    }

    for col_modelo in colunas_modelo:
        chave = _normalizar_texto(col_modelo)

        if chave in mapa_origem:
            resultado[col_modelo] = mapa_origem[chave]
            continue

        for destino, termos in sinonimos.items():
            if destino in chave:
                for termo in termos:
                    termo_norm = _normalizar_texto(termo)
                    if termo_norm in mapa_origem:
                        resultado[col_modelo] = mapa_origem[termo_norm]
                        break
            if col_modelo in resultado:
                break

        if col_modelo not in resultado:
            for origem in colunas_origem:
                origem_norm = _normalizar_texto(origem)
                if origem_norm in chave or chave in origem_norm:
                    resultado[col_modelo] = origem
                    break

    return resultado


def _render_mapeamento_manual(
    df_origem: pd.DataFrame,
    colunas_destino: List[str],
    state_key: str,
) -> Dict[str, str]:
    st.subheader("Mapeamento manual")
    st.caption("Relacione manualmente as colunas da origem com as colunas reais do modelo final.")

    if state_key not in st.session_state:
        st.session_state[state_key] = _sugerir_por_nome_modelo(list(df_origem.columns), colunas_destino)

    mapeamento = dict(st.session_state.get(state_key, {}))
    colunas_origem = list(df_origem.columns)
    usados = set()

    cab1, cab2, cab3 = st.columns([1.3, 1.7, 2.0])
    with cab1:
        st.markdown("**Coluna do modelo**")
    with cab2:
        st.markdown("**Coluna da origem**")
    with cab3:
        st.markdown("**Exemplo**")

    for destino in colunas_destino:
        atual = str(mapeamento.get(destino, "") or "").strip()
        if atual:
            usados.add(atual)

        c1, c2, c3 = st.columns([1.3, 1.7, 2.0])

        with c1:
            st.markdown(f"`{destino}`")

        with c2:
            opcoes = [""]
            for col in colunas_origem:
                if col == atual or col not in (usados - ({atual} if atual else set())):
                    opcoes.append(col)

            indice = opcoes.index(atual) if atual in opcoes else 0

            novo_valor = st.selectbox(
                f"Origem para {destino}",
                opcoes,
                index=indice,
                key=f"map_{state_key}_{destino}",
                label_visibility="collapsed",
            )
            mapeamento[destino] = novo_valor or ""

        with c3:
            origem_exemplo = mapeamento.get(destino, "")
            if origem_exemplo and origem_exemplo in df_origem.columns:
                serie = _serie_texto(df_origem, origem_exemplo)
                serie = serie[serie != ""]
                exemplo = serie.iloc[0] if not serie.empty else ""
                st.caption(str(exemplo)[:120] if exemplo else "—")
            else:
                st.caption("—")

    st.session_state[state_key] = mapeamento
    return mapeamento


# ==========================================================
# CALCULADORA
# ==========================================================
def _detectar_coluna_preco_base(colunas_origem: List[str]) -> str:
    prioridades = [
        "custo",
        "preco custo",
        "preço custo",
        "preco de custo",
        "valor custo",
        "valor",
        "preco",
        "preço",
        "vuncom",
        "vprod",
    ]
    mapa = _mapa_colunas_normalizadas(colunas_origem)

    for chave in prioridades:
        chave_norm = _normalizar_texto(chave)
        if chave_norm in mapa:
            return mapa[chave_norm]

    for col in colunas_origem:
        cl = _normalizar_texto(col)
        if "custo" in cl or "preco" in cl or "valor" in cl:
            return col

    return ""


def _detectar_coluna_preco_destino(colunas_destino: List[str], modo: str) -> str:
    prioridades_estoque = [
        "preco unitario",
        "preço unitário",
        "preco unitário",
        "preço unitario",
    ]
    prioridades_gerais = [
        "preco",
        "preço",
        "preco venda",
        "preço venda",
        "preco de venda",
        "preço de venda",
        "valor de venda",
    ]

    mapa = _mapa_colunas_normalizadas(colunas_destino)

    if modo == "estoque":
        for chave in prioridades_estoque + prioridades_gerais:
            chave_norm = _normalizar_texto(chave)
            if chave_norm in mapa:
                return mapa[chave_norm]

    for chave in prioridades_gerais + prioridades_estoque:
        chave_norm = _normalizar_texto(chave)
        if chave_norm in mapa:
            return mapa[chave_norm]

    for col in colunas_destino:
        cl = _normalizar_texto(col)
        if "preco" in cl or "preço" in cl:
            return col

    return ""


def _calcular_preco_venda_unitario(
    preco_compra: float,
    percentual_impostos: float,
    margem_lucro: float,
    custo_fixo: float,
    taxa_extra: float,
) -> float:
    base = float(preco_compra or 0.0) + float(custo_fixo or 0.0)
    impostos = float(percentual_impostos or 0.0) / 100.0
    lucro = float(margem_lucro or 0.0) / 100.0
    taxa = float(taxa_extra or 0.0) / 100.0

    denominador = 1.0 - impostos - lucro - taxa
    if denominador <= 0:
        return 0.0

    resultado = base / denominador
    return round(resultado if resultado > 0 else 0.0, 2)


def _render_calculadora(
    df_origem: pd.DataFrame,
    colunas_destino_ativas: List[str],
    modo: str,
) -> Dict[str, object]:
    st.divider()
    st.subheader("Calculadora de preço")
    st.caption("O preço gerado será gravado na coluna real de preço do modelo final.")

    colunas_origem = list(df_origem.columns)

    base_default = st.session_state.get("coluna_preco_base_widget", "")
    if not base_default or base_default not in colunas_origem:
        base_default = _detectar_coluna_preco_base(colunas_origem)

    destino_default = st.session_state.get("coluna_preco_destino_widget", "")
    if not destino_default or destino_default not in colunas_destino_ativas:
        destino_default = _detectar_coluna_preco_destino(colunas_destino_ativas, modo)

    csel1, csel2 = st.columns(2)

    with csel1:
        opcoes_origem = [""] + colunas_origem
        idx_origem = opcoes_origem.index(base_default) if base_default in opcoes_origem else 0
        coluna_preco_base = st.selectbox(
            "Coluna da fornecedora usada como preço base",
            options=opcoes_origem,
            index=idx_origem,
            key="coluna_preco_base_widget",
        )

    with csel2:
        opcoes_destino = [""] + colunas_destino_ativas
        idx_destino = opcoes_destino.index(destino_default) if destino_default in opcoes_destino else 0
        coluna_preco_destino = st.selectbox(
            "Coluna do modelo final que receberá o preço gerado",
            options=opcoes_destino,
            index=idx_destino,
            key="coluna_preco_destino_widget",
        )

    preco_base_medio = 0.0
    exemplo_base = ""

    if coluna_preco_base and coluna_preco_base in df_origem.columns:
        serie_exemplo = _serie_texto(df_origem, coluna_preco_base)
        serie_exemplo = serie_exemplo[serie_exemplo != ""]
        exemplo_base = serie_exemplo.iloc[0] if not serie_exemplo.empty else ""

        precos = _serie_float(df_origem, coluna_preco_base, default=0.0)
        precos = precos[precos > 0]
        preco_base_medio = float(precos.mean()) if not precos.empty else 0.0

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        margem = st.number_input("Lucro (%)", min_value=0.0, max_value=100.0, value=float(st.session_state.get("calc_margem_lucro", 30.0)), step=1.0, key="calc_margem_lucro")
    with c2:
        impostos = st.number_input("Impostos (%)", min_value=0.0, max_value=100.0, value=float(st.session_state.get("calc_impostos", 0.0)), step=1.0, key="calc_impostos")
    with c3:
        taxa_extra = st.number_input("Taxas extras (%)", min_value=0.0, max_value=100.0, value=float(st.session_state.get("calc_taxa_extra", 15.0)), step=1.0, key="calc_taxa_extra")
    with c4:
        custo_fixo = st.number_input("Custo fixo (R$)", min_value=0.0, value=float(st.session_state.get("calc_custo_fixo", 0.0)), step=1.0, key="calc_custo_fixo")

    preco_sugerido = _calcular_preco_venda_unitario(
        preco_compra=preco_base_medio,
        percentual_impostos=impostos,
        margem_lucro=margem,
        custo_fixo=custo_fixo,
        taxa_extra=taxa_extra,
    )

    m1, m2, m3 = st.columns(3)
    with m1:
        st.metric("Preço base médio detectado", f"R$ {preco_base_medio:.2f}")
    with m2:
        st.metric("Preço gerado", f"R$ {preco_sugerido:.2f}")
    with m3:
        st.metric("Exemplo da coluna base", str(exemplo_base) if exemplo_base else "—")

    if margem + impostos + taxa_extra >= 100:
        st.warning("A soma de lucro + impostos + taxas extras precisa ser menor que 100%.")

    return {
        "coluna_preco_base": coluna_preco_base,
        "coluna_preco_destino": coluna_preco_destino,
        "margem": margem,
        "impostos": impostos,
        "taxa_extra": taxa_extra,
        "custo_fixo": custo_fixo,
    }


# ==========================================================
# CAMPOS FIXOS DO ESTOQUE
# ==========================================================
def _detectar_coluna_deposito(colunas_modelo: List[str]) -> str:
    mapa = _mapa_colunas_normalizadas(colunas_modelo)

    for chave in ["deposito", "depósito", "deposito obrigatorio", "depósito obrigatório"]:
        chave_norm = _normalizar_texto(chave)
        if chave_norm in mapa:
            return mapa[chave_norm]

    for col in colunas_modelo:
        cl = _normalizar_texto(col)
        if "deposito" in cl or "depósito" in cl:
            return col

    return ""


def _render_campos_fixos_estoque(colunas_modelo: List[str]) -> Dict[str, str]:
    st.divider()
    st.subheader("Campos fixos do estoque")

    coluna_deposito = _detectar_coluna_deposito(colunas_modelo)

    if coluna_deposito:
        deposito_nome = st.text_input(
            f"Nome do depósito para preencher a coluna '{coluna_deposito}'",
            value=st.session_state.get("deposito_nome_widget", ""),
            key="deposito_nome_widget",
            placeholder="Ex.: Geral, Loja 1, Principal...",
        )
    else:
        deposito_nome = ""

    return {
        "coluna_deposito": coluna_deposito,
        "deposito_nome": deposito_nome,
    }


# ==========================================================
# MONTAGEM DA SAÍDA
# ==========================================================
def _montar_df_saida_exato_modelo(
    df_origem: pd.DataFrame,
    colunas_modelo: List[str],
    mapeamento_manual: Dict[str, str],
    calculadora_cfg: Dict[str, object] | None,
    estoque_cfg: Dict[str, str] | None,
    modo: str,
) -> pd.DataFrame:
    df_saida = pd.DataFrame(index=df_origem.index)

    for col_modelo in colunas_modelo:
        origem = str(mapeamento_manual.get(col_modelo, "") or "").strip()
        if origem and origem in df_origem.columns:
            df_saida[col_modelo] = df_origem[origem]
        else:
            df_saida[col_modelo] = ""

    # Preço calculado no cadastro e no estoque
    if calculadora_cfg:
        col_base = str(calculadora_cfg.get("coluna_preco_base", "") or "").strip()
        col_destino = str(calculadora_cfg.get("coluna_preco_destino", "") or "").strip()

        if col_base and col_base in df_origem.columns and col_destino:
            base = _serie_float(df_origem, col_base, default=0.0)
            df_saida[col_destino] = base.apply(
                lambda valor: _calcular_preco_venda_unitario(
                    preco_compra=valor,
                    percentual_impostos=float(calculadora_cfg.get("impostos", 0.0)),
                    margem_lucro=float(calculadora_cfg.get("margem", 0.0)),
                    custo_fixo=float(calculadora_cfg.get("custo_fixo", 0.0)),
                    taxa_extra=float(calculadora_cfg.get("taxa_extra", 0.0)),
                )
                if float(valor) > 0
                else 0.0
            )

    # Depósito manual no estoque
    if modo == "estoque" and estoque_cfg:
        coluna_deposito = str(estoque_cfg.get("coluna_deposito", "") or "").strip()
        deposito_nome = str(estoque_cfg.get("deposito_nome", "") or "").strip()

        if coluna_deposito:
            df_saida[coluna_deposito] = deposito_nome

    # Limpeza automática de GTIN/EAN em qualquer coluna do modelo
    for col in df_saida.columns:
        if _coluna_parece_gtin_ou_ean(col):
            df_saida[col] = _limpar_gtin_invalido_serie(_serie_texto(df_saida, col))

    return df_saida


def _aplicar_limpeza_gtin_ean_df_saida(df_saida: pd.DataFrame) -> tuple[pd.DataFrame, int, List[str]]:
    df_antes = df_saida.copy()
    df_saida = df_saida.copy()
    total_limpados = 0

    for col in df_saida.columns:
        if not _coluna_parece_gtin_ou_ean(col):
            continue

        serie_original = _serie_texto(df_saida, col)
        serie_limpa = _limpar_gtin_invalido_serie(serie_original)
        total_limpados += int(((serie_original != "") & (serie_limpa == "")).sum())
        df_saida[col] = serie_limpa

    logs = _gerar_logs_limpeza_gtin(df_antes, df_saida)
    return df_saida, total_limpados, logs


# ==========================================================
# VALIDAÇÃO
# ==========================================================
def _buscar_coluna_por_alias(colunas: List[str], aliases: List[str]) -> str:
    mapa = _mapa_colunas_normalizadas(colunas)
    for alias in aliases:
        alias_norm = _normalizar_texto(alias)
        if alias_norm in mapa:
            return mapa[alias_norm]

    for col in colunas:
        cl = _normalizar_texto(col)
        for alias in aliases:
            alias_norm = _normalizar_texto(alias)
            if alias_norm in cl:
                return col

    return ""


def _validar_saida_bling(df_saida: pd.DataFrame, modo: str) -> Tuple[List[str], List[str]]:
    erros: List[str] = []
    avisos: List[str] = []

    if df_saida is None or df_saida.empty:
        erros.append("Nenhum dado foi gerado.")
        return erros, avisos

    if modo == "cadastro":
        col_codigo = _buscar_coluna_por_alias(list(df_saida.columns), ["codigo", "código"])
        col_descricao = _buscar_coluna_por_alias(list(df_saida.columns), ["descricao", "descrição", "nome"])
        col_unidade = _buscar_coluna_por_alias(list(df_saida.columns), ["unidade", "un"])
        col_ncm = _buscar_coluna_por_alias(list(df_saida.columns), ["ncm"])

        obrigatorias = [
            ("Código", col_codigo),
            ("Descrição", col_descricao),
            ("Unidade", col_unidade),
            ("NCM", col_ncm),
        ]
    else:
        col_codigo = _buscar_coluna_por_alias(list(df_saida.columns), ["codigo", "código"])
        col_deposito = _buscar_coluna_por_alias(list(df_saida.columns), ["deposito", "depósito"])
        col_balanco = _buscar_coluna_por_alias(list(df_saida.columns), ["balanco", "balanço", "estoque", "saldo"])

        obrigatorias = [
            ("Código", col_codigo),
            ("Depósito", col_deposito),
            ("Balanço", col_balanco),
        ]

    for nome, col_real in obrigatorias:
        if not col_real:
            erros.append(f"Coluna obrigatória ausente no modelo: {nome}")
            continue

        serie = _serie_texto(df_saida, col_real)
        vazios = int((serie == "").sum())
        if vazios > 0:
            erros.append(f"Coluna obrigatória '{col_real}' possui {vazios} linha(s) vazia(s).")

    return erros, avisos


# ==========================================================
# EXPORTAÇÃO EXATA
# ==========================================================
def _exportar_df_exato_para_excel_bytes(df: pd.DataFrame) -> bytes:
    output = io.BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Produtos")
        ws = writer.sheets["Produtos"]

        texto_alvos = {
            "codigo",
            "código",
            "ean",
            "gtin",
            "ncm",
            "codigo de barras",
            "código de barras",
            "cean",
            "ceantrib",
            "ean tributario",
            "ean tributário",
            "gtin tributario",
            "gtin tributário",
        }
        texto_alvos_normalizados = {_normalizar_texto(x) for x in texto_alvos}
        mapa_headers = {cell.value: cell.column_letter for cell in ws[1]}

        for header, col_letter in mapa_headers.items():
            header_normalizado = _normalizar_texto(header)
            if header_normalizado in texto_alvos_normalizados or _coluna_parece_gtin_ou_ean(header):
                for cell in ws[col_letter]:
                    cell.number_format = numbers.FORMAT_TEXT

    output.seek(0)
    return output.getvalue()


# ==========================================================
# UI
# ==========================================================
def render_origem_dados() -> None:
    st.subheader("Planilhas modelo para o download")
    st.caption("Anexe os modelos oficiais. O arquivo final será baixado exatamente com as colunas e a ordem do modelo correspondente.")

    mc1, mc2 = st.columns(2)

    with mc1:
        upload_modelo_cadastro = st.file_uploader(
            "Modelo de cadastro / atualização de produtos",
            type=["xlsx", "xls", "csv"],
            key="upload_modelo_cadastro",
        )

    with mc2:
        upload_modelo_estoque = st.file_uploader(
            "Modelo de atualização de estoque",
            type=["xlsx", "xls", "csv"],
            key="upload_modelo_estoque",
        )

    df_modelo_cadastro, colunas_modelo_cadastro, origem_modelo_cadastro = _ler_planilha_modelo(upload_modelo_cadastro, "cadastro")
    df_modelo_estoque, colunas_modelo_estoque, origem_modelo_estoque = _ler_planilha_modelo(upload_modelo_estoque, "estoque")

    modo = st.radio(
        "Selecione a operação antes de tudo",
        options=["cadastro", "estoque"],
        format_func=lambda x: OPERACOES[x]["label"],
        horizontal=True,
        key="tipo_operacao_bling",
    )

    config = OPERACOES[modo]
    arquivo_saida = config["arquivo_saida"]

    if modo == "cadastro":
        df_modelo_ativo = df_modelo_cadastro
        colunas_modelo_ativas = colunas_modelo_cadastro
        origem_modelo_ativo = origem_modelo_cadastro
        nome_modelo_ativo = getattr(upload_modelo_cadastro, "name", "")
    else:
        df_modelo_ativo = df_modelo_estoque
        colunas_modelo_ativas = colunas_modelo_estoque
        origem_modelo_ativo = origem_modelo_estoque
        nome_modelo_ativo = getattr(upload_modelo_estoque, "name", "")

    st.info(
        f"Operação selecionada: **{config['label']}**. "
        "Você vai mapear manualmente, gerar o preview final e só depois baixar."
    )

    if nome_modelo_ativo:
        st.success(
            f"Modelo ativo carregado: **{nome_modelo_ativo}** "
            f"({origem_modelo_ativo}) com **{len(colunas_modelo_ativas)}** colunas."
        )
        with st.expander("Ver colunas do modelo ativo"):
            _render_lista_colunas_simples(colunas_modelo_ativas)
    else:
        st.warning("Anexe a planilha modelo da operação selecionada antes de gerar o download.")
        return

    arquivo = st.file_uploader(
        "Anexar planilha ou XML da fornecedora",
        type=["xlsx", "xls", "csv", "xml"],
        key=f"upload_origem_{modo}",
    )

    url_site = st.text_input(
        "Campo de site da fornecedora / e-commerce",
        key=f"url_site_fornecedor_{modo}",
        placeholder="https://loja-do-fornecedor.com.br",
        help="Cole a URL da loja. O sistema tenta varrer categorias e páginas de produto para extrair nome, preço, GTIN, código, categoria, imagens e demais dados disponíveis.",
    )

    ac1, ac2 = st.columns([1, 1])
    with ac1:
        buscar_site = st.button("Buscar produtos do site", width="stretch", key=f"btn_buscar_site_{modo}")
    with ac2:
        limpar_site = st.button("Limpar site carregado", width="stretch", key=f"btn_limpar_site_{modo}")

    site_df_key = f"site_df_origem_{modo}"
    site_url_key = f"site_url_origem_{modo}"

    if limpar_site:
        st.session_state.pop(site_df_key, None)
        st.session_state.pop(site_url_key, None)
        st.rerun()

    if buscar_site:
        if not str(url_site or '').strip():
            st.error("Informe a URL do site para iniciar a varredura.")
            return

        with st.spinner("Varrendo o site, categorias e páginas de produto..."):
            try:
                df_site = extrair_produtos_de_site(str(url_site).strip())
                if df_site is None or df_site.empty:
                    st.error("A varredura terminou sem produtos válidos.")
                    return
                st.session_state[site_df_key] = df_site.copy()
                st.session_state[site_url_key] = str(url_site).strip()
                _limpar_estado_geracao(modo)
                st.success(f"Varredura concluída com sucesso. {len(df_site)} produto(s) encontrados no site.")
            except Exception as e:
                st.error(f"Erro ao varrer o site: {e}")
                _log(f"Erro ao varrer o site {url_site}: {e}")
                return

    df_origem = None
    origem_atual = ""
    nome_arquivo = ""

    if arquivo is not None:
        try:
            df_origem, origem_atual = _ler_arquivo_upload(arquivo)
            nome_arquivo = str(getattr(arquivo, "name", "arquivo"))
            st.session_state.pop(site_df_key, None)
            st.session_state.pop(site_url_key, None)
        except Exception as e:
            st.error(f"Erro ao ler arquivo: {e}")
            _log(f"Erro ao ler arquivo {getattr(arquivo, 'name', 'arquivo')}: {e}")
            return
    elif site_df_key in st.session_state:
        df_origem = st.session_state.get(site_df_key)
        origem_atual = "Site da fornecedora"
        nome_arquivo = str(st.session_state.get(site_url_key, "site"))

    if df_origem is None:
        return

    if df_origem is None or df_origem.empty:
        st.warning("A origem foi lida, mas não possui dados para processar.")
        return
    assinatura_modelo = f"{modo}|{nome_modelo_ativo}|{'|'.join(colunas_modelo_ativas)}"
    origem_hash = _gerar_hash_texto(
        f"{nome_arquivo}|{'|'.join(map(str, df_origem.columns))}|{len(df_origem)}|{assinatura_modelo}"
    )

    if st.session_state.get("df_origem_hash") != origem_hash:
        _limpar_estado_geracao()
        st.session_state.pop(f"mapeamento_manual_{modo}", None)

    st.session_state["df_origem"] = df_origem.copy()
    st.session_state["origem_atual"] = origem_atual
    st.session_state["origem_arquivo_nome"] = nome_arquivo
    st.session_state["df_origem_hash"] = origem_hash

    st.caption(f"Origem lida: `{nome_arquivo}` | Origem detectada: `{origem_atual}`")

    st.subheader("Preview da origem")
    st.dataframe(df_origem.head(10), width="stretch")

    state_key = f"mapeamento_manual_{modo}"
    mapeamento_manual = _render_mapeamento_manual(
        df_origem=df_origem,
        colunas_destino=colunas_modelo_ativas,
        state_key=state_key,
    )

    calculadora_cfg = _render_calculadora(
        df_origem=df_origem,
        colunas_destino_ativas=colunas_modelo_ativas,
        modo=modo,
    )

    estoque_cfg = None
    if modo == "estoque":
        estoque_cfg = _render_campos_fixos_estoque(colunas_modelo_ativas)

    st.divider()
    st.subheader("Preview do que será baixado")

    df_preview_saida = _montar_df_saida_exato_modelo(
        df_origem=df_origem,
        colunas_modelo=colunas_modelo_ativas,
        mapeamento_manual=mapeamento_manual,
        calculadora_cfg=calculadora_cfg,
        estoque_cfg=estoque_cfg,
        modo=modo,
    )

    erros_preview, avisos_preview = _validar_saida_bling(df_preview_saida, modo)
    st.session_state["validacao_erros_saida"] = erros_preview
    st.session_state["validacao_avisos_saida"] = avisos_preview

    st.dataframe(df_preview_saida.head(20), width="stretch")

    if erros_preview:
        st.error("Pendências antes do download:\n\n- " + "\n- ".join(erros_preview))
    elif avisos_preview:
        st.warning("Avisos:\n\n- " + "\n- ".join(avisos_preview))
    else:
        st.success("Preview válido para gerar o arquivo final.")

    b1, b2, b3 = st.columns(3)

    with b1:
        if st.button("Gerar preview final", width="stretch"):
            try:
                df_saida_final = _montar_df_saida_exato_modelo(
                    df_origem=df_origem,
                    colunas_modelo=colunas_modelo_ativas,
                    mapeamento_manual=mapeamento_manual,
                    calculadora_cfg=calculadora_cfg,
                    estoque_cfg=estoque_cfg,
                    modo=modo,
                )

                df_saida_final, total_limpados, logs_gtin = _aplicar_limpeza_gtin_ean_df_saida(df_saida_final)
                erros_final, avisos_final = _validar_saida_bling(df_saida_final, modo)
                st.session_state["validacao_erros_saida"] = erros_final
                st.session_state["validacao_avisos_saida"] = avisos_final
                st.session_state["logs_gtin_saida"] = logs_gtin

                if erros_final:
                    st.error("Não foi possível liberar o download porque ainda existem pendências.")
                    return

                excel_bytes = _exportar_df_exato_para_excel_bytes(df_saida_final)

                st.session_state["df_saida"] = df_saida_final.copy()
                st.session_state["df_saida_preview_hash"] = origem_hash
                st.session_state["excel_saida_bytes"] = excel_bytes
                st.session_state["excel_saida_nome"] = arquivo_saida

                if total_limpados > 0:
                    st.success(f"Preview final gerado com sucesso. {total_limpados} GTIN/EAN inválido(s) foram deixados em branco.")
                else:
                    st.success("Preview final gerado com sucesso. Revise abaixo antes de baixar.")

            except Exception as e:
                st.error(f"Erro ao gerar preview final: {e}")
                _log(f"Erro ao gerar preview final: {e}")

    with b2:
        if st.button("Limpar GTIN/EAN inválido", width="stretch"):
            try:
                df_saida_limpa = _montar_df_saida_exato_modelo(
                    df_origem=df_origem,
                    colunas_modelo=colunas_modelo_ativas,
                    mapeamento_manual=mapeamento_manual,
                    calculadora_cfg=calculadora_cfg,
                    estoque_cfg=estoque_cfg,
                    modo=modo,
                )
                df_saida_limpa, total_limpados, logs_gtin = _aplicar_limpeza_gtin_ean_df_saida(df_saida_limpa)

                erros_final, avisos_final = _validar_saida_bling(df_saida_limpa, modo)
                st.session_state["validacao_erros_saida"] = erros_final
                st.session_state["validacao_avisos_saida"] = avisos_final
                st.session_state["logs_gtin_saida"] = logs_gtin

                if erros_final:
                    st.error("A limpeza foi aplicada, mas ainda existem pendências antes do download.")
                    return

                excel_bytes = _exportar_df_exato_para_excel_bytes(df_saida_limpa)

                st.session_state["df_saida"] = df_saida_limpa.copy()
                st.session_state["df_saida_preview_hash"] = origem_hash
                st.session_state["excel_saida_bytes"] = excel_bytes
                st.session_state["excel_saida_nome"] = arquivo_saida

                if total_limpados > 0:
                    st.success(f"Limpeza concluída. {total_limpados} GTIN/EAN inválido(s) foram deixados em branco.")
                else:
                    st.success("Limpeza concluída. Nenhum GTIN/EAN inválido foi encontrado para zerar.")

            except Exception as e:
                st.error(f"Erro ao limpar GTIN/EAN inválido: {e}")
                _log(f"Erro ao limpar GTIN/EAN inválido: {e}")

    with b3:
        if st.button("Limpar mapeamento", width="stretch"):
            st.session_state[state_key] = {}
            st.session_state.pop("df_saida", None)
            st.session_state.pop("df_saida_preview_hash", None)
            st.session_state.pop("excel_saida_bytes", None)
            st.session_state.pop("excel_saida_nome", None)
            st.session_state.pop("logs_gtin_saida", None)
            st.rerun()

    logs_gtin_saida = st.session_state.get("logs_gtin_saida", [])
    if logs_gtin_saida:
        st.caption("Validação de GTIN/EAN aplicada no arquivo final:")
        for linha in logs_gtin_saida:
            st.caption(f"- {linha}")

    df_saida_state = st.session_state.get("df_saida")
    df_saida_hash = st.session_state.get("df_saida_preview_hash")
    excel_saida_bytes = st.session_state.get("excel_saida_bytes")
    excel_saida_nome = st.session_state.get("excel_saida_nome", arquivo_saida)

    if (
        isinstance(df_saida_state, pd.DataFrame)
        and not df_saida_state.empty
        and df_saida_hash == origem_hash
        and excel_saida_bytes
    ):
        st.divider()
        st.subheader("Preview final validado para download")
        st.caption(f"{len(df_saida_state)} linhas × {len(df_saida_state.columns)} colunas")
        st.dataframe(df_saida_state.head(50), width="stretch")

        st.download_button(
            f"Baixar arquivo de {config['label']}",
            data=excel_saida_bytes,
            file_name=excel_saida_nome,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            width="stretch",
        )


def tela_origem_dados() -> None:
    render_origem_dados()
