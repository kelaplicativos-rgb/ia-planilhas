from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.ui.origem_dados_handlers import (
    aplicar_bloco_estoque,
    aplicar_precificacao,
    nome_coluna_preco_saida,
)


def _safe_str(valor) -> str:
    try:
        if valor is None:
            return ""
        texto = str(valor).strip()
        if texto.lower() in {"none", "nan", "nat"}:
            return ""
        return texto
    except Exception:
        return ""


def _safe_df_dados(df) -> bool:
    try:
        return isinstance(df, pd.DataFrame) and not df.empty and len(df.columns) > 0
    except Exception:
        return False


def _safe_copy_df(df):
    try:
        return df.copy()
    except Exception:
        return df


def _float_state(key: str, default: float = 0.0) -> float:
    try:
        valor = st.session_state.get(key, default)
        if valor in (None, ""):
            return float(default)
        return float(valor)
    except Exception:
        return float(default)


def _bool_state(key: str, default: bool = False) -> bool:
    try:
        return bool(st.session_state.get(key, default))
    except Exception:
        return default


def _set_etapa(destino: str) -> None:
    st.session_state["etapa_origem"] = destino
    st.session_state["etapa"] = destino
    st.session_state["etapa_fluxo"] = destino


def _navegar(destino: str) -> None:
    _set_etapa(destino)
    st.rerun()


def _tipo_operacao_estoque() -> bool:
    return _safe_str(st.session_state.get("tipo_operacao_bling")).lower() == "estoque"


def _origem_atual() -> str:
    return _safe_str(
        st.session_state.get("origem_dados_tipo")
        or st.session_state.get("origem_dados_radio")
    ).lower()


def _render_css() -> None:
    st.markdown(
        """
        <style>
            .prec-kicker {
                font-size: 0.78rem;
                font-weight: 700;
                letter-spacing: 0.08em;
                text-transform: uppercase;
                color: #64748b;
                margin-bottom: 0.25rem;
            }

            .prec-title {
                font-size: 2rem;
                font-weight: 800;
                line-height: 1.08;
                color: #0f172a;
                margin-bottom: 0.4rem;
            }

            .prec-subtitle {
                font-size: 1rem;
                color: #475569;
                margin-bottom: 1rem;
            }

            .prec-card {
                border: 1px solid #e5e7eb;
                border-radius: 22px;
                padding: 1rem;
                background: #ffffff;
                margin-bottom: 0.95rem;
            }

            .prec-card-title {
                font-size: 1.15rem;
                font-weight: 800;
                color: #111827;
                margin-bottom: 0.2rem;
            }

            .prec-card-subtitle {
                font-size: 0.95rem;
                color: #6b7280;
                margin-bottom: 0.85rem;
            }

            .prec-summary {
                border: 1px solid #e2e8f0;
                background: #f8fafc;
                color: #334155;
                border-radius: 18px;
                padding: 0.9rem 1rem;
                font-size: 0.94rem;
                margin-top: 0.25rem;
            }

            .prec-badge {
                display: inline-block;
                padding: 0.22rem 0.55rem;
                border-radius: 999px;
                font-size: 0.78rem;
                font-weight: 700;
                background: #eef2ff;
                color: #3730a3;
                margin-bottom: 0.5rem;
            }

            @media (max-width: 640px) {
                .prec-title {
                    font-size: 1.72rem;
                }

                .prec-card {
                    border-radius: 18px;
                    padding: 0.9rem;
                }
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_header() -> None:
    st.markdown('<div class="prec-kicker">Etapa 2</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="prec-title">Como você quer tratar o preço?</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="prec-subtitle">Escolha se vai usar a calculadora automática ou manter o preço que já veio da base.</div>',
        unsafe_allow_html=True,
    )


def _colunas_origem_validas(df_origem: pd.DataFrame) -> list[str]:
    invalidas = {"signature", "infnfe", "infprot", "versao"}

    colunas: list[str] = []
    for coluna in df_origem.columns:
        nome = _safe_str(coluna)
        if not nome:
            continue
        if nome.strip().lower() in invalidas:
            continue
        colunas.append(nome)

    return colunas


def _persistir_resultado(df_resultado: pd.DataFrame) -> None:
    st.session_state["df_precificado"] = _safe_copy_df(df_resultado)
    st.session_state["df_calc_precificado"] = _safe_copy_df(df_resultado)
    st.session_state["df_saida"] = _safe_copy_df(df_resultado)
    st.session_state["df_final"] = _safe_copy_df(df_resultado)


def _aplicar_precificacao_fluxo(df_origem: pd.DataFrame) -> pd.DataFrame | None:
    usar = _bool_state("usar_calculadora_precificacao", False)
    coluna_base = _safe_str(st.session_state.get("coluna_precificacao_resultado"))

    margem = _float_state("margem_bling", 0.0)
    impostos = _float_state("impostos_bling", 0.0)
    frete_estimado = _float_state("custofixo_bling", 0.0)
    custo_extra = _float_state("taxaextra_bling", 0.0)
    comissao_canal = _float_state("comissao_canal_percentual", 16.0)

    st.session_state["usar_calculadora_precificacao"] = usar
    st.session_state["comissao_canal_percentual"] = comissao_canal

    df_resultado = aplicar_precificacao(
        df_origem=df_origem,
        coluna_custo=coluna_base,
        margem=margem,
        impostos=impostos,
        custo_fixo=frete_estimado,
        taxa_extra=custo_extra,
    )

    if _safe_df_dados(df_resultado) and _tipo_operacao_estoque():
        df_resultado = aplicar_bloco_estoque(df_resultado, _origem_atual())

    if _safe_df_dados(df_resultado):
        _persistir_resultado(df_resultado)
        return df_resultado

    return None


def _render_resumo(df_origem: pd.DataFrame) -> None:
    coluna_saida = nome_coluna_preco_saida()
    operacao = _safe_str(
        st.session_state.get("tipo_operacao")
        or st.session_state.get("tipo_operacao_bling")
        or st.session_state.get("tipo_operacao_radio")
    )
    origem = _safe_str(
        st.session_state.get("origem_dados_tipo")
        or st.session_state.get("origem_dados_radio")
    )

    st.markdown(
        (
            '<div class="prec-summary">'
            f"<strong>Operação:</strong> {operacao or 'Não definida'}"
            f" &nbsp;&nbsp;|&nbsp;&nbsp; "
            f"<strong>Origem:</strong> {origem or 'Não definida'}"
            f" &nbsp;&nbsp;|&nbsp;&nbsp; "
            f"<strong>Linhas carregadas:</strong> {len(df_origem)}"
            f" &nbsp;&nbsp;|&nbsp;&nbsp; "
            f"<strong>Coluna final:</strong> {coluna_saida}"
            "</div>"
        ),
        unsafe_allow_html=True,
    )


def _render_escolha_principal() -> None:
    usar = _bool_state("usar_calculadora_precificacao", False)

    st.markdown('<div class="prec-card">', unsafe_allow_html=True)
    st.markdown(
        '<div class="prec-card-title">Você vai usar a calculadora?</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="prec-card-subtitle">Isso define se o sistema calcula automaticamente o preço final ou apenas mantém o valor original da base.</div>',
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns(2, gap="small")

    with col1:
        if st.button(
            "✅ Sim, calcular automaticamente",
            use_container_width=True,
            type="primary" if usar else "secondary",
            key="btn_precificacao_sim",
        ):
            st.session_state["usar_calculadora_precificacao"] = True
            st.rerun()

    with col2:
        if st.button(
            "➡️ Não, manter preço da planilha",
            use_container_width=True,
            type="primary" if not usar else "secondary",
            key="btn_precificacao_nao",
        ):
            st.session_state["usar_calculadora_precificacao"] = False
            st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)


def _render_bloco_sem_calculadora(df_origem: pd.DataFrame) -> None:
    st.markdown('<div class="prec-card">', unsafe_allow_html=True)
    st.markdown(
        '<div class="prec-card-title">Preço mantido da base</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="prec-card-subtitle">O sistema vai preservar o preço vindo da planilha fornecedora e preencher automaticamente a coluna final do modelo.</div>',
        unsafe_allow_html=True,
    )

    df_resultado = _aplicar_precificacao_fluxo(df_origem)
    coluna_saida = nome_coluna_preco_saida()

    if _safe_df_dados(df_resultado):
        st.success(
            f"O preço da base será mantido e gravado automaticamente em: {coluna_saida}"
        )
    else:
        st.warning(
            "Não foi possível preparar a base para a próxima etapa. Revise a origem dos dados."
        )

    with st.expander("Preview após preparação", expanded=False):
        df_preview = st.session_state.get("df_precificado")
        if _safe_df_dados(df_preview):
            st.dataframe(
                df_preview.head(20),
                use_container_width=True,
                hide_index=True,
            )

    st.markdown("</div>", unsafe_allow_html=True)


def _render_bloco_calculadora(df_origem: pd.DataFrame) -> None:
    opcoes = [""] + _colunas_origem_validas(df_origem)
    coluna_atual = _safe_str(st.session_state.get("coluna_precificacao_resultado"))

    if coluna_atual and coluna_atual not in opcoes:
        st.session_state["coluna_precificacao_resultado"] = ""

    st.markdown('<div class="prec-card">', unsafe_allow_html=True)
    st.markdown(
        '<div class="prec-card-title">Configurar cálculo automático</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="prec-card-subtitle">Selecione a coluna base de custo/preço e informe os percentuais e valores fixos para gerar o preço final.</div>',
        unsafe_allow_html=True,
    )

    st.markdown('<div class="prec-badge">Calculadora ativa</div>', unsafe_allow_html=True)

    st.selectbox(
        "Qual coluna de origem deve ser usada como base do preço?",
        opcoes,
        key="coluna_precificacao_resultado",
    )

    col1, col2 = st.columns(2, gap="small")

    with col1:
        st.number_input(
            "Margem desejada (%)",
            min_value=0.0,
            value=_float_state("margem_bling", 0.0),
            step=1.0,
            key="margem_bling",
        )
        st.number_input(
            "Imposto NF-e (%)",
            min_value=0.0,
            value=_float_state("impostos_bling", 0.0),
            step=1.0,
            key="impostos_bling",
        )
        st.number_input(
            "Comissão do canal (%)",
            min_value=0.0,
            value=_float_state("comissao_canal_percentual", 16.0),
            step=1.0,
            key="comissao_canal_percentual",
        )

    with col2:
        st.number_input(
            "Frete estimado (R$)",
            min_value=0.0,
            value=_float_state("custofixo_bling", 0.0),
            step=1.0,
            key="custofixo_bling",
        )
        st.number_input(
            "Custo extra fixo (R$)",
            min_value=0.0,
            value=_float_state("taxaextra_bling", 0.0),
            step=1.0,
            key="taxaextra_bling",
        )

    coluna_base = _safe_str(st.session_state.get("coluna_precificacao_resultado"))
    if not coluna_base:
        st.info("Selecione a coluna base para liberar a precificação automática.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    df_resultado = _aplicar_precificacao_fluxo(df_origem)
    coluna_saida = nome_coluna_preco_saida()

    if _safe_df_dados(df_resultado):
        st.success(
            f"O resultado da calculadora será gravado automaticamente em: {coluna_saida}"
        )
    else:
        st.warning(
            "Não foi possível gerar a precificação automática. Revise a coluna base e os dados da origem."
        )

    with st.expander("Preview após precificação", expanded=False):
        df_preview = st.session_state.get("df_precificado")
        if _safe_df_dados(df_preview):
            st.dataframe(
                df_preview.head(20),
                use_container_width=True,
                hide_index=True,
            )

    st.markdown("</div>", unsafe_allow_html=True)


def _render_navegacao(disabled_continue: bool = False) -> None:
    col1, col2 = st.columns(2, gap="small")

    with col1:
        if st.button(
            "⬅️ Voltar",
            use_container_width=True,
            key="precificacao_btn_voltar",
        ):
            _navegar("origem")

    with col2:
        if st.button(
            "Continuar ➜",
            use_container_width=True,
            type="primary",
            disabled=disabled_continue,
            key="precificacao_btn_continuar",
        ):
            _navegar("mapeamento")


def render_origem_precificacao() -> None:
    _render_css()

    df_origem = st.session_state.get("df_origem")
    if not _safe_df_dados(df_origem):
        st.warning("Carregue a base de origem antes de usar a etapa de precificação.")
        _render_navegacao(disabled_continue=True)
        return

    _render_header()
    _render_resumo(df_origem)
    _render_escolha_principal()

    usar_calculadora = _bool_state("usar_calculadora_precificacao", False)

    if usar_calculadora:
        _render_bloco_calculadora(df_origem)
        coluna_base = _safe_str(st.session_state.get("coluna_precificacao_resultado"))
        continuar_bloqueado = not bool(coluna_base and _safe_df_dados(st.session_state.get("df_precificado")))
        _render_navegacao(disabled_continue=continuar_bloqueado)
        return

    _render_bloco_sem_calculadora(df_origem)
    continuar_bloqueado = not _safe_df_dados(st.session_state.get("df_precificado"))
    _render_navegacao(disabled_continue=continuar_bloqueado)
