
from __future__ import annotations

from typing import Any, Dict, Iterable, List

import pandas as pd
import streamlit as st

from bling_app_zero.agent.agent_memory import get_agent_state, save_agent_state
from bling_app_zero.ui.app_helpers import (
    blindar_df_para_bling,
    garantir_colunas_modelo,
    log_debug,
    normalizar_coluna_busca,
    safe_df_dados,
    sincronizar_etapa_global,
    validar_df_para_download,
)

# ============================================================
# HELPERS BÁSICOS
# ============================================================


def _safe_str(valor: Any) -> str:
    if valor is None:
        return ""
    texto = str(valor).strip()
    if texto.lower() in {"none", "nan", "nat"}:
        return ""
    return texto


def _safe_list(valor: Any) -> List[Any]:
    if isinstance(valor, list):
        return valor
    if isinstance(valor, tuple):
        return list(valor)
    if isinstance(valor, set):
        return list(valor)
    if valor is None:
        return []
    return [valor]


def _safe_dict(valor: Any) -> Dict[str, Any]:
    return valor if isinstance(valor, dict) else {}


def _serie_vazia(df_fonte: pd.DataFrame) -> pd.Series:
    return pd.Series([""] * len(df_fonte), index=df_fonte.index, dtype="object")


def _get_df_by_key(chave: str) -> pd.DataFrame | None:
    if not chave:
        return None
    df = st.session_state.get(chave)
    if safe_df_dados(df):
        return df.copy()
    return None


# ============================================================
# LEITURA FLEXÍVEL DO NOVO PACOTE
# ============================================================


def _candidate_dicts_from_session() -> Iterable[Dict[str, Any]]:
    for chave in [
        "agent_outputs",
        "agent_output",
        "agent_resultado",
        "agent_result",
        "resultado_agente",
        "orquestrador_resultado",
        "ia_resultado",
        "ia_outputs",
        "wizard_outputs",
    ]:
        payload = st.session_state.get(chave)
        if isinstance(payload, dict):
            yield payload


def _candidate_dicts_from_state() -> Iterable[Dict[str, Any]]:
    state = get_agent_state()

    for attr in [
        "defaults_aplicados",
        "metricas",
    ]:
        payload = getattr(state, attr, None)
        if isinstance(payload, dict):
            yield payload


def _get_from_nested_dict(payload: Dict[str, Any], path: List[str]) -> Any:
    atual: Any = payload
    for chave in path:
        if not isinstance(atual, dict):
            return None
        atual = atual.get(chave)
    return atual


def _buscar_valor_agente(*chaves: str) -> Any:
    """
    Busca um valor em múltiplas fontes do fluxo novo:
    1) atributos diretos do AgentRunState
    2) session_state direto
    3) dicionários agregados do estado/sessão
    4) estruturas aninhadas comuns do pacote
    """
    state = get_agent_state()

    for chave in chaves:
        if hasattr(state, chave):
            valor = getattr(state, chave)
            if valor not in (None, "", [], {}, ()):
                return valor

    for chave in chaves:
        valor = st.session_state.get(chave)
        if valor not in (None, "", [], {}, ()):
            return valor

    nested_paths = [
        ["mapeamento", "mapeamento_colunas"],
        ["mapeamento", "campos_pendentes"],
        ["mapeamento", "df_base_mapeamento"],
        ["mapping", "mapeamento_colunas"],
        ["mapping", "campos_pendentes"],
        ["mapping", "df_base_mapeamento"],
        ["resultado", "mapeamento_colunas"],
        ["resultado", "campos_pendentes"],
        ["resultado", "df_base_mapeamento"],
        ["outputs", "mapeamento_colunas"],
        ["outputs", "campos_pendentes"],
        ["outputs", "df_base_mapeamento"],
    ]

    for payload in _candidate_dicts_from_state():
        for chave in chaves:
            valor = payload.get(chave)
            if valor not in (None, "", [], {}, ()):
                return valor

        for path in nested_paths:
            if path[-1] not in chaves:
                continue
            valor = _get_from_nested_dict(payload, path)
            if valor not in (None, "", [], {}, ()):
                return valor

    for payload in _candidate_dicts_from_session():
        for chave in chaves:
            valor = payload.get(chave)
            if valor not in (None, "", [], {}, ()):
                return valor

        for path in nested_paths:
            if path[-1] not in chaves:
                continue
            valor = _get_from_nested_dict(payload, path)
            if valor not in (None, "", [], {}, ()):
                return valor

    return None


def _resolver_df_flex(valor: Any) -> pd.DataFrame | None:
    if isinstance(valor, pd.DataFrame) and safe_df_dados(valor):
        return valor.copy()

    if isinstance(valor, str):
        df = _get_df_by_key(valor)
        if safe_df_dados(df):
            return df

    return None


def _get_df_base_mapeamento() -> pd.DataFrame | None:
    for chave in [
        "df_base_mapeamento",
        "df_base_mapeamento_key",
        "base_mapeamento",
        "base_mapeamento_key",
    ]:
        valor = _buscar_valor_agente(chave)
        df = _resolver_df_flex(valor)
        if safe_df_dados(df):
            return df

    return None


def _get_df_fonte_fallback() -> pd.DataFrame | None:
    """
    Compatibilidade temporária com o fluxo anterior.
    """
    state = get_agent_state()

    for chave in [
        _safe_str(state.df_final_key),
        _safe_str(state.df_mapeado_key),
        _safe_str(state.df_normalizado_key),
        _safe_str(state.df_origem_key),
        "df_final",
        "df_mapeado",
        "df_normalizado",
        "df_origem",
    ]:
        df = _get_df_by_key(chave)
        if safe_df_dados(df):
            return df

    return None


def _get_df_fonte() -> pd.DataFrame | None:
    """
    Nova prioridade:
    1) df_base_mapeamento do pacote
    2) compatibilidade com chaves históricas
    """
    df_base = _get_df_base_mapeamento()
    if safe_df_dados(df_base):
        return df_base

    return _get_df_fonte_fallback()


def _get_df_modelo() -> pd.DataFrame:
    state = get_agent_state()
    tipo_operacao_bling = _safe_str(
        state.operacao or st.session_state.get("tipo_operacao_bling") or "cadastro"
    ).lower()

    df_modelo = st.session_state.get("df_modelo_operacao")
    if safe_df_dados(df_modelo):
        return garantir_colunas_modelo(df_modelo.copy(), tipo_operacao_bling)

    return garantir_colunas_modelo(pd.DataFrame(), tipo_operacao_bling)


# ============================================================
# DEFAULTS / SUGESTÕES
# ============================================================


def _coluna_encontrada_por_aproximacao(
    colunas_fonte: List[str],
    candidatos: List[str],
) -> str:
    mapa = {normalizar_coluna_busca(col): col for col in colunas_fonte}

    for candidato in candidatos:
        chave = normalizar_coluna_busca(candidato)
        if chave in mapa:
            return mapa[chave]

    for col in colunas_fonte:
        ncol = normalizar_coluna_busca(col)
        for candidato in candidatos:
            if normalizar_coluna_busca(candidato) in ncol:
                return col

    return ""


def _defaults_mapeamento(
    colunas_fonte: List[str],
    tipo_operacao_bling: str,
) -> Dict[str, str]:
    defaults: Dict[str, str] = {}

    defaults["Código"] = _coluna_encontrada_por_aproximacao(
        colunas_fonte,
        ["codigo", "codigo fornecedor", "sku", "ref", "referencia", "gtin", "ean"],
    )

    defaults["Descrição"] = _coluna_encontrada_por_aproximacao(
        colunas_fonte,
        ["descricao", "descricao fornecedor", "produto", "nome", "titulo"],
    )

    if tipo_operacao_bling == "estoque":
        defaults["Balanço (OBRIGATÓRIO)"] = _coluna_encontrada_por_aproximacao(
            colunas_fonte,
            ["quantidade real", "quantidade", "estoque", "saldo", "balanco"],
        )
        defaults["Preço unitário (OBRIGATÓRIO)"] = _coluna_encontrada_por_aproximacao(
            colunas_fonte,
            ["preco unitario", "preco calculado", "preco base", "preco", "valor"],
        )
        defaults["Descrição"] = defaults["Descrição"] or _coluna_encontrada_por_aproximacao(
            colunas_fonte,
            ["descricao curta", "nome", "titulo"],
        )
    else:
        defaults["Descrição Curta"] = defaults.get("Descrição", "")
        defaults["Preço de venda"] = _coluna_encontrada_por_aproximacao(
            colunas_fonte,
            ["preco de venda", "preco calculado", "preco base", "preco", "valor"],
        )
        defaults["GTIN/EAN"] = _coluna_encontrada_por_aproximacao(
            colunas_fonte,
            ["gtin", "ean", "codigo de barras"],
        )
        defaults["URL Imagens"] = _coluna_encontrada_por_aproximacao(
            colunas_fonte,
            ["url imagens", "imagem", "imagens", "url imagem"],
        )
        defaults["Categoria"] = _coluna_encontrada_por_aproximacao(
            colunas_fonte,
            ["categoria", "departamento", "breadcrumb", "grupo"],
        )

    return defaults


def _normalizar_mapping_dict(mapping: Dict[str, Any], colunas_fonte: List[str]) -> Dict[str, str]:
    normalizado: Dict[str, str] = {}

    for campo, origem in _safe_dict(mapping).items():
        campo_str = _safe_str(campo)
        origem_str = _safe_str(origem)
        if not campo_str:
            continue
        if origem_str and origem_str in colunas_fonte:
            normalizado[campo_str] = origem_str
        else:
            normalizado[campo_str] = ""

    return normalizado


def _get_mapping_do_pacote(colunas_fonte: List[str]) -> Dict[str, str]:
    for chave in [
        "mapeamento_colunas",
        "mapping_colunas",
        "mapping",
        "mapeamento",
    ]:
        valor = _buscar_valor_agente(chave)
        if isinstance(valor, dict):
            return _normalizar_mapping_dict(valor, colunas_fonte)

    return {}


def _get_campos_pendentes_do_pacote() -> List[str]:
    for chave in [
        "campos_pendentes",
        "pendencias_mapeamento",
        "campos_nao_mapeados",
    ]:
        valor = _buscar_valor_agente(chave)
        if isinstance(valor, (list, tuple, set)):
            return [_safe_str(v) for v in valor if _safe_str(v)]
    return []


def _obter_mapping_atual(
    colunas_modelo: List[str],
    colunas_fonte: List[str],
    tipo_operacao_bling: str,
) -> Dict[str, str]:
    defaults = _defaults_mapeamento(colunas_fonte, tipo_operacao_bling)
    mapping_pacote = _get_mapping_do_pacote(colunas_fonte)

    state = get_agent_state()
    mapping_salvo = _safe_dict(state.mapping_salvo or st.session_state.get("mapping_origem", {}))

    mapping_final: Dict[str, str] = {}
    for coluna_modelo in colunas_modelo:
        if mapping_pacote.get(coluna_modelo) in colunas_fonte:
            mapping_final[coluna_modelo] = mapping_pacote[coluna_modelo]
        elif _safe_str(mapping_salvo.get(coluna_modelo)) in colunas_fonte:
            mapping_final[coluna_modelo] = _safe_str(mapping_salvo.get(coluna_modelo))
        else:
            mapping_final[coluna_modelo] = defaults.get(coluna_modelo, "")

    return mapping_final


# ============================================================
# MONTAGEM DA SAÍDA
# ============================================================


def _montar_df_saida(
    df_fonte: pd.DataFrame,
    colunas_modelo: List[str],
    mapping: Dict[str, str],
    tipo_operacao_bling: str,
    deposito_nome: str,
) -> pd.DataFrame:
    df_saida = pd.DataFrame(index=df_fonte.index)

    for coluna_modelo in colunas_modelo:
        origem = mapping.get(coluna_modelo, "")
        if origem and origem in df_fonte.columns:
            df_saida[coluna_modelo] = df_fonte[origem]
        else:
            df_saida[coluna_modelo] = _serie_vazia(df_fonte)

    if "Situação" in df_saida.columns:
        df_saida["Situação"] = df_saida["Situação"].replace("", "Ativo").fillna("Ativo")

    if tipo_operacao_bling == "estoque":
        if "Depósito (OBRIGATÓRIO)" in df_saida.columns:
            df_saida["Depósito (OBRIGATÓRIO)"] = _safe_str(deposito_nome)
    else:
        if "Descrição Curta" in df_saida.columns and "Descrição" in df_saida.columns:
            vazios = df_saida["Descrição Curta"].astype(str).str.strip().isin(["", "nan", "None"])
            df_saida.loc[vazios, "Descrição Curta"] = df_saida.loc[vazios, "Descrição"]

    df_saida = blindar_df_para_bling(
        df=df_saida,
        tipo_operacao_bling=tipo_operacao_bling,
        deposito_nome=deposito_nome,
    )

    return df_saida.fillna("")


def _calcular_campos_pendentes(
    colunas_modelo: List[str],
    mapping: Dict[str, str],
    campos_pendentes_pacote: List[str],
) -> List[str]:
    pendentes = [_safe_str(campo) for campo in campos_pendentes_pacote if _safe_str(campo) in colunas_modelo]

    for coluna_modelo in colunas_modelo:
        if not _safe_str(mapping.get(coluna_modelo)):
            if coluna_modelo not in pendentes:
                pendentes.append(coluna_modelo)

    return pendentes


def _salvar_estado_mapeamento(
    df_preview: pd.DataFrame,
    mapping: Dict[str, str],
    campos_pendentes: List[str],
    tipo_operacao_bling: str,
) -> None:
    st.session_state["mapping_origem"] = mapping.copy()
    st.session_state["mapeamento_colunas"] = mapping.copy()
    st.session_state["campos_pendentes"] = campos_pendentes.copy()
    st.session_state["df_preview_mapeamento"] = df_preview.copy()
    st.session_state["df_mapeado"] = df_preview.copy()
    st.session_state["df_final"] = df_preview.copy()

    state = get_agent_state()
    state.mapping_salvo = mapping.copy()
    state.df_mapeado_key = "df_mapeado"
    state.df_final_key = "df_final"
    state.operacao = _safe_str(tipo_operacao_bling or state.operacao or "cadastro").lower()
    state.etapa_atual = "mapeamento"
    state.status_execucao = "mapeamento_pronto"
    state.pendencias = campos_pendentes.copy()

    defaults_aplicados = _safe_dict(getattr(state, "defaults_aplicados", {}))
    defaults_aplicados["mapeamento_colunas"] = mapping.copy()
    defaults_aplicados["campos_pendentes"] = campos_pendentes.copy()
    defaults_aplicados["df_base_mapeamento"] = "df_final"
    state.defaults_aplicados = defaults_aplicados

    save_agent_state(state)


# ============================================================
# UI
# ============================================================


def _render_contexto_agente(
    df_fonte: pd.DataFrame,
    campos_pendentes: List[str],
    mapping_atual: Dict[str, str],
) -> None:
    st.info(
        "A IA já preparou a base de mapeamento. "
        "Agora revise os campos abaixo e informe manualmente os que ainda ficaram pendentes."
    )

    if campos_pendentes:
        st.warning(
            "Campos pendentes identificados pela IA: "
            + ", ".join(campos_pendentes)
        )
    else:
        st.success("A IA já trouxe sugestões para todos os campos do modelo.")

    with st.expander("Preview da base trazida pelo agente", expanded=False):
        st.dataframe(df_fonte.head(50), use_container_width=True)

    with st.expander("Sugestões de mapeamento recebidas do agente", expanded=False):
        if mapping_atual:
            df_map = pd.DataFrame(
                [{"Campo modelo": campo, "Coluna origem": origem} for campo, origem in mapping_atual.items()]
            )
            st.dataframe(df_map, use_container_width=True)
        else:
            st.caption("Nenhuma sugestão estruturada foi recebida do pacote novo.")


def render_origem_mapeamento() -> None:
    st.markdown("### Mapeamento de colunas")
    st.caption("Confirme a origem de cada campo do modelo final antes do download.")

    state = get_agent_state()
    df_fonte = _get_df_fonte()

    if not safe_df_dados(df_fonte):
        st.warning("Nenhum dado disponível para mapear.")
        if st.button("⬅️ Voltar para IA", use_container_width=True):
            sincronizar_etapa_global("ia_orquestrador")
            st.rerun()
        return

    tipo_operacao_bling = _safe_str(
        state.operacao or st.session_state.get("tipo_operacao_bling") or "cadastro"
    ).lower()
    deposito_nome = _safe_str(state.deposito_nome or st.session_state.get("deposito_nome"))

    df_modelo = _get_df_modelo()
    colunas_modelo = list(df_modelo.columns)
    colunas_fonte = list(df_fonte.columns)

    mapping_atual = _obter_mapping_atual(colunas_modelo, colunas_fonte, tipo_operacao_bling)
    campos_pendentes_pacote = _get_campos_pendentes_do_pacote()

    _render_contexto_agente(
        df_fonte=df_fonte,
        campos_pendentes=campos_pendentes_pacote,
        mapping_atual=mapping_atual,
    )

    st.markdown("#### Defina o mapeamento")

    opcoes_select = [""] + colunas_fonte
    mapping_novo: Dict[str, str] = {}
    usados: set[str] = set()

    for coluna_modelo in colunas_modelo:
        bloqueado = False
        ajuda = ""

        if tipo_operacao_bling == "estoque" and coluna_modelo == "Depósito (OBRIGATÓRIO)":
            bloqueado = True
            ajuda = "Preenchido automaticamente pelo campo Nome do depósito."
        elif coluna_modelo == "Situação":
            bloqueado = True
            ajuda = "Preenchido automaticamente como Ativo."

        if bloqueado:
            valor_exibido = ""
            if coluna_modelo == "Depósito (OBRIGATÓRIO)":
                valor_exibido = deposito_nome
            elif coluna_modelo == "Situação":
                valor_exibido = "Ativo"

            st.text_input(
                coluna_modelo,
                value=valor_exibido,
                disabled=True,
                help=ajuda,
                key=f"map_lock_{coluna_modelo}",
            )
            mapping_novo[coluna_modelo] = ""
            continue

        sugestao = mapping_atual.get(coluna_modelo, "")
        if sugestao not in opcoes_select:
            sugestao = ""

        idx = opcoes_select.index(sugestao) if sugestao in opcoes_select else 0
        campo_pendente = coluna_modelo in campos_pendentes_pacote

        escolha = st.selectbox(
            coluna_modelo,
            options=opcoes_select,
            index=idx,
            key=f"map_{coluna_modelo}",
            help="Campo pendente detectado pela IA. Escolha manualmente a coluna correta."
            if campo_pendente
            else None,
        )

        if campo_pendente and not escolha:
            st.caption("⚠️ Este campo ainda precisa ser definido manualmente.")

        if escolha and escolha in usados:
            st.warning(f"A coluna '{escolha}' já foi usada em outro campo.")
        elif escolha:
            usados.add(escolha)

        mapping_novo[coluna_modelo] = escolha

    campos_pendentes_finais = _calcular_campos_pendentes(
        colunas_modelo=colunas_modelo,
        mapping=mapping_novo,
        campos_pendentes_pacote=campos_pendentes_pacote,
    )

    df_preview = _montar_df_saida(
        df_fonte=df_fonte,
        colunas_modelo=colunas_modelo,
        mapping=mapping_novo,
        tipo_operacao_bling=tipo_operacao_bling,
        deposito_nome=deposito_nome,
    )

    _salvar_estado_mapeamento(
        df_preview=df_preview,
        mapping=mapping_novo,
        campos_pendentes=campos_pendentes_finais,
        tipo_operacao_bling=tipo_operacao_bling,
    )

    with st.expander("Preview do mapeamento", expanded=False):
        st.dataframe(df_preview.head(50), use_container_width=True)

    ok_download, erros_download = validar_df_para_download(
        df=df_preview,
        tipo_operacao_bling=tipo_operacao_bling,
    )

    if campos_pendentes_finais:
        with st.expander("Campos ainda pendentes", expanded=False):
            for campo in campos_pendentes_finais:
                st.warning(f"Campo sem origem definida: {campo}")

    if erros_download:
        with st.expander("Validação do mapeamento", expanded=False):
            for erro in erros_download:
                st.error(erro)

    st.markdown("---")
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("⬅️ Voltar", use_container_width=True):
            sincronizar_etapa_global("ia_orquestrador")
            st.rerun()

    with col2:
        if st.button("Zerar mapeamento", use_container_width=True):
            st.session_state["mapping_origem"] = {}
            st.session_state["mapeamento_colunas"] = {}
            st.session_state["campos_pendentes"] = colunas_modelo.copy()

            state = get_agent_state()
            state.mapping_salvo = {}
            state.pendencias = colunas_modelo.copy()

            defaults_aplicados = _safe_dict(getattr(state, "defaults_aplicados", {}))
            defaults_aplicados["mapeamento_colunas"] = {}
            defaults_aplicados["campos_pendentes"] = colunas_modelo.copy()
            state.defaults_aplicados = defaults_aplicados

            save_agent_state(state)
            st.rerun()

    with col3:
        pode_avancar = safe_df_dados(df_preview) and ok_download and not campos_pendentes_finais

        if st.button("Continuar ➜", use_container_width=True, disabled=not pode_avancar):
            log_debug("Mapeamento concluído com sucesso pelo fluxo novo do agente", "INFO")

            state = get_agent_state()
            state.df_final_key = "df_final"
            state.etapa_atual = "final"
            state.status_execucao = "final_pronto"
            state.pendencias = []
            save_agent_state(state)

            sincronizar_etapa_global("final")
            st.rerun()

