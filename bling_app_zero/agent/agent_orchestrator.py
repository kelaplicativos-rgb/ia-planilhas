
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

import pandas as pd

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
    normalizar_dataframe,
    registrar_base_no_estado,
)

PROMPT_MESTRE_DEFINITIVO = """
Você é o orquestrador oficial do projeto IA Planilhas → Bling.

Sua função principal não é explicar genericamente.
Sua função principal é executar um ETL completo e devolver saída final pronta para o Bling.

OBJETIVO CENTRAL:
Receber dados de origem, transformar, mapear, validar e devolver o resultado final pronto para importação no Bling.

FONTES DE ENTRADA ACEITAS:
- planilha
- XML
- site
- fornecedor/API
- outras origens estruturadas que virem DataFrame

SAÍDA OBRIGATÓRIA:
- df_origem lido corretamente
- df_normalizado consistente
- df_fluxo transformado
- df_final validado
- preview final pronto para exportação no padrão do Bling

REGRAS OBRIGATÓRIAS:
1. Nunca parar em dados crus quando o objetivo for saída Bling.
2. Nunca perder linhas sem registrar aviso.
3. Sempre considerar todos os produtos/registros retornados pela origem.
4. Sempre aplicar o fluxo:
   origem → normalização → mapeamento → modelo interno Bling → validação → saída final
5. Sempre priorizar o modelo interno do Bling.
6. GTIN inválido deve ficar vazio.
7. Imagens devem ser separadas por pipe |.
8. Campos obrigatórios devem ser garantidos no modelo final.
9. Operação deve respeitar cadastro ou estoque.
10. No estoque, respeitar depósito e balanço.
11. No cadastro, respeitar descrição, descrição curta, código, preço de venda, GTIN/EAN e categoria.
12. Quando houver falha, devolver erro claro e status coerente.
13. Não responder como consultor; responder como executor do fluxo.
14. O sucesso real só existe quando houver saída final utilizável no Bling.

PRIORIDADES DE DECISÃO:
- primeiro: manter todos os registros
- segundo: estruturar no modelo interno do Bling
- terceiro: validar antes de liberar
- quarto: deixar o preview final pronto para exportação

COMPORTAMENTO ESPERADO:
- direto
- operacional
- fiel ao projeto
- orientado a resultado final
- sem respostas genéricas
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
            "Aplicar modelo interno do Bling",
            "Validar saída final",
            "Liberar preview/exportação final",
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
    contexto = montar_contexto_execucao(plano)
    return json.dumps(contexto, ensure_ascii=False, indent=2)


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
        "modo: ETL completo + Bling output"
    )

    proximas_acoes = [
        "Ler a origem",
        "Normalizar a base",
        "Aplicar modelo interno do Bling",
        "Validar base final do Bling",
        "Preparar preview e exportação final",
    ]

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
        observacoes=observacoes,
        proximas_acoes=proximas_acoes,
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
        log_func("[AGENT] PROMPT MESTRE DEFINITIVO carregado no orquestrador.", "INFO")
        log_func(f"[AGENT] objetivo final: {plano.objetivo_final}", "INFO")
        log_func(f"[AGENT] plano interpretado: {plano.observacoes}", "INFO")
        log_func(
            f"[AGENT] contexto do prompt:\n{prompt_contexto_para_texto(plano)}",
            "INFO",
        )

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
        state.add_pendencia("Garantir retorno de dados antes do modelo interno do Bling.")
        save_agent_state(state)

        if callable(log_func):
            log_func(f"[AGENT] {mensagem}", "ERROR")

        return {
            "ok": False,
            "mensagem": mensagem,
            "plano": plano,
            "prompt_mestre": PROMPT_MESTRE_DEFINITIVO,
            "contexto_execucao": montar_contexto_execucao(plano),
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

    resultado_final = gerar_preview_final(
        df=df_fluxo,
        operacao=plano.operacao,
        log_func=log_func,
    )

    state = get_agent_state()
    state.status_execucao = "sucesso" if resultado_final["validacao"]["aprovado"] else "revisao"
    state.etapa_atual = "final" if resultado_final["validacao"]["aprovado"] else "validacao"
    state.clear_erros()
    state.clear_pendencias()

    if total_linhas_origem != total_linhas_normalizado:
        state.add_aviso(
            f"A quantidade de linhas mudou na normalização: origem={total_linhas_origem} normalizado={total_linhas_normalizado}"
        )

    if total_linhas_normalizado != total_linhas_fluxo:
        state.add_aviso(
            f"A quantidade de linhas mudou na montagem do fluxo: normalizado={total_linhas_normalizado} fluxo={total_linhas_fluxo}"
        )

    if total_linhas_origem == total_linhas_fluxo:
        state.add_log(
            f"Integridade de linhas preservada no ETL: {total_linhas_fluxo} registros."
        )
    else:
        state.add_aviso(
            f"ETL concluiu com alteração de volume: origem={total_linhas_origem} final_fluxo={total_linhas_fluxo}"
        )

    for aviso in resultado_final["validacao"].get("avisos", []):
        state.add_aviso(aviso)

    for erro in resultado_final["validacao"].get("erros", []):
        state.add_erro(erro)

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
        "df_origem": df_fluxo.copy(),
        "df_final": (
            resultado_final["df_final"].copy()
            if _tem_df(resultado_final["df_final"])
            else pd.DataFrame()
        ),
        "validacao": resultado_final["validacao"],
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
    return state.status_execucao in {"sucesso", "revisao", "base_pronta"}


def pode_ir_para_final() -> bool:
    state = get_agent_state()
    return bool(state.simulacao_aprovada) or state.status_execucao in {"sucesso", "revisao"}


