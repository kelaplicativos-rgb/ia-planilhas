from __future__ import annotations

import pandas as pd
import streamlit as st


ETAPAS_VALIDAS_ORIGEM = {"origem", "mapeamento", "final"}


# =========================================================
# HELPERS
# =========================================================
def _safe_df(df) -> bool:
    try:
        return isinstance(df, pd.DataFrame) and len(df.columns) > 0
    except Exception:
        return False


def _safe_df_com_linhas(df) -> bool:
    try:
        return isinstance(df, pd.DataFrame) and not df.empty and len(df.columns) > 0
    except Exception:
        return False


def _safe_str(valor) -> str:
    try:
        if valor is None:
            return ""
        if pd.isna(valor):
            return ""
    except Exception:
        pass
    return str(valor).strip()


def _set_etapa(etapa: str):
    etapa = str(etapa).strip().lower()
    st.session_state["etapa_origem"] = etapa
    st.session_state["etapa"] = etapa
    st.session_state["etapa_fluxo"] = etapa


def _get_etapa() -> str:
    for chave in ["etapa_origem", "etapa", "etapa_fluxo"]:
        val = str(st.session_state.get(chave) or "").strip().lower()
        if val:
            return val
    return "origem"


def _normalizar_coluna(nome) -> str:
    texto = _safe_str(nome).lower()
    texto = (
        texto.replace("ã", "a")
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
        .replace("ç", "c")
    )
    return texto


def _is_coluna_deposito(nome) -> bool:
    nome = _normalizar_coluna(nome)
    return "deposit" in nome


def _is_coluna_id(nome) -> bool:
    nome = _normalizar_coluna(nome)
    return nome == "id" or "id produto" in nome


def _is_coluna_imagem(nome) -> bool:
    nome = _normalizar_coluna(nome)
    return "imagem" in nome or "url" in nome


def _normalizar_situacao(valor) -> str:
    texto = _safe_str(valor).lower()
    if not texto:
        return "Ativo"
    if texto in {"inativo", "inactive", "0"}:
        return "Ativo"
    return "Ativo"


def _normalizar_urls_imagem(valor) -> str:
    texto = _safe_str(valor)
    if not texto:
        return ""
    texto = texto.replace("\n", "|").replace(";", "|").replace(",", "|")
    partes = [p.strip() for p in texto.split("|") if p.strip()]
    unicos = []
    vistos = set()
    for item in partes:
        if item not in vistos:
            vistos.add(item)
            unicos.append(item)
    return "|".join(unicos)


def _sanitizar_valor(valor):
    try:
        if valor is None:
            return ""
        if pd.isna(valor):
            return ""
    except Exception:
        pass
    return valor


def _detectar_duplicidades(mapping: dict) -> dict[str, list[str]]:
    usados: dict[str, list[str]] = {}
    for col_modelo, col_origem in mapping.items():
        col_origem = str(col_origem or "").strip()
        if not col_origem:
            continue
        usados.setdefault(col_origem, []).append(col_modelo)
    return {k: v for k, v in usados.items() if len(v) > 1}


def _obter_df_fonte():
    candidatos = [
        st.session_state.get("df_precificado"),
        st.session_state.get("df_calc_precificado"),
        st.session_state.get("df_origem"),
    ]
    for df in candidatos:
        if _safe_df_com_linhas(df):
            return df
    return None


def _obter_df_modelo():
    candidatos = [
        st.session_state.get("df_modelo_mapeamento"),
        st.session_state.get("df_modelo_cadastro"),
        st.session_state.get("df_modelo_estoque"),
        st.session_state.get("df_saida"),
        st.session_state.get("df_final"),
    ]
    for df in candidatos:
        if _safe_df(df):
            return df
    return None


def _inferir_coluna_preco(df_fonte: pd.DataFrame) -> str:
    for col in df_fonte.columns:
        nome = _normalizar_coluna(col)
        if "preco" in nome or "preço" in str(col).lower():
            return str(col)
    return ""


def _aplicar_mapeamento_automatico_preco(mapping: dict, df_modelo: pd.DataFrame, df_fonte: pd.DataFrame) -> dict:
    try:
        coluna_preco = _safe_str(st.session_state.get("coluna_precificacao_resultado"))
        if not coluna_preco:
            coluna_preco = _inferir_coluna_preco(df_fonte)

        if not coluna_preco or coluna_preco not in df_fonte.columns:
            return mapping

        mapping_out = dict(mapping)
        for col_modelo in df_modelo.columns:
            nome = _normalizar_coluna(col_modelo)
            if "preco de venda" in nome or "preco unitario" in nome:
                mapping_out[col_modelo] = coluna_preco
        return mapping_out
    except Exception:
        return dict(mapping)


def _colunas_usadas_por_outros(mapping: dict, coluna_atual: str) -> set[str]:
    usados = set()
    for col_modelo, col_origem in mapping.items():
        if str(col_modelo) == str(coluna_atual):
            continue
        col_origem = _safe_str(col_origem)
        if col_origem:
            usados.add(col_origem)
    return usados


def _opcoes_para_select(df_fonte: pd.DataFrame, mapping: dict, coluna_atual: str) -> list[str]:
    atual = _safe_str(mapping.get(coluna_atual))
    usados = _colunas_usadas_por_outros(mapping, coluna_atual)

    opcoes = [""]
    for col in df_fonte.columns:
        nome = str(col)
        if nome == atual or nome not in usados:
            opcoes.append(nome)
    return opcoes


# =========================================================
# CORE
# =========================================================
def _montar_df_saida(df_fonte, df_modelo, mapping):
    df_saida_base = st.session_state.get("df_saida")
    if isinstance(df_saida_base, pd.DataFrame) and len(df_saida_base) == len(df_fonte):
        df_saida = df_saida_base.copy()
    else:
        df_saida = pd.DataFrame(index=range(len(df_fonte)))

    deposito = str(st.session_state.get("deposito_nome", "") or "").strip()

    for col in df_modelo.columns:
        if _is_coluna_id(col):
            df_saida[col] = ""
            continue

        if _is_coluna_deposito(col):
            df_saida[col] = deposito
            continue

        origem = str(mapping.get(col, "") or "").strip()

        if origem and origem in df_fonte.columns:
            serie = df_fonte[origem].reset_index(drop=True)
            serie = serie.apply(_sanitizar_valor)
            if _is_coluna_imagem(col):
                serie = serie.apply(_normalizar_urls_imagem)
            df_saida[col] = serie
        else:
            if col not in df_saida.columns:
                df_saida[col] = ""
            else:
                df_saida[col] = df_saida[col].fillna("")

        if "situa" in str(col).lower():
            df_saida[col] = df_saida[col].apply(_normalizar_situacao)

    return df_saida


# =========================================================
# RENDER
# =========================================================
def render_origem_mapeamento():
    if _get_etapa() != "mapeamento":
        return

    df_fonte = _obter_df_fonte()
    df_modelo = _obter_df_modelo()

    if not _safe_df_com_linhas(df_fonte) or not _safe_df(df_modelo):
        st.warning("Dados inválidos.")
        return

    st.subheader("Mapeamento de colunas")

    st.text_input(
        "Nome do Depósito (Bling)",
        value=str(st.session_state.get("deposito_nome", "") or ""),
        key="deposito_nome",
        placeholder="Ex: ifood, geral, principal",
    )

    if "mapping_origem" not in st.session_state:
        st.session_state["mapping_origem"] = {}

    mapping = dict(st.session_state["mapping_origem"])
    mapping = _aplicar_mapeamento_automatico_preco(mapping, df_modelo, df_fonte)

    for col_modelo in df_modelo.columns:
        if _is_coluna_id(col_modelo):
            st.text_input(
                col_modelo,
                value="(Automático / Bloqueado)",
                disabled=True,
                key=f"id_lock_{col_modelo}",
            )
            mapping[col_modelo] = ""
            continue

        if _is_coluna_deposito(col_modelo):
            continue

        opcoes = _opcoes_para_select(df_fonte, mapping, col_modelo)
        valor_atual = _safe_str(mapping.get(col_modelo))

        valor = st.selectbox(
            col_modelo,
            opcoes,
            index=opcoes.index(valor_atual) if valor_atual in opcoes else 0,
            key=f"map_{col_modelo}",
        )
        mapping[col_modelo] = valor

    duplicidades = _detectar_duplicidades(mapping)
    erro = False

    if duplicidades:
        erro = True
        mensagens = []
        for coluna_origem, colunas_modelo in duplicidades.items():
            mensagens.append(f"'{coluna_origem}' usada em: {', '.join([str(c) for c in colunas_modelo])}")
        st.error("❌ Existe coluna sendo usada mais de uma vez.\n\n" + "\n".join(mensagens))

    if not erro:
        st.session_state["mapping_origem"] = mapping

    df_saida = _montar_df_saida(df_fonte, df_modelo, mapping)

    st.dataframe(df_saida.head(15), use_container_width=True)

    st.session_state["df_saida"] = df_saida.copy()
    st.session_state["df_final"] = df_saida.copy()

    col1, col2 = st.columns(2)

    with col1:
        if st.button("➡️ Avançar", use_container_width=True, disabled=erro):
            _set_etapa("final")
            st.rerun()

    with col2:
        if st.button("⬅️ Voltar", use_container_width=True):
            _set_etapa("origem")
            st.rerun()
