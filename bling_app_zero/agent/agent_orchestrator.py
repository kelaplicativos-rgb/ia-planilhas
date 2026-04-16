
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st

from bling_app_zero.agent.agent_memory import (
    get_agent_state,
    save_agent_state,
    update_agent_state,
)
from bling_app_zero.agent.agent_tools import (
    FerramentasAgente,
    aplicar_defaults_fluxo,
    buscar_dados_fornecedor,
    buscar_dados_site,
    detectar_deposito,
    detectar_fornecedor,
    detectar_operacao,
    detectar_origem_por_entrada,
    gerar_preview_final,
    ler_planilha_origem,
    ler_xml_nfe,
    montar_df_final_por_mapeamento,
    normalizar_dataframe,
    registrar_base_no_estado,
    sugerir_mapeamento_para_modelo,
)

PROMPT_MESTRE_DEFINITIVO = """
Você é o orquestrador oficial do projeto IA Planilhas → Bling.

Seu papel é executar ETL completo + Bling output.
Você deve preparar o fluxo para wizard visual com:
- leitura da origem
- normalização
- sugestão de mapeamento
- identificação de campos pendentes
- montagem final no modelo enviado
- preview final pronto para validação e download

Regras:
1. Nunca perder linhas sem registrar aviso.
2. Sempre priorizar o modelo enviado pelo usuário para cadastro ou estoque.
3. Sempre sugerir mapeamento automático antes de perguntar ao usuário.
4. Tudo que não puder ser mapeado com segurança deve virar campo pendente.
5. O sucesso real só existe quando houver df_final utilizável para Bling.
""".strip()


def _safe_str(valor: Any) -> str:
    if valor is None:
        return ""
    texto = str(valor).strip()
    if texto.lower() in {"none", "nan", "nat"}:
        return ""
    return texto


def _texto_lower(valor: Any) -> str:
    return _safe_str(valor).lower()


def _tem_df(df: Any) -> bool:
    return isinstance(df, pd.DataFrame) and not df.empty and len(df.columns) > 0


@dataclass
class IAPlanoExecucao:
    origem: str = "planilha"
    operacao: str = "cadastro"
    fornecedor: str = ""
    url: str = ""
    deposito: str = ""
    usar_precificacao: bool = False
    manter_preco_original: bool = True
    mapear_auto: bool = True
    usar_xml: bool = False
    usar_site: bool = False
    usar_api_fornecedor: bool = False
    categoria: str = ""
    prompt_mestre_ativo: str = PROMPT_MESTRE_DEFINITIVO
    objetivo_final: str = "Gerar planilha final pronta para o Bling"
    estrategia_execucao: List[str] = field(
        default_factory=lambda: [
            "Ler a origem completa",
            "Normalizar sem perder linhas",
            "Gerar sugestões automáticas de mapeamento",
            "Usar o modelo do usuário como base do Bling",
            "Validar e preparar preview final",
        ]
    )
    observacoes: str = ""
    proximas_acoes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def obter_prompt_mestre_definitivo() -> str:
    return PROMPT_MESTRE_DEFINITIVO


def montar_contexto_execucao(plano: IAPlanoExecucao) -> Dict[str, Any]:
    return {
        "prompt_mestre": PROMPT_MESTRE_DEFINITIVO,
        "objetivo_final": plano.objetivo_final,
        "origem": plano.origem,
        "operacao": plano.operacao,
        "fornecedor": plano.fornecedor,
        "url": plano.url,
        "deposito": plano.deposito,
        "usar_precificacao": plano.usar_precificacao,
        "manter_preco_original": plano.manter_preco_original,
        "mapear_auto": plano.mapear_auto,
        "usar_xml": plano.usar_xml,
        "usar_site": plano.usar_site,
        "usar_api_fornecedor": plano.usar_api_fornecedor,
        "estrategia_execucao": list(plano.estrategia_execucao),
        "proximas_acoes": list(plano.proximas_acoes),
        "observacoes": plano.observacoes,
    }


def prompt_contexto_para_texto(plano: IAPlanoExecucao) -> str:
    return json.dumps(montar_contexto_execucao(plano), ensure_ascii=False, indent=2)


def _extrair_url(texto: str) -> str:
    match = re.search(r"(https?://\S+)", _safe_str(texto), flags=re.IGNORECASE)
    return match.group(1) if match else ""


def _detectar_precificacao(texto: str) -> Dict[str, Any]:
    texto_norm = _texto_lower(texto)

    if "preço original" in texto_norm or "preco original" in texto_norm:
        return {"usar_precificacao": False, "manter_preco_original": True}

    if "precificar" in texto_norm or "margem" in texto_norm or "imposto" in texto_norm:
        return {"usar_precificacao": True, "manter_preco_original": False}

    return {"usar_precificacao": False, "manter_preco_original": True}


def interpretar_comando_usuario(comando: str) -> IAPlanoExecucao:
    texto = _safe_str(comando)
    origem = detectar_origem_por_entrada(texto)
    operacao = detectar_operacao(texto)
    fornecedor = detectar_fornecedor(texto)
    deposito = detectar_deposito(texto)
    url = _extrair_url(texto)
    cfg_preco = _detectar_precificacao(texto)

    observacoes = (
        f"Origem detectada: {origem}; "
        f"operação: {operacao}; "
        f"fornecedor: {fornecedor or '-'}; "
        f"depósito: {deposito or '-'}; "
        "modo: wizard visual + ETL completo"
    )

    proximas_acoes = [
        "Ler a origem",
        "Normalizar a base",
        "Sugerir mapeamento para o modelo",
        "Perguntar campos pendentes",
        "Montar preview final do Bling",
    ]

    return IAPlanoExecucao(
        origem=origem,
        operacao=operacao,
        fornecedor=fornecedor,
        url=url,
        deposito=deposito,
        usar_precificacao=bool(cfg_preco["usar_precificacao"]),
        manter_preco_original=bool(cfg_preco["manter_preco_original"]),
        usar_xml=origem == "xml",
        usar_site=origem == "site",
        usar_api_fornecedor=origem == "fornecedor",
        observacoes=observacoes,
        proximas_acoes=proximas_acoes,
    )


def plano_para_json(plano: IAPlanoExecucao) -> str:
    return json.dumps(plano.to_dict(), ensure_ascii=False, indent=2)


def _executar_fonte(
    plano: IAPlanoExecucao,
    arquivo_upload: Any,
    ferramentas: FerramentasAgente,
) -> pd.DataFrame:
    if plano.origem == "xml":
        return ler_xml_nfe(
            arquivo_upload=arquivo_upload,
            xml_reader_func=ferramentas.xml_reader_func,
            log_func=ferramentas.log_func,
        )

    if plano.origem == "site":
        return buscar_dados_site(
            comando=plano.url or plano.observacoes,
            crawler_func=ferramentas.crawler_func,
            log_func=ferramentas.log_func,
        )

    if plano.origem == "fornecedor":
        return buscar_dados_fornecedor(
            fornecedor=plano.fornecedor,
            operacao=plano.operacao,
            fetch_router_func=ferramentas.fetch_router_func,
            log_func=ferramentas.log_func,
        )

    return ler_planilha_origem(
        arquivo_upload=arquivo_upload,
        log_func=ferramentas.log_func,
    )


def _obter_modelo_base_da_sessao(plano: IAPlanoExecucao) -> pd.DataFrame:
    df_modelo = st.session_state.get("df_modelo_base")
    if _tem_df(df_modelo):
        return df_modelo.copy()

    if plano.operacao == "cadastro":
        df_modelo = st.session_state.get("df_modelo_cadastro")
        if _tem_df(df_modelo):
            return df_modelo.head(0).copy()

    if plano.operacao == "estoque":
        df_modelo = st.session_state.get("df_modelo_estoque")
        if _tem_df(df_modelo):
            return df_modelo.head(0).copy()

    return pd.DataFrame()


def _registrar_contexto_wizard(
    plano: IAPlanoExecucao,
    df_base: pd.DataFrame,
    df_modelo: pd.DataFrame,
    mapping_sugerido: Dict[str, str],
    pendentes: List[str],
    log_func: Optional[Any] = None,
) -> None:
    st.session_state["df_base_mapeamento"] = df_base.copy()
    st.session_state["mapeamento_colunas"] = dict(mapping_sugerido)
    st.session_state["campos_pendentes"] = list(pendentes)
    st.session_state["tipo_operacao"] = plano.operacao
    st.session_state["operacao"] = plano.operacao

    if plano.deposito:
        st.session_state["deposito_nome"] = plano.deposito

    if _tem_df(df_modelo):
        st.session_state["df_modelo_base"] = df_modelo.head(0).copy()

    state = get_agent_state()
    state.operacao = plano.operacao
    state.fornecedor = plano.fornecedor
    state.deposito_nome = plano.deposito
    state.etapa_atual = "mapeamento" if pendentes else "validacao"
    state.status_execucao = "mapeamento_pronto" if pendentes else "base_pronta"
    state.clear_pendencias()

    for campo in pendentes:
        state.add_pendencia(f"Confirmar destino da coluna do modelo: {campo}")

    save_agent_state(state)

    if callable(log_func):
        log_func(
            f"[AGENT] wizard preparado com {len(mapping_sugerido)} sugestões e {len(pendentes)} pendências.",
            "INFO",
        )


def executar_fluxo_real_com_ia(
    st_session_state: Any,
    comando: str,
    arquivo_upload: Any = None,
    fetch_router_func: Optional[Any] = None,
    crawler_func: Optional[Any] = None,
    xml_reader_func: Optional[Any] = None,
    log_func: Optional[Any] = None,
) -> Dict[str, Any]:
    del st_session_state

    plano = interpretar_comando_usuario(comando)

    ferramentas = FerramentasAgente(
        fetch_router_func=fetch_router_func,
        crawler_func=crawler_func,
        xml_reader_func=xml_reader_func,
        log_func=log_func,
    )

    if callable(log_func):
        log_func("[AGENT] PROMPT MESTRE DEFINITIVO carregado no orquestrador.", "INFO")
        log_func(f"[AGENT] plano interpretado: {plano.observacoes}", "INFO")
        log_func(f"[AGENT] contexto:\n{prompt_contexto_para_texto(plano)}", "INFO")

    df_origem = _executar_fonte(
        plano=plano,
        arquivo_upload=arquivo_upload,
        ferramentas=ferramentas,
    )

    if not _tem_df(df_origem):
        mensagem = "Nenhum dado foi retornado pela origem selecionada."

        state = get_agent_state()
        state.status_execucao = "erro"
        state.etapa_atual = "origem"
        state.add_erro(mensagem)
        state.add_pendencia("Garantir retorno da planilha ou origem antes do wizard.")
        save_agent_state(state)

        if callable(log_func):
            log_func(f"[AGENT] {mensagem}", "ERROR")

        return {
            "ok": False,
            "mensagem": mensagem,
            "plano": plano,
            "prompt_mestre": PROMPT_MESTRE_DEFINITIVO,
            "contexto_execucao": montar_contexto_execucao(plano),
            "mapping_sugerido": {},
            "campos_pendentes_mapeamento": [],
            "df_origem": pd.DataFrame(),
            "df_base_mapeamento": pd.DataFrame(),
            "df_final": pd.DataFrame(),
            "validacao": {
                "aprovado": False,
                "erros": [mensagem],
                "avisos": [],
                "linhas_validas": 0,
                "linhas_invalidas": 0,
                "corrigido_automaticamente": [],
            },
        }

    total_linhas_origem = len(df_origem)

    df_normalizado = normalizar_dataframe(df_origem, log_func=log_func)
    total_linhas_normalizado = len(df_normalizado) if _tem_df(df_normalizado) else 0

    df_fluxo = aplicar_defaults_fluxo(
        df=df_normalizado,
        operacao=plano.operacao,
        deposito_nome=plano.deposito,
    )
    total_linhas_fluxo = len(df_fluxo) if _tem_df(df_fluxo) else 0

    registrar_base_no_estado(
        df=df_fluxo,
        origem_tipo=plano.origem,
        operacao=plano.operacao,
        fornecedor=plano.fornecedor,
        deposito_nome=plano.deposito,
        log_func=log_func,
    )

    df_modelo = _obter_modelo_base_da_sessao(plano)

    mapping_sugerido: Dict[str, str] = {}
    pendentes: List[str] = []
    df_final = pd.DataFrame()
    validacao = {
        "aprovado": False,
        "erros": [],
        "avisos": [],
        "linhas_validas": 0,
        "linhas_invalidas": 0,
        "corrigido_automaticamente": [],
    }

    if _tem_df(df_modelo):
        mapping_sugerido, pendentes = sugerir_mapeamento_para_modelo(
            df_origem=df_fluxo,
            df_modelo=df_modelo,
            operacao=plano.operacao,
            deposito_nome=plano.deposito,
        )

        _registrar_contexto_wizard(
            plano=plano,
            df_base=df_fluxo,
            df_modelo=df_modelo,
            mapping_sugerido=mapping_sugerido,
            pendentes=pendentes,
            log_func=log_func,
        )

        if not pendentes:
            df_final = montar_df_final_por_mapeamento(
                df_origem=df_fluxo,
                df_modelo=df_modelo,
                mapping=mapping_sugerido,
                operacao=plano.operacao,
                deposito_nome=plano.deposito,
            )

            if _tem_df(df_final):
                resultado_final = gerar_preview_final(
                    df=df_final,
                    operacao=plano.operacao,
                    log_func=log_func,
                )
                validacao = resultado_final["validacao"]
                df_final = (
                    resultado_final["df_final"].copy()
                    if _tem_df(resultado_final["df_final"])
                    else pd.DataFrame()
                )
    else:
        if callable(log_func):
            log_func("[AGENT] nenhum modelo base encontrado na sessão para gerar sugestões de mapeamento.", "WARNING")

        st.session_state["df_base_mapeamento"] = df_fluxo.copy()
        st.session_state["mapeamento_colunas"] = {}
        st.session_state["campos_pendentes"] = []

    state = get_agent_state()
    state.clear_erros()
    state.clear_avisos()

    if total_linhas_origem != total_linhas_normalizado:
        state.add_aviso(
            f"A quantidade de linhas mudou na normalização: origem={total_linhas_origem} normalizado={total_linhas_normalizado}"
        )

    if total_linhas_normalizado != total_linhas_fluxo:
        state.add_aviso(
            f"A quantidade de linhas mudou na montagem do fluxo: normalizado={total_linhas_normalizado} fluxo={total_linhas_fluxo}"
        )

    if total_linhas_origem == total_linhas_fluxo:
        state.add_log(f"Integridade de linhas preservada no ETL: {total_linhas_fluxo} registros.")
    else:
        state.add_aviso(
            f"ETL concluiu com alteração de volume: origem={total_linhas_origem} final_fluxo={total_linhas_fluxo}"
        )

    for aviso in validacao.get("avisos", []):
        state.add_aviso(aviso)
    for erro in validacao.get("erros", []):
        state.add_erro(erro)

    if _tem_df(df_final):
        state.status_execucao = "sucesso" if validacao.get("aprovado") else "revisao"
        state.etapa_atual = "final" if validacao.get("aprovado") else "validacao"
    elif pendentes:
        state.status_execucao = "mapeamento_pronto"
        state.etapa_atual = "mapeamento"
    else:
        state.status_execucao = "base_pronta"
        state.etapa_atual = "validacao"

    state.add_log(
        f"Fluxo IA executado para operação={plano.operacao} origem={plano.origem} fornecedor={plano.fornecedor or '-'}"
    )
    save_agent_state(state)

    return {
        "ok": True,
        "mensagem": "Fluxo executado com sucesso.",
        "plano": plano,
        "prompt_mestre": PROMPT_MESTRE_DEFINITIVO,
        "contexto_execucao": montar_contexto_execucao(plano),
        "mapping_sugerido": dict(mapping_sugerido),
        "campos_pendentes_mapeamento": list(pendentes),
        "df_origem": df_fluxo.copy(),
        "df_base_mapeamento": df_fluxo.copy(),
        "df_final": df_final.copy() if _tem_df(df_final) else pd.DataFrame(),
        "validacao": validacao,
        "metricas_etl": {
            "linhas_origem": total_linhas_origem,
            "linhas_normalizado": total_linhas_normalizado,
            "linhas_fluxo": total_linhas_fluxo,
        },
    }


def resumo_execucao_atual() -> Dict[str, Any]:
    state = get_agent_state()
    return {
        "etapa_atual": state.etapa_atual,
        "status_execucao": state.status_execucao,
        "operacao": state.operacao,
        "fornecedor": state.fornecedor,
        "deposito_nome": state.deposito_nome,
        "simulacao_aprovada": state.simulacao_aprovada,
        "pendencias": list(state.pendencias),
        "avisos": list(state.avisos),
        "erros": list(state.erros),
        "prompt_mestre_ativo": True,
    }


def marcar_etapa_manual(etapa: str) -> None:
    update_agent_state(etapa_atual=_safe_str(etapa) or "origem")


def pode_ir_para_mapeamento() -> bool:
    state = get_agent_state()
    return state.status_execucao in {"sucesso", "revisao", "base_pronta", "mapeamento_pronto"}


def pode_ir_para_final() -> bool:
    state = get_agent_state()
    return bool(state.simulacao_aprovada) or state.status_execucao in {"sucesso", "revisao"}


