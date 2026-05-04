from __future__ import annotations

import re

import pandas as pd
import streamlit as st

from bling_app_zero.ui.app_core_flow import set_etapa_segura
from bling_app_zero.ui.app_helpers import ir_para_etapa, safe_df_dados, safe_df_estrutura, voltar_etapa_anterior
from bling_app_zero.ui.gtin_panel import render_gtin_panel
from bling_app_zero.ui.origem_mapeamento_actions import _render_botoes_fluxo, _render_resumo_agente, _render_sugestao_agente
from bling_app_zero.ui.origem_mapeamento_confidence import _render_revisao_manual
from bling_app_zero.ui.origem_mapeamento_helpers import (
    _detectar_operacao,
    _executar_ia_autonoma,
    _garantir_etapa_mapeamento_ativa,
    _inicializar_mapping,
    _obter_df_base,
    _obter_df_modelo,
    _preview_mapping,
    _render_status_base,
    _sincronizar_deposito_nome,
)


def _norm_coluna(valor: object) -> str:
    texto = str(valor or "").strip().lower()
    texto = texto.translate(str.maketrans("áàãâéêíóôõúç", "aaaaeeiooouc"))
    return re.sub(r"[^a-z0-9]+", " ", texto).strip()


def _valor_preco_valido(valor: object) -> bool:
    texto = str(valor or "").strip()
    if not texto:
        return False
    texto = texto.replace("R$", "").replace("r$", "").replace(" ", "")
    if "," in texto and "." in texto:
        texto = texto.replace(".", "").replace(",", ".")
    else:
        texto = texto.replace(",", ".")
    texto = re.sub(r"[^0-9.\-]", "", texto)
    try:
        return float(texto) > 0
    except Exception:
        return False


def _serie_tem_preco_valido(serie: pd.Series) -> bool:
    if not isinstance(serie, pd.Series):
        return False
    return bool(serie.apply(_valor_preco_valido).any())


def _coluna_preco_destino(df_modelo: pd.DataFrame, operacao: str) -> str:
    if not safe_df_estrutura(df_modelo):
        return ""
    colunas = [str(c) for c in df_modelo.columns.tolist()]
    prioridades = [
        "Preço unitário (OBRIGATÓRIO)", "Preco unitario (OBRIGATORIO)",
        "Preço unitário", "Preco unitario", "Preço", "Preco", "Valor",
    ]
    if operacao != "estoque":
        prioridades = ["Preço de venda", "Preco de venda"] + prioridades
    mapa = {_norm_coluna(c): c for c in colunas}
    for prioridade in prioridades:
        achado = mapa.get(_norm_coluna(prioridade))
        if achado:
            return achado
    for col in colunas:
        nome = _norm_coluna(col)
        if "preco" in nome or "valor" in nome or "unitario" in nome:
            return col
    return ""


def _coluna_preco_origem(df_base: pd.DataFrame, destino: str) -> str:
    if not safe_df_dados(df_base):
        return ""
    colunas = [str(c) for c in df_base.columns.tolist()]
    mapa = {_norm_coluna(c): c for c in colunas}
    if destino:
        achado = mapa.get(_norm_coluna(destino))
        if achado and _serie_tem_preco_valido(df_base[achado]):
            return achado
    for prioridade in ["Preço unitário (OBRIGATÓRIO)", "Preço unitário", "Preço de venda", "Preço", "Preco", "Valor", "price"]:
        achado = mapa.get(_norm_coluna(prioridade))
        if achado and _serie_tem_preco_valido(df_base[achado]):
            return achado
    for col in colunas:
        nome = _norm_coluna(col)
        if ("preco" in nome or "valor" in nome or "price" in nome) and _serie_tem_preco_valido(df_base[col]):
            return col
    return ""


def _garantir_preco_unitario_no_final(df_base: pd.DataFrame, df_modelo: pd.DataFrame, operacao: str) -> None:
    df_final = st.session_state.get("df_final")
    if not safe_df_estrutura(df_final) or not safe_df_dados(df_base):
        return
    destino = _coluna_preco_destino(df_modelo, operacao)
    if not destino or destino not in df_final.columns or _serie_tem_preco_valido(df_final[destino]):
        return
    origem_preco = _coluna_preco_origem(df_base, destino)
    if not origem_preco or origem_preco not in df_base.columns:
        return
    corrigido = df_final.copy().fillna("")
    corrigido.loc[:, destino] = df_base[origem_preco].astype(str).fillna("").values[: len(corrigido)]
    st.session_state["df_final"] = corrigido
    st.session_state["df_saida"] = corrigido.copy()
    st.session_state["_preco_unitario_corrigido_mapping"] = {"destino": destino, "origem": origem_preco, "linhas": int(len(corrigido))}


def render_origem_mapeamento() -> None:
    _garantir_etapa_mapeamento_ativa()
    st.subheader("3. Mapeamento com IA")

    df_base = _obter_df_base()
    df_modelo = _obter_df_modelo()
    operacao = _detectar_operacao()

    if not safe_df_dados(df_base):
        st.warning("Conclua a precificação antes de seguir para o mapeamento.")
        if st.button("⬅️ Voltar para precificação", use_container_width=True, key="btn_voltar_precificacao_mapping"):
            voltar_etapa_anterior()
        return

    if not safe_df_estrutura(df_modelo):
        st.warning("Carregue primeiro o modelo padrão antes de seguir para o mapeamento.")
        if st.button("⬅️ Voltar para origem", use_container_width=True, key="btn_voltar_origem_sem_modelo_mapping"):
            ir_para_etapa("origem")
        return

    _sincronizar_deposito_nome()
    _inicializar_mapping(df_base, df_modelo)
    _executar_ia_autonoma(df_base, df_modelo, operacao)
    _garantir_preco_unitario_no_final(df_base, df_modelo, operacao)

    _render_status_base(df_base, df_modelo)
    _render_sugestao_agente(df_base, df_modelo)
    _render_resumo_agente()

    correcao_preco = st.session_state.get("_preco_unitario_corrigido_mapping")
    if isinstance(correcao_preco, dict) and correcao_preco.get("destino"):
        st.success(f"Preço preservado automaticamente: {correcao_preco.get('origem')} ➜ {correcao_preco.get('destino')}")

    with st.expander("Revisão manual opcional", expanded=False):
        _render_revisao_manual(df_base, df_modelo, operacao)
        _garantir_preco_unitario_no_final(df_base, df_modelo, operacao)

    df_preview = st.session_state.get("df_final")
    if safe_df_estrutura(df_preview):
        _preview_mapping(df_preview)
        st.markdown("### Tratamento de GTIN")
        st.caption("Faça aqui a limpeza ou geração de GTIN antes de seguir para o preview final.")
        render_gtin_panel(df_preview)

    _render_botoes_fluxo(df_base, df_modelo)

    st.markdown("---")
    if st.button("⬅️ Voltar para precificação", use_container_width=True, key="btn_voltar_precificacao_no_rodape_mapping"):
        voltar_etapa_anterior()
