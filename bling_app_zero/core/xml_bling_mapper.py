from __future__ import annotations

from typing import Any

import pandas as pd


ALIAS_CADASTRO: dict[str, list[str]] = {
    "codigo": ["codigo", "código", "sku", "codigo sku", "cod", "código do produto"],
    "descricao": ["descricao", "descrição", "nome", "titulo", "título", "produto"],
    "descricao_curta": [
        "descricao curta",
        "descrição curta",
        "descricao complementar",
        "descrição complementar",
        "descricao do produto",
        "descrição do produto",
    ],
    "situacao": ["situacao", "situação", "status"],
    "unidade": ["unidade", "un", "unid"],
    "preco_venda": [
        "preco de venda",
        "preço de venda",
        "valor de venda",
        "valor venda",
        "preco",
        "preço",
    ],
    "preco_custo": [
        "preco de custo",
        "preço de custo",
        "custo",
        "preco compra",
        "preço compra",
        "preco de compra",
        "preço de compra",
    ],
    "ncm": ["ncm"],
    "cest": ["cest"],
    "cfop": ["cfop"],
    "gtin": ["gtin", "ean", "codigo de barras", "código de barras"],
    "gtin_tributario": [
        "gtin tributario",
        "gtin tributário",
        "ean tributario",
        "ean tributário",
        "codigo de barras tributario",
        "código de barras tributário",
    ],
    "marca": ["marca"],
    "categoria": ["categoria"],
    "origem_icms": ["origem icms", "origem"],
    "cst_csosn": ["cst/csosn", "cst", "csosn"],
    "link_externo": ["link externo"],
    "imagens": ["imagens", "imagem", "url imagens", "url imagem", "fotos", "foto"],
    "id": ["id"],
}

ALIAS_ESTOQUE: dict[str, list[str]] = {
    "codigo": ["codigo", "código", "sku", "codigo sku", "cod", "código do produto"],
    "descricao": ["descricao", "descrição", "nome", "produto"],
    "deposito": ["deposito", "depósito", "nome deposito", "nome depósito"],
    "saldo": [
        "saldo",
        "saldo estoque",
        "saldo em estoque",
        "estoque",
        "quantidade",
        "qtde",
    ],
    "preco_unitario": [
        "preco unitario",
        "preço unitário",
        "valor unitario",
        "valor unitário",
        "preco",
        "preço",
    ],
    "custo": [
        "preco de custo",
        "preço de custo",
        "custo",
        "preco compra",
        "preço compra",
        "preco de compra",
        "preço de compra",
    ],
    "gtin": ["gtin", "ean", "codigo de barras", "código de barras"],
    "id": ["id"],
}


XML_SOURCE_ALIASES: dict[str, list[str]] = {
    "codigo": ["Código", "codigo", "código"],
    "descricao": ["Descrição", "descricao", "descrição"],
    "descricao_curta": ["Descrição Curta", "descricao curta", "descrição curta"],
    "unidade": ["Unidade", "unidade"],
    "quantidade": ["Quantidade", "quantidade"],
    "preco_custo": ["Preço de custo", "preco de custo", "preço unitário", "Preço unitário"],
    "preco_unitario": ["Preço unitário", "preco unitário", "Preço de custo", "preço de custo"],
    "preco_total": ["Preço total", "preço total", "Valor total", "valor total"],
    "ncm": ["NCM", "ncm"],
    "cest": ["CEST", "cest"],
    "cfop": ["CFOP", "cfop"],
    "gtin": ["GTIN", "gtin"],
    "gtin_tributario": ["GTIN Tributário", "GTIN Tributario", "gtin tributário", "gtin tributario"],
    "origem_icms": ["Origem ICMS", "origem icms"],
    "cst_csosn": ["CST/CSOSN", "cst/csosn", "CST", "CSOSN"],
    "marca": ["Marca", "marca"],
    "categoria": ["Categoria", "categoria"],
}


def _norm(texto: Any) -> str:
    try:
        return (
            str(texto or "")
            .strip()
            .lower()
            .replace("_", " ")
            .replace("-", " ")
            .replace("/", " ")
        )
    except Exception:
        return ""


def _normalizar_df(df: pd.DataFrame | None) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame):
        return pd.DataFrame()

    try:
        out = df.copy()
        out.columns = [str(c).strip() for c in out.columns]
        return out
    except Exception:
        return df.copy()


def _localizar_coluna(df: pd.DataFrame, aliases: list[str]) -> str | None:
    if df is None or df.empty and len(df.columns) == 0:
        return None

    mapa = {_norm(col): str(col) for col in df.columns}

    for alias in aliases:
        chave = _norm(alias)
        if chave in mapa:
            return mapa[chave]

    for alias in aliases:
        chave = _norm(alias)
        for col_norm, col_real in mapa.items():
            if chave == col_norm:
                return col_real
            if chave in col_norm:
                return col_real

    return None


def _valor(df: pd.DataFrame, idx: int, aliases: list[str], default: Any = "") -> Any:
    col = _localizar_coluna(df, aliases)
    if not col:
        return default

    try:
        valor = df.iloc[idx][col]
        if pd.isna(valor):
            return default
        return valor
    except Exception:
        return default


def _numero(valor: Any, default: float = 0.0) -> float:
    try:
        texto = str(valor or "").strip()
        if not texto:
            return default
        texto = texto.replace(".", "").replace(",", ".") if ("," in texto and "." in texto) else texto.replace(",", ".")
        return float(texto)
    except Exception:
        try:
            return float(valor)
        except Exception:
            return default


def _texto(valor: Any, default: str = "") -> str:
    try:
        if pd.isna(valor):
            return default
    except Exception:
        pass
    texto = str(valor or "").strip()
    return texto if texto else default


def _linha_base_modelo(df_modelo: pd.DataFrame) -> dict[str, Any]:
    return {str(col): "" for col in df_modelo.columns}


def _set_if_exists(linha: dict[str, Any], df_modelo: pd.DataFrame, aliases: list[str], valor: Any) -> None:
    coluna = _localizar_coluna(df_modelo, aliases)
    if not coluna:
        return
    linha[coluna] = valor


def mapear_xml_para_modelo_bling(
    df_xml: pd.DataFrame,
    df_modelo: pd.DataFrame,
    tipo_operacao: str = "cadastro",
    deposito_padrao: str = "",
) -> pd.DataFrame:
    """
    Converte um DataFrame extraído de XML/NF-e para a estrutura exata do modelo do Bling.
    Retorna sempre um DataFrame com as mesmas colunas do modelo informado.
    """
    df_xml = _normalizar_df(df_xml)
    df_modelo = _normalizar_df(df_modelo)

    if df_modelo is None or len(df_modelo.columns) == 0:
        return pd.DataFrame()

    if df_xml is None or df_xml.empty:
        return pd.DataFrame(columns=list(df_modelo.columns))

    tipo = _norm(tipo_operacao)
    linhas_saida: list[dict[str, Any]] = []

    for idx in range(len(df_xml)):
        linha = _linha_base_modelo(df_modelo)

        codigo = _texto(_valor(df_xml, idx, XML_SOURCE_ALIASES["codigo"]))
        descricao = _texto(_valor(df_xml, idx, XML_SOURCE_ALIASES["descricao"]))
        descricao_curta = _texto(
            _valor(df_xml, idx, XML_SOURCE_ALIASES["descricao_curta"], default=descricao),
            default=descricao,
        )
        unidade = _texto(_valor(df_xml, idx, XML_SOURCE_ALIASES["unidade"], default="UN"), default="UN")
        quantidade = _numero(_valor(df_xml, idx, XML_SOURCE_ALIASES["quantidade"], default=0))
        preco_custo = _numero(_valor(df_xml, idx, XML_SOURCE_ALIASES["preco_custo"], default=0))
        preco_unitario = _numero(_valor(df_xml, idx, XML_SOURCE_ALIASES["preco_unitario"], default=preco_custo))
        ncm = _texto(_valor(df_xml, idx, XML_SOURCE_ALIASES["ncm"]))
        cest = _texto(_valor(df_xml, idx, XML_SOURCE_ALIASES["cest"]))
        cfop = _texto(_valor(df_xml, idx, XML_SOURCE_ALIASES["cfop"]))
        gtin = _texto(_valor(df_xml, idx, XML_SOURCE_ALIASES["gtin"]))
        gtin_trib = _texto(_valor(df_xml, idx, XML_SOURCE_ALIASES["gtin_tributario"]))
        origem_icms = _texto(_valor(df_xml, idx, XML_SOURCE_ALIASES["origem_icms"]))
        cst_csosn = _texto(_valor(df_xml, idx, XML_SOURCE_ALIASES["cst_csosn"]))
        marca = _texto(_valor(df_xml, idx, XML_SOURCE_ALIASES["marca"]))
        categoria = _texto(_valor(df_xml, idx, XML_SOURCE_ALIASES["categoria"]))

        if tipo == "estoque":
            _set_if_exists(linha, df_modelo, ALIAS_ESTOQUE["id"], "")
            _set_if_exists(linha, df_modelo, ALIAS_ESTOQUE["codigo"], codigo)
            _set_if_exists(linha, df_modelo, ALIAS_ESTOQUE["descricao"], descricao)
            _set_if_exists(linha, df_modelo, ALIAS_ESTOQUE["deposito"], deposito_padrao)
            _set_if_exists(linha, df_modelo, ALIAS_ESTOQUE["saldo"], quantidade)
            _set_if_exists(linha, df_modelo, ALIAS_ESTOQUE["preco_unitario"], preco_unitario)
            _set_if_exists(linha, df_modelo, ALIAS_ESTOQUE["custo"], preco_custo)
            _set_if_exists(linha, df_modelo, ALIAS_ESTOQUE["gtin"], gtin)
        else:
            _set_if_exists(linha, df_modelo, ALIAS_CADASTRO["id"], "")
            _set_if_exists(linha, df_modelo, ALIAS_CADASTRO["codigo"], codigo)
            _set_if_exists(linha, df_modelo, ALIAS_CADASTRO["descricao"], descricao)
            _set_if_exists(linha, df_modelo, ALIAS_CADASTRO["descricao_curta"], descricao_curta)
            _set_if_exists(linha, df_modelo, ALIAS_CADASTRO["situacao"], "Ativo")
            _set_if_exists(linha, df_modelo, ALIAS_CADASTRO["unidade"], unidade)
            _set_if_exists(linha, df_modelo, ALIAS_CADASTRO["preco_venda"], preco_unitario)
            _set_if_exists(linha, df_modelo, ALIAS_CADASTRO["preco_custo"], preco_custo)
            _set_if_exists(linha, df_modelo, ALIAS_CADASTRO["ncm"], ncm)
            _set_if_exists(linha, df_modelo, ALIAS_CADASTRO["cest"], cest)
            _set_if_exists(linha, df_modelo, ALIAS_CADASTRO["cfop"], cfop)
            _set_if_exists(linha, df_modelo, ALIAS_CADASTRO["gtin"], gtin)
            _set_if_exists(linha, df_modelo, ALIAS_CADASTRO["gtin_tributario"], gtin_trib)
            _set_if_exists(linha, df_modelo, ALIAS_CADASTRO["marca"], marca)
            _set_if_exists(linha, df_modelo, ALIAS_CADASTRO["categoria"], categoria)
            _set_if_exists(linha, df_modelo, ALIAS_CADASTRO["origem_icms"], origem_icms)
            _set_if_exists(linha, df_modelo, ALIAS_CADASTRO["cst_csosn"], cst_csosn)
            _set_if_exists(linha, df_modelo, ALIAS_CADASTRO["link_externo"], "")
            _set_if_exists(linha, df_modelo, ALIAS_CADASTRO["imagens"], "")

        linhas_saida.append(linha)

    df_saida = pd.DataFrame(linhas_saida, columns=list(df_modelo.columns))

    for col in df_saida.columns:
        try:
            df_saida[col] = df_saida[col].replace({None: ""}).fillna("")
        except Exception:
            pass

    return df_saida
