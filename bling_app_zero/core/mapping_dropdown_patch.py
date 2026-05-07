from __future__ import annotations

"""Patch do seletor de mapeamento.

Objetivo: no passo de correlação das colunas, mostrar apenas colunas que fazem
parte da captura/varredura do site. Colunas vazias, colunas artificiais e campos
estruturais do modelo Bling não devem aparecer como opção de origem porque só
atrapalham o mapeamento manual.
"""

import re
import unicodedata

import pandas as pd
import streamlit as st


COLUNAS_MODELO_BLING_PARA_OCULTAR = {
    "clonar dados do pai",
    "codigo pai",
    "código pai",
    "variacoes",
    "variações",
    "unidade de medida",
    "tipo do produto",
    "tipo produto",
    "formato",
    "situacao",
    "situação",
    "descricao complementar",
    "descrição complementar",
    "gtin ean da embalagem",
    "gtin/ean da embalagem",
    "largura embalagem",
    "altura embalagem",
    "comprimento embalagem",
    "peso liquido kg",
    "peso líquido kg",
    "peso bruto kg",
    "cross docking",
    "cross-docking",
    "frete gratis",
    "frete grátis",
    "link do video",
    "link do vídeo",
    "url video",
    "url vídeo",
}

VALORES_PADRAO_NAO_CAPTURADOS = {
    "",
    "nan",
    "none",
    "null",
    "ativo",
    "inativo",
    "sim",
    "não",
    "nao",
    "un",
    "unidade",
    "produto",
    "normal",
    "0",
    "0.0",
    "0,00",
}

COLUNAS_URL_PRODUTO_NAO_SAO_IMAGEM = {
    "url do produto",
    "url produto",
    "link do produto",
    "link produto",
    "pagina do produto",
    "página do produto",
    "link externo",
}


def _normalizar_nome(valor: object) -> str:
    texto = str(valor or "").strip().lower()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(ch for ch in texto if not unicodedata.combining(ch))
    texto = re.sub(r"[^a-z0-9]+", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def _normalizar_chave(valor: object) -> str:
    return re.sub(r"[^a-z0-9]+", "", _normalizar_nome(valor))


def _eh_coluna_url_produto(nome_coluna: object) -> bool:
    nome = _normalizar_nome(nome_coluna)
    if nome in {_normalizar_nome(v) for v in COLUNAS_URL_PRODUTO_NAO_SAO_IMAGEM}:
        return True
    return bool(
        ("url" in nome or "link" in nome or "pagina" in nome or "página" in nome)
        and "produto" in nome
        and "imagem" not in nome
        and "image" not in nome
        and "foto" not in nome
    )


def _eh_opcao_valida_para_imagens(nome_coluna: object) -> bool:
    nome = _normalizar_nome(nome_coluna)
    if not nome:
        return False
    if _eh_coluna_url_produto(nome_coluna):
        return False
    if "video" in nome or "youtube" in nome:
        return False
    if nome == "url imagens externas":
        return True
    if "url" in nome and "imagem" in nome:
        return True
    if "url" in nome and "image" in nome:
        return True
    if "url" in nome and "foto" in nome:
        return True
    if "extern" in nome and ("imagem" in nome or "image" in nome or "foto" in nome):
        return True
    if nome in {"imagens", "imagem", "images", "image", "foto", "fotos"}:
        return True
    return False


def _eh_coluna_interna(nome_coluna: object) -> bool:
    nome = str(nome_coluna or "").strip()
    nome_n = _normalizar_nome(nome)
    if not nome:
        return True
    if nome.startswith("_") and nome not in {"_preco_calculado"}:
        return True
    if "video" in nome_n or "youtube" in nome_n:
        return True
    return False


def _eh_coluna_modelo_bling_para_ocultar(nome_coluna: object) -> bool:
    nome = _normalizar_nome(nome_coluna)
    if nome in {_normalizar_nome(v) for v in COLUNAS_MODELO_BLING_PARA_OCULTAR}:
        return True
    if "descricao complementar" in nome or "descrição complementar" in nome:
        return True
    if "gtin ean da embalagem" in nome or "gtin/ean da embalagem" in nome:
        return True
    if "unidade de medida" in nome:
        return True
    if "clonar dados" in nome:
        return True
    if "cross docking" in nome or "cross-docking" in nome:
        return True
    return False


def _serie_tem_dado_capturado(serie: pd.Series) -> bool:
    if not isinstance(serie, pd.Series):
        return False
    valores = serie.fillna("").astype(str).map(lambda v: v.strip())
    valores = valores[valores.ne("")]
    if valores.empty:
        return False

    amostra = valores.head(25).tolist()
    for valor in amostra:
        valor_n = _normalizar_nome(valor)
        if valor_n not in VALORES_PADRAO_NAO_CAPTURADOS:
            return True
    return False


def _score_coluna_origem(nome_coluna: object, serie: pd.Series | None = None) -> int:
    nome = _normalizar_nome(nome_coluna)
    score = 0

    if nome == "url imagens externas":
        score += 500
    elif "url" in nome and "imagem" in nome and "extern" in nome:
        score += 450
    elif "url" in nome and ("imagem" in nome or "image" in nome or "foto" in nome):
        score += 350
    elif nome in {"imagens", "imagem", "images", "image", "foto", "fotos"}:
        score += 60

    if any(t in nome for t in ["descricao", "descrição", "produto", "nome"]):
        score += 120
    if any(t in nome for t in ["preco", "preço", "valor"]):
        score += 110
    if any(t in nome for t in ["codigo", "código", "sku", "referencia", "referência"]):
        score += 100
    if any(t in nome for t in ["gtin", "ean", "barra"]):
        score += 95
    if any(t in nome for t in ["marca", "brand"]):
        score += 80
    if any(t in nome for t in ["categoria", "category"]):
        score += 75
    if any(t in nome for t in ["estoque", "quantidade", "saldo"]):
        score += 70
    if any(t in nome for t in ["link externo", "url produto", "pagina", "página"]):
        score += 65

    if _eh_coluna_url_produto(nome_coluna):
        score -= 200

    if serie is not None and _serie_tem_dado_capturado(serie):
        score += 30

    if _eh_coluna_modelo_bling_para_ocultar(nome_coluna):
        score -= 1000

    return score


def _deduplicar_colunas(colunas: list[str], df_base: pd.DataFrame) -> list[str]:
    melhores: dict[str, tuple[int, str]] = {}
    ordem: dict[str, int] = {}

    for pos, coluna in enumerate(colunas):
        chave = _normalizar_chave(coluna)
        if not chave:
            continue
        ordem.setdefault(chave, pos)
        serie = df_base[coluna] if coluna in df_base.columns else None
        score = _score_coluna_origem(coluna, serie)
        atual = melhores.get(chave)
        if atual is None or score > atual[0]:
            melhores[chave] = (score, coluna)

    itens = []
    for chave, (score, coluna) in melhores.items():
        itens.append((ordem.get(chave, 9999), -score, coluna))
    itens.sort(key=lambda item: (item[0], item[1], item[2].lower()))
    return [coluna for _, _, coluna in itens]


def _colunas_origem_capturadas(df_base: pd.DataFrame) -> list[str]:
    if not isinstance(df_base, pd.DataFrame) or df_base.empty:
        return []

    colunas: list[str] = []
    for coluna in [str(c) for c in df_base.columns.tolist()]:
        if _eh_coluna_interna(coluna):
            continue
        if coluna not in df_base.columns:
            continue

        serie = df_base[coluna]
        tem_dados = _serie_tem_dado_capturado(serie)
        score = _score_coluna_origem(coluna, serie)

        if _eh_coluna_modelo_bling_para_ocultar(coluna):
            continue

        if not tem_dados and score < 300:
            continue

        colunas.append(coluna)

    return _deduplicar_colunas(colunas, df_base)


def _filtrar_opcoes_por_destino(coluna_modelo: str, opcoes: list[str], conf_module) -> list[str]:
    if not hasattr(conf_module, "_eh_destino_imagens_externas"):
        return opcoes
    if not conf_module._eh_destino_imagens_externas(coluna_modelo):
        return opcoes

    filtradas = [opcao for opcao in opcoes if not str(opcao).strip() or _eh_opcao_valida_para_imagens(opcao)]
    return filtradas if filtradas else [""]


def _ordenar_opcoes(coluna_modelo: str, opcoes: list[str], conf_module) -> list[str]:
    opcoes = _filtrar_opcoes_por_destino(coluna_modelo, opcoes, conf_module)
    vazias = [opcao for opcao in opcoes if not str(opcao).strip()]
    demais = [opcao for opcao in opcoes if str(opcao).strip()]

    if hasattr(conf_module, "_eh_destino_imagens_externas") and conf_module._eh_destino_imagens_externas(coluna_modelo):
        demais.sort(key=lambda opcao: (-conf_module._score_opcao_imagem_externa(opcao), str(opcao).lower()))
    else:
        demais.sort(key=lambda opcao: (-_score_coluna_origem(opcao), str(opcao).lower()))

    saida: list[str] = []
    for opcao in vazias + demais:
        if opcao not in saida:
            saida.append(opcao)
    return saida


def install_mapping_dropdown_patch() -> None:
    """Instala patch no render manual do mapeamento."""
    try:
        from bling_app_zero.ui import origem_mapeamento_confidence as conf
        from bling_app_zero.ui.app_helpers import log_debug
    except Exception:
        return

    if getattr(conf, "_dropdown_site_patch_instalado", False):
        return

    def patched_render_revisao_manual(df_base: pd.DataFrame, df_modelo: pd.DataFrame, operacao: str) -> None:
        st.caption("Ajuste manual apenas se quiser revisar ou trocar algum vínculo da IA.")

        colunas_capturadas = _colunas_origem_capturadas(df_base)
        opcoes_origem = [""] + colunas_capturadas

        if colunas_capturadas:
            st.caption(
                f"🔎 Opções filtradas: mostrando apenas {len(colunas_capturadas)} coluna(s) capturada(s) na varredura do site."
            )
        else:
            opcoes_origem = [""] + [str(c) for c in df_base.columns.tolist() if not conf._eh_coluna_video(c)]
            st.warning("Não consegui identificar colunas capturadas com segurança. Mostrando opções disponíveis.")

        bloqueados = conf._bloqueados_sem_preco(df_modelo, operacao)
        mapping_atual = st.session_state.get("mapping_manual", {}).copy()
        if hasattr(conf, "_corrigir_mapping_imagens_externas"):
            mapping_atual = conf._corrigir_mapping_imagens_externas(df_base, df_modelo, mapping_atual)

        conf._render_resumo_confianca_mapeamento(
            df_base=df_base,
            df_modelo=df_modelo,
            mapping_atual=mapping_atual,
            operacao=operacao,
        )

        colunas_ordenadas = conf._ordenar_colunas_para_revisao(
            df_base=df_base,
            df_modelo=df_modelo,
            mapping_atual=mapping_atual,
            operacao=operacao,
        )

        for coluna_modelo in colunas_ordenadas:
            if coluna_modelo in bloqueados:
                if conf._eh_coluna_video(coluna_modelo):
                    st.markdown(
                        conf._montar_badge_html(
                            icone="🚫",
                            titulo=f"{coluna_modelo} mantido vazio",
                            subtitulo="Campo de vídeo bloqueado para não levar URL de propaganda.",
                            fundo="#F8FAFC",
                            borda="#94A3B8",
                            texto="#334155",
                        ),
                        unsafe_allow_html=True,
                    )
                    st.text_input(
                        f"🚫 {coluna_modelo}",
                        value="Bloqueado automaticamente (vídeo fica vazio)",
                        disabled=True,
                        key=f"map_lock_video_{coluna_modelo}",
                    )
                    mapping_atual[coluna_modelo] = ""
                    continue

                motivo = []
                if coluna_modelo == conf._coluna_deposito_modelo(df_modelo) and operacao == "estoque":
                    motivo.append("depósito fixo da operação")

                st.markdown(
                    conf._montar_badge_html(
                        icone="🤖",
                        titulo=f"{coluna_modelo} preenchido automaticamente",
                        subtitulo=", ".join(motivo) if motivo else "campo automático",
                        fundo="#EFF6FF",
                        borda="#3B82F6",
                        texto="#1E3A8A",
                    ),
                    unsafe_allow_html=True,
                )
                st.text_input(
                    f"🤖 {coluna_modelo}",
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
            if conf._eh_coluna_video(valor_atual):
                valor_atual = ""
                mapping_atual[coluna_modelo] = ""

            detalhe = conf._detalhe_confianca_mapeamento(
                df_base=df_base,
                coluna_modelo=coluna_modelo,
                coluna_origem=valor_atual,
            )

            st.markdown(
                conf._montar_badge_html(
                    icone=str(detalhe["emoji"]),
                    titulo=str(detalhe["titulo"]),
                    subtitulo=str(detalhe["subtitulo"]),
                    fundo=str(detalhe["cor_fundo"]),
                    borda=str(detalhe["cor_borda"]),
                    texto=str(detalhe["cor_texto"]),
                ),
                unsafe_allow_html=True,
            )

            opcoes_coluna = [""]
            for opcao in opcoes_origem[1:]:
                if opcao == valor_atual or opcao not in usados_em_outros:
                    opcoes_coluna.append(opcao)

            opcoes_coluna = _filtrar_opcoes_por_destino(coluna_modelo, opcoes_coluna, conf)

            if valor_atual and valor_atual in df_base.columns and valor_atual not in opcoes_coluna and not conf._eh_coluna_video(valor_atual):
                if valor_atual in colunas_capturadas and (
                    not hasattr(conf, "_eh_destino_imagens_externas")
                    or not conf._eh_destino_imagens_externas(coluna_modelo)
                    or _eh_opcao_valida_para_imagens(valor_atual)
                ):
                    opcoes_coluna.append(valor_atual)

            opcoes_coluna = _ordenar_opcoes(coluna_modelo, opcoes_coluna, conf)
            index_atual = opcoes_coluna.index(valor_atual) if valor_atual in opcoes_coluna else 0

            novo_valor = st.selectbox(
                f"{detalhe['emoji']} {coluna_modelo}",
                options=opcoes_coluna,
                index=index_atual,
                key=f"map_{coluna_modelo}",
                help=f"Confiança atual: {detalhe['pct']}%",
            )

            if conf._eh_coluna_video(novo_valor):
                novo_valor = ""

            mapping_atual[coluna_modelo] = novo_valor

        for coluna_modelo in [str(c) for c in df_modelo.columns.tolist()]:
            if conf._eh_coluna_video(coluna_modelo):
                mapping_atual[coluna_modelo] = ""

        if hasattr(conf, "_corrigir_mapping_imagens_externas"):
            mapping_atual = conf._corrigir_mapping_imagens_externas(df_base, df_modelo, mapping_atual)

        st.session_state["mapping_manual"] = mapping_atual
        st.session_state["df_final"] = conf._aplicar_mapping(df_base, df_modelo, mapping_atual)

    conf._render_revisao_manual = patched_render_revisao_manual
    conf._dropdown_site_patch_instalado = True
    try:
        log_debug("Patch do seletor de mapeamento por site instalado.", nivel="INFO")
    except Exception:
        pass
