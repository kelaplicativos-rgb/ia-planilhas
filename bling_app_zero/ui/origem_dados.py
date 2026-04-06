from __future__ import annotations

import streamlit as st

from bling_app_zero.core.mapeamento_auto import sugestao_automatica
from bling_app_zero.ui.origem_dados_helpers import (
    log_debug,
    ler_planilha_segura,
)
from bling_app_zero.ui.origem_dados_site import render_origem_site


# ==========================================================
# HELPERS
# ==========================================================
def _obter_df_origem():
    df = st.session_state.get("df_origem")
    if df is None:
        return None
    try:
        if df.empty:
            return None
    except Exception:
        return None
    return df


def _obter_colunas_modelo_ativo() -> list[str]:
    """
    Tenta descobrir as colunas alvo do modelo ativo sem quebrar o fluxo atual.
    """
    candidatos = [
        st.session_state.get("colunas_modelo_ativo"),
        st.session_state.get("colunas_modelo"),
        st.session_state.get("modelo_ativo_colunas"),
        st.session_state.get("colunas_bling_modelo"),
    ]

    for item in candidatos:
        if isinstance(item, list) and item:
            return [str(x) for x in item if str(x).strip()]

    dfs_candidatos = [
        st.session_state.get("df_modelo_ativo"),
        st.session_state.get("df_modelo_cadastro"),
        st.session_state.get("df_modelo_estoque"),
        st.session_state.get("modelo_ativo_df"),
    ]

    for df in dfs_candidatos:
        try:
            if df is not None and not df.empty:
                return [str(c) for c in df.columns]
        except Exception:
            continue

    return []


def _obter_mapeamento_inicial(df_origem, colunas_alvo: list[str]) -> dict[str, str]:
    """
    Usa IA/sugestão automática quando disponível, mas sem quebrar o fluxo.
    Sempre retorna no formato:
        {coluna_origem: coluna_alvo}
    """
    mapeamento: dict[str, str] = {}

    if df_origem is None or df_origem.empty:
        return mapeamento

    if not colunas_alvo:
        return mapeamento

    try:
        sugestoes = sugestao_automatica(df_origem, colunas_alvo)

        if isinstance(sugestoes, dict):
            for k, v in sugestoes.items():
                if k is None or v is None:
                    continue
                k_str = str(k).strip()
                v_str = str(v).strip()

                if not k_str or not v_str:
                    continue

                # aceita tanto origem->alvo quanto alvo->origem
                if k_str in df_origem.columns and v_str in colunas_alvo:
                    mapeamento[k_str] = v_str
                elif k_str in colunas_alvo and v_str in df_origem.columns:
                    mapeamento[v_str] = k_str

    except Exception as e:
        log_debug(f"Erro ao gerar sugestão automática de mapeamento: {e}", "WARNING")

    return mapeamento


def _inicializar_estado_mapeamento(df_origem, colunas_alvo: list[str]) -> None:
    hash_atual = f"{tuple(df_origem.columns)}|{tuple(colunas_alvo)}"
    hash_salvo = st.session_state.get("mapeamento_origem_hash")

    if hash_salvo == hash_atual and "mapeamento_origem" in st.session_state:
        return

    mapeamento_inicial = _obter_mapeamento_inicial(df_origem, colunas_alvo)

    st.session_state["mapeamento_origem"] = mapeamento_inicial
    st.session_state["mapeamento_origem_hash"] = hash_atual
    st.session_state["mapeamento_origem_confirmado"] = False

    log_debug(
        f"Mapeamento inicial preparado com {len(mapeamento_inicial)} sugestoes",
        "INFO",
    )


def _colunas_alvo_disponiveis(
    coluna_origem_atual: str,
    colunas_alvo: list[str],
    mapeamento_atual: dict[str, str],
) -> list[str]:
    alvo_atual = mapeamento_atual.get(coluna_origem_atual, "")
    usados = {
        alvo for origem, alvo in mapeamento_atual.items()
        if origem != coluna_origem_atual and str(alvo).strip()
    }

    opcoes = [""]
    for alvo in colunas_alvo:
        if alvo == alvo_atual or alvo not in usados:
            opcoes.append(alvo)

    return opcoes


def _render_preview_compacto(df_origem) -> None:
    try:
        st.dataframe(
            df_origem.head(10),
            use_container_width=True,
            height=260,
        )
    except Exception:
        st.dataframe(df_origem.head(10), use_container_width=True)


def _render_mapeamento(df_origem) -> None:
    st.subheader("Mapeamento de colunas")

    colunas_alvo = _obter_colunas_modelo_ativo()

    if not colunas_alvo:
        st.warning(
            "Nenhuma coluna do modelo ativo foi encontrada. "
            "Anexe ou carregue primeiro a planilha modelo para continuar o mapeamento."
        )
        if st.button("⬅️ Voltar", use_container_width=True):
            st.session_state["etapa_origem"] = "upload"
            st.rerun()
        return

    _inicializar_estado_mapeamento(df_origem, colunas_alvo)

    mapeamento_atual: dict[str, str] = st.session_state.get("mapeamento_origem", {})

    st.caption(f"{len(df_origem.columns)} colunas de origem detectadas")
    st.caption(f"{len(colunas_alvo)} colunas disponíveis no modelo ativo")

    with st.expander("Ver colunas do modelo ativo", expanded=False):
        st.write(colunas_alvo)

    st.markdown("### Pré-visualização da origem")
    _render_preview_compacto(df_origem)

    st.markdown("### Mapeamento manual com sugestão automática")

    col1, col2 = st.columns([1, 1])

    with col1:
        if st.button("🧠 Aplicar sugestões IA novamente", use_container_width=True):
            st.session_state["mapeamento_origem"] = _obter_mapeamento_inicial(df_origem, colunas_alvo)
            st.session_state["mapeamento_origem_confirmado"] = False
            st.rerun()

    with col2:
        if st.button("🧹 Limpar mapeamento", use_container_width=True):
            st.session_state["mapeamento_origem"] = {}
            st.session_state["mapeamento_origem_confirmado"] = False
            st.rerun()

    mapeamento_editado: dict[str, str] = {}

    for coluna_origem in df_origem.columns:
        valor_sugerido = mapeamento_atual.get(coluna_origem, "")
        opcoes = _colunas_alvo_disponiveis(coluna_origem, colunas_alvo, mapeamento_atual)

        if valor_sugerido not in opcoes:
            opcoes = ["", valor_sugerido] + [x for x in opcoes if x not in ("", valor_sugerido)]

        exemplo = ""
        try:
            serie = df_origem[coluna_origem].dropna().astype(str)
            if not serie.empty:
                exemplo = serie.iloc[0][:120]
        except Exception:
            exemplo = ""

        c1, c2 = st.columns([1.1, 1.6])

        with c1:
            st.text_input(
                "Coluna origem",
                value=str(coluna_origem),
                disabled=True,
                key=f"origem_label_{coluna_origem}",
            )

        with c2:
            escolha = st.selectbox(
                f"Mapear para ({coluna_origem})",
                options=opcoes,
                index=opcoes.index(valor_sugerido) if valor_sugerido in opcoes else 0,
                key=f"map_select_{coluna_origem}",
                help=f"Exemplo: {exemplo}" if exemplo else None,
            )
            if escolha:
                mapeamento_editado[str(coluna_origem)] = str(escolha)

    st.session_state["mapeamento_origem"] = mapeamento_editado

    st.markdown("### Prévia do mapeamento final")

    if mapeamento_editado:
        linhas = []
        for origem, alvo in mapeamento_editado.items():
            linhas.append(
                {
                    "Coluna de origem": origem,
                    "Coluna do modelo": alvo,
                }
            )
        st.dataframe(linhas, use_container_width=True, height=260)
    else:
        st.info("Nenhuma coluna foi mapeada ainda.")

    c3, c4 = st.columns([1, 1])

    with c3:
        if st.button("⬅️ Voltar", use_container_width=True):
            st.session_state["etapa_origem"] = "upload"
            st.rerun()

    with c4:
        if st.button("✅ Confirmar mapeamento", use_container_width=True):
            st.session_state["mapeamento_origem"] = mapeamento_editado
            st.session_state["mapeamento_origem_confirmado"] = True
            st.success("Mapeamento confirmado com sucesso.")
            log_debug(
                f"Mapeamento confirmado com {len(mapeamento_editado)} campos",
                "SUCCESS",
            )


# ==========================================================
# MAIN UI
# ==========================================================
def render_origem_dados() -> None:
    st.subheader("Origem dos dados")

    etapa = st.session_state.get("etapa_origem", "upload")

    # ==========================================================
    # ETAPA: UPLOAD
    # ==========================================================
    if etapa == "upload":
        origem = st.selectbox(
            "Selecione a origem",
            ["Planilha", "XML", "Site"],
            key="origem_tipo",
        )

        df_origem = None

        # =========================
        # PLANILHA
        # =========================
        if origem == "Planilha":
            arquivo = st.file_uploader(
                "Envie a planilha",
                type=["xlsx", "xls", "csv", "xlsm", "xlsb"],
                key="upload_planilha_origem",
            )

            if arquivo:
                log_debug("Iniciando leitura da planilha")
                df_origem = ler_planilha_segura(arquivo)

                if df_origem is None or df_origem.empty:
                    log_debug("Erro planilha", "ERROR")
                    st.error("Erro ao ler planilha")
                    return

        # =========================
        # XML
        # =========================
        elif origem == "XML":
            st.warning("XML ainda em construção")
            return

        # =========================
        # SITE
        # =========================
        elif origem == "Site":
            df_origem = render_origem_site()

        if df_origem is None or df_origem.empty:
            return

        st.session_state["df_origem"] = df_origem

        st.divider()
        st.subheader("Pré-visualização dos dados")

        try:
            _render_preview_compacto(df_origem)
            st.success(f"{len(df_origem)} registros carregados")
        except Exception as e:
            log_debug(f"Erro ao gerar preview: {e}", "ERROR")
            st.error("Erro ao gerar preview")
            return

        if st.button("➡️ Continuar para mapeamento", use_container_width=True):
            st.session_state["etapa_origem"] = "mapeamento"
            st.rerun()

    # ==========================================================
    # ETAPA: MAPEAMENTO
    # ==========================================================
    elif etapa == "mapeamento":
        df_origem = _obter_df_origem()

        if df_origem is None:
            st.warning("Nenhum dado de origem foi encontrado.")
            if st.button("⬅️ Voltar", use_container_width=True):
                st.session_state["etapa_origem"] = "upload"
                st.rerun()
            return

        _render_mapeamento(df_origem)
