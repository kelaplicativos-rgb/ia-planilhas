from __future__ import annotations

import re
from typing import Any

import pandas as pd
import streamlit as st

from bling_app_zero.ui.app_core_flow import set_etapa_segura
from bling_app_zero.ui.app_helpers import safe_df_dados, safe_df_estrutura


CANDIDATOS_PRECO_CADASTRO = [
    "Preço de venda",
    "Preco de venda",
    "Preço unitário (OBRIGATÓRIO)",
    "Preço unitário",
    "Preco unitario",
    "Preço",
    "Preco",
    "Valor",
]

CANDIDATOS_CODIGO = [
    "Código",
    "Codigo",
    "Código produto *",
    "Codigo produto *",
    "Código do produto",
    "Codigo do produto",
    "SKU",
    "sku",
]

CANDIDATOS_DESCRICAO = [
    "Descrição",
    "Descricao",
    "Descrição Produto",
    "Descricao Produto",
    "Nome",
    "Produto",
]


def _norm(valor: Any) -> str:
    texto = str(valor or "").strip().lower()
    texto = texto.translate(str.maketrans("áàãâéêíóôõúç", "aaaaeeiooouc"))
    return re.sub(r"[^a-z0-9]+", " ", texto).strip()


def _to_float(valor: Any) -> float:
    if valor is None:
        return 0.0
    texto = str(valor).strip()
    if not texto:
        return 0.0
    texto = texto.replace("R$", "").replace("r$", "").replace(" ", "")
    if "," in texto and "." in texto:
        texto = texto.replace(".", "").replace(",", ".")
    else:
        texto = texto.replace(",", ".")
    texto = re.sub(r"[^0-9.\-]", "", texto)
    try:
        return float(texto)
    except Exception:
        return 0.0


def _fmt_brl(valor: float) -> str:
    try:
        return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "R$ 0,00"


def _fmt_planilha(valor: float) -> str:
    try:
        return f"{float(valor):.2f}".replace(".", ",")
    except Exception:
        return "0,00"


def _calcular_preco(
    custo: Any,
    custo_fixo: float,
    frete_fixo: float,
    embalagem_fixa: float,
    despesa_fixa: float,
    taxa_extra: float,
    comissao_percent: float,
    cartao_percent: float,
    impostos_percent: float,
    lucro_percent: float,
    outros_percent: float,
) -> float:
    custo_total = (
        _to_float(custo)
        + _to_float(custo_fixo)
        + _to_float(frete_fixo)
        + _to_float(embalagem_fixa)
        + _to_float(despesa_fixa)
        + _to_float(taxa_extra)
    )
    percentual_total = (
        _to_float(comissao_percent)
        + _to_float(cartao_percent)
        + _to_float(impostos_percent)
        + _to_float(lucro_percent)
        + _to_float(outros_percent)
    ) / 100.0
    divisor = 1.0 - percentual_total
    if divisor <= 0:
        return 0.0
    return round(custo_total / divisor, 2)


def _obter_base_precificacao() -> pd.DataFrame:
    for chave in ("df_precificado", "df_preview_inteligente", "df_saida", "df_origem"):
        df = st.session_state.get(chave)
        if safe_df_dados(df):
            return df.copy().fillna("").reset_index(drop=True)
    return pd.DataFrame()


def _achar_coluna(df: pd.DataFrame, candidatos: list[str]) -> str:
    if not safe_df_estrutura(df):
        return ""
    mapa = {_norm(c): str(c) for c in df.columns}
    for candidato in candidatos:
        achado = mapa.get(_norm(candidato))
        if achado:
            return achado
    return ""


def _detectar_coluna_custo(df: pd.DataFrame) -> str:
    candidatos = [
        "Preço de custo",
        "Preco de custo",
        "Preço custo",
        "Preco custo",
        "Custo",
        "Valor custo",
        "Preço unitário (OBRIGATÓRIO)",
        "Preço unitário",
        "Preço de venda",
        "Preço",
        "Preco",
        "Valor",
    ]
    achado = _achar_coluna(df, candidatos)
    if achado:
        return achado
    for col in df.columns:
        nome = _norm(col)
        if any(token in nome for token in ["custo", "preco", "valor", "price"]):
            return str(col)
    return ""


def _coluna_preco_destino(df: pd.DataFrame) -> str:
    operacao = str(st.session_state.get("tipo_operacao", "cadastro") or "cadastro").strip().lower()
    if operacao == "estoque":
        achado = _achar_coluna(df, ["Preço unitário (OBRIGATÓRIO)", "Preço unitário", "Preco unitario", "Preço", "Preco"])
        return achado or "Preço unitário (OBRIGATÓRIO)"
    achado = _achar_coluna(df, CANDIDATOS_PRECO_CADASTRO)
    return achado or "Preço de venda"


def _aplicar_precificacao(df: pd.DataFrame, coluna_custo: str, valores: dict[str, float]) -> pd.DataFrame:
    if not safe_df_dados(df):
        return pd.DataFrame()
    base = df.copy().fillna("")
    if not coluna_custo or coluna_custo not in base.columns:
        return base

    destino = _coluna_preco_destino(base)
    calculado = base[coluna_custo].apply(
        lambda custo: _calcular_preco(
            custo=custo,
            custo_fixo=valores["custo_fixo"],
            frete_fixo=valores["frete_fixo"],
            embalagem_fixa=valores["embalagem_fixa"],
            despesa_fixa=valores["despesa_fixa"],
            taxa_extra=valores["taxa_extra"],
            comissao_percent=valores["comissao_percent"],
            cartao_percent=valores["cartao_percent"],
            impostos_percent=valores["impostos_percent"],
            lucro_percent=valores["lucro_percent"],
            outros_percent=valores["outros_percent"],
        )
    )
    base[destino] = calculado.apply(_fmt_planilha)
    base["Preço calculado"] = calculado.apply(_fmt_planilha)
    return base.fillna("")


def _preparar_para_mapeamento(df: pd.DataFrame) -> None:
    base = df.copy().fillna("").reset_index(drop=True)
    st.session_state["df_precificado"] = base.copy()
    st.session_state["df_saida"] = base.copy()
    st.session_state.pop("df_final", None)
    st.session_state["pricing_fluxo_pronto"] = True


def _avancar_para_mapeamento(df: pd.DataFrame) -> None:
    if not safe_df_dados(df):
        st.error("Não foi possível preparar a planilha para o mapeamento.")
        return
    _preparar_para_mapeamento(df)
    if set_etapa_segura("mapeamento", origem="precificacao_continuar"):
        st.rerun()
    st.error("Não foi possível avançar para o mapeamento. Confira se o modelo Bling está carregado.")


def _voltar_para_origem() -> None:
    if set_etapa_segura("origem", origem="precificacao_voltar"):
        st.rerun()
    st.session_state["wizard_etapa_atual"] = "origem"
    st.session_state["etapa"] = "origem"
    st.rerun()


def _render_preview(df: pd.DataFrame, coluna_custo: str) -> None:
    if not safe_df_dados(df):
        return
    destino = _coluna_preco_destino(df)
    colunas_preview: list[str] = []
    for nome in [
        _achar_coluna(df, CANDIDATOS_CODIGO),
        _achar_coluna(df, CANDIDATOS_DESCRICAO),
        coluna_custo,
        "Preço calculado",
        destino,
    ]:
        if nome and nome in df.columns and nome not in colunas_preview:
            colunas_preview.append(nome)
    if not colunas_preview:
        colunas_preview = list(df.columns[:8])
    st.dataframe(df[colunas_preview].head(30), use_container_width=True)
    with st.expander("Ver preview ampliado", expanded=False):
        st.dataframe(df.head(150), use_container_width=True)


def render_origem_precificacao() -> None:
    st.subheader("2. Precificação")

    df_base = _obter_base_precificacao()
    if not safe_df_dados(df_base):
        st.warning("A planilha de origem precisa estar carregada antes da precificação.")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("⬅️ Voltar para origem", use_container_width=True, key="btn_voltar_prec_sem_dados"):
                _voltar_para_origem()
        with col2:
            st.button("Continuar ➜", use_container_width=True, disabled=True, key="btn_continuar_prec_sem_dados")
        return

    st.info(
        "A precificação é opcional. Deixe a coluna de custo/base em branco para seguir direto sem recalcular preços."
    )

    colunas = [str(c) for c in df_base.columns]
    if "pricing_coluna_custo" not in st.session_state or st.session_state.get("pricing_coluna_custo") not in [""] + colunas:
        st.session_state["pricing_coluna_custo"] = ""

    with st.container(border=True):
        st.markdown("### Base de cálculo")
        opcoes = [""] + colunas
        atual = st.session_state.get("pricing_coluna_custo", "")
        coluna_custo = st.selectbox(
            "Coluna de custo/base",
            options=opcoes,
            index=opcoes.index(atual) if atual in opcoes else 0,
            key="pricing_coluna_custo",
            format_func=lambda valor: "Não aplicar calculadora agora" if str(valor).strip() == "" else str(valor),
        )
        if coluna_custo:
            st.caption(f"Se aplicar a calculadora, o preço será gravado em: {_coluna_preco_destino(df_base)}")
        else:
            st.caption("Sem coluna base selecionada: o sistema seguirá usando o preço já capturado/mapeado na próxima etapa.")

    with st.container(border=True):
        st.markdown("### Despesas fixas por produto")
        c1, c2 = st.columns(2)
        c3, c4 = st.columns(2)
        c5, _ = st.columns(2)
        with c1:
            custo_fixo = st.number_input("Custo fixo adicional (R$)", min_value=0.0, step=0.01, key="pricing_custo_fixo")
        with c2:
            frete_fixo = st.number_input("Frete / custo logístico (R$)", min_value=0.0, step=0.01, key="pricing_frete_fixo")
        with c3:
            embalagem_fixa = st.number_input("Embalagem (R$)", min_value=0.0, step=0.01, key="pricing_embalagem_fixa")
        with c4:
            despesa_fixa = st.number_input("Outras despesas fixas (R$)", min_value=0.0, step=0.01, key="pricing_despesa_fixa")
        with c5:
            taxa_extra = st.number_input("Taxa extra fixa (R$)", min_value=0.0, step=0.01, key="pricing_taxa_extra")

    with st.container(border=True):
        st.markdown("### Percentuais sobre a venda")
        c1, c2 = st.columns(2)
        c3, c4 = st.columns(2)
        c5, _ = st.columns(2)
        with c1:
            comissao_percent = st.number_input("Comissão marketplace (%)", min_value=0.0, max_value=99.99, step=0.01, key="pricing_comissao_marketplace_percent")
        with c2:
            cartao_percent = st.number_input("Taxa cartão / financeira (%)", min_value=0.0, max_value=99.99, step=0.01, key="pricing_taxa_cartao_percent")
        with c3:
            impostos_percent = st.number_input("Impostos (%)", min_value=0.0, max_value=99.99, step=0.01, key="pricing_impostos_percent")
        with c4:
            lucro_percent = st.number_input("Lucro desejado (%)", min_value=0.0, max_value=99.99, step=0.01, key="pricing_margem_percent")
        with c5:
            outros_percent = st.number_input("Outros percentuais (%)", min_value=0.0, max_value=99.99, step=0.01, key="pricing_outros_percent")

    valores = {
        "custo_fixo": custo_fixo,
        "frete_fixo": frete_fixo,
        "embalagem_fixa": embalagem_fixa,
        "despesa_fixa": despesa_fixa,
        "taxa_extra": taxa_extra,
        "comissao_percent": comissao_percent,
        "cartao_percent": cartao_percent,
        "impostos_percent": impostos_percent,
        "lucro_percent": lucro_percent,
        "outros_percent": outros_percent,
    }
    percentual_total = sum(_to_float(valores[k]) for k in ["comissao_percent", "cartao_percent", "impostos_percent", "lucro_percent", "outros_percent"])

    if percentual_total >= 100:
        st.error("A soma dos percentuais precisa ser menor que 100%.")
    elif percentual_total >= 80:
        st.warning("A soma dos percentuais está alta. Confira se as taxas estão corretas.")

    with st.container(border=True):
        st.markdown("### Simulação")
        valor_teste = st.number_input("Valor de teste (R$)", min_value=0.0, step=0.01, key="pricing_valor_teste")
        simulado = _calcular_preco(valor_teste, **valores)
        st.success(f"Preço calculado: {_fmt_brl(simulado)}")

    st.markdown("### Aplicar na planilha")
    if st.button("Aplicar precificação", use_container_width=True, key="btn_aplicar_precificacao"):
        if percentual_total >= 100:
            st.error("Não é possível aplicar: a soma dos percentuais precisa ser menor que 100%.")
        elif not coluna_custo:
            df_sem_calculo = df_base.copy().fillna("")
            _preparar_para_mapeamento(df_sem_calculo)
            st.session_state["pricing_df_preview"] = df_sem_calculo.copy()
            st.session_state["pricing_aplicada_ok"] = False
            st.session_state["pricing_pulada_ok"] = True
            st.info("Calculadora não aplicada. O fluxo seguirá com o preço já existente para o mapeamento final.")
        else:
            df_aplicado = _aplicar_precificacao(df_base, coluna_custo, valores)
            _preparar_para_mapeamento(df_aplicado)
            st.session_state["pricing_df_preview"] = df_aplicado.copy()
            st.session_state["pricing_aplicada_ok"] = True
            st.session_state["pricing_pulada_ok"] = False
            st.success("Precificação aplicada com sucesso.")

    df_preview = st.session_state.get("pricing_df_preview")
    if not safe_df_dados(df_preview):
        df_preview = df_base.copy()

    if safe_df_dados(df_preview):
        titulo = "### Preview da planilha precificada" if st.session_state.get("pricing_aplicada_ok") else "### Preview da planilha atual"
        st.markdown(titulo)
        _render_preview(df_preview, coluna_custo)

    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("⬅️ Voltar para origem", use_container_width=True, key="btn_voltar_precificacao"):
            _voltar_para_origem()
    with col2:
        if st.button("Continuar ➜", use_container_width=True, key="btn_continuar_precificacao"):
            df_final_prec = st.session_state.get("pricing_df_preview")
            if not safe_df_dados(df_final_prec):
                df_final_prec = df_base.copy()
            st.session_state["pricing_pulada_ok"] = not bool(coluna_custo and st.session_state.get("pricing_aplicada_ok"))
            st.session_state["pricing_aplicada_ok"] = bool(coluna_custo and st.session_state.get("pricing_aplicada_ok"))
            _avancar_para_mapeamento(df_final_prec)
