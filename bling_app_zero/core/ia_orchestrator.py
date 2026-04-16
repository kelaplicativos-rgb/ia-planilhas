
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from typing import Any, Callable, Dict, Optional

import pandas as pd


# ============================================================
# MODELO DO PLANO
# ============================================================

@dataclass
class IAPlanoExecucao:
    origem: str = "planilha"
    operacao: str = "cadastro"
    fornecedor: str = ""
    url: str = ""
    deposito: str = ""
    usar_precificacao: bool = False
    manter_preco_original: bool = True
    margem: float = 0.0
    impostos: float = 0.0
    custo_fixo: float = 0.0
    taxa_extra: float = 0.0
    mapear_auto: bool = True
    usar_xml: bool = False
    usar_site: bool = False
    usar_api_fornecedor: bool = False
    categoria: str = ""
    observacoes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ============================================================
# HELPERS GERAIS
# ============================================================

def _safe_str(valor: Any) -> str:
    if valor is None:
        return ""
    texto = str(valor).strip()
    if texto.lower() in {"none", "nan", "nat"}:
        return ""
    return texto


def _normalizar_texto(valor: Any) -> str:
    texto = _safe_str(valor).lower()
    trocas = {
        "ã": "a",
        "á": "a",
        "à": "a",
        "â": "a",
        "é": "e",
        "ê": "e",
        "í": "i",
        "ó": "o",
        "ô": "o",
        "õ": "o",
        "ú": "u",
        "ç": "c",
        "_": " ",
        "-": " ",
        "/": " ",
        ".": " ",
        ",": " ",
        "(": " ",
        ")": " ",
        ":": " ",
        ";": " ",
    }
    for origem, destino in trocas.items():
        texto = texto.replace(origem, destino)
    return " ".join(texto.split())


def _to_float_seguro(valor: Any, default: float = 0.0) -> float:
    texto = _safe_str(valor)
    if not texto:
        return default

    texto = texto.replace("R$", "").replace(" ", "")
    if "," in texto and "." in texto:
        texto = texto.replace(".", "").replace(",", ".")
    else:
        texto = texto.replace(",", ".")

    try:
        return float(texto)
    except Exception:
        return default


def _formatar_numero_bling(valor: Any) -> str:
    return f"{_to_float_seguro(valor, 0.0):.2f}".replace(".", ",")


def _garantir_df(df: Any) -> pd.DataFrame:
    if isinstance(df, pd.DataFrame):
        return df.copy().fillna("")
    return pd.DataFrame()


def _extrair_url(texto: str) -> str:
    match = re.search(r"https?://[^\s]+", texto, re.IGNORECASE)
    return match.group(0).strip() if match else ""


def _normalizar_colunas(df: pd.DataFrame) -> pd.DataFrame:
    base = _garantir_df(df)
    if base.empty:
        return base
    base.columns = [_safe_str(col) for col in base.columns]
    return base


def _primeira_coluna_existente(df: pd.DataFrame, candidatos: list[str]) -> str:
    mapa = {_normalizar_texto(col): col for col in df.columns}

    for candidato in candidatos:
        chave = _normalizar_texto(candidato)
        if chave in mapa:
            return mapa[chave]

    for col in df.columns:
        ncol = _normalizar_texto(col)
        for candidato in candidatos:
            if _normalizar_texto(candidato) in ncol:
                return col

    return ""


def _modelo_padrao_por_operacao(tipo_operacao_bling: str) -> pd.DataFrame:
    if str(tipo_operacao_bling).strip().lower() == "estoque":
        return pd.DataFrame(
            columns=[
                "Código",
                "Descrição",
                "Depósito (OBRIGATÓRIO)",
                "Balanço (OBRIGATÓRIO)",
                "Preço unitário (OBRIGATÓRIO)",
                "Situação",
            ]
        )

    return pd.DataFrame(
        columns=[
            "Código",
            "Descrição",
            "Descrição Curta",
            "Preço de venda",
            "GTIN/EAN",
            "Situação",
            "URL Imagens",
            "Categoria",
        ]
    )


# ============================================================
# HEURÍSTICAS DE INTENÇÃO
# ============================================================

def _detectar_operacao(texto: str) -> str:
    t = _normalizar_texto(texto)

    gatilhos_estoque = [
        "atualizar estoque",
        "estoque",
        "saldo",
        "balanco",
        "balanço",
        "deposito",
        "depósito",
    ]
    for gatilho in gatilhos_estoque:
        if gatilho in t:
            return "estoque"

    return "cadastro"


def _detectar_origem(texto: str) -> str:
    t = _normalizar_texto(texto)

    if "xml" in t or "nota fiscal" in t or "nfe" in t or "nf e" in t:
        return "xml"

    if "site" in t or "buscar no site" in t or "categoria" in t or "url" in t:
        return "site"

    if "api" in t or "fornecedor" in t:
        return "api_fornecedor"

    if "planilha" in t or "xlsx" in t or "csv" in t or "xls" in t:
        return "planilha"

    return "planilha"


def _detectar_fornecedor(texto: str) -> str:
    t = _normalizar_texto(texto)

    if "atacadum" in t:
        return "atacadum"
    if "mega center" in t or "megacenter" in t or "mega center eletronicos" in t:
        return "mega_center"
    if "oba oba mix" in t or "obaobamix" in t:
        return "oba_oba_mix"

    return ""


def _detectar_deposito(texto: str) -> str:
    texto_original = _safe_str(texto)

    padroes = [
        r"deposito\s+([A-Za-z0-9_\-\s]+)",
        r"dep[oó]sito\s+([A-Za-z0-9_\-\s]+)",
        r"no deposito\s+([A-Za-z0-9_\-\s]+)",
        r"no dep[oó]sito\s+([A-Za-z0-9_\-\s]+)",
    ]

    for padrao in padroes:
        m = re.search(padrao, texto_original, re.IGNORECASE)
        if m:
            return _safe_str(m.group(1))

    if "ifood" in _normalizar_texto(texto):
        return "iFood"

    return ""


def _detectar_precificacao(texto: str) -> dict:
    t = _normalizar_texto(texto)

    resultado = {
        "usar_precificacao": False,
        "manter_preco_original": True,
        "margem": 0.0,
        "impostos": 0.0,
        "custo_fixo": 0.0,
        "taxa_extra": 0.0,
    }

    if "preco original" in t or "preço original" in t or "manter preco" in t or "manter preço" in t:
        return resultado

    if "precificacao 0" in t or "precificação 0" in t:
        resultado["usar_precificacao"] = True
        resultado["manter_preco_original"] = False
        return resultado

    if "olist" in t or "calculadora" in t or "margem" in t or "precificacao" in t or "precificação" in t:
        resultado["usar_precificacao"] = True
        resultado["manter_preco_original"] = False

        margem_match = re.search(r"margem\s*(?:de)?\s*(\d+[\,\.]?\d*)", t, re.IGNORECASE)
        impostos_match = re.search(r"impostos?\s*(?:de)?\s*(\d+[\,\.]?\d*)", t, re.IGNORECASE)
        custo_match = re.search(r"custo\s*fixo\s*(?:de)?\s*(\d+[\,\.]?\d*)", t, re.IGNORECASE)
        taxa_match = re.search(r"taxa\s*extra\s*(?:de)?\s*(\d+[\,\.]?\d*)", t, re.IGNORECASE)

        if margem_match:
            resultado["margem"] = _to_float_seguro(margem_match.group(1), 0.0)
        if impostos_match:
            resultado["impostos"] = _to_float_seguro(impostos_match.group(1), 0.0)
        if custo_match:
            resultado["custo_fixo"] = _to_float_seguro(custo_match.group(1), 0.0)
        if taxa_match:
            resultado["taxa_extra"] = _to_float_seguro(taxa_match.group(1), 0.0)

    return resultado


def _detectar_categoria(texto: str) -> str:
    texto_original = _safe_str(texto)

    padroes = [
        r"categoria\s+([A-Za-z0-9_\-\s]+)",
        r"categorias\s+([A-Za-z0-9_\-\s]+)",
        r"na categoria\s+([A-Za-z0-9_\-\s]+)",
    ]

    for padrao in padroes:
        m = re.search(padrao, texto_original, re.IGNORECASE)
        if m:
            return _safe_str(m.group(1))

    return ""


# ============================================================
# INTERPRETAÇÃO DO COMANDO
# ============================================================

def interpretar_comando_usuario(comando: str) -> IAPlanoExecucao:
    texto = _safe_str(comando)

    plano = IAPlanoExecucao()
    plano.operacao = _detectar_operacao(texto)
    plano.origem = _detectar_origem(texto)
    plano.fornecedor = _detectar_fornecedor(texto)
    plano.url = _extrair_url(texto)
    plano.deposito = _detectar_deposito(texto)
    plano.categoria = _detectar_categoria(texto)

    cfg_precificacao = _detectar_precificacao(texto)
    plano.usar_precificacao = cfg_precificacao["usar_precificacao"]
    plano.manter_preco_original = cfg_precificacao["manter_preco_original"]
    plano.margem = cfg_precificacao["margem"]
    plano.impostos = cfg_precificacao["impostos"]
    plano.custo_fixo = cfg_precificacao["custo_fixo"]
    plano.taxa_extra = cfg_precificacao["taxa_extra"]

    plano.usar_xml = plano.origem == "xml"
    plano.usar_site = plano.origem == "site"
    plano.usar_api_fornecedor = plano.origem == "api_fornecedor" or bool(plano.fornecedor)

    if plano.fornecedor and plano.origem == "planilha":
        plano.origem = "api_fornecedor"
        plano.usar_api_fornecedor = True

    if plano.url and plano.origem == "planilha":
        plano.origem = "site"
        plano.usar_site = True

    plano.observacoes = _montar_resumo_execucao(plano)
    return plano


def _montar_resumo_execucao(plano: IAPlanoExecucao) -> str:
    partes = [
        f"origem={plano.origem}",
        f"operacao={plano.operacao}",
    ]
    if plano.fornecedor:
        partes.append(f"fornecedor={plano.fornecedor}")
    if plano.url:
        partes.append(f"url={plano.url}")
    if plano.deposito:
        partes.append(f"deposito={plano.deposito}")
    if plano.categoria:
        partes.append(f"categoria={plano.categoria}")
    if plano.usar_precificacao:
        partes.append(
            "precificacao="
            f"margem:{plano.margem}|impostos:{plano.impostos}|"
            f"custo_fixo:{plano.custo_fixo}|taxa_extra:{plano.taxa_extra}"
        )
    else:
        partes.append("precificacao=manter_preco_original")
    return " ; ".join(partes)


# ============================================================
# NORMALIZAÇÃO DA BASE
# ============================================================

def normalizar_df_para_fluxo(df: pd.DataFrame) -> pd.DataFrame:
    base = _normalizar_colunas(df)
    if base.empty:
        return base

    col_codigo = _primeira_coluna_existente(
        base,
        ["codigo_fornecedor", "codigo", "sku", "referencia", "ref", "cprod"],
    )
    col_descricao = _primeira_coluna_existente(
        base,
        ["descricao_fornecedor", "descricao", "produto", "nome", "xprod", "titulo"],
    )
    col_preco = _primeira_coluna_existente(
        base,
        ["preco_base", "preco", "valor", "vUnCom", "vuncom", "preco site"],
    )
    col_quantidade = _primeira_coluna_existente(
        base,
        ["quantidade_real", "quantidade", "estoque", "saldo", "qcom", "balanco"],
    )
    col_gtin = _primeira_coluna_existente(
        base,
        ["gtin", "ean", "gtin/ean", "codigo de barras", "cean"],
    )
    col_categoria = _primeira_coluna_existente(
        base,
        ["categoria", "departamento", "breadcrumb", "grupo"],
    )
    col_imagens = _primeira_coluna_existente(
        base,
        ["url_imagens", "imagem", "imagens", "url imagem", "url imagens"],
    )

    saida = pd.DataFrame(index=base.index)
    saida["codigo_fornecedor"] = base[col_codigo] if col_codigo else ""
    saida["descricao_fornecedor"] = base[col_descricao] if col_descricao else ""
    saida["preco_base"] = base[col_preco].apply(_formatar_numero_bling) if col_preco else ""
    saida["quantidade_real"] = base[col_quantidade] if col_quantidade else ""
    saida["gtin"] = base[col_gtin] if col_gtin else ""
    saida["categoria"] = base[col_categoria] if col_categoria else ""
    saida["url_imagens"] = base[col_imagens] if col_imagens else ""

    for col in base.columns:
        if col not in saida.columns:
            saida[col] = base[col]

    return saida.fillna("")


def aplicar_precificacao_inicial(df: pd.DataFrame, plano: IAPlanoExecucao) -> pd.DataFrame:
    base = _garantir_df(df)
    if base.empty:
        return base

    tipo = str(plano.operacao).strip().lower()

    if plano.manter_preco_original or not plano.usar_precificacao:
        base["Preço calculado"] = base["preco_base"].apply(_to_float_seguro)
    else:
        fator = 1 + (float(plano.margem) / 100.0) + (float(plano.impostos) / 100.0)
        preco_base = base["preco_base"].apply(_to_float_seguro)
        base["Preço calculado"] = (
            (preco_base * fator)
            + float(plano.custo_fixo)
            + float(plano.taxa_extra)
        ).round(2)

    if tipo == "estoque":
        base["Preço unitário (OBRIGATÓRIO)"] = base["Preço calculado"].apply(_formatar_numero_bling)
    else:
        base["Preço de venda"] = base["Preço calculado"].apply(_formatar_numero_bling)

    return base.fillna("")


# ============================================================
# EXECUÇÃO DA FONTE
# ============================================================

def executar_fonte_por_plano(
    plano: IAPlanoExecucao,
    arquivo_upload: Any = None,
    fetch_router_func: Optional[Callable] = None,
    crawler_func: Optional[Callable] = None,
    xml_reader_func: Optional[Callable] = None,
) -> pd.DataFrame:
    if plano.origem == "xml" and arquivo_upload is not None and callable(xml_reader_func):
        try:
            df = xml_reader_func(arquivo_upload)
            return _garantir_df(df)
        except Exception:
            return pd.DataFrame()

    if plano.origem == "site" and callable(crawler_func):
        if not plano.url:
            return pd.DataFrame()

        tentativas = [
            lambda: crawler_func(
                url=plano.url,
                max_paginas=5,
                max_threads=5,
                padrao_disponivel=10,
            ),
            lambda: crawler_func(plano.url, 5, 5, 10),
        ]

        for tentativa in tentativas:
            try:
                df = tentativa()
                df = _garantir_df(df)
                if not df.empty:
                    return df
            except Exception:
                continue

        return pd.DataFrame()

    if plano.origem == "api_fornecedor" and callable(fetch_router_func):
        tentativas = [
            lambda: fetch_router_func(
                fornecedor=plano.fornecedor,
                categoria=plano.categoria,
                operacao=plano.operacao,
            ),
            lambda: fetch_router_func(plano.fornecedor, plano.categoria, plano.operacao),
            lambda: fetch_router_func(plano.fornecedor),
        ]

        for tentativa in tentativas:
            try:
                df = tentativa()
                df = _garantir_df(df)
                if not df.empty:
                    return df
            except Exception:
                continue

    return pd.DataFrame()


# ============================================================
# EXECUÇÃO REAL DO FLUXO
# ============================================================

def executar_fluxo_real_com_ia(
    st_session_state: Any,
    comando: str,
    arquivo_upload: Any = None,
    fetch_router_func: Optional[Callable] = None,
    crawler_func: Optional[Callable] = None,
    xml_reader_func: Optional[Callable] = None,
    log_func: Optional[Callable[[str, str], None]] = None,
) -> Dict[str, Any]:
    plano = interpretar_comando_usuario(comando)

    if callable(log_func):
        log_func(f"Plano IA interpretado: {plano.observacoes}", "INFO")

    df_origem = executar_fonte_por_plano(
        plano=plano,
        arquivo_upload=arquivo_upload,
        fetch_router_func=fetch_router_func,
        crawler_func=crawler_func,
        xml_reader_func=xml_reader_func,
    )

    if df_origem.empty:
        mensagem = "Nenhum dado foi retornado pela origem selecionada."
        if callable(log_func):
            log_func(mensagem, "ERROR")
        return {
            "ok": False,
            "mensagem": mensagem,
            "plano": plano,
            "df_origem": pd.DataFrame(),
        }

    df_normalizado = normalizar_df_para_fluxo(df_origem)
    if df_normalizado.empty:
        mensagem = "A origem retornou dados, mas a normalização gerou base vazia."
        if callable(log_func):
            log_func(mensagem, "ERROR")
        return {
            "ok": False,
            "mensagem": mensagem,
            "plano": plano,
            "df_origem": pd.DataFrame(),
        }

    df_processado = aplicar_precificacao_inicial(df_normalizado, plano)

    aplicar_plano_no_session_state(st_session_state, plano)

    st_session_state["df_origem"] = df_processado.copy()
    st_session_state["df_saida"] = df_processado.copy()
    st_session_state["df_precificado"] = df_processado.copy()
    st_session_state["df_calc_precificado"] = df_processado.copy()
    st_session_state["df_modelo_operacao"] = _modelo_padrao_por_operacao(plano.operacao)
    st_session_state["origem_tipo"] = plano.origem
    st_session_state["ia_plano_execucao"] = plano.to_dict()
    st_session_state["etapa"] = "mapeamento"
    st_session_state["etapa_origem"] = "mapeamento"

    if callable(log_func):
        log_func(
            f"Fluxo IA executado com sucesso: {len(df_processado)} linha(s) prontas para mapeamento.",
            "INFO",
        )

    return {
        "ok": True,
        "mensagem": "Fluxo executado com sucesso.",
        "plano": plano,
        "df_origem": df_processado.copy(),
    }


# ============================================================
# SESSION STATE
# ============================================================

def aplicar_plano_no_session_state(st_session_state: Any, plano: IAPlanoExecucao) -> None:
    operacao_label = "Atualização de Estoque" if plano.operacao == "estoque" else "Cadastro de Produtos"

    st_session_state["tipo_operacao"] = operacao_label
    st_session_state["tipo_operacao_radio"] = operacao_label
    st_session_state["tipo_operacao_bling"] = plano.operacao
    st_session_state["origem_tipo_ia"] = plano.origem
    st_session_state["fornecedor_ia"] = plano.fornecedor
    st_session_state["origem_site_url"] = plano.url
    st_session_state["deposito_nome"] = plano.deposito
    st_session_state["usar_calculadora_precificacao"] = bool(plano.usar_precificacao)
    st_session_state["precificacao_margem"] = float(plano.margem)
    st_session_state["precificacao_impostos"] = float(plano.impostos)
    st_session_state["precificacao_custo_fixo"] = float(plano.custo_fixo)
    st_session_state["precificacao_taxa_extra"] = float(plano.taxa_extra)
    st_session_state["categoria_ia"] = plano.categoria
    st_session_state["ia_plano_execucao"] = plano.to_dict()


# ============================================================
# SERIALIZAÇÃO
# ============================================================

def plano_para_json(plano: IAPlanoExecucao) -> str:
    return json.dumps(plano.to_dict(), ensure_ascii=False, indent=2)


def json_para_plano(payload: str | dict) -> IAPlanoExecucao:
    if isinstance(payload, str):
        try:
            data = json.loads(payload)
        except Exception:
            data = {}
    elif isinstance(payload, dict):
        data = payload
    else:
        data = {}

    return IAPlanoExecucao(
        origem=_safe_str(data.get("origem")) or "planilha",
        operacao=_safe_str(data.get("operacao")) or "cadastro",
        fornecedor=_safe_str(data.get("fornecedor")),
        url=_safe_str(data.get("url")),
        deposito=_safe_str(data.get("deposito")),
        usar_precificacao=bool(data.get("usar_precificacao", False)),
        manter_preco_original=bool(data.get("manter_preco_original", True)),
        margem=float(data.get("margem", 0.0) or 0.0),
        impostos=float(data.get("impostos", 0.0) or 0.0),
        custo_fixo=float(data.get("custo_fixo", 0.0) or 0.0),
        taxa_extra=float(data.get("taxa_extra", 0.0) or 0.0),
        mapear_auto=bool(data.get("mapear_auto", True)),
        usar_xml=bool(data.get("usar_xml", False)),
        usar_site=bool(data.get("usar_site", False)),
        usar_api_fornecedor=bool(data.get("usar_api_fornecedor", False)),
        categoria=_safe_str(data.get("categoria")),
        observacoes=_safe_str(data.get("observacoes")),
    )
    
