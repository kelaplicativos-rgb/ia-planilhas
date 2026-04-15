

from __future__ import annotations

from collections.abc import Callable

import pandas as pd
import streamlit as st

from bling_app_zero.ui.origem_mapeamento_core import (
    montar_df_saida_mapeado,
    obter_df_fonte_mapeamento,
    obter_df_modelo_mapeamento,
)
from bling_app_zero.ui.origem_mapeamento_ui import (
    render_formulario_mapeamento,
)
from bling_app_zero.ui.origem_mapeamento_validacao import (
    detectar_duplicidades_mapping,
)

NavCallback = Callable[[], None] | None

ETAPAS_VALIDAS_ORIGEM = {"origem", "mapeamento", "final"}


# =========================================================
# HELPERS BASE
# =========================================================
def _safe_dict(valor) -> dict:
    try:
        return dict(valor or {})
    except Exception:
        return {}


def _safe_copy_df(df):
    try:
        return df.copy()
    except Exception:
        return df


def _tem_estrutura_df(df) -> bool:
    try:
        return df is not None and hasattr(df, "columns") and len(df.columns) > 0
    except Exception:
        return False


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


def _normalizar_etapa(valor, default: str = "origem") -> str:
    etapa = _safe_str(valor or default).lower()
    if etapa not in ETAPAS_VALIDAS_ORIGEM:
        return default
    return etapa


def get_etapa_mapeamento() -> str:
    for chave in ("etapa_origem", "etapa", "etapa_fluxo"):
        etapa = _normalizar_etapa(st.session_state.get(chave), "")
        if etapa:
            return etapa
    return "origem"


def set_etapa_mapeamento(etapa: str) -> None:
    etapa_normalizada = _normalizar_etapa(etapa, "origem")
    st.session_state["etapa_origem"] = etapa_normalizada
    st.session_state["etapa"] = etapa_normalizada
    st.session_state["etapa_fluxo"] = etapa_normalizada


def garantir_estado_mapeamento() -> None:
    defaults = {
        "mapping_origem": {},
        "mapping_origem_rascunho": {},
        "mapeamento_retorno_preservado": False,
        "deposito_nome": "",
        "df_preview_mapeamento": None,
    }
    for chave, valor in defaults.items():
        if chave not in st.session_state:
            st.session_state[chave] = valor

    st.session_state["mapping_origem"] = _safe_dict(
        st.session_state.get("mapping_origem")
    )
    st.session_state["mapping_origem_rascunho"] = _safe_dict(
        st.session_state.get("mapping_origem_rascunho")
    )


def _persistir_df_saida(df_saida) -> None:
    if not _tem_estrutura_df(df_saida):
        return
    st.session_state["df_saida"] = _safe_copy_df(df_saida)
    st.session_state["df_final"] = _safe_copy_df(df_saida)
    st.session_state["df_preview_mapeamento"] = _safe_copy_df(df_saida)


def _persistir_mapping(mapping: dict) -> None:
    st.session_state["mapping_origem"] = _safe_dict(mapping)
    st.session_state["mapping_origem_rascunho"] = _safe_dict(mapping)


def _restaurar_mapping_inicial() -> dict:
    mapping_salvo = _safe_dict(st.session_state.get("mapping_origem"))
    if mapping_salvo:
        return mapping_salvo

    mapping_rascunho = _safe_dict(st.session_state.get("mapping_origem_rascunho"))
    if mapping_rascunho:
        return mapping_rascunho

    return {}


def _navegar(destino: str, callback: NavCallback = None) -> None:
    if callable(callback):
        callback()
        return

    set_etapa_mapeamento(destino)
    st.rerun()


def _voltar_preservando_estado(on_back: NavCallback = None) -> None:
    mapping_atual = _safe_dict(st.session_state.get("mapping_origem_rascunho"))
    if mapping_atual:
        st.session_state["mapping_origem"] = mapping_atual

    df_preview = st.session_state.get("df_preview_mapeamento")
    if _tem_estrutura_df(df_preview):
        st.session_state["df_saida"] = _safe_copy_df(df_preview)
        st.session_state["df_final"] = _safe_copy_df(df_preview)

    st.session_state["mapeamento_retorno_preservado"] = True
    _navegar("origem", on_back)


def _continuar_para_final(
    on_continue: NavCallback = None,
    *,
    erro: bool,
    df_saida=None,
) -> None:
    if erro:
        st.warning("Corrija os campos duplicados antes de continuar.")
        return

    if not _tem_estrutura_df(df_saida):
        st.warning("Nenhum preview válido foi gerado para continuar.")
        return

    _persistir_df_saida(df_saida)
    st.session_state["mapeamento_retorno_preservado"] = True
    _navegar("final", on_continue)


# =========================================================
# HELPERS VISUAIS LIMPOS
# =========================================================
def _render_resumo_operacional(df_fonte: pd.DataFrame, df_modelo: pd.DataFrame) -> None:
    operacao = _safe_str(
        st.session_state.get("tipo_operacao")
        or st.session_state.get("tipo_operacao_bling")
        or st.session_state.get("tipo_operacao_radio")
    )
    origem = _safe_str(
        st.session_state.get("origem_dados_tipo")
        or st.session_state.get("origem_dados_radio")
    )

    linhas = 0
    colunas_origem = 0
    colunas_modelo = 0

    if _tem_estrutura_df(df_fonte):
        try:
            linhas = int(len(df_fonte))
            colunas_origem = int(len(df_fonte.columns))
        except Exception:
            pass

    if _tem_estrutura_df(df_modelo):
        try:
            colunas_modelo = int(len(df_modelo.columns))
        except Exception:
            pass

    c1, c2, c3 = st.columns(3, gap="small")

    with c1:
        st.caption("Operação")
        st.markdown(f"**{operacao or 'Não definida'}**")

    with c2:
        st.caption("Origem")
        st.markdown(f"**{origem or 'Não definida'}**")

    with c3:
        st.caption("Base")
        st.markdown(
            f"**{linhas} linha(s) · {colunas_origem} origem · {colunas_modelo} modelo**"
        )


def _render_cabecalho_bloco(titulo: str, descricao: str = "") -> None:
    st.markdown(f"#### {titulo}")
    if descricao:
        st.caption(descricao)


def _render_configuracao_mapeamento() -> None:
    deposito_atual = _safe_str(st.session_state.get("deposito_nome"))

    st.text_input(
        "Nome do Depósito (Bling)",
        value=deposito_atual,
        key="deposito_nome",
        placeholder="Ex: principal, ifood, loja 1",
        help="Esse valor pode ser usado no fluxo de estoque quando a coluna de depósito existir no modelo.",
    )


def _render_preview_curto(df_fonte: pd.DataFrame, df_modelo: pd.DataFrame) -> None:
    col1, col2 = st.columns(2, gap="small")

    with col1:
        with st.expander("Colunas da origem", expanded=False):
            st.write(list(df_fonte.columns))

    with col2:
        with st.expander("Colunas do modelo", expanded=False):
            st.write(list(df_modelo.columns))


def _render_alertas_duplicidade(duplicidades: dict[str, list[str]]) -> None:
    if not duplicidades:
        st.success("✅ Nenhuma duplicidade detectada no mapeamento atual.")
        return

    mensagens = []
    for coluna_origem, colunas_modelo in duplicidades.items():
        mensagens.append(
            f"'{coluna_origem}' usada em: {', '.join([str(c) for c in colunas_modelo])}"
        )

    st.error("❌ Existe coluna de origem sendo usada mais de uma vez.")
    for msg in mensagens:
        st.write(f"- {msg}")


def _render_preview_mapeamento_visual(
    df_saida: pd.DataFrame,
    duplicidades: dict[str, list[str]],
) -> None:
    _render_alertas_duplicidade(duplicidades)

    with st.expander("Visualizar preview mapeado", expanded=True):
        st.dataframe(df_saida.head(15), use_container_width=True)


def _render_footer_nav(
    *,
    erro: bool,
    on_back: NavCallback = None,
    on_continue: NavCallback = None,
    df_saida=None,
) -> None:
    col1, col2 = st.columns(2, gap="small")

    with col1:
        if st.button(
            "⬅️ Voltar para origem",
            use_container_width=True,
            key="mapeamento_btn_voltar_footer",
        ):
            _voltar_preservando_estado(on_back)

    with col2:
        if st.button(
            "➡️ Continuar para preview final",
            use_container_width=True,
            type="primary",
            disabled=erro,
            key="mapeamento_btn_continuar_footer",
        ):
            _continuar_para_final(
                on_continue,
                erro=erro,
                df_saida=df_saida,
            )

    if erro:
        st.caption("Remova as duplicidades para liberar a próxima etapa.")


# =========================================================
# RENDER PRINCIPAL
# =========================================================
def render_origem_mapeamento(
    on_back: NavCallback = None,
    on_continue: NavCallback = None,
) -> None:
    garantir_estado_mapeamento()

    if get_etapa_mapeamento() != "mapeamento":
        return

    df_fonte = obter_df_fonte_mapeamento()
    df_modelo = obter_df_modelo_mapeamento()

    if not _tem_estrutura_df(df_fonte) or not _tem_estrutura_df(df_modelo):
        st.warning("Dados inválidos para o mapeamento.")

        col1, col2 = st.columns(2, gap="small")
        with col1:
            if st.button(
                "⬅️ Voltar para origem",
                use_container_width=True,
                key="mapeamento_btn_voltar_erro",
            ):
                _voltar_preservando_estado(on_back)

        with col2:
            st.button(
                "➡️ Continuar para preview final",
                use_container_width=True,
                disabled=True,
                key="mapeamento_btn_continuar_erro",
            )
        return

    _render_resumo_operacional(df_fonte, df_modelo)

    st.divider()

    _render_cabecalho_bloco(
        "Como usar esta etapa",
        "Mapeie cada coluna do modelo para uma coluna da origem. O campo ID permanece bloqueado e o preview abaixo mostra como a saída final ficará.",
    )

    st.divider()

    _render_cabecalho_bloco(
        "Configuração do mapeamento",
        "Revise o depósito padrão e use a referência rápida para mapear com mais segurança.",
    )
    _render_configuracao_mapeamento()
    _render_preview_curto(df_fonte, df_modelo)

    st.divider()

    _render_cabecalho_bloco(
        "Formulário de mapeamento",
        "Relacione as colunas da origem com o modelo final.",
    )

    mapping_inicial = _restaurar_mapping_inicial()
    mapping_atualizado = render_formulario_mapeamento(
        df_fonte,
        df_modelo,
        mapping_inicial,
    )
    mapping_atualizado = _safe_dict(mapping_atualizado)

    st.session_state["mapping_origem_rascunho"] = _safe_dict(mapping_atualizado)

    duplicidades = detectar_duplicidades_mapping(mapping_atualizado)
    erro = bool(duplicidades)

    df_saida = None

    if not erro:
        _persistir_mapping(mapping_atualizado)
        df_saida = montar_df_saida_mapeado(df_fonte, df_modelo, mapping_atualizado)

        if _tem_estrutura_df(df_saida):
            _persistir_df_saida(df_saida)

    st.divider()

    _render_cabecalho_bloco(
        "Preview do mapeamento",
        "Confira como a saída final está ficando antes de avançar.",
    )

    if _tem_estrutura_df(df_saida):
        _render_preview_mapeamento_visual(df_saida, duplicidades)
    else:
        _render_alertas_duplicidade(duplicidades)
        st.warning("Nenhum preview válido foi gerado com o mapeamento atual.")

    st.divider()

    _render_footer_nav(
        erro=erro,
        on_back=on_back,
        on_continue=on_continue,
        df_saida=df_saida,
            )

