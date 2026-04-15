
from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.ui.app_helpers import (
    log_debug,
    safe_df_dados,
    safe_df_estrutura,
    sincronizar_etapa_global,
)

try:
    from bling_app_zero.ui.origem_mapeamento_core import (
        montar_df_saida_mapeado as _montar_df_saida_mapeado_core,
        obter_df_fonte_mapeamento as _obter_df_fonte_mapeamento_core,
        obter_df_modelo_mapeamento as _obter_df_modelo_mapeamento_core,
    )
except Exception:
    _montar_df_saida_mapeado_core = None
    _obter_df_fonte_mapeamento_core = None
    _obter_df_modelo_mapeamento_core = None


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


def _modelo_padrao_local() -> pd.DataFrame:
    tipo = _safe_str(st.session_state.get("tipo_operacao_bling")).lower()
    if tipo == "estoque":
        colunas = [
            "Código",
            "Descrição",
            "Depósito (OBRIGATÓRIO)",
            "Balanço (OBRIGATÓRIO)",
            "Preço unitário (OBRIGATÓRIO)",
            "Situação",
        ]
    else:
        colunas = [
            "Código",
            "Descrição",
            "Descrição Curta",
            "Preço de venda",
            "GTIN/EAN",
            "Situação",
            "URL Imagens",
        ]
    return pd.DataFrame(columns=colunas)


def _obter_df_fonte_mapeamento() -> pd.DataFrame | None:
    if callable(_obter_df_fonte_mapeamento_core):
        try:
            df = _obter_df_fonte_mapeamento_core()
            if safe_df_dados(df):
                return df
        except Exception as e:
            log_debug(f"Fallback core fonte mapeamento: {e}", "WARNING")

    for chave in ["df_precificado", "df_calc_precificado", "df_saida", "df_final", "df_origem"]:
        df = st.session_state.get(chave)
        if safe_df_dados(df):
            return _safe_copy_df(df)
    return None


def _obter_df_modelo_mapeamento() -> pd.DataFrame | None:
    if callable(_obter_df_modelo_mapeamento_core):
        try:
            df = _obter_df_modelo_mapeamento_core()
            if safe_df_estrutura(df):
                return df
        except Exception as e:
            log_debug(f"Fallback core modelo mapeamento: {e}", "WARNING")

    df_modelo = st.session_state.get("df_modelo_operacao")
    if safe_df_estrutura(df_modelo):
        return _safe_copy_df(df_modelo)

    return _modelo_padrao_local()


def _is_coluna_bloqueada(nome_coluna: str) -> bool:
    nome = _normalizar_texto(nome_coluna)
    return (
        nome == "id"
        or nome.startswith("id ")
        or " id " in f" {nome} "
        or "deposito" in nome
    )


def _is_coluna_preco(nome_coluna: str) -> bool:
    nome = _normalizar_texto(nome_coluna)
    return "preco de venda" in nome or "preco unitario" in nome


def _is_coluna_situacao(nome_coluna: str) -> bool:
    return "situacao" in _normalizar_texto(nome_coluna)


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
        if col_modelo in mapping and (not mapping[col_modelo] or mapping[col_modelo] in colunas_fonte):
            continue

        nome = _normalizar_texto(col_modelo)

        if _is_coluna_bloqueada(col_modelo):
            mapping[col_modelo] = ""
            continue

        if _is_coluna_situacao(col_modelo):
            mapping[col_modelo] = "__DEFAULT_ATIVO__"
            continue

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


def _montar_df_saida_mapeado(
    df_base: pd.DataFrame,
    df_modelo: pd.DataFrame,
    mapping: dict[str, str],
) -> pd.DataFrame:
    if callable(_montar_df_saida_mapeado_core):
        try:
            return _montar_df_saida_mapeado_core(df_base, df_modelo, mapping)
        except Exception as e:
            log_debug(f"Fallback montar df mapeado: {e}", "WARNING")

    df_saida = pd.DataFrame(index=df_base.index)

    for col_modelo in df_modelo.columns:
        col_modelo = str(col_modelo)
        origem = _safe_str(mapping.get(col_modelo))

        if origem and origem in df_base.columns:
            df_saida[col_modelo] = df_base[origem]
        else:
            df_saida[col_modelo] = ""

    return df_saida


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


def _persistir_resultado(mapping: dict[str, str], defaults: dict[str, str], df_preview: pd.DataFrame) -> None:
    st.session_state["mapping_origem"] = dict(mapping or {})
    st.session_state["mapping_origem_rascunho"] = dict(mapping or {})
    st.session_state["mapping_origem_defaults"] = dict(defaults or {})
    st.session_state["df_preview_mapeamento"] = _safe_copy_df(df_preview)
    st.session_state["df_saida"] = _safe_copy_df(df_preview)
    st.session_state["df_final"] = _safe_copy_df(df_preview)


def render_origem_mapeamento(
    df_origem: pd.DataFrame | None = None,
    df_modelo: pd.DataFrame | None = None,
) -> pd.DataFrame | None:
    st.markdown("### 🧩 Mapeamento")

    df_base = df_origem if safe_df_dados(df_origem) else _obter_df_fonte_mapeamento()
    df_destino = df_modelo if safe_df_estrutura(df_modelo) else _obter_df_modelo_mapeamento()

    if not safe_df_dados(df_base):
        st.warning("Carregue uma origem válida antes de abrir o mapeamento.")
        return None

    if not safe_df_estrutura(df_destino):
        st.warning("Nenhum modelo de destino disponível para mapear.")
        return None

    mapping_salvo = st.session_state.get("mapping_origem", {})
    mapping_inicial = _inferir_mapping_inicial(df_base, df_destino, mapping_salvo)

    colunas_fonte = [str(c) for c in df_base.columns]
    mapping_novo: dict[str, str] = {}
    defaults_novos: dict[str, str] = {}
    usados: set[str] = set()

    st.caption(
        f"Origem: {len(df_base)} linha(s) | Modelo: {len(df_destino.columns)} coluna(s)"
    )
    st.markdown("---")

    for idx, col_modelo in enumerate(df_destino.columns):
        col_modelo = str(col_modelo)
        st.markdown(f"**{col_modelo}**")

        if _is_coluna_bloqueada(col_modelo):
            if "deposito" in _normalizar_texto(col_modelo):
                defaults_novos[col_modelo] = _safe_str(st.session_state.get("deposito_nome"))
                st.info(
                    f"Preenchido automaticamente pelo depósito informado: **{defaults_novos[col_modelo] or 'vazio'}**"
                )
            else:
                defaults_novos[col_modelo] = ""
                st.info("Campo bloqueado automaticamente.")
            continue

        if _is_coluna_situacao(col_modelo):
            defaults_novos[col_modelo] = "Ativo"
            st.info("Preenchido automaticamente como **Ativo**.")
            continue

        valor_inicial = _safe_str(mapping_inicial.get(col_modelo))
        opcoes = [""]

        for col in colunas_fonte:
            if col == valor_inicial or col not in usados:
                opcoes.append(col)

        index = opcoes.index(valor_inicial) if valor_inicial in opcoes else 0

        selecionado = st.selectbox(
            f"Selecionar coluna de origem para {col_modelo}",
            options=opcoes,
            index=index,
            key=f"map_{idx}_{col_modelo}",
            label_visibility="collapsed",
        )

        selecionado = _safe_str(selecionado)
        mapping_novo[col_modelo] = selecionado

        if selecionado:
            usados.add(selecionado)

    df_preview = _montar_df_saida_mapeado(df_base, df_destino, mapping_novo)
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
