from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.ui.app_helpers import (
    log_debug,
    safe_df_dados,
    safe_df_estrutura,
    sincronizar_etapa_global,
)
from bling_app_zero.ui.origem_mapeamento_core import (
    montar_df_saida_mapeado,
    obter_df_fonte_mapeamento,
    obter_df_modelo_mapeamento,
)


# =========================
# HELPERS
# =========================
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


def _safe_copy_df(df):
    try:
        return df.copy()
    except Exception:
        return df


def _normalizar_texto(valor: str) -> str:
    try:
        return (
            _safe_str(valor)
            .lower()
            .replace("ç", "c")
            .replace("ã", "a")
            .replace("á", "a")
            .replace("à", "a")
            .replace("â", "a")
            .replace("é", "e")
            .replace("ê", "e")
            .replace("í", "i")
            .replace("ó", "o")
            .replace("ô", "o")
            .replace("õ", "o")
            .replace("ú", "u")
        )
    except Exception:
        return _safe_str(valor).lower()


def _is_coluna_bloqueada(nome_coluna: str) -> bool:
    nome = _normalizar_texto(nome_coluna)
    return (
        nome == "id"
        or nome.startswith("id ")
        or " id " in f" {nome} "
        or "deposito" in nome
        or "depósito" in _safe_str(nome_coluna).lower()
    )


def _is_coluna_preco(nome_coluna: str) -> bool:
    nome = _normalizar_texto(nome_coluna)
    return "preco de venda" in nome or "preco unitario" in nome


def _is_coluna_situacao(nome_coluna: str) -> bool:
    nome = _normalizar_texto(nome_coluna)
    return "situacao" in nome


def _label_operacao() -> str:
    tipo = _safe_str(
        st.session_state.get("tipo_operacao")
        or st.session_state.get("tipo_operacao_bling")
    ).lower()
    if tipo == "estoque":
        return "Atualização de Estoque"
    return "Cadastro de Produtos"


def _inferir_mapping_inicial(
    df_fonte: pd.DataFrame,
    df_modelo: pd.DataFrame,
    mapping_salvo: dict,
) -> dict[str, str]:
    mapping = {}

    if isinstance(mapping_salvo, dict):
        for k, v in mapping_salvo.items():
            k_txt = _safe_str(k)
            v_txt = _safe_str(v)
            if k_txt:
                mapping[k_txt] = v_txt

    colunas_fonte = [str(c) for c in df_fonte.columns]

    for col_modelo in df_modelo.columns:
        col_modelo = str(col_modelo)
        if col_modelo in mapping and (
            not mapping[col_modelo] or mapping[col_modelo] in colunas_fonte
        ):
            continue

        nome = _normalizar_texto(col_modelo)

        if _is_coluna_bloqueada(col_modelo):
            mapping[col_modelo] = ""
            continue

        if _is_coluna_situacao(col_modelo):
            mapping[col_modelo] = "__DEFAULT_ATIVO__"
            continue

        # Se a precificação já colocou o preço na própria base, tenta reaproveitar.
        if _is_coluna_preco(col_modelo) and col_modelo in colunas_fonte:
            mapping[col_modelo] = col_modelo
            continue

        for col_fonte in colunas_fonte:
            nome_fonte = _normalizar_texto(col_fonte)

            if nome_fonte == nome:
                mapping[col_modelo] = col_fonte
                break

            if "descricao curta" in nome and "descricao curta" in nome_fonte:
                mapping[col_modelo] = col_fonte
                break

            if nome in {"descricao", "descricao produto"} and (
                "descricao" in nome_fonte or "produto" in nome_fonte or "nome" in nome_fonte
            ):
                mapping[col_modelo] = col_fonte
                break

            if "gtin" in nome or "ean" in nome:
                if "gtin" in nome_fonte or "ean" in nome_fonte or "barra" in nome_fonte:
                    mapping[col_modelo] = col_fonte
                    break

            if "codigo" in nome:
                if "codigo" in nome_fonte or "sku" in nome_fonte:
                    mapping[col_modelo] = col_fonte
                    break

            if "preco de custo" in nome and "custo" in nome_fonte:
                mapping[col_modelo] = col_fonte
                break

            if _is_coluna_preco(col_modelo):
                if (
                    "preco de venda" in nome_fonte
                    or "preco unitario" in nome_fonte
                    or "preco" in nome_fonte
                    or "valor" in nome_fonte
                    or "custo" in nome_fonte
                ):
                    mapping[col_modelo] = col_fonte
                    break

    return mapping


def _aplicar_defaults_no_df(df_preview: pd.DataFrame, defaults: dict[str, str]) -> pd.DataFrame:
    try:
        df_out = _safe_copy_df(df_preview)
        if not isinstance(df_out, pd.DataFrame):
            return pd.DataFrame()

        for col_modelo, valor_default in (defaults or {}).items():
            col_txt = _safe_str(col_modelo)
            if not col_txt or col_txt not in df_out.columns:
                continue
            df_out[col_txt] = _safe_str(valor_default)

        return df_out
    except Exception as e:
        log_debug(f"Erro ao aplicar defaults no preview: {e}", "ERROR")
        return df_preview if isinstance(df_preview, pd.DataFrame) else pd.DataFrame()


def _persistir_resultado(
    mapping: dict[str, str],
    defaults: dict[str, str],
    df_preview: pd.DataFrame,
) -> None:
    st.session_state["mapping_origem"] = dict(mapping or {})
    st.session_state["mapping_origem_rascunho"] = dict(mapping or {})
    st.session_state["mapping_origem_defaults"] = dict(defaults or {})
    st.session_state["df_preview_mapeamento"] = _safe_copy_df(df_preview)
    st.session_state["df_saida"] = _safe_copy_df(df_preview)
    st.session_state["df_final"] = _safe_copy_df(df_preview)


def _render_resumo(df_base: pd.DataFrame, df_modelo: pd.DataFrame) -> None:
    operacao = _label_operacao()
    st.markdown(
        (
            f"**Operação:** {operacao}"
            f" &nbsp;&nbsp;|&nbsp;&nbsp; "
            f"**Linhas da origem:** {len(df_base)}"
            f" &nbsp;&nbsp;|&nbsp;&nbsp; "
            f"**Colunas do modelo:** {len(df_modelo.columns)}"
        ),
        unsafe_allow_html=True,
    )


# =========================
# RENDER PRINCIPAL
# =========================
def render_origem_mapeamento(
    df_origem: pd.DataFrame | None = None,
    df_modelo: pd.DataFrame | None = None,
) -> pd.DataFrame | None:
    st.markdown("### 🧩 Mapeamento")

    df_base = df_origem if safe_df_dados(df_origem) else obter_df_fonte_mapeamento()
    df_destino = df_modelo if safe_df_estrutura(df_modelo) else obter_df_modelo_mapeamento()

    if not safe_df_dados(df_base):
        st.warning("Carregue uma origem válida antes de abrir o mapeamento.")
        return None

    if not safe_df_estrutura(df_destino):
        st.warning("Nenhum modelo de destino disponível para mapear.")
        return None

    mapping_salvo = st.session_state.get("mapping_origem", {})
    mapping_inicial = _inferir_mapping_inicial(df_base, df_destino, mapping_salvo)

    colunas_fonte = [str(c) for c in df_base.columns]
    opcoes_select = [""] + colunas_fonte

    _render_resumo(df_base, df_destino)
    st.markdown("---")

    mapping_novo: dict[str, str] = {}
    defaults_novos: dict[str, str] = {}

    used_sources: set[str] = set()

    for col_modelo in df_destino.columns:
        col_modelo = str(col_modelo)
        valor_inicial = _safe_str(mapping_inicial.get(col_modelo))

        if valor_inicial and valor_inicial in colunas_fonte:
            used_sources.add(valor_inicial)

    for idx, col_modelo in enumerate(df_destino.columns):
        col_modelo = str(col_modelo)
        chave_select = f"map_dest_{idx}_{col_modelo}"

        st.markdown(f"**{col_modelo}**")

        if _is_coluna_bloqueada(col_modelo):
            if "deposito" in _normalizar_texto(col_modelo):
                deposito = _safe_str(st.session_state.get("deposito_nome"))
                st.info(f"Preenchido automaticamente pelo depósito informado: **{deposito or 'vazio'}**")
                defaults_novos[col_modelo] = deposito
            else:
                st.info("Campo bloqueado automaticamente.")
                defaults_novos[col_modelo] = ""
            continue

        if _is_coluna_situacao(col_modelo):
            st.info("Preenchido automaticamente como **Ativo**.")
            defaults_novos[col_modelo] = "Ativo"
            continue

        valor_inicial = _safe_str(mapping_inicial.get(col_modelo))
        if valor_inicial not in opcoes_select:
            valor_inicial = ""

        # Evita dupla seleção da mesma coluna de origem, mas preserva a já escolhida.
        opcoes_livres = [""]
        for item in colunas_fonte:
            if item == valor_inicial or item not in used_sources:
                opcoes_livres.append(item)

        indice_inicial = opcoes_livres.index(valor_inicial) if valor_inicial in opcoes_livres else 0

        selecionado = st.selectbox(
            f"Selecionar coluna de origem para {col_modelo}",
            options=opcoes_livres,
            index=indice_inicial,
            key=chave_select,
            label_visibility="collapsed",
        )

        mapping_novo[col_modelo] = _safe_str(selecionado)

        if selecionado:
            used_sources.add(selecionado)

    df_preview = montar_df_saida_mapeado(df_base, df_destino, mapping_novo)
    df_preview = _aplicar_defaults_no_df(df_preview, defaults_novos)

    with st.expander("🔎 Preview do mapeamento", expanded=False):
        if isinstance(df_preview, pd.DataFrame) and not df_preview.empty:
            st.dataframe(df_preview.head(20), use_container_width=True)
        else:
            st.caption("Sem preview disponível no momento.")

    st.markdown("---")
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("⬅️ Voltar", use_container_width=True, key="btn_map_voltar"):
            st.session_state["mapping_origem_rascunho"] = dict(mapping_novo)
            sincronizar_etapa_global("precificacao")
            st.rerun()

    with col2:
        if st.button("Salvar mapeamento", use_container_width=True, key="btn_map_salvar"):
            _persistir_resultado(mapping_novo, defaults_novos, df_preview)
            st.success("Mapeamento salvo.")
            log_debug("Mapeamento salvo com sucesso.", "INFO")

    with col3:
        pode_continuar = safe_df_dados(df_preview)

        if st.button(
            "Continuar para preview final ➡️",
            use_container_width=True,
            key="btn_map_continuar",
            type="primary",
            disabled=not pode_continuar,
        ):
            _persistir_resultado(mapping_novo, defaults_novos, df_preview)
            log_debug("Mapeamento finalizado e enviado para preview final.", "INFO")
            sincronizar_etapa_global("final")
            st.rerun()

    return df_preview
