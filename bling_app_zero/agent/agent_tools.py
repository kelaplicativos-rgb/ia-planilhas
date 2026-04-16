
from __future__ import annotations

import io
import re
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

import pandas as pd
import streamlit as st

from bling_app_zero.agent.agent_memory import (
    get_agent_state,
    save_agent_state,
    sync_agent_with_session,
    update_agent_state,
)
from bling_app_zero.agent.agent_validator import validar_dataframe_bling


def _safe_str(valor: Any) -> str:
    if valor is None:
        return ""
    texto = str(valor).strip()
    if texto.lower() in {"none", "nan", "nat"}:
        return ""
    return texto


def _safe_lower(valor: Any) -> str:
    return _safe_str(valor).lower()


def _is_df_valido(df: Any) -> bool:
    return isinstance(df, pd.DataFrame) and not df.empty and len(df.columns) > 0


def _log(log_func: Optional[Callable[[str, str], None]], mensagem: str, nivel: str = "INFO") -> None:
    if callable(log_func):
        log_func(mensagem, nivel)


def _normalizar_nome_coluna(nome: Any) -> str:
    texto = _safe_str(nome)
    texto = re.sub(r"\s+", " ", texto)
    return texto


def _deduplicar_colunas(df: pd.DataFrame) -> pd.DataFrame:
    if not _is_df_valido(df):
        return pd.DataFrame()

    colunas = []
    usados: Dict[str, int] = {}
    for coluna in df.columns:
        base = _normalizar_nome_coluna(coluna) or "coluna"
        if base not in usados:
            usados[base] = 1
            colunas.append(base)
        else:
            usados[base] += 1
            colunas.append(f"{base}_{usados[base]}")
    novo = df.copy()
    novo.columns = colunas
    return novo


def _limpar_strings_df(df: pd.DataFrame) -> pd.DataFrame:
    novo = df.copy()
    for coluna in novo.columns:
        try:
            if novo[coluna].dtype == object:
                novo[coluna] = novo[coluna].apply(
                    lambda v: "" if str(v).strip().lower() in {"nan", "nat", "none"} else v
                )
        except Exception:
            continue
    return novo


def normalizar_dataframe(df: pd.DataFrame, log_func: Optional[Callable[[str, str], None]] = None) -> pd.DataFrame:
    if not _is_df_valido(df):
        _log(log_func, "[AGENT_TOOLS] normalizar_dataframe recebeu DataFrame vazio.", "WARNING")
        return pd.DataFrame()

    base = df.copy()
    base = _deduplicar_colunas(base)
    base = _limpar_strings_df(base)
    base = base.reset_index(drop=True)

    _log(
        log_func,
        f"[AGENT_TOOLS] base normalizada com {len(base)} linhas e {len(base.columns)} colunas.",
        "INFO",
    )
    return base


def detectar_origem_por_entrada(comando: str, arquivo_upload: Any = None) -> str:
    texto = _safe_lower(comando)

    if arquivo_upload is not None:
        nome = _safe_lower(getattr(arquivo_upload, "name", ""))
        if nome.endswith(".xml"):
            return "xml"
        if nome.endswith(".csv"):
            return "planilha"
        if nome.endswith(".xlsx") or nome.endswith(".xls"):
            return "planilha"

    if "xml" in texto:
        return "xml"

    if "site" in texto or "url" in texto or "http://" in texto or "https://" in texto:
        return "site"

    if "fornecedor" in texto or "mega center" in texto or "atacadum" in texto or "oba oba" in texto:
        return "fornecedor"

    return "planilha"


def detectar_operacao(comando: str) -> str:
    texto = _safe_lower(comando)
    if "estoque" in texto or "atualiza estoque" in texto or "atualizar estoque" in texto:
        return "estoque"
    return "cadastro"


def detectar_fornecedor(comando: str) -> str:
    texto = _safe_lower(comando)

    mapas = {
        "mega center eletrônicos": [
            "mega center eletrônicos",
            "mega center eletronicos",
            "mega center",
            "megacenter",
        ],
        "atacadum": ["atacadum"],
        "oba oba mix": ["oba oba mix", "obaoba mix", "oba oba"],
    }

    for nome, apelidos in mapas.items():
        if any(apelido in texto for apelido in apelidos):
            return nome

    return ""


def detectar_deposito(comando: str) -> str:
    texto_original = _safe_str(comando)
    texto = texto_original.lower()

    padroes = [
        r"dep[oó]sito\s+([a-zA-Z0-9_\- ]+)",
        r"no\s+dep[oó]sito\s+([a-zA-Z0-9_\- ]+)",
        r"para\s+o\s+dep[oó]sito\s+([a-zA-Z0-9_\- ]+)",
    ]

    for padrao in padroes:
        match = re.search(padrao, texto, flags=re.IGNORECASE)
        if match:
            return _safe_str(match.group(1))

    for candidato in ["ifood", "principal", "geral"]:
        if candidato in texto:
            return candidato

    return ""


def ler_planilha_origem(arquivo_upload: Any, log_func: Optional[Callable[[str, str], None]] = None) -> pd.DataFrame:
    if arquivo_upload is None:
        _log(log_func, "[AGENT_TOOLS] nenhum arquivo de planilha enviado.", "WARNING")
        return pd.DataFrame()

    nome = _safe_lower(getattr(arquivo_upload, "name", ""))

    try:
        bruto = arquivo_upload.getvalue()
    except Exception:
        bruto = None

    try:
        if nome.endswith(".csv"):
            if bruto is None:
                return pd.DataFrame()
            tentativas = ["utf-8", "utf-8-sig", "latin1"]
            separadores = [None, ";", ",", "\t"]
            for encoding in tentativas:
                for sep in separadores:
                    try:
                        df = pd.read_csv(io.BytesIO(bruto), sep=sep, engine="python", encoding=encoding)
                        if _is_df_valido(df):
                            _log(log_func, f"[AGENT_TOOLS] CSV lido com sucesso: {nome}", "INFO")
                            return df
                    except Exception:
                        continue
            return pd.DataFrame()

        if nome.endswith(".xlsx") or nome.endswith(".xls"):
            if bruto is None:
                return pd.DataFrame()
            for engine in [None, "openpyxl", "xlrd"]:
                try:
                    kwargs = {}
                    if engine:
                        kwargs["engine"] = engine
                    df = pd.read_excel(io.BytesIO(bruto), **kwargs)
                    if _is_df_valido(df):
                        _log(log_func, f"[AGENT_TOOLS] Excel lido com sucesso: {nome}", "INFO")
                        return df
                except Exception:
                    continue
    except Exception as exc:
        _log(log_func, f"[AGENT_TOOLS] falha lendo planilha: {exc}", "ERROR")
        return pd.DataFrame()

    _log(log_func, f"[AGENT_TOOLS] formato de planilha não suportado: {nome}", "ERROR")
    return pd.DataFrame()


def ler_xml_nfe(
    arquivo_upload: Any,
    xml_reader_func: Optional[Callable[[Any], pd.DataFrame]] = None,
    log_func: Optional[Callable[[str, str], None]] = None,
) -> pd.DataFrame:
    if arquivo_upload is None:
        _log(log_func, "[AGENT_TOOLS] XML não enviado.", "WARNING")
        return pd.DataFrame()

    if not callable(xml_reader_func):
        _log(log_func, "[AGENT_TOOLS] xml_reader_func indisponível.", "ERROR")
        return pd.DataFrame()

    try:
        df = xml_reader_func(arquivo_upload)
    except Exception as exc:
        _log(log_func, f"[AGENT_TOOLS] erro ao converter XML: {exc}", "ERROR")
        return pd.DataFrame()

    if _is_df_valido(df):
        _log(log_func, f"[AGENT_TOOLS] XML convertido com {len(df)} linhas.", "INFO")
        return df

    _log(log_func, "[AGENT_TOOLS] XML convertido sem dados.", "WARNING")
    return pd.DataFrame()


def buscar_dados_fornecedor(
    fornecedor: str,
    operacao: str,
    fetch_router_func: Optional[Callable[..., pd.DataFrame]] = None,
    log_func: Optional[Callable[[str, str], None]] = None,
) -> pd.DataFrame:
    fornecedor_limpo = _safe_str(fornecedor)
    if not fornecedor_limpo:
        _log(log_func, "[AGENT_TOOLS] fornecedor ausente.", "WARNING")
        return pd.DataFrame()

    if not callable(fetch_router_func):
        _log(log_func, "[AGENT_TOOLS] fetch_router_func indisponível.", "ERROR")
        return pd.DataFrame()

    try:
        df = fetch_router_func(
            fornecedor=fornecedor_limpo,
            categoria="",
            operacao=operacao,
            extra_config={},
        )
    except TypeError:
        try:
            df = fetch_router_func(fornecedor_limpo)
        except Exception as exc:
            _log(log_func, f"[AGENT_TOOLS] erro buscando fornecedor: {exc}", "ERROR")
            return pd.DataFrame()
    except Exception as exc:
        _log(log_func, f"[AGENT_TOOLS] erro buscando fornecedor: {exc}", "ERROR")
        return pd.DataFrame()

    if _is_df_valido(df):
        _log(log_func, f"[AGENT_TOOLS] fornecedor '{fornecedor_limpo}' retornou {len(df)} linhas.", "INFO")
        return df

    _log(log_func, f"[AGENT_TOOLS] fornecedor '{fornecedor_limpo}' sem dados.", "WARNING")
    return pd.DataFrame()


def buscar_dados_site(
    comando: str,
    crawler_func: Optional[Callable[..., pd.DataFrame]] = None,
    log_func: Optional[Callable[[str, str], None]] = None,
) -> pd.DataFrame:
    if not callable(crawler_func):
        _log(log_func, "[AGENT_TOOLS] crawler_func indisponível.", "ERROR")
        return pd.DataFrame()

    url = ""
    match = re.search(r"(https?://\S+)", _safe_str(comando), flags=re.IGNORECASE)
    if match:
        url = match.group(1)

    try:
        if url:
            try:
                df = crawler_func(url=url)
            except TypeError:
                df = crawler_func(url)
        else:
            try:
                df = crawler_func(comando=_safe_str(comando))
            except TypeError:
                df = crawler_func(_safe_str(comando))
    except Exception as exc:
        _log(log_func, f"[AGENT_TOOLS] erro no crawler: {exc}", "ERROR")
        return pd.DataFrame()

    if _is_df_valido(df):
        _log(log_func, f"[AGENT_TOOLS] crawler retornou {len(df)} linhas.", "INFO")
        return df

    _log(log_func, "[AGENT_TOOLS] crawler sem retorno útil.", "WARNING")
    return pd.DataFrame()


def aplicar_defaults_fluxo(df: pd.DataFrame, operacao: str, deposito_nome: str = "") -> pd.DataFrame:
    if not _is_df_valido(df):
        return pd.DataFrame()

    base = df.copy()

    if operacao == "estoque":
        if "Depósito (OBRIGATÓRIO)" not in base.columns:
            base["Depósito (OBRIGATÓRIO)"] = _safe_str(deposito_nome)
        else:
            if _safe_str(deposito_nome):
                base["Depósito (OBRIGATÓRIO)"] = base["Depósito (OBRIGATÓRIO)"].apply(
                    lambda v: _safe_str(v) or _safe_str(deposito_nome)
                )

    if "Condição" in base.columns:
        base["Condição"] = base["Condição"].apply(lambda v: _safe_str(v) or "NOVO")

    return base


def registrar_base_no_estado(
    df: pd.DataFrame,
    origem_tipo: str,
    operacao: str,
    fornecedor: str = "",
    deposito_nome: str = "",
    log_func: Optional[Callable[[str, str], None]] = None,
) -> None:
    state = sync_agent_with_session()

    st.session_state["df_origem"] = df.copy()
    st.session_state["df_normalizado"] = df.copy()

    state.origem_tipo = origem_tipo
    state.operacao = operacao
    state.fornecedor = fornecedor
    state.deposito_nome = deposito_nome
    state.df_origem_key = "df_origem"
    state.df_normalizado_key = "df_normalizado"
    state.etapa_atual = "origem"
    state.status_execucao = "base_pronta"

    if fornecedor:
        state.defaults_aplicados["fornecedor"] = fornecedor
    if deposito_nome:
        state.defaults_aplicados["deposito_nome"] = deposito_nome

    state.add_log(f"Base registrada pelo agente. origem={origem_tipo} operacao={operacao}")
    save_agent_state(state)

    _log(log_func, "[AGENT_TOOLS] base registrada no estado do app.", "INFO")


def gerar_preview_final(
    df: pd.DataFrame,
    operacao: str,
    log_func: Optional[Callable[[str, str], None]] = None,
) -> Dict[str, Any]:
    validacao = validar_dataframe_bling(df=df, operacao=operacao)

    st.session_state["df_final"] = validacao.df_resultado.copy() if isinstance(validacao.df_resultado, pd.DataFrame) else pd.DataFrame()

    update_agent_state(
        df_final_key="df_final",
        etapa_atual="final" if validacao.aprovado else "validacao",
        status_execucao="final_pronto" if validacao.aprovado else "validacao_pendente",
        simulacao_aprovada=bool(validacao.aprovado),
    )

    _log(
        log_func,
        f"[AGENT_TOOLS] preview final gerado. aprovado={validacao.aprovado} linhas={len(df) if _is_df_valido(df) else 0}",
        "INFO",
    )

    return {
        "aprovado": validacao.aprovado,
        "df_final": st.session_state.get("df_final", pd.DataFrame()),
        "validacao": validacao.to_dict(),
    }


@dataclass
class FerramentasAgente:
    fetch_router_func: Optional[Callable[..., pd.DataFrame]] = None
    crawler_func: Optional[Callable[..., pd.DataFrame]] = None
    xml_reader_func: Optional[Callable[[Any], pd.DataFrame]] = None
    log_func: Optional[Callable[[str, str], None]] = None
  
