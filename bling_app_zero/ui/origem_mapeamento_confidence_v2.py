from __future__ import annotations

import re
import unicodedata

import pandas as pd
import streamlit as st

from bling_app_zero.ui.mapeamento.mapping_engine import (
    analyze_mapping,
    log_mapping_analysis,
    render_mapping_feedback,
)
from bling_app_zero.ui.mapeamento.source_columns import escolher_df_origem_captura, opcoes_origem_mapeamento
from bling_app_zero.ui.mapeamento_sample_hint import render_amostra_vermelha
from bling_app_zero.ui.origem_mapeamento_helpers import (
    _aplicar_mapping,
    _campos_bloqueados_automaticos,
    _coluna_deposito_modelo,
    _coluna_preco_prioritaria,
    _eh_coluna_video,
)


CAMPOS_MODELO_AUTO_VAZIO = {
    "clonar dados do pai",
    "codigo pai",
    "código pai",
    "variacoes",
    "variações",
    "unidade de medida",
    "condicao do produto",
    "condição do produto",
    "descricao complementar",
    "descrição complementar",
    "gtin ean da embalagem",
    "gtin/ean da embalagem",
    "cross docking",
    "cross-docking",
    "frete gratis",
    "frete grátis",
    "garantia",
    "observacoes",
    "observações",
    "tags",
    "cest",
    "cfop",
    "origem",
    "ncm",
    "peso liquido kg",
    "peso líquido kg",
    "peso bruto kg",
    "largura embalagem",
    "altura embalagem",
    "comprimento embalagem",
}


def _norm(valor: object) -> str:
    texto = str(valor or "").strip().lower()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(ch for ch in texto if not unicodedata.combining(ch))
    texto = re.sub(r"[^a-z0-9]+", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def _tem(nome: str, termos: tuple[str, ...] | list[str] | set[str]) -> bool:
    return any(t in nome for t in termos)


def _campo_modelo_auto_vazio(coluna_modelo: object) -> bool:
    nome = _norm(coluna_modelo)
    if not nome:
        return True
    if nome in {_norm(v) for v in CAMPOS_MODELO_AUTO_VAZIO}:
        return True
    if "video" in nome or "youtube" in nome:
        return True
    if "descricao complementar" in nome or "descrição complementar" in nome:
        return True
    if "gtin ean da embalagem" in nome or "gtin/ean da embalagem" in nome:
        return True
    if "clonar dados" in nome:
        return True
    if "cross docking" in nome or "cross-docking" in nome:
        return True
    if "condicao do produto" in nome or "condição do produto" in nome:
        return True
    return False


def _destino_modelo(coluna_modelo: object) -> str:
    nome = _norm(coluna_modelo)
    if _campo_modelo_auto_vazio(coluna_modelo):
        return "auto_vazio"
    if _tem(nome, ("imagem", "image", "foto")):
        return "imagens"
    if _tem(nome, ("gtin", "ean", "barra")):
        return "gtin"
    if "ncm" in nome:
        return "ncm"
    if _tem(nome, ("preco", "preço", "valor")):
        return "preco"
    if _tem(nome, ("marca", "brand", "fabricante")):
        return "marca"
    if _tem(nome, ("categoria", "category", "departamento", "segmento")):
        return "categoria"
    if _tem(nome, ("quantidade", "estoque", "saldo", "qtd")):
        return "quantidade"
    if _tem(nome, ("codigo", "código", "sku", "referencia", "referência", "cod no fornecedor")):
        return "codigo"
    if _tem(nome, ("descricao curta", "descrição curta", "resumo")):
        return "descricao_curta"
    if _tem(nome, ("descricao", "descrição", "nome", "produto", "titulo", "título")):
        return "descricao"
    if _tem(nome, ("url produto", "url do produto", "link externo", "link produto", "pagina produto", "página produto")):
        return "link_produto"
    return ""


def _eh_url_produto(coluna: object) -> bool:
    nome = _norm(coluna)
    return bool(
        ("url" in nome or "link" in nome or "pagina" in nome or "página" in nome)
        and "produto" in nome
        and not _tem(nome, ("imagem", "image", "foto"))
    ) or nome in {"link externo", "url do produto", "url produto", "link produto", "pagina do produto", "página do produto"}


def _eh_coluna_imagem(coluna: object) -> bool:
    nome = _norm(coluna)
    if not nome or _eh_url_produto(coluna):
        return False
    if _tem(nome, ("video", "youtube")):
        return False
    if nome == "url imagens externas":
        return True
    if "url" in nome and _tem(nome, ("imagem", "image", "foto")):
        return True
    if "extern" in nome and _tem(nome, ("imagem", "image", "foto")):
        return True
    return nome in {"imagens", "imagem", "images", "image", "foto", "fotos"}


def _opcao_compativel(coluna_modelo: object, coluna_origem: object) -> bool:
    if not str(coluna_origem or "").strip():
        return True

    destino = _destino_modelo(coluna_modelo)
    nome = _norm(coluna_origem)

    if destino == "auto_vazio":
        return False
    if _campo_modelo_auto_vazio(coluna_origem):
        return False

    if destino == "imagens":
        return _eh_coluna_imagem(coluna_origem)
    if destino == "link_produto":
        return _eh_url_produto(coluna_origem)
    if _eh_url_produto(coluna_origem):
        return False

    if destino == "gtin":
        return _tem(nome, ("gtin", "ean", "barra")) and "embalagem" not in nome
    if destino == "ncm":
        return "ncm" in nome
    if destino == "preco":
        return _tem(nome, ("preco", "preço", "valor", "custo", "price"))
    if destino == "marca":
        return _tem(nome, ("marca", "brand", "fabricante"))
    if destino == "categoria":
        return _tem(nome, ("categoria", "category", "departamento", "segmento"))
    if destino == "quantidade":
        return _tem(nome, ("quantidade", "estoque", "saldo", "qtd", "stock"))
    if destino == "codigo":
        return _tem(nome, ("codigo", "código", "sku", "referencia", "referência", "cod"))
    if destino in {"descricao", "descricao_curta"}:
        if _eh_coluna_imagem(coluna_origem) or _eh_url_produto(coluna_origem):
            return False
        return _tem(nome, ("descricao", "descrição", "nome", "produto", "titulo", "título", "resumo"))

    return True


def _score_opcao(coluna_modelo: object, coluna_origem: object) -> int:
    destino = _destino_modelo(coluna_modelo)
    nome = _norm(coluna_origem)
    score = 0

    if destino == "imagens":
        if nome == "url imagens externas":
            return 1000
        if "url" in nome and "imagem" in nome and "extern" in nome:
            return 950
        if "url" in nome and _tem(nome, ("imagem", "image", "foto")):
            return 850
        if _eh_coluna_imagem(coluna_origem):
            return 300
    elif destino == "preco" and _tem(nome, ("preco", "preço", "valor", "custo")):
        score += 500
    elif destino == "gtin" and _tem(nome, ("gtin", "ean", "barra")):
        score += 500
    elif destino == "codigo" and _tem(nome, ("codigo", "código", "sku", "referencia", "referência", "cod")):
        score += 500
    elif destino in {"descricao", "descricao_curta"} and _tem(nome, ("descricao", "descrição", "nome", "produto", "titulo", "título", "resumo")):
        score += 500
    elif destino == "marca" and _tem(nome, ("marca", "brand", "fabricante")):
        score += 500
    elif destino == "categoria" and _tem(nome, ("categoria", "category", "departamento", "segmento")):
        score += 500
    elif destino == "quantidade" and _tem(nome, ("quantidade", "estoque", "saldo", "qtd", "stock")):
        score += 500

    if _norm(coluna_modelo) == nome:
        score += 100
    return score


def _filtrar_opcoes_para_destino(coluna_modelo: object, opcoes_origem: list[str]) -> list[str]:
    opcoes = [opcao for opcao in opcoes_origem if _opcao_compativel(coluna_modelo, opcao)]
    vazias = [opcao for opcao in opcoes if not str(opcao).strip()]
    demais = [opcao for opcao in opcoes if str(opcao).strip()]
    demais.sort(key=lambda opcao: (-_score_opcao(coluna_modelo, opcao), str(opcao).lower()))

    saida: list[str] = []
    for opcao in vazias + demais:
        if opcao not in saida:
            saida.append(opcao)
    return saida or [""]


def _bloqueados_sem_preco(df_modelo: pd.DataFrame, operacao: str) -> set[str]:
    bloqueados = set(_campos_bloqueados_automaticos(df_modelo, operacao))
    coluna_preco = _coluna_preco_prioritaria(df_modelo, operacao)
    if coluna_preco in bloqueados:
        bloqueados.remove(coluna_preco)

    for coluna in [str(c) for c in df_modelo.columns.tolist()] if isinstance(df_modelo, pd.DataFrame) else []:
        if _campo_modelo_auto_vazio(coluna):
            bloqueados.add(coluna)

    return bloqueados


def _badge(titulo: str, subtitulo: str = "") -> None:
    st.markdown(f"**{titulo}**")
    if subtitulo:
        st.caption(subtitulo)


def _status_basico(df_base: pd.DataFrame, coluna_modelo: str, coluna_origem: str) -> tuple[str, str]:
    if _eh_coluna_video(coluna_modelo) or _campo_modelo_auto_vazio(coluna_modelo):
        return "OFF", "Campo mantido vazio automaticamente."
    if not coluna_origem:
        return "PENDENTE", "Escolha uma coluna real da origem."
    if coluna_origem not in df_base.columns:
        return "ERRO", "Coluna nao encontrada na origem."
    if _eh_coluna_video(coluna_origem) or not _opcao_compativel(coluna_modelo, coluna_origem):
        return "ERRO", "Origem incompatível com este campo."

    analise = analyze_mapping(df_base, coluna_modelo, coluna_origem)
    if analise.status == "valid":
        return "OK", f"Correlação real: {int(analise.confidence * 100)}%"
    if analise.status == "warning":
        return "ATENÇÃO", f"Correlação incerta: {int(analise.confidence * 100)}%"
    return "ERRO", f"Correlação inválida: {int(analise.confidence * 100)}%"


def _render_resumo(df_origem: pd.DataFrame, df_modelo: pd.DataFrame, mapping: dict[str, str], bloqueados: set[str]) -> None:
    total = len(df_modelo.columns)
    preenchidos = 0
    pendentes = 0
    automaticos = 0
    invalidos = 0
    alertas = 0

    for coluna in [str(c) for c in df_modelo.columns.tolist()]:
        origem = str(mapping.get(coluna, "") or "").strip()
        if coluna in bloqueados:
            automaticos += 1
        elif origem:
            if not _opcao_compativel(coluna, origem):
                invalidos += 1
            else:
                analise = analyze_mapping(df_origem, coluna, origem)
                if analise.status == "invalid":
                    invalidos += 1
                elif analise.status == "warning":
                    alertas += 1
                else:
                    preenchidos += 1
        else:
            pendentes += 1

    st.caption(
        f"Origem/captura: {len(df_origem.columns)} colunas | Modelo: {total} | "
        f"Válidos: {preenchidos} | Alertas: {alertas} | Inválidos: {invalidos} | "
        f"Pendentes: {pendentes} | Automáticos: {automaticos}"
    )


def _ordenar_colunas(df_modelo: pd.DataFrame, mapping: dict[str, str], bloqueados: set[str]) -> list[str]:
    itens: list[tuple[int, str, str]] = []
    for coluna in [str(c) for c in df_modelo.columns.tolist()]:
        if coluna in bloqueados:
            ordem = 3
        elif not str(mapping.get(coluna, "") or "").strip():
            ordem = 0
        else:
            ordem = 2
        itens.append((ordem, coluna.lower(), coluna))
    itens.sort(key=lambda item: (item[0], item[1]))
    return [coluna for _, _, coluna in itens]


def _render_feedback_correlacao(df_origem: pd.DataFrame, coluna_modelo: str, coluna_origem: str) -> None:
    if coluna_origem and not _opcao_compativel(coluna_modelo, coluna_origem):
        st.error("Correlação inválida: esta coluna não pertence ao tipo de campo selecionado.")
        return
    analise = analyze_mapping(df_origem, coluna_modelo, coluna_origem)
    log_mapping_analysis(analise)
    render_mapping_feedback(analise)


def _render_revisao_manual(df_base: pd.DataFrame, df_modelo: pd.DataFrame, operacao: str) -> None:
    st.caption("Ajuste manual. O seletor agora filtra por tipo de campo para não mostrar colunas lixo.")

    if not isinstance(df_base, pd.DataFrame) or df_base.empty or not isinstance(df_modelo, pd.DataFrame):
        st.warning("Base ou modelo invalido para mapeamento.")
        return

    df_origem = escolher_df_origem_captura(st.session_state)
    if not isinstance(df_origem, pd.DataFrame) or df_origem.empty:
        df_origem = df_base

    opcoes_origem_global = opcoes_origem_mapeamento(
        df_origem,
        df_modelo,
        incluir_vazio=True,
        bloquear_video=True,
        video_checker=_eh_coluna_video,
    )
    bloqueados = _bloqueados_sem_preco(df_modelo, operacao)
    mapping_atual = st.session_state.get("mapping_manual", {})
    if not isinstance(mapping_atual, dict):
        mapping_atual = {}
    mapping_atual = mapping_atual.copy()

    _render_resumo(df_origem, df_modelo, mapping_atual, bloqueados)

    for coluna_modelo in _ordenar_colunas(df_modelo, mapping_atual, bloqueados):
        if coluna_modelo in bloqueados:
            motivo = "campo mantido vazio automaticamente"
            if _eh_coluna_video(coluna_modelo):
                motivo = "video fica vazio"
            elif coluna_modelo == _coluna_deposito_modelo(df_modelo) and operacao == "estoque":
                motivo = "deposito fixo da operacao"
            _badge(f"AUTO {coluna_modelo}", motivo)
            mapping_atual[coluna_modelo] = ""
            continue

        opcoes_origem = _filtrar_opcoes_para_destino(coluna_modelo, opcoes_origem_global)

        valor_atual = str(mapping_atual.get(coluna_modelo, "") or "").strip()
        if valor_atual not in opcoes_origem or _eh_coluna_video(valor_atual) or not _opcao_compativel(coluna_modelo, valor_atual):
            valor_atual = ""
            mapping_atual[coluna_modelo] = ""

        status, detalhe = _status_basico(df_origem, coluna_modelo, valor_atual)
        _badge(f"{status} {coluna_modelo}", detalhe)

        novo_valor = st.selectbox(
            f"{coluna_modelo}",
            options=opcoes_origem,
            index=opcoes_origem.index(valor_atual) if valor_atual in opcoes_origem else 0,
            key=f"map_{coluna_modelo}",
            help="Escolha somente uma coluna real e compatível com este campo.",
        )

        novo_valor = str(novo_valor or "").strip()
        mapping_atual[coluna_modelo] = "" if _eh_coluna_video(novo_valor) else novo_valor

        if novo_valor:
            _render_feedback_correlacao(df_origem, coluna_modelo, novo_valor)
            render_amostra_vermelha(df_origem, novo_valor, prefixo="Selecionado")
        else:
            _render_feedback_correlacao(df_origem, coluna_modelo, "")

    for coluna_modelo in [str(c) for c in df_modelo.columns.tolist()]:
        if _eh_coluna_video(coluna_modelo) or _campo_modelo_auto_vazio(coluna_modelo):
            mapping_atual[coluna_modelo] = ""

    st.session_state["mapping_manual"] = mapping_atual
    st.session_state["df_final"] = _aplicar_mapping(df_base, df_modelo, mapping_atual)
