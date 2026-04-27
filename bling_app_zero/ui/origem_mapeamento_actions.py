from __future__ import annotations

import re

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


def _normalizar_nome_coluna(valor) -> str:
    texto = str(valor or "").strip().lower()
    texto = texto.replace("ç", "c")
    texto = texto.replace("ã", "a").replace("á", "a").replace("à", "a").replace("â", "a")
    texto = texto.replace("é", "e").replace("ê", "e")
    texto = texto.replace("í", "i")
    texto = texto.replace("ó", "o").replace("ô", "o").replace("õ", "o")
    texto = texto.replace("ú", "u")
    texto = re.sub(r"[^a-z0-9]+", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def _colunas_por_termos(df_modelo: pd.DataFrame, termos: list[str]) -> list[str]:
    if not isinstance(df_modelo, pd.DataFrame):
        return []

    encontrados: list[str] = []
    termos_norm = [_normalizar_nome_coluna(t) for t in termos]

    for coluna in df_modelo.columns:
        nome_original = str(coluna)
        nome_norm = _normalizar_nome_coluna(nome_original)

        if any(termo and termo in nome_norm for termo in termos_norm):
            encontrados.append(nome_original)

    return list(dict.fromkeys(encontrados))


def _colunas_obrigatorias_cadastro(df_modelo: pd.DataFrame) -> dict[str, list[str]]:
    descricao = []
    coluna_descricao = _coluna_descricao_modelo(df_modelo)
    if coluna_descricao:
        descricao.append(coluna_descricao)
    else:
        descricao = _colunas_por_termos(
            df_modelo,
            [
                "descricao",
                "descricao do produto",
                "nome",
                "produto",
            ],
        )

    preco = _colunas_por_termos(
        df_modelo,
        [
            "preco de venda",
            "preco venda",
            "preco",
            "valor venda",
            "valor unitario",
            "preco unitario",
            "preço de venda",
            "preço venda",
            "preço",
            "preço unitário",
        ],
    )

    codigo = _colunas_por_termos(
        df_modelo,
        [
            "codigo",
            "codigo do produto",
            "sku",
            "referencia",
            "código",
            "código do produto",
            "referência",
        ],
    )

    return {
        "descricao": descricao,
        "preco": preco,
        "codigo": codigo,
    }


def _colunas_obrigatorias_estoque(df_modelo: pd.DataFrame) -> dict[str, list[str]]:
    codigo = _colunas_por_termos(
        df_modelo,
        [
            "codigo",
            "codigo do produto",
            "sku",
            "referencia",
            "código",
            "código do produto",
            "referência",
        ],
    )

    quantidade = _colunas_por_termos(
        df_modelo,
        [
            "quantidade",
            "estoque",
            "saldo",
            "balanco",
            "balanço",
            "qtd",
            "qtde",
        ],
    )

    deposito = _colunas_por_termos(
        df_modelo,
        [
            "deposito",
            "depósito",
        ],
    )

    preco = _colunas_por_termos(
        df_modelo,
        [
            "preco unitario",
            "preco unitario obrigatorio",
            "preco",
            "valor unitario",
            "preço unitário",
            "preço unitário obrigatório",
            "preço",
        ],
    )

    return {
        "codigo": codigo,
        "quantidade": quantidade,
        "deposito": deposito,
        "preco": preco,
    }


def _campo_tem_mapeamento(mapping: dict[str, str], colunas_modelo: list[str]) -> bool:
    for coluna in colunas_modelo:
        if str(mapping.get(coluna, "") or "").strip():
            return True
    return False


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

    if operacao == "cadastro":
        obrigatorios = _colunas_obrigatorias_cadastro(df_modelo)

        if obrigatorios["descricao"] and not _campo_tem_mapeamento(mapping, obrigatorios["descricao"]):
            erros.append("Mapeie a coluna de descrição/nome do produto para o modelo de cadastro.")

        if obrigatorios["preco"] and not _campo_tem_mapeamento(mapping, obrigatorios["preco"]):
            erros.append(
                "Mapeie uma coluna de preço para o modelo de cadastro ou aplique a precificação antes de continuar."
            )

    if operacao == "estoque":
        obrigatorios = _colunas_obrigatorias_estoque(df_modelo)

        if obrigatorios["codigo"] and not _campo_tem_mapeamento(mapping, obrigatorios["codigo"]):
            erros.append("Mapeie a coluna de código/SKU/referência para atualização de estoque.")

        if obrigatorios["quantidade"] and not _campo_tem_mapeamento(mapping, obrigatorios["quantidade"]):
            erros.append("Mapeie a coluna de quantidade/estoque/saldo para atualização de estoque.")

        if obrigatorios["deposito"]:
            deposito_nome = str(st.session_state.get("deposito_nome", "") or "").strip()
            if not deposito_nome:
                erros.append("Informe o nome do depósito antes de gerar a atualização de estoque.")

    return len(erros) == 0, erros


def _render_alerta_validacao_modelo(df_modelo: pd.DataFrame, mapping: dict[str, str]) -> None:
    valido, erros = _validar_mapping_pronto(df_modelo, mapping)

    with st.expander("Validação do modelo oficial", expanded=not valido):
        if valido:
            st.success("Mapeamento mínimo aprovado para o modelo selecionado.")
            return

        st.error("Ajuste os campos obrigatórios antes de gerar o resultado final.")
        for erro in erros:
            st.write(f"- {erro}")


def _render_botoes_fluxo(df_base: pd.DataFrame, df_modelo: pd.DataFrame) -> None:
    mapping = st.session_state.get("mapping_manual", {}).copy()
    valido, erros = _validar_mapping_pronto(df_modelo, mapping)

    _render_alerta_validacao_modelo(df_modelo, mapping)

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
