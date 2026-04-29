from __future__ import annotations

import re

import pandas as pd
import streamlit as st

from bling_app_zero.ui.app_helpers import (
    get_etapa,
    ir_para_etapa,
    safe_df_dados,
    sincronizar_etapa_global,
    voltar_etapa_anterior,
)


def _garantir_etapa_precificacao_ativa() -> None:
    if get_etapa() != "precificacao":
        sincronizar_etapa_global("precificacao")

    st.session_state["_etapa_url_inicializada"] = True
    st.session_state["_ultima_etapa_sincronizada_url"] = "precificacao"


def _to_float(valor) -> float:
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

    texto = re.sub(r"[^0-9\.\-]", "", texto)

    try:
        return float(texto)
    except Exception:
        return 0.0


def _fmt_brl(valor: float) -> str:
    try:
        return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "R$ 0,00"


def _fmt_numero_planilha(valor: float) -> str:
    try:
        return f"{float(valor):.2f}".replace(".", ",")
    except Exception:
        return "0,00"


def _calcular_preco_olist(
    custo: float,
    custo_fixo: float,
    frete_fixo: float,
    embalagem_fixa: float,
    despesa_fixa: float,
    taxa_extra: float,
    comissao_marketplace_percent: float,
    taxa_cartao_percent: float,
    impostos_percent: float,
    margem_percent: float,
    outros_percent: float,
) -> float:
    custo = _to_float(custo)
    custo_fixo = _to_float(custo_fixo)
    frete_fixo = _to_float(frete_fixo)
    embalagem_fixa = _to_float(embalagem_fixa)
    despesa_fixa = _to_float(despesa_fixa)
    taxa_extra = _to_float(taxa_extra)

    comissao_marketplace_percent = _to_float(comissao_marketplace_percent)
    taxa_cartao_percent = _to_float(taxa_cartao_percent)
    impostos_percent = _to_float(impostos_percent)
    margem_percent = _to_float(margem_percent)
    outros_percent = _to_float(outros_percent)

    custo_total = (
        custo
        + custo_fixo
        + frete_fixo
        + embalagem_fixa
        + despesa_fixa
        + taxa_extra
    )

    percentual_total = (
        comissao_marketplace_percent
        + taxa_cartao_percent
        + impostos_percent
        + margem_percent
        + outros_percent
    ) / 100.0

    divisor = 1.0 - percentual_total
    if divisor <= 0:
        return 0.0

    return round(custo_total / divisor, 2)


def _normalizar_texto(valor) -> str:
    return str(valor or "").strip().lower()


def _detectar_coluna_custo(df: pd.DataFrame) -> str:
    if not safe_df_dados(df):
        return ""

    candidatos = [
        "preco_custo",
        "preço_custo",
        "preco custo",
        "preço custo",
        "custo",
        "valor custo",
        "valor_custo",
        "preco_base",
        "preço base",
        "valor base",
        "preco",
        "preço",
        "valor",
        "preço de custo",
        "preco de custo",
    ]

    mapa = {_normalizar_texto(c): str(c) for c in df.columns}

    for candidato in candidatos:
        chave = _normalizar_texto(candidato)
        if chave in mapa:
            return mapa[chave]

    for col in df.columns:
        nome = _normalizar_texto(col)
        if "custo" in nome or "preco" in nome or "preço" in nome or "valor" in nome:
            return str(col)

    return ""


def _coluna_preco_destino() -> str:
    operacao = str(st.session_state.get("tipo_operacao") or "").strip().lower()
    if operacao == "estoque":
        return "Preço unitário (OBRIGATÓRIO)"
    return "Preço de venda"


def _inicializar_estado_precificacao(df_origem: pd.DataFrame) -> None:
    colunas = [str(c) for c in df_origem.columns.tolist()]
    sugestao_custo = _detectar_coluna_custo(df_origem)

    if st.session_state.get("pricing_coluna_custo", "") not in colunas:
        st.session_state["pricing_coluna_custo"] = sugestao_custo

    defaults = {
        "pricing_custo_fixo": 0.0,
        "pricing_frete_fixo": 0.0,
        "pricing_embalagem_fixa": 0.0,
        "pricing_despesa_fixa": 0.0,
        "pricing_taxa_extra": 0.0,
        "pricing_comissao_marketplace_percent": 0.0,
        "pricing_taxa_cartao_percent": 0.0,
        "pricing_impostos_percent": 0.0,
        "pricing_margem_percent": 0.0,
        "pricing_outros_percent": 0.0,
        "pricing_valor_teste": 0.0,
        "pricing_df_preview": st.session_state.get("pricing_df_preview"),
        "pricing_aplicada_ok": bool(st.session_state.get("pricing_aplicada_ok", False)),
        "pricing_pulada_ok": bool(st.session_state.get("pricing_pulada_ok", False)),
    }

    for chave, valor in defaults.items():
        if chave not in st.session_state:
            st.session_state[chave] = valor


def _limpar_preview_se_base_sumiu(df_origem: pd.DataFrame) -> None:
    if not safe_df_dados(df_origem):
        st.session_state["pricing_df_preview"] = None
        st.session_state["df_precificado"] = None
        st.session_state["pricing_aplicada_ok"] = False
        st.session_state["pricing_pulada_ok"] = False


def _aplicar_precificacao_dataframe(
    df: pd.DataFrame,
    coluna_custo: str,
    custo_fixo: float,
    frete_fixo: float,
    embalagem_fixa: float,
    despesa_fixa: float,
    taxa_extra: float,
    comissao_marketplace_percent: float,
    taxa_cartao_percent: float,
    impostos_percent: float,
    margem_percent: float,
    outros_percent: float,
) -> pd.DataFrame:
    if not safe_df_dados(df):
        return pd.DataFrame()

    if not coluna_custo or coluna_custo not in df.columns:
        return df.copy()

    base = df.copy()

    base["_preco_calculado_num"] = base[coluna_custo].apply(
        lambda x: _calcular_preco_olist(
            custo=x,
            custo_fixo=custo_fixo,
            frete_fixo=frete_fixo,
            embalagem_fixa=embalagem_fixa,
            despesa_fixa=despesa_fixa,
            taxa_extra=taxa_extra,
            comissao_marketplace_percent=comissao_marketplace_percent,
            taxa_cartao_percent=taxa_cartao_percent,
            impostos_percent=impostos_percent,
            margem_percent=margem_percent,
            outros_percent=outros_percent,
        )
    )

    base["_preco_calculado"] = base["_preco_calculado_num"].apply(_fmt_numero_planilha)

    destino = _coluna_preco_destino()
    base[destino] = base["_preco_calculado"]
    base["Preço calculado"] = base["_preco_calculado"]

    colunas_inicio = []
    for nome in [
        "Código",
        "codigo",
        "Código do produto",
        "Descrição",
        "descricao",
        "Descrição do produto",
        coluna_custo,
        "Preço calculado",
        destino,
    ]:
        if nome in base.columns and nome not in colunas_inicio:
            colunas_inicio.append(nome)

    restantes = [c for c in base.columns if c not in colunas_inicio]
    base = base[colunas_inicio + restantes]

    return base


def _usar_origem_sem_precificar(df_origem: pd.DataFrame) -> pd.DataFrame:
    if not safe_df_dados(df_origem):
        return pd.DataFrame()

    base = df_origem.copy().fillna("")
    st.session_state["df_precificado"] = base
    st.session_state["pricing_df_preview"] = base.copy()
    st.session_state["pricing_aplicada_ok"] = False
    st.session_state["pricing_pulada_ok"] = True
    return base


def _render_preview(df: pd.DataFrame, coluna_custo: str) -> None:
    if not safe_df_dados(df):
        return

    destino = _coluna_preco_destino()

    if bool(st.session_state.get("pricing_pulada_ok", False)) and not bool(
        st.session_state.get("pricing_aplicada_ok", False)
    ):
        st.markdown("### Preview da origem sem precificação")
        st.caption("A calculadora não foi aplicada. O mapeamento usará os dados originais carregados.")
    else:
        st.markdown("### Preview da planilha precificada")

    colunas_preview = []
    for nome in [
        "Código",
        "codigo",
        "Código do produto",
        "Descrição",
        "descricao",
        "Descrição do produto",
        coluna_custo,
        "Preço calculado",
        destino,
    ]:
        if nome in df.columns and nome not in colunas_preview:
            colunas_preview.append(nome)

    if not colunas_preview:
        colunas_preview = list(df.columns[:8])

    preview = df[colunas_preview].head(30).copy()
    st.dataframe(preview, use_container_width=True)

    with st.expander("Ver preview ampliado", expanded=False):
        st.dataframe(df.head(150), use_container_width=True)


def render_origem_precificacao() -> None:
    _garantir_etapa_precificacao_ativa()

    st.subheader("2. Precificação")

    df_origem = st.session_state.get("df_origem")
    _limpar_preview_se_base_sumiu(df_origem)

    if not safe_df_dados(df_origem):
        st.warning("A planilha de origem precisa estar carregada antes da precificação.")

        col1, col2 = st.columns(2)
        with col1:
            if st.button(
                "⬅️ Voltar para origem",
                use_container_width=True,
                key="btn_voltar_prec_sem_dados",
            ):
                st.session_state["_ultima_etapa_sincronizada_url"] = "origem"
                voltar_etapa_anterior()

        with col2:
            st.button(
                "Continuar ➜",
                use_container_width=True,
                disabled=True,
                key="btn_continuar_prec_sem_dados",
            )
        return

    _inicializar_estado_precificacao(df_origem)

    colunas = [str(c) for c in df_origem.columns.tolist()]
    destino = _coluna_preco_destino()

    st.info(
        "A precificação é opcional. Você pode aplicar a calculadora ou seguir direto "
        "para o mapeamento usando os dados originais."
    )

    with st.container(border=True):
        st.markdown("### Base de cálculo")

        opcoes_coluna = [""] + colunas
        valor_atual = st.session_state.get("pricing_coluna_custo", "")
        indice_coluna = opcoes_coluna.index(valor_atual) if valor_atual in opcoes_coluna else 0

        coluna_custo = st.selectbox(
            "Coluna de custo/base",
            options=opcoes_coluna,
            index=indice_coluna,
            key="pricing_coluna_custo",
        )

        st.caption(f"Se a calculadora for aplicada, o preço calculado será gravado em: {destino}")

    with st.container(border=True):
        st.markdown("### Despesas fixas por produto")

        c1, c2 = st.columns(2)
        c3, c4 = st.columns(2)
        c5, _ = st.columns(2)

        with c1:
            custo_fixo = st.number_input(
                "Custo fixo adicional (R$)",
                min_value=0.0,
                step=0.01,
                key="pricing_custo_fixo",
            )

        with c2:
            frete_fixo = st.number_input(
                "Frete / custo logístico (R$)",
                min_value=0.0,
                step=0.01,
                key="pricing_frete_fixo",
            )

        with c3:
            embalagem_fixa = st.number_input(
                "Embalagem (R$)",
                min_value=0.0,
                step=0.01,
                key="pricing_embalagem_fixa",
            )

        with c4:
            despesa_fixa = st.number_input(
                "Outras despesas fixas (R$)",
                min_value=0.0,
                step=0.01,
                key="pricing_despesa_fixa",
            )

        with c5:
            taxa_extra = st.number_input(
                "Taxa extra fixa (R$)",
                min_value=0.0,
                step=0.01,
                key="pricing_taxa_extra",
            )

    with st.container(border=True):
        st.markdown("### Percentuais sobre a venda")

        c1, c2 = st.columns(2)
        c3, c4 = st.columns(2)
        c5, _ = st.columns(2)

        with c1:
            comissao_marketplace_percent = st.number_input(
                "Comissão marketplace (%)",
                min_value=0.0,
                max_value=99.99,
                step=0.01,
                key="pricing_comissao_marketplace_percent",
            )

        with c2:
            taxa_cartao_percent = st.number_input(
                "Taxa cartão / financeira (%)",
                min_value=0.0,
                max_value=99.99,
                step=0.01,
                key="pricing_taxa_cartao_percent",
            )

        with c3:
            impostos_percent = st.number_input(
                "Impostos (%)",
                min_value=0.0,
                max_value=99.99,
                step=0.01,
                key="pricing_impostos_percent",
            )

        with c4:
            margem_percent = st.number_input(
                "Lucro desejado (%)",
                min_value=0.0,
                max_value=99.99,
                step=0.01,
                key="pricing_margem_percent",
            )

        with c5:
            outros_percent = st.number_input(
                "Outros percentuais (%)",
                min_value=0.0,
                max_value=99.99,
                step=0.01,
                key="pricing_outros_percent",
            )

    percentual_total = (
        _to_float(comissao_marketplace_percent)
        + _to_float(taxa_cartao_percent)
        + _to_float(impostos_percent)
        + _to_float(margem_percent)
        + _to_float(outros_percent)
    )

    if percentual_total >= 100:
        st.error("A soma dos percentuais precisa ser menor que 100%.")
    elif percentual_total >= 80:
        st.warning("A soma dos percentuais está alta. Confira se as taxas estão corretas.")

    with st.container(border=True):
        st.markdown("### Simulação")

        custo_teste = st.number_input(
            "Valor de teste (R$)",
            min_value=0.0,
            step=0.01,
            key="pricing_valor_teste",
        )

        resultado_teste = _calcular_preco_olist(
            custo=custo_teste,
            custo_fixo=custo_fixo,
            frete_fixo=frete_fixo,
            embalagem_fixa=embalagem_fixa,
            despesa_fixa=despesa_fixa,
            taxa_extra=taxa_extra,
            comissao_marketplace_percent=comissao_marketplace_percent,
            taxa_cartao_percent=taxa_cartao_percent,
            impostos_percent=impostos_percent,
            margem_percent=margem_percent,
            outros_percent=outros_percent,
        )

        st.success(f"Preço calculado: {_fmt_brl(resultado_teste)}")

    st.markdown("### Aplicar na planilha")

    if st.button(
        "Aplicar precificação",
        use_container_width=True,
        key="btn_aplicar_precificacao",
    ):
        if not coluna_custo:
            st.error("Selecione a coluna base de custo/preço para calcular.")
        elif percentual_total >= 100:
            st.error("Não é possível aplicar: a soma dos percentuais precisa ser menor que 100%.")
        else:
            df_precificado = _aplicar_precificacao_dataframe(
                df=df_origem,
                coluna_custo=coluna_custo,
                custo_fixo=custo_fixo,
                frete_fixo=frete_fixo,
                embalagem_fixa=embalagem_fixa,
                despesa_fixa=despesa_fixa,
                taxa_extra=taxa_extra,
                comissao_marketplace_percent=comissao_marketplace_percent,
                taxa_cartao_percent=taxa_cartao_percent,
                impostos_percent=impostos_percent,
                margem_percent=margem_percent,
                outros_percent=outros_percent,
            )

            st.session_state["df_precificado"] = df_precificado
            st.session_state["pricing_df_preview"] = df_precificado.copy()
            st.session_state["pricing_aplicada_ok"] = True
            st.session_state["pricing_pulada_ok"] = False
            st.success("Precificação aplicada com sucesso.")

    df_preview = st.session_state.get("pricing_df_preview")
    if safe_df_dados(df_preview):
        _render_preview(df_preview, coluna_custo)

    st.markdown("---")

    col1, col2 = st.columns(2)

    with col1:
        if st.button(
            "⬅️ Voltar para origem",
            use_container_width=True,
            key="btn_voltar_precificacao",
        ):
            st.session_state["_ultima_etapa_sincronizada_url"] = "origem"
            voltar_etapa_anterior()

    with col2:
        if st.button(
            "Continuar ➜",
            use_container_width=True,
            key="btn_continuar_precificacao",
        ):
            if not safe_df_dados(st.session_state.get("df_precificado")):
                df_sem_precificacao = _usar_origem_sem_precificar(df_origem)
                if not safe_df_dados(df_sem_precificacao):
                    st.error("Não foi possível preparar a origem para o mapeamento.")
                    return
                st.success("Seguindo sem aplicar precificação. A origem será usada no mapeamento.")

            st.session_state["_ultima_etapa_sincronizada_url"] = "mapeamento"
            ir_para_etapa("mapeamento")

