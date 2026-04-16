
from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

import streamlit as st

try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None  # type: ignore

from bling_app_zero.agent.agent_memory import (
    get_agent_state,
    save_agent_state,
    update_agent_state,
)


# ============================================================
# CONFIG
# ============================================================

DEFAULT_MODEL = "gpt-4o-mini"
SESSION_PLAN_KEY = "agent_plan"
SESSION_LAST_RESULT_KEY = "agent_last_result"
SESSION_LAST_ERROR_KEY = "agent_last_error"
SESSION_LAST_RAW_KEY = "agent_last_raw"
SESSION_LAST_PROVIDER_KEY = "agent_last_provider"


# ============================================================
# MODELS
# ============================================================

@dataclass
class IAOrchestratorResult:
    prompt_usuario: str = ""
    operacao: str = "cadastro"  # cadastro | estoque
    origem: str = "planilha"  # planilha | site | xml | pdf | api_fornecedor
    fornecedor: str = ""
    deposito_nome: str = ""
    url_site: str = ""
    modelo_llm: str = ""
    provider: str = "fallback"
    confidence: float = 0.0
    status: str = "aguardando_input"  # aguardando_input | pronto_para_proximo_fluxo | erro
    etapa_atual: str = "origem"
    proxima_etapa: str = "origem"
    proxima_pergunta: str = ""
    resumo: str = ""
    pendencias: List[str] = field(default_factory=list)
    avisos: List[str] = field(default_factory=list)
    erros: List[str] = field(default_factory=list)
    proximas_acoes: List[str] = field(default_factory=list)
    usar_gpt: bool = False
    raw: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ============================================================
# HELPERS
# ============================================================

def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"none", "nan", "nat"}:
        return ""
    return text


def _normalize_text(value: Any) -> str:
    text = _safe_str(value).lower()
    table = str.maketrans(
        {
            "ã": "a",
            "á": "a",
            "à": "a",
            "â": "a",
            "ä": "a",
            "é": "e",
            "ê": "e",
            "ë": "e",
            "í": "i",
            "ï": "i",
            "ó": "o",
            "ô": "o",
            "õ": "o",
            "ö": "o",
            "ú": "u",
            "ü": "u",
            "ç": "c",
        }
    )
    text = text.translate(table)
    text = re.sub(r"[_\-/|:;,.()]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _extract_url(text: str) -> str:
    match = re.search(r"https?://[^\s]+", _safe_str(text), flags=re.IGNORECASE)
    return match.group(0).strip() if match else ""


def _extract_deposito(prompt: str, deposito_ui: str = "") -> str:
    if _safe_str(deposito_ui):
        return _safe_str(deposito_ui)

    text_original = _safe_str(prompt)
    patterns = [
        r"(?:deposito|depósito)\s*[:=-]?\s*([A-Za-z0-9 _\-/]+)",
        r"(?:no|do)\s+(?:deposito|depósito)\s*([A-Za-z0-9 _\-/]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text_original, flags=re.IGNORECASE)
        if match:
            return _safe_str(match.group(1))

    normalized = _normalize_text(text_original)
    if "ifood" in normalized:
        return "iFood"
    return ""


def _detect_operacao(prompt: str, operacao_ui: str = "") -> str:
    ui = _normalize_text(operacao_ui)
    text = _normalize_text(prompt)

    if any(token in text for token in ["estoque", "saldo", "balanco", "balanço", "deposito", "depósito"]):
        return "estoque"

    if any(token in text for token in ["cadastro", "cadastrar", "catalogo", "catálogo", "produto novo"]):
        return "cadastro"

    if ui in {"cadastro", "estoque"}:
        return ui

    return "cadastro"


def _detect_origem(prompt: str, origem_ui: str = "", url_site: str = "") -> str:
    if _safe_str(url_site):
        return "site"

    ui = _normalize_text(origem_ui)
    text = _normalize_text(prompt)

    if any(token in text for token in ["xml", "nfe", "nf e", "nota fiscal"]):
        return "xml"

    if "pdf" in text:
        return "pdf"

    if any(token in text for token in ["site", "url", "categoria", "buscar no site", "scraping", "scraper"]):
        return "site"

    if any(token in text for token in ["api", "fornecedor api", "integracao fornecedor"]):
        return "api_fornecedor"

    if any(token in text for token in ["planilha", "xlsx", "xls", "csv"]):
        return "planilha"

    if ui in {"planilha", "site", "xml", "pdf", "api_fornecedor"}:
        return ui

    return "planilha"


def _detect_fornecedor(prompt: str, url_site: str = "") -> str:
    text = f"{_safe_str(prompt)} {_safe_str(url_site)}"
    normalized = _normalize_text(text)

    rules = {
        "mega_center": ["mega center", "megacenter", "mega center eletronicos", "megacentereletronicos"],
        "atacadum": ["atacadum"],
        "oba_oba_mix": ["oba oba mix", "obaobamix"],
    }
    for fornecedor, aliases in rules.items():
        if any(alias in normalized for alias in aliases):
            return fornecedor
    return ""


def _build_resumo(operacao: str, origem: str, deposito_nome: str, fornecedor: str, url_site: str) -> str:
    parts = [
        f"Operação: {'Atualização de estoque' if operacao == 'estoque' else 'Cadastro de produtos'}",
        f"Origem: {origem}",
    ]
    if fornecedor:
        parts.append(f"Fornecedor: {fornecedor}")
    if deposito_nome:
        parts.append(f"Depósito: {deposito_nome}")
    if url_site:
        parts.append(f"URL: {url_site}")
    return " | ".join(parts)


def _build_proximas_acoes(operacao: str, origem: str) -> List[str]:
    actions: List[str] = []

    if origem == "site":
        actions.extend(
            [
                "Receber o modelo Bling da operação selecionada",
                "Executar a coleta do site",
                "Normalizar os dados coletados",
                "Preparar o fluxo de mapeamento",
            ]
        )
    elif origem == "xml":
        actions.extend(
            [
                "Receber o XML e o modelo Bling",
                "Normalizar a base do XML",
                "Preparar o mapeamento automático",
            ]
        )
    elif origem == "pdf":
        actions.extend(
            [
                "Receber o PDF e o modelo Bling",
                "Extrair dados do PDF",
                "Normalizar a base",
                "Preparar o mapeamento automático",
            ]
        )
    else:
        actions.extend(
            [
                "Receber a planilha fornecedora e o modelo Bling",
                "Normalizar colunas",
                "Preparar o mapeamento automático",
            ]
        )

    if operacao == "estoque":
        actions.append("Validar depósito, balanço e preço unitário")
    else:
        actions.append("Validar descrição, descrição curta e preço de venda")

    return actions


def _build_pendencias(operacao: str, origem: str, deposito_nome: str, url_site: str) -> List[str]:
    pending: List[str] = []

    if origem == "site" and not _safe_str(url_site):
        pending.append("informar_url_site")

    if operacao == "estoque" and not _safe_str(deposito_nome):
        pending.append("informar_deposito")

    pending.append("anexar_modelo_bling")

    if origem == "planilha":
        pending.append("anexar_planilha_fornecedora")
    elif origem == "xml":
        pending.append("anexar_xml")
    elif origem == "pdf":
        pending.append("anexar_pdf")
    elif origem == "site":
        pending.append("executar_coleta_site")

    return pending


def _infer_status(pendencias: List[str]) -> str:
    if not pendencias:
        return "pronto_para_proximo_fluxo"
    return "aguardando_input"


def _infer_next_question(operacao: str, origem: str, pendencias: List[str]) -> str:
    if "informar_url_site" in pendencias:
        return "Informe a URL da categoria ou do site que deseja coletar."
    if "informar_deposito" in pendencias:
        return "Qual é o nome do depósito que deve ser usado na atualização de estoque?"
    if "anexar_planilha_fornecedora" in pendencias:
        return "Agora anexe a planilha fornecedora que servirá como origem dos dados."
    if "anexar_xml" in pendencias:
        return "Agora anexe o XML da nota fiscal para eu continuar."
    if "anexar_pdf" in pendencias:
        return "Agora anexe o PDF que servirá como origem dos dados."
    if "anexar_modelo_bling" in pendencias:
        if operacao == "estoque":
            return "Agora anexe o modelo Bling de atualização de estoque."
        return "Agora anexe o modelo Bling de cadastro de produtos."
    if origem == "site":
        return "Posso seguir para o fluxo do site e preparar a coleta."
    return "Posso seguir para o próximo fluxo e preparar o mapeamento."


def _extract_json_block(content: str) -> Dict[str, Any]:
    text = _safe_str(content)
    if not text:
        return {}

    try:
        return json.loads(text)
    except Exception:
        pass

    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        return {}

    try:
        return json.loads(match.group(0))
    except Exception:
        return {}


def _get_api_key() -> str:
    secrets = {}
    try:
        secrets = st.secrets  # type: ignore[assignment]
    except Exception:
        secrets = {}

    candidates = [
        secrets.get("OPENAI_API_KEY") if isinstance(secrets, dict) else None,
        (secrets.get("openai", {}) or {}).get("api_key") if isinstance(secrets, dict) else None,
        os.getenv("OPENAI_API_KEY"),
    ]
    for candidate in candidates:
        if _safe_str(candidate):
            return _safe_str(candidate)
    return ""


def _get_model_name() -> str:
    try:
        secrets = st.secrets
        if isinstance(secrets, dict):
            return _safe_str((secrets.get("openai", {}) or {}).get("model")) or DEFAULT_MODEL
    except Exception:
        pass
    return DEFAULT_MODEL


def _call_gpt(
    prompt_usuario: str,
    operacao_ui: str = "",
    origem_ui: str = "",
    deposito_nome_ui: str = "",
    url_site_ui: str = "",
) -> Dict[str, Any]:
    api_key = _get_api_key()
    if not api_key or OpenAI is None:
        raise RuntimeError("OPENAI_API_KEY não configurada.")

    client = OpenAI(api_key=api_key)
    model_name = _get_model_name()

    system_prompt = """
Você é o orquestrador do sistema IA Planilhas → Bling.
Sua função é interpretar o pedido do usuário e devolver SOMENTE JSON válido.

Regras:
- operacao: "cadastro" ou "estoque"
- origem: "planilha", "site", "xml", "pdf" ou "api_fornecedor"
- fornecedor: string curta ou ""
- deposito_nome: string ou ""
- url_site: string ou ""
- confidence: número entre 0 e 1
- pendencias: lista de códigos curtos
- proxima_pergunta: pergunta objetiva e curta
- resumo: resumo operacional curto
- proximas_acoes: lista curta
- Não invente URL.
- Se operação for estoque e não houver depósito, inclua "informar_deposito".
- Se origem for site e não houver URL, inclua "informar_url_site".
- Sempre inclua "anexar_modelo_bling".
- Para planilha, inclua "anexar_planilha_fornecedora".
- Para xml, inclua "anexar_xml".
- Para pdf, inclua "anexar_pdf".
- Para site, inclua "executar_coleta_site".
"""

    user_payload = {
        "pedido_usuario": _safe_str(prompt_usuario),
        "ui": {
            "operacao": _safe_str(operacao_ui),
            "origem": _safe_str(origem_ui),
            "deposito_nome": _safe_str(deposito_nome_ui),
            "url_site": _safe_str(url_site_ui),
        },
    }

    response = client.chat.completions.create(
        model=model_name,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": json.dumps(user_payload, ensure_ascii=False),
            },
        ],
    )

    content = response.choices[0].message.content if response.choices else "{}"
    payload = _extract_json_block(content or "{}")
    payload["_model_name"] = model_name
    return payload


def _normalize_llm_payload(
    payload: Dict[str, Any],
    prompt_usuario: str,
    operacao_ui: str,
    origem_ui: str,
    deposito_nome_ui: str,
    url_site_ui: str,
) -> IAOrchestratorResult:
    operacao = _safe_str(payload.get("operacao")) or _detect_operacao(prompt_usuario, operacao_ui)
    origem = _safe_str(payload.get("origem")) or _detect_origem(prompt_usuario, origem_ui, url_site_ui)
    fornecedor = _safe_str(payload.get("fornecedor")) or _detect_fornecedor(prompt_usuario, url_site_ui)
    deposito_nome = _safe_str(payload.get("deposito_nome")) or _extract_deposito(prompt_usuario, deposito_nome_ui)
    url_site = _safe_str(payload.get("url_site")) or _extract_url(url_site_ui) or _extract_url(prompt_usuario)

    pendencias = payload.get("pendencias")
    if not isinstance(pendencias, list):
        pendencias = _build_pendencias(operacao, origem, deposito_nome, url_site)

    cleaned_pendencias = [str(item).strip() for item in pendencias if _safe_str(item)]
    if "anexar_modelo_bling" not in cleaned_pendencias:
        cleaned_pendencias.append("anexar_modelo_bling")

    if origem == "planilha" and "anexar_planilha_fornecedora" not in cleaned_pendencias:
        cleaned_pendencias.append("anexar_planilha_fornecedora")
    if origem == "xml" and "anexar_xml" not in cleaned_pendencias:
        cleaned_pendencias.append("anexar_xml")
    if origem == "pdf" and "anexar_pdf" not in cleaned_pendencias:
        cleaned_pendencias.append("anexar_pdf")
    if origem == "site" and "executar_coleta_site" not in cleaned_pendencias:
        cleaned_pendencias.append("executar_coleta_site")
    if operacao == "estoque" and not deposito_nome and "informar_deposito" not in cleaned_pendencias:
        cleaned_pendencias.append("informar_deposito")
    if origem == "site" and not url_site and "informar_url_site" not in cleaned_pendencias:
        cleaned_pendencias.append("informar_url_site")

    status = _infer_status(cleaned_pendencias)
    proxima_etapa = "modelo" if status == "pronto_para_proximo_fluxo" else "origem"

    proximas_acoes = payload.get("proximas_acoes")
    if not isinstance(proximas_acoes, list):
        proximas_acoes = _build_proximas_acoes(operacao, origem)

    confidence = payload.get("confidence", 0.0)
    try:
        confidence = float(confidence)
    except Exception:
        confidence = 0.0

    resumo = _safe_str(payload.get("resumo")) or _build_resumo(
        operacao=operacao,
        origem=origem,
        deposito_nome=deposito_nome,
        fornecedor=fornecedor,
        url_site=url_site,
    )

    proxima_pergunta = _safe_str(payload.get("proxima_pergunta")) or _infer_next_question(
        operacao=operacao,
        origem=origem,
        pendencias=cleaned_pendencias,
    )

    result = IAOrchestratorResult(
        prompt_usuario=_safe_str(prompt_usuario),
        operacao=operacao,
        origem=origem,
        fornecedor=fornecedor,
        deposito_nome=deposito_nome,
        url_site=url_site,
        modelo_llm=_safe_str(payload.get("_model_name")) or _get_model_name(),
        provider="openai",
        confidence=max(0.0, min(confidence, 1.0)),
        status=status,
        etapa_atual="origem",
        proxima_etapa=proxima_etapa,
        proxima_pergunta=proxima_pergunta,
        resumo=resumo,
        pendencias=cleaned_pendencias,
        avisos=[str(item).strip() for item in payload.get("avisos", []) if _safe_str(item)]
        if isinstance(payload.get("avisos"), list)
        else [],
        erros=[],
        proximas_acoes=[str(item).strip() for item in proximas_acoes if _safe_str(item)],
        usar_gpt=True,
        raw=payload,
    )
    return result


def _fallback_orchestrate(
    prompt_usuario: str,
    operacao_ui: str = "",
    origem_ui: str = "",
    deposito_nome_ui: str = "",
    url_site_ui: str = "",
    erro_llm: str = "",
) -> IAOrchestratorResult:
    operacao = _detect_operacao(prompt_usuario, operacao_ui)
    origem = _detect_origem(prompt_usuario, origem_ui, url_site_ui)
    fornecedor = _detect_fornecedor(prompt_usuario, url_site_ui)
    deposito_nome = _extract_deposito(prompt_usuario, deposito_nome_ui)
    url_site = _extract_url(url_site_ui) or _extract_url(prompt_usuario)

    pendencias = _build_pendencias(operacao, origem, deposito_nome, url_site)
    avisos: List[str] = []
    if erro_llm:
        avisos.append(f"GPT indisponível no momento. Fallback aplicado: {erro_llm}")

    return IAOrchestratorResult(
        prompt_usuario=_safe_str(prompt_usuario),
        operacao=operacao,
        origem=origem,
        fornecedor=fornecedor,
        deposito_nome=deposito_nome,
        url_site=url_site,
        modelo_llm="",
        provider="fallback",
        confidence=0.55,
        status=_infer_status(pendencias),
        etapa_atual="origem",
        proxima_etapa="modelo" if not pendencias else "origem",
        proxima_pergunta=_infer_next_question(operacao, origem, pendencias),
        resumo=_build_resumo(operacao, origem, deposito_nome, fornecedor, url_site),
        pendencias=pendencias,
        avisos=avisos,
        erros=[],
        proximas_acoes=_build_proximas_acoes(operacao, origem),
        usar_gpt=False,
        raw={},
    )


# ============================================================
# SESSION BRIDGE
# ============================================================

def apply_result_to_session(result: IAOrchestratorResult) -> Dict[str, Any]:
    state = get_agent_state()

    state.origem_tipo = result.origem
    state.fornecedor = result.fornecedor or state.fornecedor
    state.operacao = result.operacao
    state.deposito_nome = result.deposito_nome or state.deposito_nome
    state.etapa_atual = result.etapa_atual
    state.status_execucao = result.status
    state.pendencias = list(result.pendencias)
    state.avisos = list(result.avisos)
    state.erros = list(result.erros)

    save_agent_state(state)

    st.session_state["tipo_operacao"] = result.operacao
    st.session_state["tipo_operacao_bling"] = result.operacao
    st.session_state["origem_tipo"] = result.origem
    st.session_state["fornecedor_nome"] = result.fornecedor
    st.session_state["fornecedor_detectado"] = result.fornecedor
    st.session_state["deposito_nome"] = result.deposito_nome
    st.session_state["url_site_origem"] = result.url_site
    st.session_state["agent_plan"] = result.to_dict()
    st.session_state[SESSION_PLAN_KEY] = result.to_dict()
    st.session_state[SESSION_LAST_RESULT_KEY] = result.to_dict()
    st.session_state[SESSION_LAST_PROVIDER_KEY] = result.provider
    st.session_state[SESSION_LAST_RAW_KEY] = result.raw

    if result.status == "pronto_para_proximo_fluxo":
        st.session_state["fluxo_etapa"] = "modelo"
    else:
        st.session_state["fluxo_etapa"] = "origem"

    return result.to_dict()


# ============================================================
# PUBLIC API
# ============================================================

def executar_fluxo_gpt(
    prompt_usuario: str,
    operacao_ui: str = "",
    origem_ui: str = "",
    deposito_nome_ui: str = "",
    url_site_ui: str = "",
) -> Dict[str, Any]:
    prompt_usuario = _safe_str(prompt_usuario)

    if not prompt_usuario and not _safe_str(url_site_ui):
        result = IAOrchestratorResult(
            prompt_usuario="",
            status="aguardando_input",
            proxima_pergunta="Descreva o que deseja fazer para eu iniciar o fluxo.",
            resumo="Aguardando o primeiro comando do usuário.",
            pendencias=["descrever_pedido"],
            avisos=[],
            erros=[],
            proximas_acoes=[],
        )
        return apply_result_to_session(result)

    try:
        llm_payload = _call_gpt(
            prompt_usuario=prompt_usuario,
            operacao_ui=operacao_ui,
            origem_ui=origem_ui,
            deposito_nome_ui=deposito_nome_ui,
            url_site_ui=url_site_ui,
        )
        result = _normalize_llm_payload(
            payload=llm_payload,
            prompt_usuario=prompt_usuario,
            operacao_ui=operacao_ui,
            origem_ui=origem_ui,
            deposito_nome_ui=deposito_nome_ui,
            url_site_ui=url_site_ui,
        )
    except Exception as exc:
        st.session_state[SESSION_LAST_ERROR_KEY] = str(exc)
        result = _fallback_orchestrate(
            prompt_usuario=prompt_usuario,
            operacao_ui=operacao_ui,
            origem_ui=origem_ui,
            deposito_nome_ui=deposito_nome_ui,
            url_site_ui=url_site_ui,
            erro_llm=str(exc),
        )

    return apply_result_to_session(result)


def obter_plano_corrente() -> Dict[str, Any]:
    payload = st.session_state.get(SESSION_PLAN_KEY) or st.session_state.get("agent_plan") or {}
    if isinstance(payload, dict):
        return payload
    return {}


def limpar_fluxo_gpt() -> None:
    state = get_agent_state()
    state.status_execucao = "idle"
    state.etapa_atual = "origem"
    state.pendencias = []
    state.avisos = []
    state.erros = []
    save_agent_state(state)

    for key in [
        "ia_prompt_home",
        "deposito_nome_input",
        "url_site_origem",
        "fornecedor_nome",
        "fornecedor_detectado",
        "agent_plan",
        SESSION_PLAN_KEY,
        SESSION_LAST_RESULT_KEY,
        SESSION_LAST_ERROR_KEY,
        SESSION_LAST_RAW_KEY,
        SESSION_LAST_PROVIDER_KEY,
    ]:
        if key in st.session_state:
            try:
                del st.session_state[key]
            except Exception:
                st.session_state[key] = ""

    st.session_state["tipo_operacao"] = "cadastro"
    st.session_state["tipo_operacao_bling"] = "cadastro"
    st.session_state["origem_tipo"] = "planilha"
    st.session_state["deposito_nome"] = ""
    st.session_state["fluxo_etapa"] = "origem"


def sincronizar_agent_memory_com_resultado() -> None:
    plano = obter_plano_corrente()
    if not plano:
        return

    update_agent_state(
        origem_tipo=_safe_str(plano.get("origem")) or None,
        fornecedor=_safe_str(plano.get("fornecedor")) or None,
        operacao=_safe_str(plano.get("operacao")) or None,
        deposito_nome=_safe_str(plano.get("deposito_nome")) or None,
        etapa_atual=_safe_str(plano.get("etapa_atual")) or "origem",
        status_execucao=_safe_str(plano.get("status")) or "idle",
        pendencias=list(plano.get("pendencias", [])) if isinstance(plano.get("pendencias"), list) else [],
        avisos=list(plano.get("avisos", [])) if isinstance(plano.get("avisos"), list) else [],
        erros=list(plano.get("erros", [])) if isinstance(plano.get("erros"), list) else [],
    )
