
from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional

import pandas as pd


# ============================================================
# MODELOS
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
# NORMALIZAÇÃO
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


def _extrair_url(texto: str) -> str:
    match = re.search(r"https?://[^\s]+", texto, re.IGNORECASE)
    return match.group(0).strip() if match else ""


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

    # caso comum do seu fluxo
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
# PLANEJAMENTO
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

    if plano.operacao == "estoque" and not plano.deposito:
        plano.deposito = ""

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
# APLICAÇÃO DO PLANO AO SESSION STATE
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
# EXECUÇÃO DE FONTES
# ============================================================

def executar_fonte_por_plano(
    plano: IAPlanoExecucao,
    arquivo_upload: Any = None,
    fetch_router_func: Optional[Any] = None,
    crawler_func: Optional[Any] = None,
    xml_reader_func: Optional[Any] = None,
) -> pd.DataFrame:
    if plano.origem == "xml" and arquivo_upload is not None and callable(xml_reader_func):
        df = xml_reader_func(arquivo_upload)
        return _garantir_df(df)

    if plano.origem == "site" and callable(crawler_func):
        if not plano.url:
            return pd.DataFrame()
        try:
            df = crawler_func(
                url=plano.url,
                max_paginas=5,
                max_threads=5,
                padrao_disponivel=10,
            )
            return _garantir_df(df)
        except TypeError:
            try:
                df = crawler_func(plano.url, 5, 5, 10)
                return _garantir_df(df)
            except Exception:
                return pd.DataFrame()
        except Exception:
            return pd.DataFrame()

    if plano.origem == "api_fornecedor" and callable(fetch_router_func):
        try:
            df = fetch_router_func(
                fornecedor=plano.fornecedor,
                categoria=plano.categoria,
                operacao=plano.operacao,
            )
            return _garantir_df(df)
        except TypeError:
            try:
                df = fetch_router_func(plano.fornecedor)
                return _garantir_df(df)
            except Exception:
                return pd.DataFrame()
        except Exception:
            return pd.DataFrame()

    return pd.DataFrame()


def _garantir_df(df: Any) -> pd.DataFrame:
    if isinstance(df, pd.DataFrame):
        return df.copy().fillna("")
    return pd.DataFrame()


# ============================================================
# SERIALIZAÇÃO / DEBUG
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
