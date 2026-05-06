from __future__ import annotations

"""Revisão manual do mapeamento com amostra compacta da origem.

Mostra, abaixo de cada campo do modelo, a primeira linha da coluna selecionada em
vermelho pequeno para facilitar a conferência no celular.
"""

import html as html_lib

import pandas as pd
import streamlit as st

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


def _badge(titulo: str, subtitulo: str = "", cor: str = "#0F172A", fundo: str = "#F8FAFC", borda: str = "#CBD5E1") -> None:
    subtitulo_html = ""
    if subtitulo:
        subtitulo_html = f"<div style='font-size:12px; opacity:.86; margin-top:2px'>{html_lib.escape(subtitulo)}</div>"
    st.markdown(
        f"""
        <div style="background:{fundo}; border:1px solid {borda}; border-left:5px solid {borda};
                    color:{cor}; border-radius:10px; padding:9px 11px; margin:8px 0 6px 0;">
            <div style="font-weight:700; font-size:14px;">{html_lib.escape(titulo)}</div>
            {subtitulo_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def _primeira_amostra(df_base: pd.DataFrame, coluna: str) -> str:
    if not isinstance(df_base, pd.DataFrame) or coluna not in df_base.columns:
        return ""
    try:
        for valor in df_base[coluna].fillna("").astype(str).tolist():
            texto = " ".join(str(valor or "").replace("\n", " ").replace("\r", " ").split()).strip()
            if texto:
                return texto[:117] + "..." if len(texto) > 120 else texto
    except Exception:
        return ""
    return ""


def _status_basico(df_base: pd.DataFrame, coluna_modelo: str, coluna_origem: str) -> tuple[str, str, str, str, str]:
    if _eh_coluna_video(coluna_modelo):
        return "🚫", "Campo de vídeo bloqueado", "Vídeo fica vazio para evitar propaganda.", "#334155", "#94A3B8"
    if not coluna_origem:
        return "🔴", "Sem coluna de origem", "Escolha uma coluna para este campo.", "#991B1B", "#EF4444"
    if coluna_origem not in df_base.columns:
        return "🔴", "Coluna não encontrada", "Selecione outra coluna.", "#991B1B", "#EF4444"
    if _eh_coluna_video(coluna_origem):
        return "🔴", "Origem de vídeo bloqueada", "Escolha outra coluna.", "#991B1B", "#EF4444"
    return "🟢", "Coluna selecionada", f"Origem: {coluna_origem}", "#065F46", "#10B981"


def _render_resumo(df_base: pd.DataFrame, df_modelo: pd.DataFrame, mapping: dict[str, str], bloqueados: set[str]) -> None:
    total = len(df_modelo.columns)
    preenchidos = 0
    pendentes = 0
    automaticos = 0
    for coluna in [str(c) for c in df_modelo.columns.tolist()]:
        if coluna in bloqueados:
            automaticos += 1
        elif str(mapping.get(coluna, "") or "").strip():
            preenchidos += 1
        else:
            pendentes += 1
    _badge(
        "🧭 Mapa visual do mapeamento",
        f"Total: {total} • Preenchidos: {preenchidos} • Pendentes: {pendentes} • Automáticos: {automaticos}",
        cor="#0F172A",
        fundo="#F8FAFC",
        borda="#CBD5E1",
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


def _render_revisao_manual(df_base: pd.DataFrame, df_modelo: pd.DataFrame, operacao: str) -> None:
    st.caption("Ajuste manual. A linha vermelha mostra a primeira amostra real da coluna selecionada.")

    if not isinstance(df_base, pd.DataFrame) or df_base.empty or not isinstance(df_modelo, pd.DataFrame):
        st.warning("Base ou modelo inválido para mapeamento.")
        return

    opcoes_origem = [""] + [str(c) for c in df_base.columns.tolist() if not _eh_coluna_video(c)]
    bloqueados = _bloqueados_sem_preco(df_modelo, operacao)
    mapping_atual = st.session_state.get("mapping_manual", {})
    if not isinstance(mapping_atual, dict):
        mapping_atual = {}
    mapping_atual = mapping_atual.copy()

    _render_resumo(df_base, df_modelo, mapping_atual, bloqueados)

    for coluna_modelo in _ordenar_colunas(df_modelo, mapping_atual, bloqueados):
        if coluna_modelo in bloqueados:
            if _eh_coluna_video(coluna_modelo):
                _badge(f"🚫 {coluna_modelo}", "Bloqueado automaticamente: vídeo fica vazio.", cor="#334155", borda="#94A3B8")
            else:
                motivo = "campo automático"
                if coluna_modelo == _coluna_deposito_modelo(df_modelo) and operacao == "estoque":
                    motivo = "depósito fixo da operação"
                _badge(f"🤖 {coluna_modelo}", motivo, cor="#1E3A8A", fundo="#EFF6FF", borda="#3B82F6")
            mapping_atual[coluna_modelo] = ""
            continue

        valor_atual = str(mapping_atual.get(coluna_modelo, "") or "").strip()
        if valor_atual not in opcoes_origem or _eh_coluna_video(valor_atual):
            valor_atual = ""

        emoji, titulo, subtitulo, cor, borda = _status_basico(df_base, coluna_modelo, valor_atual)
        _badge(f"{emoji} {coluna_modelo}", subtitulo or titulo, cor=cor, fundo="#FEF2F2" if emoji == "🔴" else "#ECFDF5", borda=borda)

        if valor_atual:
            render_amostra_vermelha(df_base, valor_atual, prefixo="1ª linha")

        novo_valor = st.selectbox(
            f"{coluna_modelo}",
            options=opcoes_origem,
            index=opcoes_origem.index(valor_atual) if valor_atual in opcoes_origem else 0,
            key=f"map_{coluna_modelo}",
            help="Escolha a coluna da origem. A amostra aparece em vermelho acima do campo.",
        )

        novo_valor = str(novo_valor or "").strip()
        if novo_valor and novo_valor != valor_atual:
            render_amostra_vermelha(df_base, novo_valor, prefixo="Selecionado")
        mapping_atual[coluna_modelo] = "" if _eh_coluna_video(novo_valor) else novo_valor

    for coluna_modelo in [str(c) for c in df_modelo.columns.tolist()]:
        if _eh_coluna_video(coluna_modelo):
            mapping_atual[coluna_modelo] = ""

    st.session_state["mapping_manual"] = mapping_atual
    st.session_state["df_final"] = _aplicar_mapping(df_base, df_modelo, mapping_atual)
