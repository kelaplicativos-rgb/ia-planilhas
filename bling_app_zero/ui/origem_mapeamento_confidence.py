from __future__ import annotations

import html as html_lib

import pandas as pd
import streamlit as st

from bling_app_zero.ui.origem_mapeamento_helpers import (
    MAP_DESTINOS_SEMANTICOS,
    _campos_bloqueados_automaticos,
    _coluna_deposito_modelo,
    _coluna_preco_prioritaria,
    _destino_modelo_semantico,
    _eh_coluna_video,
    _inferir_tipo_coluna,
    _normalizar_texto_busca,
    _aplicar_mapping,
    _score_coluna_para_destino,
    _detectar_operacao,
    _preview_mapping,
    normalizar_texto,
)


def _montar_badge_html(
    icone: str,
    titulo: str,
    subtitulo: str = "",
    fundo: str = "#F3F4F6",
    borda: str = "#D1D5DB",
    texto: str = "#111827",
) -> str:
    subtitulo_html = ""
    if subtitulo:
        subtitulo_html = (
            f"<div style='font-size:12px; color:{texto}; opacity:0.88; margin-top:2px;'>"
            f"{html_lib.escape(subtitulo)}"
            f"</div>"
        )

    return f"""
    <div style="
        background:{fundo};
        border:1px solid {borda};
        border-left:6px solid {borda};
        color:{texto};
        border-radius:10px;
        padding:10px 12px;
        margin:10px 0 8px 0;
    ">
        <div style="font-weight:700; font-size:14px;">
            {html_lib.escape(icone)} {html_lib.escape(titulo)}
        </div>
        {subtitulo_html}
    </div>
    """


def _detalhe_confianca_mapeamento(
    df_base: pd.DataFrame,
    coluna_modelo: str,
    coluna_origem: str,
) -> dict[str, object]:
    coluna_modelo = str(coluna_modelo or "").strip()
    coluna_origem = str(coluna_origem or "").strip()

    if _eh_coluna_video(coluna_modelo):
        return {
            "status": "auto",
            "emoji": "🚫",
            "titulo": f"{coluna_modelo} bloqueado automaticamente",
            "subtitulo": "Campo de vídeo mantido vazio para evitar propaganda do fornecedor.",
            "pct": 0,
            "cor_fundo": "#F8FAFC",
            "cor_borda": "#94A3B8",
            "cor_texto": "#334155",
        }

    if not coluna_origem or coluna_origem not in df_base.columns:
        return {
            "status": "erro",
            "emoji": "🔴",
            "titulo": f"{coluna_modelo} sem correspondência",
            "subtitulo": "Selecione manualmente uma coluna de origem.",
            "pct": 0,
            "cor_fundo": "#FEF2F2",
            "cor_borda": "#EF4444",
            "cor_texto": "#991B1B",
        }

    if _eh_coluna_video(coluna_origem):
        return {
            "status": "erro",
            "emoji": "🔴",
            "titulo": f"{coluna_modelo} usando coluna de vídeo",
            "subtitulo": "Vídeo foi bloqueado porque costuma trazer propaganda do fornecedor.",
            "pct": 0,
            "cor_fundo": "#FEF2F2",
            "cor_borda": "#EF4444",
            "cor_texto": "#991B1B",
        }

    destino = _destino_modelo_semantico(coluna_modelo)
    nome_modelo_n = normalizar_texto(coluna_modelo)
    nome_origem_n = normalizar_texto(coluna_origem)
    mapping_sugerido = st.session_state.get("mapping_sugerido", {})
    sugerido_pela_ia = str(mapping_sugerido.get(coluna_modelo, "") or "").strip()
    foi_sugerido_igual = sugerido_pela_ia == coluna_origem

    inferencia_origem = _inferir_tipo_coluna(coluna_origem, df_base[coluna_origem])
    score_semantico = 0
    if destino:
        score_semantico = _score_coluna_para_destino(
            coluna_origem,
            df_base[coluna_origem],
            destino,
        )

    igualdade_total = nome_modelo_n == nome_origem_n
    tipo_confirmado = bool(destino) and inferencia_origem == destino

    pct = 20
    motivos: list[str] = []

    if igualdade_total:
        pct += 45
        motivos.append("nome idêntico")

    if foi_sugerido_igual:
        pct += 15
        motivos.append("sugestão da IA")

    if tipo_confirmado:
        pct += 20
        motivos.append("tipo confirmado")

    if score_semantico >= 18:
        pct += 10
        motivos.append("semântica muito forte")
    elif score_semantico >= 12:
        pct += 8
        motivos.append("semântica forte")
    elif score_semantico >= 8:
        pct += 5
        motivos.append("semântica parcial")

    nome_origem_busca = _normalizar_texto_busca(coluna_origem)
    for alias in MAP_DESTINOS_SEMANTICOS.get(destino, []):
        if alias in nome_origem_busca:
            pct += 5
            motivos.append("alias compatível")
            break

    pct = min(95, pct)

    if pct >= 80:
        return {
            "status": "ok",
            "emoji": "🟢",
            "titulo": f"{coluna_modelo} confirmado automaticamente",
            "subtitulo": f"Origem: {coluna_origem} • " + ", ".join(motivos or ["alta confiança"]),
            "pct": pct,
            "cor_fundo": "#ECFDF5",
            "cor_borda": "#10B981",
            "cor_texto": "#065F46",
        }

    if pct >= 55:
        return {
            "status": "revisar",
            "emoji": "🟡",
            "titulo": f"{coluna_modelo} com correspondência provável",
            "subtitulo": f"Origem: {coluna_origem} • revise por segurança",
            "pct": pct,
            "cor_fundo": "#FFFBEB",
            "cor_borda": "#F59E0B",
            "cor_texto": "#92400E",
        }

    return {
        "status": "erro",
        "emoji": "🔴",
        "titulo": f"{coluna_modelo} precisa de atenção",
        "subtitulo": f"Origem atual: {coluna_origem} • baixa confiança",
        "pct": pct,
        "cor_fundo": "#FEF2F2",
        "cor_borda": "#EF4444",
        "cor_texto": "#991B1B",
    }


def _render_resumo_confianca_mapeamento(
    df_base: pd.DataFrame,
    df_modelo: pd.DataFrame,
    mapping_atual: dict[str, str],
    operacao: str,
) -> None:
    bloqueados = _campos_bloqueados_automaticos(df_modelo, operacao)
    stats = {"ok": 0, "revisar": 0, "erro": 0, "auto": 0}

    for coluna_modelo in [str(c) for c in df_modelo.columns.tolist()]:
        if coluna_modelo in bloqueados and not _eh_coluna_video(coluna_modelo):
            stats["auto"] += 1
            continue

        detalhe = _detalhe_confianca_mapeamento(
            df_base=df_base,
            coluna_modelo=coluna_modelo,
            coluna_origem=str(mapping_atual.get(coluna_modelo, "") or "").strip(),
        )
        stats[detalhe["status"]] = stats.get(detalhe["status"], 0) + 1

    total_validaveis = stats["ok"] + stats["revisar"] + stats["erro"]
    pct_conclusao = int(((stats["ok"] + stats["revisar"]) / total_validaveis) * 100) if total_validaveis else 100

    st.markdown(
        _montar_badge_html(
            icone="🧭",
            titulo=f"Mapa visual do mapeamento • {pct_conclusao}% pronto",
            subtitulo=(
                f"🔴 Corrigir: {stats['erro']}   •   "
                f"🟡 Revisar: {stats['revisar']}   •   "
                f"🟢 Confirmados: {stats['ok']}   •   "
                f"🤖/🚫 Automáticos: {stats['auto']}"
            ),
            fundo="#F8FAFC",
            borda="#CBD5E1",
            texto="#0F172A",
        ),
        unsafe_allow_html=True,
    )


def _ordem_status_visual(status: str) -> int:
    ordem = {
        "erro": 0,
        "revisar": 1,
        "ok": 2,
        "auto": 3,
    }
    return ordem.get(str(status or "").strip().lower(), 99)


def _ordenar_colunas_para_revisao(
    df_base: pd.DataFrame,
    df_modelo: pd.DataFrame,
    mapping_atual: dict[str, str],
    operacao: str,
) -> list[str]:
    colunas_modelo = [str(c) for c in df_modelo.columns.tolist()]
    bloqueados = _campos_bloqueados_automaticos(df_modelo, operacao)

    itens: list[tuple[int, str, str]] = []

    for coluna_modelo in colunas_modelo:
        if coluna_modelo in bloqueados:
            status = "auto"
        else:
            detalhe = _detalhe_confianca_mapeamento(
                df_base=df_base,
                coluna_modelo=coluna_modelo,
                coluna_origem=str(mapping_atual.get(coluna_modelo, "") or "").strip(),
            )
            status = str(detalhe.get("status", "") or "")

        itens.append((_ordem_status_visual(status), coluna_modelo.lower(), coluna_modelo))

    itens.sort(key=lambda x: (x[0], x[1]))
    return [coluna_modelo for _, _, coluna_modelo in itens]


def _render_revisao_manual(df_base: pd.DataFrame, df_modelo: pd.DataFrame, operacao: str) -> None:
    st.caption("Ajuste manual apenas se quiser revisar ou trocar algum vínculo da IA.")

    opcoes_origem = [""] + [str(c) for c in df_base.columns.tolist() if not _eh_coluna_video(c)]
    bloqueados = _campos_bloqueados_automaticos(df_modelo, operacao)
    mapping_atual = st.session_state.get("mapping_manual", {}).copy()

    _render_resumo_confianca_mapeamento(
        df_base=df_base,
        df_modelo=df_modelo,
        mapping_atual=mapping_atual,
        operacao=operacao,
    )

    colunas_ordenadas = _ordenar_colunas_para_revisao(
        df_base=df_base,
        df_modelo=df_modelo,
        mapping_atual=mapping_atual,
        operacao=operacao,
    )

    for coluna_modelo in colunas_ordenadas:
        if coluna_modelo in bloqueados:
            if _eh_coluna_video(coluna_modelo):
                st.markdown(
                    _montar_badge_html(
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
            if coluna_modelo == _coluna_preco_prioritaria(df_modelo, operacao):
                motivo.append("preço calculado")
            if coluna_modelo == _coluna_deposito_modelo(df_modelo) and operacao == "estoque":
                motivo.append("depósito fixo da operação")

            st.markdown(
                _montar_badge_html(
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
        if _eh_coluna_video(valor_atual):
            valor_atual = ""
            mapping_atual[coluna_modelo] = ""

        detalhe = _detalhe_confianca_mapeamento(
            df_base=df_base,
            coluna_modelo=coluna_modelo,
            coluna_origem=valor_atual,
        )

        st.markdown(
            _montar_badge_html(
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

        if valor_atual and valor_atual not in opcoes_coluna and not _eh_coluna_video(valor_atual):
            opcoes_coluna.append(valor_atual)

        index_atual = opcoes_coluna.index(valor_atual) if valor_atual in opcoes_coluna else 0

        novo_valor = st.selectbox(
            f"{detalhe['emoji']} {coluna_modelo}",
            options=opcoes_coluna,
            index=index_atual,
            key=f"map_{coluna_modelo}",
            help=f"Confiança atual: {detalhe['pct']}%",
        )

        if _eh_coluna_video(novo_valor):
            novo_valor = ""

        mapping_atual[coluna_modelo] = novo_valor

    for coluna_modelo in [str(c) for c in df_modelo.columns.tolist()]:
        if _eh_coluna_video(coluna_modelo):
            mapping_atual[coluna_modelo] = ""

    st.session_state["mapping_manual"] = mapping_atual
    st.session_state["df_final"] = _aplicar_mapping(df_base, df_modelo, mapping_atual)
