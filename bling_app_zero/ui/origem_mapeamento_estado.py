from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.ui.origem_mapeamento_core import (
    aplicar_mapeamento_automatico_preco,
)
from bling_app_zero.ui.origem_mapeamento_validacao import (
    is_coluna_deposito,
    is_coluna_id,
    opcoes_select_mapeamento,
    safe_str,
)


def _safe_dict(valor) -> dict:
    try:
        return dict(valor or {})
    except Exception:
        return {}


def _tem_df(df) -> bool:
    try:
        return isinstance(df, pd.DataFrame) and len(df.columns) > 0
    except Exception:
        return False


def _mapping_base_com_rascunho(mapping: dict) -> dict:
    base = _safe_dict(mapping)
    rascunho = _safe_dict(st.session_state.get("mapping_origem_rascunho"))

    if not rascunho:
        return base

    combinado = base.copy()
    combinado.update(rascunho)
    return combinado


def _limpar_widget_coluna(col_modelo: str) -> None:
    try:
        st.session_state.pop(f"map_{col_modelo}", None)
    except Exception:
        pass


def render_cabecalho_mapeamento() -> None:
    st.subheader("Mapeamento de colunas")
    st.caption(
        "Relacione as colunas da sua origem com os campos do modelo Bling. "
        "Ao voltar para a etapa anterior, o rascunho do mapeamento será preservado."
    )

    st.text_input(
        "Nome do Depósito (Bling)",
        value=str(st.session_state.get("deposito_nome", "") or ""),
        key="deposito_nome",
        placeholder="Ex: ifood, geral, principal",
    )


def render_formulario_mapeamento(
    df_fonte: pd.DataFrame,
    df_modelo: pd.DataFrame,
    mapping: dict,
) -> dict:
    mapping_inicial = _mapping_base_com_rascunho(mapping)
    mapping_local = aplicar_mapeamento_automatico_preco(
        mapping_inicial,
        df_modelo,
        df_fonte,
    )

    resultado: dict[str, str] = {}

    for col_modelo in df_modelo.columns:
        if is_coluna_id(col_modelo):
            st.text_input(
                col_modelo,
                value="(Automático / Bloqueado)",
                disabled=True,
                key=f"id_lock_{col_modelo}",
            )
            resultado[col_modelo] = ""
            _limpar_widget_coluna(col_modelo)
            continue

        if is_coluna_deposito(col_modelo):
            resultado[col_modelo] = safe_str(mapping_local.get(col_modelo))
            _limpar_widget_coluna(col_modelo)
            continue

        opcoes = opcoes_select_mapeamento(df_fonte, mapping_local, col_modelo)
        if not opcoes:
            opcoes = [""]

        valor_rascunho = safe_str(st.session_state.get(f"map_{col_modelo}"))
        valor_base = safe_str(mapping_local.get(col_modelo))
        valor_atual = valor_rascunho or valor_base

        if valor_atual not in opcoes:
            valor_atual = ""

        indice_atual = opcoes.index(valor_atual) if valor_atual in opcoes else 0

        valor_escolhido = st.selectbox(
            col_modelo,
            opcoes,
            index=indice_atual,
            key=f"map_{col_modelo}",
            help="Selecione uma coluna da origem para preencher este campo do modelo.",
        )

        resultado[col_modelo] = safe_str(valor_escolhido)

    st.session_state["mapping_origem_rascunho"] = _safe_dict(resultado)
    return resultado


def render_preview_mapeamento(
    df_saida: pd.DataFrame,
    duplicidades: dict[str, list[str]],
) -> None:
    st.markdown("### Prévia do resultado")

    if duplicidades:
        mensagens = []
        for coluna_origem, colunas_modelo in duplicidades.items():
            mensagens.append(
                f"'{coluna_origem}' usada em: {', '.join([str(c) for c in colunas_modelo])}"
            )

        st.error(
            "❌ Existe coluna sendo usada mais de uma vez.\n\n"
            + "\n".join(mensagens)
        )

    if not _tem_df(df_saida):
        st.warning("Nenhuma prévia válida foi gerada até o momento.")
        return

    with st.expander("Visualizar prévia mapeada", expanded=False):
        st.dataframe(df_saida.head(15), use_container_width=True)
        
