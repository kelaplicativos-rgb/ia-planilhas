
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

import pandas as pd

from bling_app_zero.agent.agent_memory import get_agent_state, save_agent_state, update_agent_state
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
    normalizar_dataframe,
    registrar_base_no_estado,
)


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
    observacoes: str = ""
    proximas_acoes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


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

    plano = IAPlanoExecucao(
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
        observacoes=f"Origem detectada: {origem}; operação: {operacao}; fornecedor: {fornecedor or '-'}",
        proximas_acoes=[
            "Ler a origem",
            "Normalizar a base",
            "Aplicar defaults do fluxo",
            "Validar base final do Bling",
        ],
    )
    return plano


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
        log_func(f"[AGENT] plano interpretado: {plano.observacoes}", "INFO")

    df_origem = _executar_fonte(plano=plano, arquivo_upload=arquivo_upload, ferramentas=ferramentas)

    if not _tem_df(df_origem):
        mensagem = "Nenhum dado foi retornado pela origem selecionada."
        state = get_agent_state()
        state.status_execucao = "erro"
        state.etapa_atual = "origem"
        state.add_erro(mensagem)
        save_agent_state(state)

        if callable(log_func):
            log_func(f"[AGENT] {mensagem}", "ERROR")

        return {
            "ok": False,
            "mensagem": mensagem,
            "plano": plano,
            "df_origem": pd.DataFrame(),
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

    df_normalizado = normalizar_dataframe(df_origem, log_func=log_func)
    df_fluxo = aplicar_defaults_fluxo(
        df=df_normalizado,
        operacao=plano.operacao,
        deposito_nome=plano.deposito,
    )

    registrar_base_no_estado(
        df=df_fluxo,
        origem_tipo=plano.origem,
        operacao=plano.operacao,
        fornecedor=plano.fornecedor,
        deposito_nome=plano.deposito,
        log_func=log_func,
    )

    resultado_final = gerar_preview_final(
        df=df_fluxo,
        operacao=plano.operacao,
        log_func=log_func,
    )

    state = get_agent_state()
    state.status_execucao = "sucesso" if resultado_final["validacao"]["aprovado"] else "revisao"
    state.etapa_atual = "final" if resultado_final["validacao"]["aprovado"] else "validacao"
    state.clear_erros()
    for aviso in resultado_final["validacao"].get("avisos", []):
        state.add_aviso(aviso)
    for erro in resultado_final["validacao"].get("erros", []):
        state.add_erro(erro)
    state.add_log(f"Fluxo IA executado para operação={plano.operacao} origem={plano.origem}")
    save_agent_state(state)

    return {
        "ok": True,
        "mensagem": "Fluxo executado com sucesso.",
        "plano": plano,
        "df_origem": df_fluxo.copy(),
        "df_final": resultado_final["df_final"].copy() if _tem_df(resultado_final["df_final"]) else pd.DataFrame(),
        "validacao": resultado_final["validacao"],
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
    }


def marcar_etapa_manual(etapa: str) -> None:
    update_agent_state(etapa_atual=_safe_str(etapa) or "origem")


def pode_ir_para_mapeamento() -> bool:
    state = get_agent_state()
    return state.status_execucao in {"sucesso", "revisao", "base_pronta"}


def pode_ir_para_final() -> bool:
    state = get_agent_state()
    return bool(state.simulacao_aprovada) or state.status_execucao in {"sucesso", "revisao"}


