import csv
import hashlib
import io
import xml.etree.ElementTree as ET
from typing import Dict, List, Tuple

import pandas as pd
import streamlit as st
from pandas.errors import ParserError

from bling_app_zero.core.mapeamento_ia import mapear_colunas_ia
from bling_app_zero.core.memoria_fornecedor import (
    recuperar_mapeamento,
    salvar_mapeamento,
)
from bling_app_zero.core.precificacao import (
    calcular_preco_compra_automatico_df,
    calcular_preco_venda,
    calcular_preco_venda_df,
)
from bling_app_zero.utils.excel import df_to_excel_bytes


OPERACOES = {
    "cadastro": {
        "label": "Cadastro / atualização de produtos",
        "arquivo_saida": "bling_cadastro.xlsx",
        "colunas_destino_padrao": [
            "sku",
            "nome",
            "gtin",
            "ncm",
            "marca",
            "categoria",
            "preco",
            "custo",
            "estoque",
            "peso",
        ],
        "defaults": {},
    },
    "estoque": {
        "label": "Atualização de estoque",
        "arquivo_saida": "bling_estoque.xlsx",
        "colunas_destino_padrao": [
            "sku",
            "estoque",
        ],
        "defaults": {},
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
# UTIL
# ==========================================================
def _gerar_hash_texto(texto: str) -> str:
    return hashlib.md5(texto.encode("utf-8")).hexdigest()


def _gerar_hash_arquivo_df(df: pd.DataFrame, nome_arquivo: str) -> str:
    base = f"{nome_arquivo}|{'|'.join(map(str, df.columns))}|{len(df)}"
    return _gerar_hash_texto(base)


def _normalizar_colunas(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(col).strip() for col in df.columns]
    return df


def _local_name(tag: str) -> str:
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def _find_child_text(element: ET.Element, child_name: str) -> str:
    for child in list(element):
        if _local_name(child.tag) == child_name:
            return (child.text or "").strip()
    return ""


# ==========================================================
# XML
# ==========================================================
def _parse_nfe_xml_produtos(xml_bytes: bytes) -> pd.DataFrame:
    root = ET.fromstring(xml_bytes)
    itens = []

    for det in root.iter():
        if _local_name(det.tag) != "det":
            continue

        prod = None
        imposto = None

        for child in list(det):
            nome = _local_name(child.tag)
            if nome == "prod":
                prod = child
            elif nome == "imposto":
                imposto = child

        if prod is None:
            continue

        item = {
            "cprod": _find_child_text(prod, "cProd"),
            "cean": _find_child_text(prod, "cEAN"),
            "xprod": _find_child_text(prod, "xProd"),
            "ncm": _find_child_text(prod, "NCM"),
            "cfop": _find_child_text(prod, "CFOP"),
            "ucom": _find_child_text(prod, "uCom"),
            "qcom": _find_child_text(prod, "qCom"),
            "vuncom": _find_child_text(prod, "vUnCom"),
            "vprod": _find_child_text(prod, "vProd"),
            "ceantrib": _find_child_text(prod, "cEANTrib"),
            "utrib": _find_child_text(prod, "uTrib"),
            "qtrib": _find_child_text(prod, "qTrib"),
            "vuntrib": _find_child_text(prod, "vUnTrib"),
        }

        if imposto is not None:
            item["vtottrib"] = _find_child_text(imposto, "vTotTrib")
        else:
            item["vtottrib"] = ""

        itens.append(item)

    if not itens:
        raise ValueError("Nenhum produto foi encontrado no XML da NF-e.")

    df = pd.DataFrame(itens)

    if "vuncom" in df.columns and "custo_total_item_xml" not in df.columns:
        df["custo_total_item_xml"] = df["vuncom"]

    return _normalizar_colunas(df)


# ==========================================================
# CSV ROBUSTO
# ==========================================================
def _detectar_encoding(raw_bytes: bytes) -> str:
    candidatos = ["utf-8-sig", "utf-8", "cp1252", "latin1"]

    for enc in candidatos:
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
    if contagens[melhor] > 0:
        return melhor

    return None


def _tentar_ler_csv_com_config(
    texto: str,
    sep: str | None,
    tolerante: bool = False,
) -> pd.DataFrame:
    kwargs = {
        "engine": "python",
        "dtype": str,
        "keep_default_na": False,
    }

    if sep:
        kwargs["sep"] = sep
    else:
        kwargs["sep"] = None

    if tolerante:
        kwargs["on_bad_lines"] = "skip"

    return pd.read_csv(io.StringIO(texto), **kwargs)


def _ler_csv_robusto(arquivo) -> Tuple[pd.DataFrame, str]:
    raw_bytes = arquivo.getvalue()
    encoding = _detectar_encoding(raw_bytes)
    texto = raw_bytes.decode(encoding, errors="replace")
    separador = _detectar_separador(texto)

    tentativas = []

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

        except ParserError as e:
            tentativas.append(f"{cfg['rotulo']}: {e}")
        except Exception as e:
            tentativas.append(f"{cfg['rotulo']}: {e}")

    if melhor_df is None or melhor_df.empty:
        detalhes = " | ".join(tentativas[-4:]) if tentativas else "sem detalhes"
        raise ValueError(f"Não foi possível ler o CSV. Tentativas: {detalhes}")

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
                df_xml = pd.read_xml(io.BytesIO(xml_bytes))
                return _normalizar_colunas(df_xml), "XML genérico"
            except Exception as e:
                raise ValueError(f"Não foi possível ler o XML: {e}") from e

    if nome_arquivo.endswith(".csv"):
        return _ler_csv_robusto(arquivo)

    df_excel = pd.read_excel(arquivo, dtype=str)
    return _normalizar_colunas(df_excel), "Planilha"


def _ler_planilha_modelo(upload_modelo, modo: str) -> Tuple[pd.DataFrame | None, List[str], str]:
    if not upload_modelo:
        return None, OPERACOES[modo]["colunas_destino_padrao"], ""

    try:
        df_modelo, origem_modelo = _ler_arquivo_upload(upload_modelo)
        if df_modelo is None:
            return None, OPERACOES[modo]["colunas_destino_padrao"], ""

        colunas_modelo = [str(c).strip() for c in df_modelo.columns if str(c).strip()]
        if not colunas_modelo:
            return None, OPERACOES[modo]["colunas_destino_padrao"], ""

        return df_modelo, colunas_modelo, origem_modelo
    except Exception as e:
        st.warning(f"Não foi possível ler a planilha modelo de {OPERACOES[modo]['label']}: {e}")
        _log(f"Falha ao ler modelo {modo}: {e}")
        return None, OPERACOES[modo]["colunas_destino_padrao"], ""


# ==========================================================
# ESTADO
# ==========================================================
def _limpar_estado_geracao(modo: str | None = None) -> None:
    chaves_base = [
        "df_saida",
        "df_saida_preview_hash",
        "excel_saida_bytes",
        "excel_saida_nome",
        "df_origem_hash",
        "coluna_preco_base_cadastro",
        "coluna_preco_destino_cadastro",
        "modelo_cadastro_hash",
        "modelo_estoque_hash",
    ]
    for chave in chaves_base:
        st.session_state.pop(chave, None)

    if modo:
        st.session_state.pop(f"mapeamento_manual_{modo}", None)


# ==========================================================
# MAPEAMENTO / SAÍDA
# ==========================================================
def _montar_df_saida_base(
    df_origem: pd.DataFrame,
    colunas_destino: List[str],
    mapeamento_manual: Dict[str, str],
    defaults: Dict[str, object] | None = None,
) -> pd.DataFrame:
    defaults = defaults or {}
    df_saida = pd.DataFrame(index=df_origem.index)

    for destino in colunas_destino:
        origem_selecionada = str(mapeamento_manual.get(destino, "") or "").strip()

        if origem_selecionada and origem_selecionada in df_origem.columns:
            df_saida[destino] = df_origem[origem_selecionada]
        else:
            valor_padrao = defaults.get(destino, "")
            df_saida[destino] = valor_padrao

    return df_saida


def _aplicar_modelo_na_saida(
    df_saida_base: pd.DataFrame,
    colunas_modelo: List[str],
    df_modelo: pd.DataFrame | None = None,
) -> pd.DataFrame:
    df_final = pd.DataFrame(index=df_saida_base.index)

    for col in colunas_modelo:
        if col in df_saida_base.columns:
            df_final[col] = df_saida_base[col]
        else:
            valor_padrao = ""
            if df_modelo is not None and not df_modelo.empty and col in df_modelo.columns:
                try:
                    primeiro = df_modelo[col].iloc[0]
                    valor_padrao = "" if pd.isna(primeiro) else primeiro
                except Exception:
                    valor_padrao = ""
            df_final[col] = valor_padrao

    return df_final


def _sugerir_mapeamento_inicial(
    colunas_origem: List[str],
    colunas_destino: List[str],
    memoria: Dict,
) -> Dict[str, str]:
    mapeamento_manual: Dict[str, str] = {}

    try:
        mapeamento_memoria = recuperar_mapeamento(memoria, colunas_origem)
    except Exception:
        mapeamento_memoria = {}

    if mapeamento_memoria:
        for origem, destino in mapeamento_memoria.items():
            if destino in colunas_destino and origem in colunas_origem:
                if destino not in mapeamento_manual:
                    mapeamento_manual[destino] = origem

    try:
        mapa_ia = mapear_colunas_ia(colunas_origem, colunas_destino)
    except Exception:
        mapa_ia = {}

    for origem, dados in mapa_ia.items():
        destino = str(dados.get("destino", "") or "").strip()
        score = float(dados.get("score", 0) or 0)

        if (
            destino
            and destino in colunas_destino
            and origem in colunas_origem
            and score >= 0.60
            and destino not in mapeamento_manual
        ):
            mapeamento_manual[destino] = origem

    return mapeamento_manual


def _render_mapeamento_manual(
    df_origem: pd.DataFrame,
    colunas_destino: List[str],
    state_key: str,
) -> Dict[str, str]:
    st.subheader("Mapeamento manual")
    st.caption("Relacione manualmente as colunas da origem com as colunas do arquivo final.")

    if state_key not in st.session_state:
        st.session_state[state_key] = {}

    mapeamento = dict(st.session_state.get(state_key, {}))
    colunas_origem = list(df_origem.columns)

    cab1, cab2, cab3 = st.columns([1.25, 1.8, 2.1])
    with cab1:
        st.markdown("**Coluna final**")
    with cab2:
        st.markdown("**Coluna da origem**")
    with cab3:
        st.markdown("**Exemplo**")

    usados = set()

    for destino in colunas_destino:
        atual = str(mapeamento.get(destino, "") or "").strip()
        if atual:
            usados.add(atual)

        c1, c2, c3 = st.columns([1.25, 1.8, 2.1])

        with c1:
            st.markdown(f"`{destino}`")

        with c2:
            opcoes = [""]
            for col in colunas_origem:
                if col == atual or col not in (usados - ({atual} if atual else set())):
                    opcoes.append(col)

            index = opcoes.index(atual) if atual in opcoes else 0

            novo_valor = st.selectbox(
                f"Origem para {destino}",
                opcoes,
                index=index,
                key=f"map_{state_key}_{destino}",
                label_visibility="collapsed",
            )
            mapeamento[destino] = novo_valor or ""

        with c3:
            origem_exemplo = mapeamento.get(destino, "")
            if origem_exemplo and origem_exemplo in df_origem.columns:
                serie = df_origem[origem_exemplo].astype(str).replace("nan", "").replace("None", "")
                serie = serie[serie.str.strip() != ""]
                exemplo = serie.iloc[0] if not serie.empty else ""
                st.caption(str(exemplo)[:120] if exemplo else "—")
            else:
                st.caption("—")

    st.session_state[state_key] = mapeamento
    return mapeamento


# ==========================================================
# PREÇO
# ==========================================================
def _detectar_coluna_preco_base(colunas_origem: List[str]) -> str:
    prioridades = [
        "custo",
        "preco_custo",
        "preço_custo",
        "preco de custo",
        "preço de custo",
        "valor_unitario",
        "valor unitario",
        "valor",
        "preco",
        "preço",
        "vuncom",
        "vprod",
    ]

    mapa = {str(col).strip().lower(): col for col in colunas_origem}

    for chave in prioridades:
        if chave in mapa:
            return mapa[chave]

    for col in colunas_origem:
        cl = str(col).strip().lower()
        if "custo" in cl or "preco" in cl or "valor" in cl:
            return col

    return ""


def _detectar_coluna_preco_destino(colunas_destino: List[str]) -> str:
    prioridades = [
        "preco",
        "preço",
        "preco venda",
        "preço venda",
        "preco de venda",
        "preço de venda",
        "valor de venda",
        "preco_venda",
        "preço_venda",
        "valor venda",
    ]

    mapa = {str(col).strip().lower(): col for col in colunas_destino}

    for chave in prioridades:
        if chave in mapa:
            return mapa[chave]

    for col in colunas_destino:
        cl = str(col).strip().lower()
        if "preco" in cl or "preço" in cl:
            return col

    return "preco" if "preco" in colunas_destino else ""


def _render_calculadora_cadastro(
    df_origem: pd.DataFrame,
    colunas_destino_ativas: List[str],
) -> Dict[str, object]:
    st.divider()
    st.subheader("Calculadora de preço de venda")
    st.caption(
        "Selecione a coluna de custo/preço da planilha fornecedora e a coluna de preço de venda do modelo final."
    )

    colunas_origem = list(df_origem.columns)

    coluna_preco_base_default = st.session_state.get("coluna_preco_base_cadastro", "")
    if not coluna_preco_base_default or coluna_preco_base_default not in colunas_origem:
        coluna_preco_base_default = _detectar_coluna_preco_base(colunas_origem)

    coluna_preco_destino_default = st.session_state.get("coluna_preco_destino_cadastro", "")
    if not coluna_preco_destino_default or coluna_preco_destino_default not in colunas_destino_ativas:
        coluna_preco_destino_default = _detectar_coluna_preco_destino(colunas_destino_ativas)

    csel1, csel2 = st.columns(2)

    with csel1:
        opcoes_preco_origem = [""] + colunas_origem
        idx_origem = opcoes_preco_origem.index(coluna_preco_base_default) if coluna_preco_base_default in opcoes_preco_origem else 0
        coluna_preco_base = st.selectbox(
            "Coluna da fornecedora usada como preço base",
            options=opcoes_preco_origem,
            index=idx_origem,
            key="coluna_preco_base_cadastro_widget",
        )

    with csel2:
        opcoes_preco_destino = [""] + colunas_destino_ativas
        idx_destino = opcoes_preco_destino.index(coluna_preco_destino_default) if coluna_preco_destino_default in opcoes_preco_destino else 0
        coluna_preco_destino = st.selectbox(
            "Coluna do modelo final que receberá o preço de venda",
            options=opcoes_preco_destino,
            index=idx_destino,
            key="coluna_preco_destino_cadastro_widget",
        )

    st.session_state["coluna_preco_base_cadastro"] = coluna_preco_base
    st.session_state["coluna_preco_destino_cadastro"] = coluna_preco_destino

    preco_compra_detectado = 0.0
    exemplo_base = ""

    if coluna_preco_base and coluna_preco_base in df_origem.columns:
        serie_exemplo = df_origem[coluna_preco_base].astype(str)
        serie_exemplo = serie_exemplo[serie_exemplo.str.strip() != ""]
        exemplo_base = serie_exemplo.iloc[0] if not serie_exemplo.empty else ""

        df_tmp = pd.DataFrame({"custo": df_origem[coluna_preco_base]})
        preco_compra_detectado = calcular_preco_compra_automatico_df(df_tmp)

    st.session_state["preco_compra_modulo_precificacao"] = float(preco_compra_detectado or 0.0)

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        margem = st.number_input(
            "Lucro (%)",
            min_value=0.0,
            max_value=100.0,
            value=float(st.session_state.get("calc_margem_lucro", 30.0)),
            step=1.0,
            key="calc_margem_lucro",
        )

    with c2:
        impostos = st.number_input(
            "Impostos (%)",
            min_value=0.0,
            max_value=100.0,
            value=float(st.session_state.get("calc_impostos", 0.0)),
            step=1.0,
            key="calc_impostos",
        )

    with c3:
        taxa_extra = st.number_input(
            "Taxas extras (%)",
            min_value=0.0,
            max_value=100.0,
            value=float(st.session_state.get("calc_taxa_extra", 15.0)),
            step=1.0,
            key="calc_taxa_extra",
        )

    with c4:
        custo_fixo = st.number_input(
            "Custo fixo (R$)",
            min_value=0.0,
            value=float(st.session_state.get("calc_custo_fixo", 0.0)),
            step=1.0,
            key="calc_custo_fixo",
        )

    preco_sugerido = calcular_preco_venda(
        preco_compra=preco_compra_detectado,
        percentual_impostos=impostos,
        margem_lucro=margem,
        custo_fixo=custo_fixo,
        taxa_extra=taxa_extra,
    )
    st.session_state["preco_venda_calculado"] = float(preco_sugerido or 0.0)

    m1, m2, m3 = st.columns(3)
    with m1:
        st.metric("Preço base médio detectado", f"R$ {preco_compra_detectado:.2f}")
    with m2:
        st.metric("Preço de venda sugerido", f"R$ {preco_sugerido:.2f}")
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


def _aplicar_preco_no_df_saida(
    df_saida: pd.DataFrame,
    df_origem: pd.DataFrame,
    coluna_preco_base_origem: str,
    coluna_preco_destino: str,
    impostos: float,
    margem: float,
    custo_fixo: float,
    taxa_extra: float,
) -> pd.DataFrame:
    if (
        not coluna_preco_base_origem
        or coluna_preco_base_origem not in df_origem.columns
        or not coluna_preco_destino
    ):
        return df_saida

    df_tmp = df_saida.copy()
    df_tmp["__preco_base__"] = df_origem[coluna_preco_base_origem]

    df_tmp = calcular_preco_venda_df(
        df=df_tmp,
        coluna_preco_base="__preco_base__",
        percentual_impostos=float(impostos or 0.0),
        margem_lucro=float(margem or 0.0),
        custo_fixo=float(custo_fixo or 0.0),
        taxa_extra=float(taxa_extra or 0.0),
        nome_coluna_saida=coluna_preco_destino,
    )

    df_tmp = df_tmp.drop(columns=["__preco_base__"], errors="ignore")
    return df_tmp


# ==========================================================
# UI
# ==========================================================
def render_origem_dados() -> None:
    st.title("Origem dos dados")

    st.subheader("Planilhas modelo para o download")
    st.caption(
        "Anexe os modelos oficiais. O arquivo final será montado com as mesmas colunas e na mesma ordem do modelo correspondente."
    )

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

    df_modelo_cadastro, colunas_modelo_cadastro, origem_modelo_cadastro = _ler_planilha_modelo(
        upload_modelo_cadastro,
        "cadastro",
    )
    df_modelo_estoque, colunas_modelo_estoque, origem_modelo_estoque = _ler_planilha_modelo(
        upload_modelo_estoque,
        "estoque",
    )

    modo = st.radio(
        "Selecione a operação antes de tudo",
        options=["cadastro", "estoque"],
        format_func=lambda x: OPERACOES[x]["label"],
        horizontal=True,
        key="tipo_operacao_bling",
    )

    config = OPERACOES[modo]
    arquivo_saida = config["arquivo_saida"]
    defaults = config.get("defaults", {})

    if modo == "cadastro":
        df_modelo_ativo = df_modelo_cadastro
        colunas_destino_ativas = colunas_modelo_cadastro
        origem_modelo_ativo = origem_modelo_cadastro
        nome_modelo_ativo = getattr(upload_modelo_cadastro, "name", "")
    else:
        df_modelo_ativo = df_modelo_estoque
        colunas_destino_ativas = colunas_modelo_estoque
        origem_modelo_ativo = origem_modelo_estoque
        nome_modelo_ativo = getattr(upload_modelo_estoque, "name", "")

    st.info(
        f"Operação selecionada: **{config['label']}**. "
        "Você vai mapear manualmente, gerar o preview final e só depois baixar."
    )

    if nome_modelo_ativo:
        st.success(
            f"Modelo ativo carregado: **{nome_modelo_ativo}** "
            f"({origem_modelo_ativo}) com **{len(colunas_destino_ativas)}** colunas."
        )
        with st.expander("Ver colunas do modelo ativo"):
            st.write(colunas_destino_ativas)
            if df_modelo_ativo is not None and not df_modelo_ativo.empty:
                st.dataframe(df_modelo_ativo.head(5), width="stretch")
    else:
        st.warning(
            "Nenhuma planilha modelo foi anexada para essa operação. "
            "O sistema usará as colunas padrão internas."
        )

    arquivo = st.file_uploader(
        "Anexar planilha ou XML da fornecedora",
        type=["xlsx", "xls", "csv", "xml"],
        key=f"upload_origem_{modo}",
    )

    if not arquivo:
        return

    try:
        df_origem, origem_atual = _ler_arquivo_upload(arquivo)
    except Exception as e:
        st.error(f"Erro ao ler arquivo: {e}")
        _log(f"Erro ao ler arquivo {getattr(arquivo, 'name', 'arquivo')}: {e}")
        return

    if df_origem is None or df_origem.empty:
        st.warning("O arquivo foi lido, mas não possui dados para processar.")
        return

    nome_arquivo = str(getattr(arquivo, "name", "arquivo"))
    assinatura_modelo = f"{modo}|{nome_modelo_ativo}|{'|'.join(colunas_destino_ativas)}"
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

    st.caption(f"Arquivo lido: `{nome_arquivo}` | Origem detectada: `{origem_atual}`")

    st.subheader("Preview da origem")
    st.dataframe(df_origem.head(10), width="stretch")

    memoria = st.session_state.get("mapeamento_memoria", {})
    state_key = f"mapeamento_manual_{modo}"

    if state_key not in st.session_state:
        st.session_state[state_key] = _sugerir_mapeamento_inicial(
            colunas_origem=list(df_origem.columns),
            colunas_destino=colunas_destino_ativas,
            memoria=memoria,
        )

    mapeamento_manual = _render_mapeamento_manual(
        df_origem=df_origem,
        colunas_destino=colunas_destino_ativas,
        state_key=state_key,
    )

    calculadora_cfg = None
    if modo == "cadastro":
        calculadora_cfg = _render_calculadora_cadastro(
            df_origem=df_origem,
            colunas_destino_ativas=colunas_destino_ativas,
        )

    st.divider()
    st.subheader("Preview do que será baixado")

    df_saida_base = _montar_df_saida_base(
        df_origem=df_origem,
        colunas_destino=colunas_destino_ativas,
        mapeamento_manual=mapeamento_manual,
        defaults=defaults,
    )

    if modo == "cadastro" and calculadora_cfg:
        df_saida_base = _aplicar_preco_no_df_saida(
            df_saida=df_saida_base,
            df_origem=df_origem,
            coluna_preco_base_origem=str(calculadora_cfg.get("coluna_preco_base", "") or "").strip(),
            coluna_preco_destino=str(calculadora_cfg.get("coluna_preco_destino", "") or "").strip(),
            impostos=float(calculadora_cfg.get("impostos", 0.0)),
            margem=float(calculadora_cfg.get("margem", 0.0)),
            custo_fixo=float(calculadora_cfg.get("custo_fixo", 0.0)),
            taxa_extra=float(calculadora_cfg.get("taxa_extra", 0.0)),
        )

    df_preview_saida = _aplicar_modelo_na_saida(
        df_saida_base=df_saida_base,
        colunas_modelo=colunas_destino_ativas,
        df_modelo=df_modelo_ativo,
    )

    st.dataframe(df_preview_saida.head(20), width="stretch")

    b1, b2 = st.columns(2)

    with b1:
        if st.button("Gerar preview final", width="stretch"):
            try:
                df_saida_base_final = _montar_df_saida_base(
                    df_origem=df_origem,
                    colunas_destino=colunas_destino_ativas,
                    mapeamento_manual=mapeamento_manual,
                    defaults=defaults,
                )

                if modo == "cadastro" and calculadora_cfg:
                    df_saida_base_final = _aplicar_preco_no_df_saida(
                        df_saida=df_saida_base_final,
                        df_origem=df_origem,
                        coluna_preco_base_origem=str(calculadora_cfg.get("coluna_preco_base", "") or "").strip(),
                        coluna_preco_destino=str(calculadora_cfg.get("coluna_preco_destino", "") or "").strip(),
                        impostos=float(calculadora_cfg.get("impostos", 0.0)),
                        margem=float(calculadora_cfg.get("margem", 0.0)),
                        custo_fixo=float(calculadora_cfg.get("custo_fixo", 0.0)),
                        taxa_extra=float(calculadora_cfg.get("taxa_extra", 0.0)),
                    )

                    coluna_base = str(calculadora_cfg.get("coluna_preco_base", "") or "").strip()
                    if coluna_base and coluna_base in df_origem.columns:
                        st.session_state["preco_compra_modulo_precificacao"] = float(
                            calcular_preco_compra_automatico_df(
                                pd.DataFrame({"custo": df_origem[coluna_base]})
                            )
                        )

                df_saida_final = _aplicar_modelo_na_saida(
                    df_saida_base=df_saida_base_final,
                    colunas_modelo=colunas_destino_ativas,
                    df_modelo=df_modelo_ativo,
                )

                if df_saida_final.empty:
                    st.warning("Nenhum dado foi gerado.")
                    return

                mapa_para_memoria = {}
                for destino, origem in mapeamento_manual.items():
                    if origem:
                        mapa_para_memoria[origem] = destino

                try:
                    salvar_mapeamento(
                        memoria,
                        list(df_origem.columns),
                        mapa_para_memoria,
                    )
                    st.session_state["mapeamento_memoria"] = memoria
                except Exception as e:
                    _log(f"Falha ao salvar memória de mapeamento: {e}")

                excel_bytes = df_to_excel_bytes(df_saida_final)

                st.session_state["df_saida"] = df_saida_final.copy()
                st.session_state["df_saida_preview_hash"] = origem_hash
                st.session_state["excel_saida_bytes"] = excel_bytes
                st.session_state["excel_saida_nome"] = arquivo_saida

                st.success("Preview final gerado com sucesso. Revise abaixo antes de baixar.")

            except Exception as e:
                st.error(f"Erro ao gerar preview final: {e}")
                _log(f"Erro ao gerar preview final: {e}")

    with b2:
        if st.button("Limpar mapeamento", width="stretch"):
            st.session_state[state_key] = {}
            st.session_state.pop("df_saida", None)
            st.session_state.pop("df_saida_preview_hash", None)
            st.session_state.pop("excel_saida_bytes", None)
            st.session_state.pop("excel_saida_nome", None)
            st.rerun()

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
