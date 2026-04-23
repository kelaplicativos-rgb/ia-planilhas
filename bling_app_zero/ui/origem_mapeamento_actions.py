from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.ui.app_helpers import ir_para_etapa, log_debug, safe_df_estrutura
from bling_app_zero.ui.origem_mapeamento_helpers import (
    _aplicar_mapping,
    _campos_bloqueados_automaticos,
    _coluna_descricao_modelo,
    _detectar_operacao,
    _eh_coluna_video,
    _limpar_mapeamento_por_status,
)


def _render_sugestao_agente(df_base: pd.DataFrame, df_modelo: pd.DataFrame) -> None:
    operacao = _detectar_operacao()
    mapping_atual = st.session_state.get("mapping_manual", {}).copy()

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button(
            "🔄 Reprocessar IA",
            use_container_width=True,
            key="btn_reprocessar_agente_mapping",
        ):
            st.session_state["_ia_auto_mapping_executado"] = False
            st.session_state["df_final"] = None
            st.rerun()

    with col2:
        if st.button(
            "🧹 Limpar vermelho/amarelo",
            use_container_width=True,
            key="btn_limpar_vermelho_amarelo_mapping",
        ):
            novo = _limpar_mapeamento_por_status(
                df_base=df_base,
                df_modelo=df_modelo,
                mapping_atual=mapping_atual,
                operacao=operacao,
                modo="erros_revisar",
            )
            st.session_state["mapping_manual"] = novo
            st.session_state["df_final"] = _aplicar_mapping(df_base, df_modelo, novo)
            log_debug(
                "Limpeza seletiva aplicada: campos vermelhos e amarelos foram limpos, preservando os verdes.",
                nivel="INFO",
            )
            st.rerun()

    with col3:
        if st.button(
            "💣 Limpar tudo",
            use_container_width=True,
            key="btn_limpar_tudo_mapping",
        ):
            novo = _limpar_mapeamento_por_status(
                df_base=df_base,
                df_modelo=df_modelo,
                mapping_atual=mapping_atual,
                operacao=operacao,
                modo="tudo",
            )
            st.session_state["mapping_manual"] = novo
            st.session_state["df_final"] = _aplicar_mapping(df_base, df_modelo, novo)
            log_debug("Limpeza total aplicada no mapeamento manual.", nivel="INFO")
            st.rerun()


def _render_resumo_agente() -> None:
    pacote = st.session_state.get("agent_ui_package", {})
    if not isinstance(pacote, dict) or not pacote:
        return

    diagnostico = pacote.get("diagnostico", {}) if isinstance(pacote.get("diagnostico"), dict) else {}
    obrigatorios = pacote.get("obrigatorios", []) if isinstance(pacote.get("obrigatorios"), list) else []

    with st.expander("Diagnóstico da IA", expanded=False):
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Campos mapeados", int(diagnostico.get("mapeados", 0) or 0))
        with c2:
            st.metric("Faltando", int(diagnostico.get("faltando", 0) or 0))
        with c3:
            st.metric("Duplicidade", "Sim" if bool(pacote.get("tem_duplicidade", False)) else "Não")

        faltando_obrigatorios = diagnostico.get("faltando_obrigatorios", [])
        if obrigatorios:
            st.caption(f"Obrigatórios monitorados: {', '.join([str(x) for x in obrigatorios])}")

        if faltando_obrigatorios:
            st.warning(
                "Campos obrigatórios ainda sem sugestão: "
                + ", ".join([str(x) for x in faltando_obrigatorios])
            )
        else:
            st.success("IA fechou os obrigatórios automaticamente.")


def _validar_mapping_pronto(df_modelo: pd.DataFrame, mapping: dict[str, str]) -> tuple[bool, list[str]]:
    erros = []
    operacao = _detectar_operacao()

    coluna_descricao = _coluna_descricao_modelo(df_modelo)
    if operacao == "cadastro" and coluna_descricao and not str(mapping.get(coluna_descricao, "") or "").strip():
        erros.append("Mapeie a coluna de descrição.")

    bloqueados = _campos_bloqueados_automaticos(df_modelo, operacao)

    usados = []
    for coluna_modelo, coluna_origem in mapping.items():
        coluna_modelo = str(coluna_modelo)
        coluna_origem = str(coluna_origem or "").strip()

        if not coluna_origem:
            continue

        if coluna_modelo in bloqueados or _eh_coluna_video(coluna_origem):
            continue

        usados.append(coluna_origem)

    duplicados = sorted({c for c in usados if usados.count(c) > 1})
    if duplicados:
        erros.append(f"Existem colunas de origem usadas mais de uma vez: {', '.join(duplicados)}")

    return len(erros) == 0, erros


def _render_botoes_fluxo(df_base: pd.DataFrame, df_modelo: pd.DataFrame) -> None:
    mapping = st.session_state.get("mapping_manual", {}).copy()
    valido, erros = _validar_mapping_pronto(df_modelo, mapping)

    col1, col2 = st.columns(2)

    with col1:
        if st.button(
            "✅ Regenerar resultado final",
            use_container_width=True,
            key="btn_gerar_resultado_final_mapping",
        ):
            if not valido:
                for erro in erros:
                    st.error(erro)
                return

            df_final = _aplicar_mapping(df_base, df_modelo, mapping)
            st.session_state["df_final"] = df_final
            st.success("Resultado final gerado com sucesso.")
            st.rerun()

    with col2:
        if st.button(
            "➡️ Ir para preview final",
            use_container_width=True,
            key="btn_ir_preview_final",
        ):
            df_final = st.session_state.get("df_final")
            if not safe_df_estrutura(df_final):
                if not valido:
                    for erro in erros:
                        st.error(erro)
                    return

                df_final = _aplicar_mapping(df_base, df_modelo, mapping)
                st.session_state["df_final"] = df_final

            ir_para_etapa("preview_final")
            st.rerun()
