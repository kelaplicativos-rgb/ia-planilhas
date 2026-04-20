
from __future__ import annotations

import hashlib
import re

import pandas as pd
import streamlit as st

from bling_app_zero.agent.agent_orchestrator import construir_pacote_agente_para_ui
from bling_app_zero.ui.app_helpers import (
    blindar_df_para_bling,
    get_etapa,
    ir_para_etapa,
    normalizar_imagens_pipe,
    normalizar_texto,
    safe_df_dados,
    safe_df_estrutura,
    safe_lower,
    sincronizar_etapa_global,
    voltar_etapa_anterior,
)


def _garantir_etapa_mapeamento_ativa() -> None:
    if get_etapa() != "mapeamento":
        sincronizar_etapa_global("mapeamento")

    st.session_state["_etapa_url_inicializada"] = True
    st.session_state["_ultima_etapa_sincronizada_url"] = "mapeamento"


def _normalizar_texto_busca(valor) -> str:
    texto = str(valor or "").strip().lower()
    texto = re.sub(r"\s+", " ", texto)
    return texto


def _hash_df(df: pd.DataFrame) -> str:
    if not isinstance(df, pd.DataFrame):
        return ""

    try:
        partes = []
        partes.append("|".join([str(c).strip() for c in df.columns.tolist()]))
        amostra = df.head(20).fillna("").astype(str)
        for _, row in amostra.iterrows():
            partes.append("|".join(row.tolist()))
        bruto = "\n".join(partes)
        return hashlib.sha256(bruto.encode("utf-8")).hexdigest()
    except Exception:
        return ""


def _detectar_operacao() -> str:
    operacao = safe_lower(
        st.session_state.get("tipo_operacao")
        or st.session_state.get("tipo_operacao_bling")
        or ""
    )
    if operacao not in {"cadastro", "estoque"}:
        return "cadastro"
    return operacao


def _obter_df_base() -> pd.DataFrame:
    df_precificado = st.session_state.get("df_precificado")
    if safe_df_dados(df_precificado):
        return df_precificado.copy()
    return pd.DataFrame()


def _obter_df_modelo() -> pd.DataFrame:
    df_modelo = st.session_state.get("df_modelo")
    if safe_df_estrutura(df_modelo):
        return df_modelo.copy()
    return pd.DataFrame()


def _colunas_preco_modelo(df_modelo: pd.DataFrame) -> list[str]:
    candidatos = []

    for col in df_modelo.columns:
        nome = str(col)
        n = _normalizar_texto_busca(nome)

        if n in {
            "preco",
            "preço",
            "preco de venda",
            "preço de venda",
            "preco unitario obrigatorio",
            "preço unitário obrigatório",
            "preco unitario",
            "preço unitário",
            "valor",
            "valor venda",
            "valor unitario",
            "valor unitário",
        }:
            candidatos.append(nome)
            continue

        if "preco" in n or "preço" in n or "valor" in n:
            candidatos.append(nome)

    vistos = set()
    saida = []
    for c in candidatos:
        if c not in vistos:
            vistos.add(c)
            saida.append(c)

    return saida


def _coluna_preco_prioritaria(df_modelo: pd.DataFrame, operacao: str) -> str:
    prioridades_estoque = [
        "Preço unitário (OBRIGATÓRIO)",
        "Preço unitário",
        "Preço",
        "Valor",
    ]
    prioridades_cadastro = [
        "Preço de venda",
        "Preço",
        "Valor",
    ]

    colunas = [str(c) for c in df_modelo.columns.tolist()]
    prioridades = prioridades_estoque if operacao == "estoque" else prioridades_cadastro

    for prioridade in prioridades:
        if prioridade in colunas:
            return prioridade

    candidatas = _colunas_preco_modelo(df_modelo)
    return candidatas[0] if candidatas else ""


def _coluna_imagens_modelo(df_modelo: pd.DataFrame) -> str:
    colunas = [str(c) for c in df_modelo.columns.tolist()]

    for prioridade in ["URL Imagens", "Url Imagens", "Imagens", "Imagem"]:
        if prioridade in colunas:
            return prioridade

    for col in colunas:
        n = _normalizar_texto_busca(col)
        if "imagem" in n or "image" in n:
            return col

    return ""


def _coluna_deposito_modelo(df_modelo: pd.DataFrame) -> str:
    colunas = [str(c) for c in df_modelo.columns.tolist()]

    for prioridade in [
        "Depósito (OBRIGATÓRIO)",
        "Depósito",
        "Deposito (OBRIGATÓRIO)",
        "Deposito",
    ]:
        if prioridade in colunas:
            return prioridade

    for col in colunas:
        n = _normalizar_texto_busca(col)
        if "deposito" in n or "depósito" in n:
            return col

    return ""


def _coluna_situacao_modelo(df_modelo: pd.DataFrame) -> str:
    colunas = [str(c) for c in df_modelo.columns.tolist()]

    for prioridade in ["Situação", "Situacao"]:
        if prioridade in colunas:
            return prioridade

    for col in colunas:
        n = _normalizar_texto_busca(col)
        if "situacao" in n or "situação" in n:
            return col

    return ""


def _coluna_descricao_modelo(df_modelo: pd.DataFrame) -> str:
    for prioridade in ["Descrição", "Descricao"]:
        if prioridade in df_modelo.columns:
            return prioridade

    for col in df_modelo.columns:
        n = _normalizar_texto_busca(col)
        if n == "descricao" or n == "descrição":
            return str(col)

    return ""


def _coluna_descricao_curta_modelo(df_modelo: pd.DataFrame) -> str:
    for prioridade in ["Descrição Curta", "Descricao Curta"]:
        if prioridade in df_modelo.columns:
            return prioridade

    for col in df_modelo.columns:
        n = _normalizar_texto_busca(col)
        if "descricao curta" in n or "descrição curta" in n:
            return str(col)

    return ""


def _resetar_mapping_para_modelo(df_modelo: pd.DataFrame) -> dict[str, str]:
    return {str(c): "" for c in df_modelo.columns.tolist()}


def _inicializar_mapping(df_base: pd.DataFrame, df_modelo: pd.DataFrame) -> dict[str, str]:
    hash_base = _hash_df(df_base)
    hash_modelo = _hash_df(df_modelo)

    hash_base_anterior = normalizar_texto(st.session_state.get("mapping_hash_base", ""))
    hash_modelo_anterior = normalizar_texto(st.session_state.get("mapping_hash_modelo", ""))

    precisa_resetar = (
        hash_base != hash_base_anterior
        or hash_modelo != hash_modelo_anterior
        or not isinstance(st.session_state.get("mapping_manual"), dict)
    )

    if precisa_resetar:
        st.session_state["mapping_manual"] = _resetar_mapping_para_modelo(df_modelo)
        st.session_state["mapping_sugerido"] = {}
        st.session_state["agent_ui_package"] = {}
        st.session_state["df_final"] = None

    mapping_salvo = st.session_state.get("mapping_manual", {})
    colunas_modelo = [str(c) for c in df_modelo.columns.tolist()]

    if not isinstance(mapping_salvo, dict):
        mapping_salvo = {}

    mapping_salvo = {k: v for k, v in mapping_salvo.items() if k in colunas_modelo}

    for coluna in colunas_modelo:
        mapping_salvo.setdefault(coluna, "")

    st.session_state["mapping_manual"] = mapping_salvo
    st.session_state["mapping_hash_base"] = hash_base
    st.session_state["mapping_hash_modelo"] = hash_modelo

    return mapping_salvo


def _campos_bloqueados_automaticos(df_modelo: pd.DataFrame, operacao: str) -> set[str]:
    bloqueados = set()

    coluna_preco = _coluna_preco_prioritaria(df_modelo, operacao)
    if coluna_preco:
        bloqueados.add(coluna_preco)

    coluna_deposito = _coluna_deposito_modelo(df_modelo)
    if operacao == "estoque" and coluna_deposito:
        bloqueados.add(coluna_deposito)

    return bloqueados


def _aplicar_defaults_pos_mapping(saida: pd.DataFrame, df_modelo: pd.DataFrame, operacao: str) -> pd.DataFrame:
    base = saida.copy()

    coluna_preco = _coluna_preco_prioritaria(df_modelo, operacao)
    if coluna_preco and "_preco_calculado" in st.session_state.get("df_precificado", pd.DataFrame()).columns:
        df_precificado = st.session_state.get("df_precificado")
        if safe_df_dados(df_precificado):
            base[coluna_preco] = df_precificado["_preco_calculado"]

    if operacao == "estoque":
        coluna_deposito = _coluna_deposito_modelo(df_modelo)
        if coluna_deposito:
            base[coluna_deposito] = normalizar_texto(st.session_state.get("deposito_nome", ""))

    coluna_situacao = _coluna_situacao_modelo(df_modelo)
    if coluna_situacao and coluna_situacao in base.columns:
        serie = base[coluna_situacao].astype(str).str.strip()
        base.loc[serie.eq(""), coluna_situacao] = "Ativo"

    coluna_imagens = _coluna_imagens_modelo(df_modelo)
    if coluna_imagens and coluna_imagens in base.columns:
        base[coluna_imagens] = base[coluna_imagens].apply(normalizar_imagens_pipe)

    return base.fillna("")


def _aplicar_mapping(df_base: pd.DataFrame, df_modelo: pd.DataFrame, mapping: dict[str, str]) -> pd.DataFrame:
    operacao = _detectar_operacao()
    saida = pd.DataFrame(index=df_base.index)

    for coluna_modelo in df_modelo.columns:
        coluna_modelo = str(coluna_modelo)
        coluna_origem = str(mapping.get(coluna_modelo, "") or "").strip()

        if coluna_origem and coluna_origem in df_base.columns:
            saida[coluna_modelo] = df_base[coluna_origem]
        else:
            saida[coluna_modelo] = ""

    saida = _aplicar_defaults_pos_mapping(saida, df_modelo, operacao)

    tipo_operacao_bling = normalizar_texto(st.session_state.get("tipo_operacao_bling", operacao)) or operacao
    deposito_nome = normalizar_texto(st.session_state.get("deposito_nome", ""))

    saida = blindar_df_para_bling(
        df=saida,
        tipo_operacao_bling=tipo_operacao_bling,
        deposito_nome=deposito_nome,
    )

    return saida.fillna("")


def _preview_mapping(df_final: pd.DataFrame) -> None:
    if not safe_df_estrutura(df_final):
        return

    st.markdown("### Preview do resultado mapeado")

    if df_final.empty:
        st.dataframe(pd.DataFrame(columns=df_final.columns), use_container_width=True)
    else:
        st.dataframe(df_final.head(50), use_container_width=True)

    with st.expander("Ver preview completo", expanded=False):
        st.dataframe(df_final.head(200), use_container_width=True)


def _render_status_base(df_base: pd.DataFrame, df_modelo: pd.DataFrame) -> None:
    c1, c2, c3 = st.columns(3)

    with c1:
        st.metric("Linhas base", len(df_base.index) if isinstance(df_base, pd.DataFrame) else 0)

    with c2:
        st.metric("Colunas origem", len(df_base.columns) if isinstance(df_base, pd.DataFrame) else 0)

    with c3:
        st.metric("Colunas modelo", len(df_modelo.columns) if isinstance(df_modelo, pd.DataFrame) else 0)


def _render_sugestao_agente(df_base: pd.DataFrame, df_modelo: pd.DataFrame, operacao: str) -> None:
    col1, col2 = st.columns(2)

    with col1:
        if st.button("✨ Sugerir com IA", use_container_width=True, key="btn_sugerir_agente_mapping"):
            pacote = construir_pacote_agente_para_ui(
                df_base=df_base,
                df_modelo=df_modelo,
                operacao=operacao,
            )

            mapping_recebido = pacote.get("mapping", {}) if isinstance(pacote, dict) else {}
            if not isinstance(mapping_recebido, dict):
                mapping_recebido = {}

            mapping_atual = st.session_state.get("mapping_manual", {}).copy()

            for coluna_modelo in df_modelo.columns:
                coluna_modelo = str(coluna_modelo)
                valor = str(mapping_recebido.get(coluna_modelo, "") or "").strip()
                if valor in df_base.columns:
                    mapping_atual[coluna_modelo] = valor

            st.session_state["mapping_manual"] = mapping_atual
            st.session_state["mapping_sugerido"] = mapping_recebido
            st.session_state["agent_ui_package"] = pacote
            st.session_state["df_final"] = None

            provider = str(pacote.get("provider", "") or "").strip().lower() if isinstance(pacote, dict) else ""
            model = str(pacote.get("model", "") or "").strip() if isinstance(pacote, dict) else ""
            erro = str(pacote.get("erro", "") or "").strip() if isinstance(pacote, dict) else ""

            if provider in {"openai", "fallback_local"} and not erro:
                origem_msg = "GPT" if provider == "openai" else "fallback local"
                sufixo_model = f" ({model})" if model else ""
                st.success(f"Sugestão aplicada com {origem_msg}{sufixo_model}.")
            elif erro:
                st.warning(erro)
            else:
                st.info("Sugestão aplicada com heurística local.")

            st.rerun()

    with col2:
        if st.button("🧹 Zerar mapeamento", use_container_width=True, key="btn_zerar_mapeamento"):
            st.session_state["mapping_manual"] = _resetar_mapping_para_modelo(df_modelo)
            st.session_state["mapping_sugerido"] = {}
            st.session_state["agent_ui_package"] = {}
            st.session_state["df_final"] = None
            st.rerun()


def _render_resumo_agente() -> None:
    pacote = st.session_state.get("agent_ui_package", {})
    if not isinstance(pacote, dict) or not pacote:
        return

    diagnostico = pacote.get("diagnostico", {}) if isinstance(pacote.get("diagnostico"), dict) else {}
    obrigatorios = pacote.get("obrigatorios", []) if isinstance(pacote.get("obrigatorios"), list) else []

    st.markdown("### Diagnóstico da IA")

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


def _render_revisao_manual(df_base: pd.DataFrame, df_modelo: pd.DataFrame, operacao: str) -> None:
    st.markdown("### Revisão do mapeamento")

    opcoes_origem = [""] + [str(c) for c in df_base.columns.tolist()]
    bloqueados = _campos_bloqueados_automaticos(df_modelo, operacao)

    mapping_atual = st.session_state.get("mapping_manual", {}).copy()

    for coluna_modelo in df_modelo.columns:
        coluna_modelo = str(coluna_modelo)

        if coluna_modelo in bloqueados:
            motivo = []
            if coluna_modelo == _coluna_preco_prioritaria(df_modelo, operacao):
                motivo.append("preço calculado")
            if coluna_modelo == _coluna_deposito_modelo(df_modelo) and operacao == "estoque":
                motivo.append("depósito fixo da operação")

            st.text_input(
                coluna_modelo,
                value=f"Preenchido automaticamente ({', '.join(motivo)})",
                disabled=True,
                key=f"map_lock_{coluna_modelo}",
            )
            mapping_atual[coluna_modelo] = ""
            continue

        usados_em_outros = {
            str(v).strip()
            for k, v in mapping_atual.items()
            if str(k) != coluna_modelo and str(v).strip()
        }

        valor_atual = str(mapping_atual.get(coluna_modelo, "") or "").strip()

        opcoes_coluna = [""]
        for opcao in opcoes_origem[1:]:
            if opcao == valor_atual or opcao not in usados_em_outros:
                opcoes_coluna.append(opcao)

        if valor_atual and valor_atual not in opcoes_coluna:
            opcoes_coluna.append(valor_atual)

        index_atual = opcoes_coluna.index(valor_atual) if valor_atual in opcoes_coluna else 0

        novo_valor = st.selectbox(
            f"{coluna_modelo}",
            options=opcoes_coluna,
            index=index_atual,
            key=f"map_{coluna_modelo}",
        )

        mapping_atual[coluna_modelo] = novo_valor

    st.session_state["mapping_manual"] = mapping_atual


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

        if coluna_modelo in bloqueados:
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
        if st.button("✅ Gerar resultado final", use_container_width=True, key="btn_gerar_resultado_final_mapping"):
            if not valido:
                for erro in erros:
                    st.error(erro)
                return

            df_final = _aplicar_mapping(df_base, df_modelo, mapping)
            st.session_state["df_final"] = df_final
            st.success("Resultado final gerado com sucesso.")
            st.rerun()

    with col2:
        if st.button("➡️ Ir para preview final", use_container_width=True, key="btn_ir_preview_final"):
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


def render_origem_mapeamento() -> None:
    _garantir_etapa_mapeamento_ativa()

    st.subheader("3. Mapeamento com IA")
    st.caption(
        "Aqui o sistema usa IA para sugerir o mapeamento entre a base já precificada e o modelo padrão, "
        "mas a revisão manual continua sendo a etapa final de decisão."
    )

    df_base = _obter_df_base()
    df_modelo = _obter_df_modelo()
    operacao = _detectar_operacao()

    if not safe_df_dados(df_base):
        st.warning("Conclua a precificação antes de seguir para o mapeamento.")
        if st.button("⬅️ Voltar para precificação", use_container_width=True, key="btn_voltar_precificacao_mapping"):
            voltar_etapa_anterior()
        return

    if not safe_df_estrutura(df_modelo):
        st.warning("Carregue primeiro o modelo padrão antes de seguir para o mapeamento.")
        if st.button("⬅️ Voltar para origem", use_container_width=True, key="btn_voltar_origem_sem_modelo_mapping"):
            ir_para_etapa("origem")
        return

    _inicializar_mapping(df_base, df_modelo)
    _render_status_base(df_base, df_modelo)
    _render_sugestao_agente(df_base, df_modelo, operacao)
    _render_resumo_agente()
    _render_revisao_manual(df_base, df_modelo, operacao)

    mapping = st.session_state.get("mapping_manual", {}).copy()
    if isinstance(mapping, dict):
        df_preview = _aplicar_mapping(df_base, df_modelo, mapping)
        _preview_mapping(df_preview)

    _render_botoes_fluxo(df_base, df_modelo)

    st.markdown("---")
    if st.button("⬅️ Voltar para precificação", use_container_width=True, key="btn_voltar_precificacao_no_rodape_mapping"):
        voltar_etapa_anterior()
