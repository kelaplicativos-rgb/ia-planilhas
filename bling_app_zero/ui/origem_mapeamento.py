from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st


ETAPAS_VALIDAS_ORIGEM = {"origem", "mapeamento", "final", "envio"}


# =========================================================
# HELPERS BÁSICOS
# =========================================================
def _safe_df(df: Any) -> bool:
    try:
        return isinstance(df, pd.DataFrame) and len(df.columns) > 0
    except Exception:
        return False


def _safe_df_com_linhas(df: Any) -> bool:
    try:
        return isinstance(df, pd.DataFrame) and len(df.columns) > 0 and not df.empty
    except Exception:
        return False


def _safe_str(valor: Any) -> str:
    try:
        texto = str(valor or "").strip()
        if texto.lower() in {"none", "nan", "<na>", "nat"}:
            return ""
        return texto
    except Exception:
        return ""


def _normalizar_nome_coluna(nome: Any) -> str:
    return _safe_str(nome).lower()


def _set_etapa(etapa: str) -> None:
    etapa_norm = _safe_str(etapa).lower() or "origem"
    if etapa_norm not in ETAPAS_VALIDAS_ORIGEM:
        etapa_norm = "origem"

    st.session_state["etapa_origem"] = etapa_norm
    st.session_state["etapa"] = etapa_norm
    st.session_state["etapa_fluxo"] = etapa_norm


def _get_etapa() -> str:
    for chave in ("etapa_origem", "etapa", "etapa_fluxo"):
        valor = _safe_str(st.session_state.get(chave)).lower()
        if valor:
            return valor
    return "origem"


# =========================================================
# DETECÇÃO DE COLUNAS ESPECIAIS
# =========================================================
def _is_coluna_deposito(nome: Any) -> bool:
    nome_norm = _normalizar_nome_coluna(nome)
    return "deposit" in nome_norm or "armaz" in nome_norm


def _is_coluna_id(nome: Any) -> bool:
    nome_norm = _normalizar_nome_coluna(nome)
    return nome_norm == "id" or "id produto" in nome_norm


def _is_coluna_preco_venda(nome: Any) -> bool:
    nome_norm = _normalizar_nome_coluna(nome)
    return nome_norm in {
        "preço de venda",
        "preco de venda",
        "valor venda",
        "preço",
        "preco",
    } or (
        "venda" in nome_norm
        and ("preço" in nome_norm or "preco" in nome_norm or "valor" in nome_norm)
    )


def _is_coluna_situacao(nome: Any) -> bool:
    nome_norm = _normalizar_nome_coluna(nome)
    return "situa" in nome_norm or "status" in nome_norm


def _is_coluna_quantidade(nome: Any) -> bool:
    nome_norm = _normalizar_nome_coluna(nome)
    return nome_norm in {"quantidade", "qtd", "estoque", "saldo"} or "quantidade" in nome_norm


# =========================================================
# FONTE / MODELO
# =========================================================
def _obter_df_modelo() -> pd.DataFrame | None:
    candidatos = [
        st.session_state.get("df_modelo_mapeamento"),
        st.session_state.get("df_modelo_cadastro"),
        st.session_state.get("df_modelo_estoque"),
    ]

    for df in candidatos:
        if _safe_df(df):
            return df.copy()

    return None


def _obter_df_fonte() -> pd.DataFrame | None:
    candidatos = [
        st.session_state.get("df_calc_precificado"),
        st.session_state.get("df_precificado"),
        st.session_state.get("df_origem"),
    ]

    for df in candidatos:
        if _safe_df_com_linhas(df):
            return df.copy()

    return None


# =========================================================
# NORMALIZAÇÃO
# =========================================================
def _sanitizar_valor(valor: Any) -> Any:
    try:
        if valor is None:
            return ""

        if isinstance(valor, (int, float)) and not pd.isna(valor):
            return valor

        texto = str(valor).replace("⚠️", "").strip()
        if texto.lower() in {"none", "nan", "<na>", "nat"}:
            return ""
        return texto
    except Exception:
        return ""


def _normalizar_situacao(valor: Any) -> str:
    try:
        texto = _safe_str(valor).lower()
        if texto in {"ativo", "1", "true", "sim", "yes"}:
            return "Ativo"
        if texto in {"inativo", "0", "false", "não", "nao", "no"}:
            return "Inativo"
        return "Ativo" if texto else "Inativo"
    except Exception:
        return "Inativo"


def _normalizar_quantidade(valor: Any) -> int:
    try:
        texto = _safe_str(valor).lower()
        if texto in {"sem estoque", "indisponível", "indisponivel", "zerado"}:
            return 0
        if texto == "":
            return 0
        return max(int(float(str(valor).replace(",", "."))), 0)
    except Exception:
        return 0


# =========================================================
# MAPEAMENTO AUTOMÁTICO
# =========================================================
def _detectar_duplicidades(mapping: dict[str, str]) -> dict[str, list[str]]:
    usados: dict[str, list[str]] = {}

    for col_modelo, col_origem in mapping.items():
        origem = _safe_str(col_origem)
        if not origem:
            continue
        usados.setdefault(origem, []).append(col_modelo)

    return {origem: cols for origem, cols in usados.items() if len(cols) > 1}


def _aplicar_mapeamento_automatico_preco(
    mapping: dict[str, str],
    df_modelo: pd.DataFrame,
    df_fonte: pd.DataFrame,
) -> dict[str, str]:
    try:
        col_preco_origem = _safe_str(st.session_state.get("coluna_preco_unitario_origem"))
        if not col_preco_origem or col_preco_origem not in df_fonte.columns:
            return mapping

        novo = dict(mapping)
        for col_modelo in df_modelo.columns:
            if _is_coluna_preco_venda(col_modelo) and not _safe_str(novo.get(col_modelo)):
                novo[col_modelo] = col_preco_origem
        return novo
    except Exception:
        return mapping


def _sugerir_mapeamento_inicial(
    df_modelo: pd.DataFrame,
    df_fonte: pd.DataFrame,
    mapping_existente: dict[str, str],
) -> dict[str, str]:
    sugestao = dict(mapping_existente)

    colunas_fonte = list(df_fonte.columns)
    colunas_fonte_norm = {_normalizar_nome_coluna(c): c for c in colunas_fonte}

    aliases = {
        "descrição": ["descrição", "descricao", "nome", "titulo", "título", "produto"],
        "descrição curta": ["descrição curta", "descricao curta", "descrição", "descricao", "nome"],
        "código": ["código", "codigo", "sku", "ref", "referencia", "referência"],
        "marca": ["marca", "fabricante"],
        "ncm": ["ncm"],
        "gtin": ["gtin", "ean", "codigo de barras", "código de barras"],
        "gtin tributário": ["gtin tributário", "gtin tributario", "ean tributário", "ean tributario"],
        "situação": ["situação", "situacao", "status"],
        "link externo": ["link externo", "link", "url", "produto url"],
        "imagens": ["imagem", "imagens", "foto", "fotos", "url imagem"],
        "quantidade": ["quantidade", "qtd", "estoque", "saldo"],
        "preço de venda": ["preço de venda", "preco de venda", "preço", "preco", "valor venda", "valor"],
        "preço": ["preço", "preco", "valor", "valor venda"],
        "preço de custo": ["preço de custo", "preco de custo", "custo", "valor custo"],
        "unidade": ["unidade", "und", "ucom"],
    }

    for col_modelo in df_modelo.columns:
        if _safe_str(sugestao.get(col_modelo)):
            continue
        if _is_coluna_id(col_modelo) or _is_coluna_deposito(col_modelo):
            continue

        nome_modelo = _normalizar_nome_coluna(col_modelo)

        if nome_modelo in colunas_fonte_norm:
            sugestao[col_modelo] = colunas_fonte_norm[nome_modelo]
            continue

        for alias in aliases.get(nome_modelo, []):
            alias_norm = _normalizar_nome_coluna(alias)
            if alias_norm in colunas_fonte_norm:
                sugestao[col_modelo] = colunas_fonte_norm[alias_norm]
                break

        if _safe_str(sugestao.get(col_modelo)):
            continue

        for col_fonte in colunas_fonte:
            nome_fonte = _normalizar_nome_coluna(col_fonte)
            if nome_modelo and (nome_modelo in nome_fonte or nome_fonte in nome_modelo):
                sugestao[col_modelo] = col_fonte
                break

    return _aplicar_mapeamento_automatico_preco(sugestao, df_modelo, df_fonte)


# =========================================================
# MONTAGEM DE SAÍDA
# =========================================================
def _criar_df_saida_base(df_fonte: pd.DataFrame, df_modelo: pd.DataFrame) -> pd.DataFrame:
    df_saida_base = st.session_state.get("df_saida")

    if (
        isinstance(df_saida_base, pd.DataFrame)
        and len(df_saida_base) == len(df_fonte)
        and list(df_saida_base.columns) == list(df_modelo.columns)
    ):
        return df_saida_base.copy()

    return pd.DataFrame(index=range(len(df_fonte)), columns=list(df_modelo.columns))


def _montar_df_saida(
    df_fonte: pd.DataFrame,
    df_modelo: pd.DataFrame,
    mapping: dict[str, str],
) -> pd.DataFrame:
    df_saida = _criar_df_saida_base(df_fonte, df_modelo)
    deposito = _safe_str(st.session_state.get("deposito_nome"))

    for col_modelo in df_modelo.columns:
        if _is_coluna_id(col_modelo):
            df_saida[col_modelo] = ""
            continue

        if _is_coluna_deposito(col_modelo):
            df_saida[col_modelo] = deposito
            continue

        origem = _safe_str(mapping.get(col_modelo))
        if origem and origem in df_fonte.columns:
            serie = df_fonte[origem].reset_index(drop=True).apply(_sanitizar_valor)

            if _is_coluna_situacao(col_modelo):
                serie = serie.apply(_normalizar_situacao)

            if _is_coluna_quantidade(col_modelo):
                serie = serie.apply(_normalizar_quantidade)

            df_saida[col_modelo] = serie
        else:
            if col_modelo not in df_saida.columns:
                df_saida[col_modelo] = ""

            if _is_coluna_situacao(col_modelo):
                df_saida[col_modelo] = df_saida[col_modelo].fillna("").apply(_normalizar_situacao)
            else:
                df_saida[col_modelo] = df_saida[col_modelo].fillna("")

    return df_saida


# =========================================================
# UI
# =========================================================
def _render_preview_fonte(df_fonte: pd.DataFrame) -> None:
    st.caption("Prévia da origem")
    st.dataframe(df_fonte.head(8), use_container_width=True)


def _render_alerta_duplicidade(duplicidades: dict[str, list[str]]) -> None:
    if not duplicidades:
        return

    linhas = []
    for origem, destinos in duplicidades.items():
        linhas.append(f"• {origem}: {', '.join(destinos)}")

    st.error("❌ Existe coluna de origem usada mais de uma vez:\n\n" + "\n".join(linhas))


def _render_campos_mapeamento(
    df_modelo: pd.DataFrame,
    df_fonte: pd.DataFrame,
    mapping_atual: dict[str, str],
) -> dict[str, str]:
    novo_mapping = dict(mapping_atual)
    opcoes = [""] + list(df_fonte.columns)

    for col_modelo in df_modelo.columns:
        if _is_coluna_id(col_modelo):
            st.text_input(
                col_modelo,
                value="(Automático / Bloqueado)",
                disabled=True,
                key=f"map_id_{col_modelo}",
            )
            novo_mapping[col_modelo] = ""
            continue

        if _is_coluna_deposito(col_modelo):
            st.text_input(
                col_modelo,
                value=_safe_str(st.session_state.get("deposito_nome")),
                disabled=True,
                key=f"map_dep_{col_modelo}",
            )
            novo_mapping[col_modelo] = ""
            continue

        valor_atual = _safe_str(novo_mapping.get(col_modelo))
        index_atual = opcoes.index(valor_atual) if valor_atual in opcoes else 0

        valor = st.selectbox(
            col_modelo,
            opcoes,
            index=index_atual,
            key=f"map_{col_modelo}",
        )
        novo_mapping[col_modelo] = _safe_str(valor)

    return novo_mapping


# =========================================================
# RENDER PRINCIPAL
# =========================================================
def render_origem_mapeamento() -> None:
    if _get_etapa() != "mapeamento":
        return

    df_fonte = _obter_df_fonte()
    df_modelo = _obter_df_modelo()

    if not _safe_df_com_linhas(df_fonte) or not _safe_df(df_modelo):
        st.warning("Dados inválidos para o mapeamento. Volte para a origem.")
        return

    st.subheader("Mapeamento de colunas")

    st.text_input(
        "Nome do Depósito (Bling)",
        value=_safe_str(st.session_state.get("deposito_nome")),
        key="deposito_nome",
        placeholder="Ex: ifood, geral, principal",
    )

    _render_preview_fonte(df_fonte)

    if "mapping_origem" not in st.session_state or not isinstance(
        st.session_state.get("mapping_origem"), dict
    ):
        st.session_state["mapping_origem"] = {}

    mapping = dict(st.session_state["mapping_origem"])
    mapping = _sugerir_mapeamento_inicial(df_modelo, df_fonte, mapping)

    st.markdown("---")
    mapping = _render_campos_mapeamento(df_modelo, df_fonte, mapping)

    duplicidades = _detectar_duplicidades(mapping)
    tem_erro = bool(duplicidades)

    if tem_erro:
        _render_alerta_duplicidade(duplicidades)
    else:
        st.session_state["mapping_origem"] = dict(mapping)

    df_saida = _montar_df_saida(df_fonte, df_modelo, mapping)

    st.markdown("---")
    st.caption("Prévia do resultado mapeado")
    st.dataframe(df_saida.head(15), use_container_width=True)

    st.session_state["df_saida"] = df_saida.copy()
    st.session_state["df_final"] = df_saida.copy()
    st.session_state["df_modelo_mapeamento"] = df_modelo.copy()

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("Limpar mapeamento", use_container_width=True):
            st.session_state["mapping_origem"] = {}
            for chave in list(st.session_state.keys()):
                if str(chave).startswith("map_"):
                    st.session_state.pop(chave, None)
            st.rerun()

    with col2:
        if st.button("⬅️ Voltar", use_container_width=True):
            _set_etapa("origem")
            st.rerun()

    with col3:
        if st.button("➡️ Avançar", use_container_width=True, type="primary", disabled=tem_erro):
            st.session_state["df_saida"] = df_saida.copy()
            st.session_state["df_final"] = df_saida.copy()
            _set_etapa("final")
            st.rerun()
