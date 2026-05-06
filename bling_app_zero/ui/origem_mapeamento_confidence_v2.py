from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.ui.mapeamento.mapping_engine import (
    analyze_mapping,
    log_mapping_analysis,
    render_mapping_feedback,
)
from bling_app_zero.ui.mapeamento.source_columns import escolher_df_origem_captura, opcoes_origem_mapeamento
from bling_app_zero.ui.mapeamento_sample_hint import render_amostra_vermelha
from bling_app_zero.ui.origem_mapeamento_helpers import (
    _aplicar_mapping,
    _campos_bloqueados_automaticos,
    _coluna_deposito_modelo,
    _coluna_preco_prioritaria,
    _eh_coluna_video,
)


def _bloqueados_sem_preco(df_modelo: pd.DataFrame, operacao: str) -> set[str]:
    bloqueados = set(_campos_bloqueados_automaticos(df_modelo, operacao))
    coluna_preco = _coluna_preco_prioritaria(df_modelo, operacao)
    if coluna_preco in bloqueados:
        bloqueados.remove(coluna_preco)
    return bloqueados


def _badge(titulo: str, subtitulo: str = "") -> None:
    st.markdown(f"**{titulo}**")
    if subtitulo:
        st.caption(subtitulo)


def _status_basico(df_base: pd.DataFrame, coluna_modelo: str, coluna_origem: str) -> tuple[str, str]:
    if _eh_coluna_video(coluna_modelo):
        return "OFF", "Campo de video bloqueado."
    if not coluna_origem:
        return "PENDENTE", "Escolha uma coluna real da origem."
    if coluna_origem not in df_base.columns:
        return "ERRO", "Coluna nao encontrada na origem."
    if _eh_coluna_video(coluna_origem):
        return "ERRO", "Origem de video bloqueada."

    analise = analyze_mapping(df_base, coluna_modelo, coluna_origem)
    if analise.status == "valid":
        return "OK", f"Correlação real: {int(analise.confidence * 100)}%"
    if analise.status == "warning":
        return "ATENÇÃO", f"Correlação incerta: {int(analise.confidence * 100)}%"
    return "ERRO", f"Correlação inválida: {int(analise.confidence * 100)}%"


def _render_resumo(df_origem: pd.DataFrame, df_modelo: pd.DataFrame, mapping: dict[str, str], bloqueados: set[str]) -> None:
    total = len(df_modelo.columns)
    preenchidos = 0
    pendentes = 0
    automaticos = 0
    invalidos = 0
    alertas = 0

    for coluna in [str(c) for c in df_modelo.columns.tolist()]:
        origem = str(mapping.get(coluna, "") or "").strip()
        if coluna in bloqueados:
            automaticos += 1
        elif origem:
            analise = analyze_mapping(df_origem, coluna, origem)
            if analise.status == "invalid":
                invalidos += 1
            elif analise.status == "warning":
                alertas += 1
            else:
                preenchidos += 1
        else:
            pendentes += 1

    st.caption(
        f"Origem/captura: {len(df_origem.columns)} colunas | Modelo: {total} | "
        f"Válidos: {preenchidos} | Alertas: {alertas} | Inválidos: {invalidos} | "
        f"Pendentes: {pendentes} | Automáticos: {automaticos}"
    )


def _ordenar_colunas(df_modelo: pd.DataFrame, mapping: dict[str, str], bloqueados: set[str]) -> list[str]:
    itens: list[tuple[int, str, str]] = []
    for coluna in [str(c) for c in df_modelo.columns.tolist()]:
        if coluna in bloqueados:
            ordem = 3
        elif not str(mapping.get(coluna, "") or "").strip():
            ordem = 0
        else:
            ordem = 2
        itens.append((ordem, coluna.lower(), coluna))
    itens.sort(key=lambda item: (item[0], item[1]))
    return [coluna for _, _, coluna in itens]


def _render_feedback_correlacao(df_origem: pd.DataFrame, coluna_modelo: str, coluna_origem: str) -> None:
    analise = analyze_mapping(df_origem, coluna_modelo, coluna_origem)
    log_mapping_analysis(analise)
    render_mapping_feedback(analise)


def _render_revisao_manual(df_base: pd.DataFrame, df_modelo: pd.DataFrame, operacao: str) -> None:
    st.caption("Ajuste manual. O seletor mostra somente as colunas da origem/captura e valida a correlação por nome + conteúdo real.")

    if not isinstance(df_base, pd.DataFrame) or df_base.empty or not isinstance(df_modelo, pd.DataFrame):
        st.warning("Base ou modelo invalido para mapeamento.")
        return

    df_origem = escolher_df_origem_captura(st.session_state)
    if not isinstance(df_origem, pd.DataFrame) or df_origem.empty:
        df_origem = df_base

    opcoes_origem = opcoes_origem_mapeamento(
        df_origem,
        df_modelo,
        incluir_vazio=True,
        bloquear_video=True,
        video_checker=_eh_coluna_video,
    )
    bloqueados = _bloqueados_sem_preco(df_modelo, operacao)
    mapping_atual = st.session_state.get("mapping_manual", {})
    if not isinstance(mapping_atual, dict):
        mapping_atual = {}
    mapping_atual = mapping_atual.copy()

    _render_resumo(df_origem, df_modelo, mapping_atual, bloqueados)

    for coluna_modelo in _ordenar_colunas(df_modelo, mapping_atual, bloqueados):
        if coluna_modelo in bloqueados:
            motivo = "campo automatico"
            if _eh_coluna_video(coluna_modelo):
                motivo = "video fica vazio"
            elif coluna_modelo == _coluna_deposito_modelo(df_modelo) and operacao == "estoque":
                motivo = "deposito fixo da operacao"
            _badge(f"AUTO {coluna_modelo}", motivo)
            mapping_atual[coluna_modelo] = ""
            continue

        valor_atual = str(mapping_atual.get(coluna_modelo, "") or "").strip()
        if valor_atual not in opcoes_origem or _eh_coluna_video(valor_atual):
            valor_atual = ""

        status, detalhe = _status_basico(df_origem, coluna_modelo, valor_atual)
        _badge(f"{status} {coluna_modelo}", detalhe)

        novo_valor = st.selectbox(
            f"{coluna_modelo}",
            options=opcoes_origem,
            index=opcoes_origem.index(valor_atual) if valor_atual in opcoes_origem else 0,
            key=f"map_{coluna_modelo}",
            help="Escolha somente uma coluna real da origem/captura. A correlação agora valida também o conteúdo da coluna.",
        )

        novo_valor = str(novo_valor or "").strip()
        mapping_atual[coluna_modelo] = "" if _eh_coluna_video(novo_valor) else novo_valor

        if novo_valor:
            _render_feedback_correlacao(df_origem, coluna_modelo, novo_valor)
            render_amostra_vermelha(df_origem, novo_valor, prefixo="Selecionado")
        else:
            _render_feedback_correlacao(df_origem, coluna_modelo, "")

    for coluna_modelo in [str(c) for c in df_modelo.columns.tolist()]:
        if _eh_coluna_video(coluna_modelo):
            mapping_atual[coluna_modelo] = ""

    st.session_state["mapping_manual"] = mapping_atual
    st.session_state["df_final"] = _aplicar_mapping(df_base, df_modelo, mapping_atual)
