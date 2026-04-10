from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st


ETAPAS_VALIDAS_ORIGEM = {"origem", "mapeamento", "final", "envio"}


# =========================================================
# HELPERS
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


def _set_etapa(etapa: str) -> None:
    etapa = str(etapa or "").strip().lower()
    if etapa not in ETAPAS_VALIDAS_ORIGEM:
        etapa = "origem"

    st.session_state["etapa_origem"] = etapa
    st.session_state["etapa"] = etapa
    st.session_state["etapa_fluxo"] = etapa


def _get_etapa() -> str:
    for chave in ["etapa_origem", "etapa", "etapa_fluxo"]:
        try:
            val = str(st.session_state.get(chave) or "").strip().lower()
            if val:
                return val
        except Exception:
            pass
    return "origem"


def _normalizar_nome_coluna(nome: Any) -> str:
    try:
        return str(nome or "").strip().lower()
    except Exception:
        return ""


def _is_coluna_deposito(nome: Any) -> bool:
    nome = _normalizar_nome_coluna(nome)
    return "deposit" in nome


def _is_coluna_id(nome: Any) -> bool:
    nome = _normalizar_nome_coluna(nome)
    return nome == "id" or "id produto" in nome


def _is_coluna_situacao(nome: Any) -> bool:
    nome = _normalizar_nome_coluna(nome)
    return "situa" in nome or nome == "status"


def _is_coluna_preco_venda(nome: Any) -> bool:
    nome = _normalizar_nome_coluna(nome)
    return nome in {"preço de venda", "preco de venda", "valor venda"} or (
        "venda" in nome and ("preço" in nome or "preco" in nome or "valor" in nome)
    )


def _safe_str(valor: Any) -> str:
    try:
        texto = str(valor or "").strip()
        if texto.lower() in {"none", "nan", "<na>", "nat"}:
            return ""
        return texto
    except Exception:
        return ""


def _sanitizar_valor(valor: Any) -> str:
    try:
        if valor is None:
            return ""

        texto = str(valor)
        texto = texto.replace("⚠️", "").strip()

        if texto.lower() in {"none", "nan", "<na>", "nat"}:
            return ""

        return texto
    except Exception:
        return ""


def _normalizar_situacao(valor: Any) -> str:
    try:
        texto = str(valor or "").strip().lower()

        if texto in {"ativo", "1", "true", "sim", "yes"}:
            return "Ativo"

        if texto in {"inativo", "0", "false", "não", "nao", "no"}:
            return "Inativo"

        if texto == "":
            return "Ativo"

        return "Ativo"
    except Exception:
        return "Ativo"


def _detectar_duplicidades(mapping: dict[str, str]) -> dict[str, list[str]]:
    usados: dict[str, list[str]] = {}

    for col_modelo, col_origem in mapping.items():
        origem = _safe_str(col_origem)
        if not origem:
            continue
        usados.setdefault(origem, []).append(col_modelo)

    return {origem: cols for origem, cols in usados.items() if len(cols) > 1}


def _inicializar_mapping_vazio(colunas_modelo: list[str]) -> dict[str, str]:
    mapping_atual = st.session_state.get("mapping_origem")
    if isinstance(mapping_atual, dict):
        return dict(mapping_atual)

    return {str(col): "" for col in colunas_modelo}


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
    """
    Regra:
    - Para mapear, a fonte deve ser a origem/precificação.
    - Nunca usar df_saida/df_final como fonte de selectbox, pois isso recicla o próprio modelo.
    """
    candidatos = [
        st.session_state.get("df_calc_precificado"),
        st.session_state.get("df_precificado"),
        st.session_state.get("df_origem"),
    ]

    for df in candidatos:
        if _safe_df_com_linhas(df):
            return df.copy()

    return None


def _obter_df_saida_base(df_fonte: pd.DataFrame, df_modelo: pd.DataFrame) -> pd.DataFrame:
    try:
        df_saida_base = st.session_state.get("df_saida")

        if (
            isinstance(df_saida_base, pd.DataFrame)
            and len(df_saida_base) == len(df_fonte)
            and list(df_saida_base.columns) == list(df_modelo.columns)
        ):
            return df_saida_base.copy()
    except Exception:
        pass

    return pd.DataFrame(index=range(len(df_fonte)), columns=list(df_modelo.columns))


def _aplicar_mapeamento_automatico_preco(
    mapping: dict[str, str],
    df_modelo: pd.DataFrame,
    df_fonte: pd.DataFrame,
) -> dict[str, str]:
    try:
        col_preco_origem = _safe_str(st.session_state.get("coluna_preco_unitario_origem"))

        if not col_preco_origem or col_preco_origem not in df_fonte.columns:
            return mapping

        novo_mapping = dict(mapping)

        for col_modelo in df_modelo.columns:
            if _is_coluna_preco_venda(col_modelo) and not _safe_str(novo_mapping.get(col_modelo)):
                novo_mapping[str(col_modelo)] = col_preco_origem

        return novo_mapping
    except Exception:
        return mapping


def _sugerir_mapeamento_basico(
    mapping: dict[str, str],
    df_modelo: pd.DataFrame,
    df_fonte: pd.DataFrame,
) -> dict[str, str]:
    try:
        colunas_origem = list(df_fonte.columns)
        colunas_origem_norm = {_normalizar_nome_coluna(c): c for c in colunas_origem}

        aliases: dict[str, list[str]] = {
            "código": ["codigo", "código", "sku", "ref", "referencia", "referência"],
            "descrição": ["descrição", "descricao", "nome", "titulo", "título", "produto"],
            "descrição curta": ["descrição curta", "descricao curta", "descrição", "descricao", "nome"],
            "preço": ["preço", "preco", "valor", "valor venda"],
            "preço de venda": ["preço de venda", "preco de venda", "valor venda", "preço", "preco"],
            "preço de custo": ["preço de custo", "preco de custo", "custo"],
            "marca": ["marca", "fabricante"],
            "ncm": ["ncm"],
            "gtin": ["gtin", "ean", "codigo de barras", "código de barras"],
            "gtin tributário": ["gtin tributário", "gtin tributario", "ean tributário", "ean tributario"],
            "unidade": ["unidade", "und", "ucom"],
            "quantidade": ["quantidade", "qtd", "estoque", "saldo"],
            "situação": ["situação", "situacao", "status"],
            "imagens": ["imagens", "imagem", "foto", "fotos", "url imagem"],
            "link externo": ["link externo", "url", "link", "produto url"],
            "depósito": ["deposito", "depósito", "armazem", "armazém"],
        }

        novo_mapping = dict(mapping)
        usados = {v for v in novo_mapping.values() if _safe_str(v)}

        for col_modelo in df_modelo.columns:
            col_modelo_str = str(col_modelo)

            if _safe_str(novo_mapping.get(col_modelo_str)):
                continue

            if _is_coluna_id(col_modelo_str) or _is_coluna_deposito(col_modelo_str):
                continue

            nome_modelo_norm = _normalizar_nome_coluna(col_modelo_str)

            # 1. Match direto
            if nome_modelo_norm in colunas_origem_norm and colunas_origem_norm[nome_modelo_norm] not in usados:
                novo_mapping[col_modelo_str] = colunas_origem_norm[nome_modelo_norm]
                usados.add(colunas_origem_norm[nome_modelo_norm])
                continue

            # 2. Aliases conhecidos
            for chave_alias, lista_alias in aliases.items():
                chave_alias_norm = _normalizar_nome_coluna(chave_alias)
                if chave_alias_norm != nome_modelo_norm:
                    continue

                encontrado = None
                for alias in lista_alias:
                    alias_norm = _normalizar_nome_coluna(alias)
                    if alias_norm in colunas_origem_norm:
                        candidato = colunas_origem_norm[alias_norm]
                        if candidato not in usados:
                            encontrado = candidato
                            break

                if encontrado:
                    novo_mapping[col_modelo_str] = encontrado
                    usados.add(encontrado)
                break

        return novo_mapping
    except Exception:
        return mapping


# =========================================================
# CORE
# =========================================================
def _montar_df_saida(
    df_fonte: pd.DataFrame,
    df_modelo: pd.DataFrame,
    mapping: dict[str, str],
) -> pd.DataFrame:
    df_saida = _obter_df_saida_base(df_fonte, df_modelo)
    deposito = _safe_str(st.session_state.get("deposito_nome"))

    for col in df_modelo.columns:
        col_str = str(col)

        if _is_coluna_id(col_str):
            df_saida[col_str] = ""
            continue

        if _is_coluna_deposito(col_str):
            df_saida[col_str] = deposito
            continue

        origem = _safe_str(mapping.get(col_str))

        if origem and origem in df_fonte.columns:
            serie = df_fonte[origem].reset_index(drop=True)
            serie = serie.apply(_sanitizar_valor)
            df_saida[col_str] = serie
        else:
            if col_str not in df_saida.columns:
                df_saida[col_str] = ""
            else:
                df_saida[col_str] = df_saida[col_str].fillna("")

        if _is_coluna_situacao(col_str):
            df_saida[col_str] = df_saida[col_str].apply(_normalizar_situacao)

    return df_saida


def _render_aviso_duplicidades(duplicidades: dict[str, list[str]]) -> None:
    if not duplicidades:
        return

    st.error("❌ Existe coluna de origem sendo usada mais de uma vez.")

    for col_origem, colunas_modelo in duplicidades.items():
        st.caption(
            f"Origem '{col_origem}' usada em: {', '.join(str(c) for c in colunas_modelo)}"
        )


# =========================================================
# RENDER
# =========================================================
def render_origem_mapeamento() -> None:
    if _get_etapa() != "mapeamento":
        return

    df_fonte = _obter_df_fonte()
    df_modelo = _obter_df_modelo()

    if not _safe_df_com_linhas(df_fonte):
        st.warning("Dados de origem inválidos para o mapeamento.")
        return

    if not _safe_df(df_modelo):
        st.warning("Modelo do Bling inválido para o mapeamento.")
        return

    st.subheader("Mapeamento de colunas")
    st.caption("Mapeie as colunas da origem para as colunas do modelo do Bling.")

    st.text_input(
        "Nome do Depósito (Bling)",
        value=_safe_str(st.session_state.get("deposito_nome")),
        key="deposito_nome",
        placeholder="Ex: ifood, geral, principal",
    )

    st.markdown("### Prévia da origem")
    st.dataframe(df_fonte.head(10), use_container_width=True)

    mapping = _inicializar_mapping_vazio(list(df_modelo.columns))
    mapping = _sugerir_mapeamento_basico(mapping, df_modelo, df_fonte)
    mapping = _aplicar_mapeamento_automatico_preco(mapping, df_modelo, df_fonte)

    st.markdown("### Mapeamento")

    for col_modelo in df_modelo.columns:
        col_modelo_str = str(col_modelo)

        if _is_coluna_id(col_modelo_str):
            st.text_input(
                col_modelo_str,
                value="(Automático / Bloqueado)",
                disabled=True,
                key=f"map_locked_{col_modelo_str}",
            )
            mapping[col_modelo_str] = ""
            continue

        if _is_coluna_deposito(col_modelo_str):
            st.text_input(
                col_modelo_str,
                value="Preenchido automaticamente pelo campo de depósito",
                disabled=True,
                key=f"map_deposito_{col_modelo_str}",
            )
            mapping[col_modelo_str] = ""
            continue

        opcoes = [""] + list(df_fonte.columns)
        valor_atual = _safe_str(st.session_state.get(f"map_{col_modelo_str}", mapping.get(col_modelo_str, "")))

        valor = st.selectbox(
            col_modelo_str,
            opcoes,
            index=opcoes.index(valor_atual) if valor_atual in opcoes else 0,
            key=f"map_{col_modelo_str}",
        )

        mapping[col_modelo_str] = valor

    duplicidades = _detectar_duplicidades(mapping)
    erro = bool(duplicidades)

    if erro:
        _render_aviso_duplicidades(duplicidades)

    if st.button("🧹 Limpar mapeamento", use_container_width=True):
        for col_modelo in df_modelo.columns:
            st.session_state.pop(f"map_{col_modelo}", None)
        st.session_state["mapping_origem"] = {}
        st.rerun()

    if not erro:
        st.session_state["mapping_origem"] = dict(mapping)

        df_saida = _montar_df_saida(df_fonte, df_modelo, mapping)

        st.markdown("### Prévia do modelo montado")
        st.dataframe(df_saida.head(15), use_container_width=True)

        # Mantém a base pronta para a tela final.
        st.session_state["df_saida"] = df_saida.copy()
        st.session_state["df_final"] = df_saida.copy()

    col1, col2 = st.columns(2)

    with col1:
        if st.button("➡️ Avançar", use_container_width=True, disabled=erro, type="primary"):
            if not erro and _safe_df(st.session_state.get("df_saida")):
                st.session_state["df_final"] = st.session_state["df_saida"].copy()
            _set_etapa("final")
            st.rerun()

    with col2:
        if st.button("⬅️ Voltar", use_container_width=True):
            _set_etapa("origem")
            st.rerun()
