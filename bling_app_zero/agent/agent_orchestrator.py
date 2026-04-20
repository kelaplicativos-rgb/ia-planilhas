
from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from bling_app_zero.ui.app_helpers import (
    log_debug,
    normalizar_texto,
    safe_df_dados,
    safe_df_estrutura,
    validar_df_para_download,
)

from bling_app_zero.agent.agent_tools import (
    AgentResult,
    aplicar_regras_pos_processamento,
    construir_resumo_colunas_origem,
    detectar_campos_obrigatorios_modelo,
    extrair_colunas_modelo,
    forcar_preenchimento_obrigatorios,
    gerar_diagnostico_mapping,
    gerar_mapping_fallback,
    limpar_mapping_para_modelo,
    mapping_tem_duplicidade,
    tentar_mapping_openai,
)


# ============================================================
# HELPERS
# ============================================================

def _resolver_operacao() -> str:
    operacao = normalizar_texto(
        st.session_state.get("tipo_operacao")
        or st.session_state.get("tipo_operacao_bling")
        or "cadastro"
    )
    return operacao if operacao in {"cadastro", "estoque"} else "cadastro"


def _normalizar_agent_result(resultado: AgentResult | dict[str, Any] | None) -> dict[str, Any]:
    if resultado is None:
        return {
            "ok": False,
            "mapping": {},
            "provider": "none",
            "model": "",
            "erro": "Resultado do agente vazio.",
            "diagnostico": {},
        }

    if isinstance(resultado, AgentResult):
        return {
            "ok": bool(resultado.ok),
            "mapping": dict(resultado.mapping or {}),
            "provider": str(resultado.provider or ""),
            "model": str(resultado.model or ""),
            "erro": str(resultado.erro or ""),
            "diagnostico": dict(resultado.diagnostico or {}),
        }

    if isinstance(resultado, dict):
        return {
            "ok": bool(resultado.get("ok", False)),
            "mapping": dict(resultado.get("mapping", {}) or {}),
            "provider": str(resultado.get("provider", "") or ""),
            "model": str(resultado.get("model", "") or ""),
            "erro": str(resultado.get("erro", "") or ""),
            "diagnostico": dict(resultado.get("diagnostico", {}) or {}),
        }

    return {
        "ok": False,
        "mapping": {},
        "provider": "none",
        "model": "",
        "erro": "Formato de resultado inválido.",
        "diagnostico": {},
    }


def _salvar_memoria_agente(
    mapping: dict[str, str],
    diagnostico: dict[str, Any],
    provider: str,
    model: str,
) -> None:
    st.session_state["agent_last_mapping"] = dict(mapping or {})
    st.session_state["agent_last_diagnostico"] = dict(diagnostico or {})
    st.session_state["agent_last_provider"] = str(provider or "")
    st.session_state["agent_last_model"] = str(model or "")


# ============================================================
# ORQUESTRAÇÃO DE MAPEAMENTO
# ============================================================

def sugerir_mapeamento_agente(
    df_base: pd.DataFrame,
    df_modelo: pd.DataFrame,
    operacao: str | None = None,
) -> dict[str, Any]:
    operacao_resolvida = normalizar_texto(operacao or _resolver_operacao()) or "cadastro"

    if not safe_df_dados(df_base):
        erro = "Base de dados ausente ou vazia para sugerir mapeamento."
        log_debug(erro, nivel="ERRO")
        return {
            "ok": False,
            "mapping": {},
            "provider": "none",
            "model": "",
            "erro": erro,
            "diagnostico": {},
        }

    if not safe_df_estrutura(df_modelo):
        erro = "Modelo Bling ausente para sugerir mapeamento."
        log_debug(erro, nivel="ERRO")
        return {
            "ok": False,
            "mapping": {},
            "provider": "none",
            "model": "",
            "erro": erro,
            "diagnostico": {},
        }

    colunas_modelo = extrair_colunas_modelo(df_modelo)
    obrigatorios = detectar_campos_obrigatorios_modelo(df_modelo, operacao_resolvida)
    resumo_origem = construir_resumo_colunas_origem(df_base)

    resultado_openai = _normalizar_agent_result(
        tentar_mapping_openai(
            df_base=df_base,
            df_modelo=df_modelo,
            operacao=operacao_resolvida,
            resumo_origem=resumo_origem,
        )
    )

    mapping = limpar_mapping_para_modelo(
        mapping=resultado_openai.get("mapping", {}) or {},
        df_modelo=df_modelo,
        df_base=df_base,
    )

    if not any(str(v or "").strip() for v in mapping.values()):
        fallback = gerar_mapping_fallback(
            df_base=df_base,
            df_modelo=df_modelo,
            operacao=operacao_resolvida,
        )
        mapping = limpar_mapping_para_modelo(
            mapping=fallback,
            df_modelo=df_modelo,
            df_base=df_base,
        )
        if not resultado_openai.get("provider"):
            resultado_openai["provider"] = "fallback_local"

    mapping = aplicar_regras_pos_processamento(
        mapping=mapping,
        df_base=df_base,
        df_modelo=df_modelo,
        operacao=operacao_resolvida,
    )

    mapping = forcar_preenchimento_obrigatorios(
        mapping=mapping,
        df_base=df_base,
        df_modelo=df_modelo,
        operacao=operacao_resolvida,
    )

    diagnostico = gerar_diagnostico_mapping(
        mapping=mapping,
        colunas_modelo=colunas_modelo,
        obrigatorios=obrigatorios,
    )

    if mapping_tem_duplicidade(mapping):
        diagnostico["tem_duplicidade"] = True

    if diagnostico.get("faltando_obrigatorios"):
        log_debug(
            "Forçando preenchimento obrigatório, mas ainda restaram campos: "
            + ", ".join(diagnostico["faltando_obrigatorios"]),
            nivel="ERRO",
        )

    ok = bool(any(str(v or "").strip() for v in mapping.values()))
    erro = str(resultado_openai.get("erro", "") or "").strip()

    provider = str(resultado_openai.get("provider", "") or "").strip()
    model = str(resultado_openai.get("model", "") or "").strip()

    payload = {
        "ok": ok,
        "mapping": mapping,
        "provider": provider or "fallback_local",
        "model": model,
        "erro": erro,
        "diagnostico": diagnostico,
        "resumo_origem": resumo_origem,
    }

    _salvar_memoria_agente(
        mapping=payload["mapping"],
        diagnostico=payload["diagnostico"],
        provider=payload["provider"],
        model=payload["model"],
    )

    log_debug(
        f"Agente de mapeamento executado | ok={payload['ok']} | "
        f"provider={payload['provider']} | model={payload['model']} | "
        f"campos_mapeados={payload['diagnostico'].get('mapeados', 0)}",
        nivel="INFO",
    )

    return payload


# ============================================================
# APOIO À VALIDAÇÃO DO FLUXO
# ============================================================

def validar_resultado_final_agente(
    df_final: pd.DataFrame,
    operacao: str | None = None,
) -> dict[str, Any]:
    operacao_resolvida = normalizar_texto(operacao or _resolver_operacao()) or "cadastro"

    valido, erros = validar_df_para_download(df_final, operacao_resolvida)

    diagnostico = {
        "ok": bool(valido),
        "erros": list(erros or []),
        "operacao": operacao_resolvida,
        "linhas": int(len(df_final.index)) if isinstance(df_final, pd.DataFrame) else 0,
        "colunas": int(len(df_final.columns)) if isinstance(df_final, pd.DataFrame) else 0,
    }

    st.session_state["agent_last_validacao_df_final"] = diagnostico

    log_debug(
        f"Validação complementar do agente | ok={diagnostico['ok']} | "
        f"linhas={diagnostico['linhas']} | colunas={diagnostico['colunas']}",
        nivel="INFO" if diagnostico["ok"] else "ERRO",
    )

    return diagnostico


# ============================================================
# PACOTE DE APOIO PARA UI
# ============================================================

def construir_pacote_agente_para_ui(
    df_base: pd.DataFrame,
    df_modelo: pd.DataFrame,
    operacao: str | None = None,
) -> dict[str, Any]:
    operacao_resolvida = normalizar_texto(operacao or _resolver_operacao()) or "cadastro"
    sugestao = sugerir_mapeamento_agente(
        df_base=df_base,
        df_modelo=df_modelo,
        operacao=operacao_resolvida,
    )

    obrigatorios = detectar_campos_obrigatorios_modelo(df_modelo, operacao_resolvida)
    duplicidade = mapping_tem_duplicidade(sugestao.get("mapping", {}) or {})

    pacote = {
        "ok": bool(sugestao.get("ok", False)),
        "operacao": operacao_resolvida,
        "mapping": dict(sugestao.get("mapping", {}) or {}),
        "provider": str(sugestao.get("provider", "") or ""),
        "model": str(sugestao.get("model", "") or ""),
        "erro": str(sugestao.get("erro", "") or ""),
        "diagnostico": dict(sugestao.get("diagnostico", {}) or {}),
        "obrigatorios": list(obrigatorios),
        "tem_duplicidade": bool(duplicidade),
    }

    st.session_state["agent_ui_package"] = pacote
    return pacote

