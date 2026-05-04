from __future__ import annotations

import re

import pandas as pd
import streamlit as st

from bling_app_zero.ui.app_core_flow import set_etapa_segura
from bling_app_zero.ui.app_helpers import ir_para_etapa, safe_df_dados, safe_df_estrutura, voltar_etapa_anterior
from bling_app_zero.ui.gtin_panel import render_gtin_panel
from bling_app_zero.ui.origem_mapeamento_actions import _render_botoes_fluxo, _render_resumo_agente, _render_sugestao_agente
from bling_app_zero.ui.origem_mapeamento_confidence import _render_revisao_manual
from bling_app_zero.ui.origem_mapeamento_helpers import (
    _aplicar_mapping,
    _detectar_operacao,
    _destino_modelo_semantico,
    _executar_ia_autonoma,
    _garantir_etapa_mapeamento_ativa,
    _inicializar_mapping,
    _normalizar_texto_busca,
    _obter_df_base,
    _obter_df_modelo,
    _preview_mapping,
    _render_status_base,
    _sincronizar_deposito_nome,
)


def _norm_coluna(valor: object) -> str:
    texto = str(valor or "").strip().lower()
    texto = texto.translate(str.maketrans("áàãâéêíóôõúç", "aaaaeeiooouc"))
    return re.sub(r"[^a-z0-9]+", " ", texto).strip()


def _valor_preco_valido(valor: object) -> bool:
    texto = str(valor or "").strip()
    if not texto:
        return False
    texto = texto.replace("R$", "").replace("r$", "").replace(" ", "")
    if "," in texto and "." in texto:
        texto = texto.replace(".", "").replace(",", ".")
    else:
        texto = texto.replace(",", ".")
    texto = re.sub(r"[^0-9.\-]", "", texto)
    try:
        return float(texto) > 0
    except Exception:
        return False


def _serie_tem_preco_valido(serie: pd.Series) -> bool:
    if not isinstance(serie, pd.Series):
        return False
    return bool(serie.apply(_valor_preco_valido).any())


def _coluna_preco_destino(df_modelo: pd.DataFrame, operacao: str) -> str:
    if not safe_df_estrutura(df_modelo):
        return ""
    colunas = [str(c) for c in df_modelo.columns.tolist()]
    prioridades = [
        "Preço unitário (OBRIGATÓRIO)", "Preco unitario (OBRIGATORIO)",
        "Preço unitário", "Preco unitario", "Preço", "Preco", "Valor",
    ]
    if operacao != "estoque":
        prioridades = ["Preço de venda", "Preco de venda"] + prioridades
    mapa = {_norm_coluna(c): c for c in colunas}
    for prioridade in prioridades:
        achado = mapa.get(_norm_coluna(prioridade))
        if achado:
            return achado
    for col in colunas:
        nome = _norm_coluna(col)
        if "preco" in nome or "valor" in nome or "unitario" in nome:
            return col
    return ""


def _coluna_preco_origem(df_base: pd.DataFrame, destino: str) -> str:
    if not safe_df_dados(df_base):
        return ""
    colunas = [str(c) for c in df_base.columns.tolist()]
    mapa = {_norm_coluna(c): c for c in colunas}
    if destino:
        achado = mapa.get(_norm_coluna(destino))
        if achado and _serie_tem_preco_valido(df_base[achado]):
            return achado
    for prioridade in ["Preço unitário (OBRIGATÓRIO)", "Preço unitário", "Preço de venda", "Preço", "Preco", "Valor", "price"]:
        achado = mapa.get(_norm_coluna(prioridade))
        if achado and _serie_tem_preco_valido(df_base[achado]):
            return achado
    for col in colunas:
        nome = _norm_coluna(col)
        if ("preco" in nome or "valor" in nome or "price" in nome) and _serie_tem_preco_valido(df_base[col]):
            return col
    return ""


def _garantir_preco_unitario_no_final(df_base: pd.DataFrame, df_modelo: pd.DataFrame, operacao: str) -> None:
    df_final = st.session_state.get("df_final")
    if not safe_df_estrutura(df_final) or not safe_df_dados(df_base):
        return
    destino = _coluna_preco_destino(df_modelo, operacao)
    if not destino or destino not in df_final.columns or _serie_tem_preco_valido(df_final[destino]):
        return
    origem_preco = _coluna_preco_origem(df_base, destino)
    if not origem_preco or origem_preco not in df_base.columns:
        return
    corrigido = df_final.copy().fillna("")
    corrigido.loc[:, destino] = df_base[origem_preco].astype(str).fillna("").values[: len(corrigido)]
    st.session_state["df_final"] = corrigido
    st.session_state["df_saida"] = corrigido.copy()
    st.session_state["_preco_unitario_corrigido_mapping"] = {"destino": destino, "origem": origem_preco, "linhas": int(len(corrigido))}


def _colunas_descricao_modelo(df_modelo: pd.DataFrame) -> list[str]:
    if not safe_df_estrutura(df_modelo):
        return []

    colunas = [str(c) for c in df_modelo.columns.tolist()]
    prioridades = [
        "Descrição",
        "Descricao",
        "Descrição do produto",
        "Descricao do produto",
        "Nome do produto",
        "Produto",
    ]

    encontrados: list[str] = []
    mapa = {_norm_coluna(c): c for c in colunas}

    for prioridade in prioridades:
        achado = mapa.get(_norm_coluna(prioridade))
        if achado and achado not in encontrados:
            encontrados.append(achado)

    for col in colunas:
        destino = _destino_modelo_semantico(col)
        nome = _normalizar_texto_busca(col)
        if destino in {"descricao", "descricao_curta"} or "descricao" in nome or "descrição" in nome:
            if col not in encontrados:
                encontrados.append(col)

    return encontrados


def _sugerir_coluna_descricao_origem(df_base: pd.DataFrame, destino_modelo: str) -> str:
    if not safe_df_dados(df_base):
        return ""

    colunas = [str(c) for c in df_base.columns.tolist()]
    destino_norm = _normalizar_texto_busca(destino_modelo)

    if "curta" in destino_norm:
        prioridades = ["Descrição curta", "Descricao curta", "Resumo", "Nome", "Produto", "Descrição", "Descricao", "Título", "Titulo"]
    else:
        prioridades = ["Descrição", "Descricao", "Nome", "Produto", "Título", "Titulo", "Descrição curta", "Descricao curta"]

    mapa = {_norm_coluna(c): c for c in colunas}
    for prioridade in prioridades:
        achado = mapa.get(_norm_coluna(prioridade))
        if achado:
            return achado

    melhores: list[tuple[int, str]] = []
    for col in colunas:
        nome = _normalizar_texto_busca(col)
        score = 0
        if "descricao" in nome or "descrição" in nome:
            score += 30
        if "nome" in nome or "produto" in nome or "titulo" in nome or "título" in nome:
            score += 22
        if "complement" in nome:
            score -= 18
        if "video" in nome or "vídeo" in nome:
            score -= 99

        try:
            amostra = df_base[col].dropna().astype(str).head(20).tolist()
            media_tamanho = sum(len(v.strip()) for v in amostra if v.strip()) / max(1, len([v for v in amostra if v.strip()]))
            if media_tamanho >= 8:
                score += 10
            if media_tamanho >= 25 and "curta" not in destino_norm:
                score += 8
        except Exception:
            pass

        if score > 0:
            melhores.append((score, col))

    melhores.sort(key=lambda item: item[0], reverse=True)
    return melhores[0][1] if melhores else ""


def _render_regra_obrigatoria_descricao(df_base: pd.DataFrame, df_modelo: pd.DataFrame, operacao: str) -> bool:
    """Pergunta sempre a correlação da descrição antes da revisão manual geral."""
    destinos_descricao = _colunas_descricao_modelo(df_modelo)
    if not destinos_descricao:
        return True

    st.markdown("### 📝 Descrição do produto")
    st.info(
        "Escolha qual coluna da planilha do fornecedor deve alimentar a descrição do produto no modelo Bling. "
        "Essa escolha manual prevalece sobre a sugestão da IA e fica salva no mapeamento."
    )

    mapping_atual = st.session_state.get("mapping_manual", {})
    if not isinstance(mapping_atual, dict):
        mapping_atual = {}

    opcoes_origem = [""] + [str(c) for c in df_base.columns.tolist()]
    alterou = False
    faltando: list[str] = []

    for destino in destinos_descricao:
        valor_atual = str(mapping_atual.get(destino, "") or "").strip()
        if valor_atual not in df_base.columns:
            valor_atual = _sugerir_coluna_descricao_origem(df_base, destino)
            if valor_atual:
                mapping_atual[destino] = valor_atual
                alterou = True

        index_atual = opcoes_origem.index(valor_atual) if valor_atual in opcoes_origem else 0

        novo_valor = st.selectbox(
            f"Qual coluna do fornecedor corresponde a: {destino}?",
            options=opcoes_origem,
            index=index_atual,
            key=f"map_descricao_obrigatoria_{destino}",
            help="Regra obrigatória: confirme a coluna real de descrição para evitar mapeamento errado.",
        )

        novo_valor = str(novo_valor or "").strip()
        if novo_valor != str(mapping_atual.get(destino, "") or "").strip():
            mapping_atual[destino] = novo_valor
            alterou = True

        if not novo_valor:
            faltando.append(destino)
        elif novo_valor in df_base.columns:
            amostra = df_base[novo_valor].dropna().astype(str).head(5).tolist()
            if amostra:
                st.caption("Amostra da coluna escolhida:")
                st.dataframe(pd.DataFrame({novo_valor: amostra}), use_container_width=True, hide_index=True)

    st.session_state["mapping_manual"] = mapping_atual

    if alterou or not safe_df_estrutura(st.session_state.get("df_final")):
        st.session_state["df_final"] = _aplicar_mapping(df_base, df_modelo, mapping_atual)
        _garantir_preco_unitario_no_final(df_base, df_modelo, operacao)

    if faltando:
        st.warning("Confirme a coluna de descrição antes de seguir. Campos pendentes: " + ", ".join(faltando))
        return False

    st.success("Descrição confirmada e aplicada no preview final.")
    return True


def render_origem_mapeamento() -> None:
    _garantir_etapa_mapeamento_ativa()
    st.subheader("3. Mapeamento com IA")

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

    _sincronizar_deposito_nome()
    _inicializar_mapping(df_base, df_modelo)
    _executar_ia_autonoma(df_base, df_modelo, operacao)
    _garantir_preco_unitario_no_final(df_base, df_modelo, operacao)

    _render_status_base(df_base, df_modelo)
    _render_sugestao_agente(df_base, df_modelo)
    _render_resumo_agente()

    correcao_preco = st.session_state.get("_preco_unitario_corrigido_mapping")
    if isinstance(correcao_preco, dict) and correcao_preco.get("destino"):
        st.success(f"Preço preservado automaticamente: {correcao_preco.get('origem')} ➜ {correcao_preco.get('destino')}")

    descricao_ok = _render_regra_obrigatoria_descricao(df_base, df_modelo, operacao)

    with st.expander("Revisão manual opcional", expanded=not descricao_ok):
        _render_revisao_manual(df_base, df_modelo, operacao)
        _garantir_preco_unitario_no_final(df_base, df_modelo, operacao)

    df_preview = st.session_state.get("df_final")
    if safe_df_estrutura(df_preview):
        _preview_mapping(df_preview)
        st.markdown("### Tratamento de GTIN")
        st.caption("Faça aqui a limpeza ou geração de GTIN antes de seguir para o preview final.")
        render_gtin_panel(df_preview)

    _render_botoes_fluxo(df_base, df_modelo)

    st.markdown("---")
    if st.button("⬅️ Voltar para precificação", use_container_width=True, key="btn_voltar_precificacao_no_rodape_mapping"):
        voltar_etapa_anterior()
