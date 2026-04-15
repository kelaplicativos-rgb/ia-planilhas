from __future__ import annotations

from collections.abc import Callable

import pandas as pd
import streamlit as st

from bling_app_zero.ui.origem_mapeamento_core import (
    montar_df_saida_mapeado,
    obter_df_fonte_mapeamento,
    obter_df_modelo_mapeamento,
)
from bling_app_zero.ui.origem_mapeamento_ui import (
    render_formulario_mapeamento,
)
from bling_app_zero.ui.origem_mapeamento_validacao import (
    detectar_duplicidades_mapping,
)

NavCallback = Callable[[], None] | None

ETAPAS_VALIDAS_ORIGEM = {"origem", "mapeamento", "final"}


# =========================================================
# HELPERS BASE
# =========================================================
def _safe_dict(valor) -> dict:
    try:
        return dict(valor or {})
    except Exception:
        return {}


def _safe_copy_df(df):
    try:
        return df.copy()
    except Exception:
        return df


def _tem_estrutura_df(df) -> bool:
    try:
        return df is not None and hasattr(df, "columns") and len(df.columns) > 0
    except Exception:
        return False


def _safe_str(valor) -> str:
    try:
        if valor is None:
            return ""
        texto = str(valor).strip()
        if texto.lower() in {"none", "nan", "nat"}:
            return ""
        return texto
    except Exception:
        return ""


def _normalizar_etapa(valor, default: str = "origem") -> str:
    etapa = _safe_str(valor or default).lower()
    if etapa not in ETAPAS_VALIDAS_ORIGEM:
        return default
    return etapa


def get_etapa_mapeamento() -> str:
    for chave in ("etapa_origem", "etapa", "etapa_fluxo"):
        etapa = _normalizar_etapa(st.session_state.get(chave), "")
        if etapa:
            return etapa
    return "origem"


def set_etapa_mapeamento(etapa: str) -> None:
    etapa_normalizada = _normalizar_etapa(etapa, "origem")
    st.session_state["etapa_origem"] = etapa_normalizada
    st.session_state["etapa"] = etapa_normalizada
    st.session_state["etapa_fluxo"] = etapa_normalizada


def garantir_estado_mapeamento() -> None:
    defaults = {
        "mapping_origem": {},
        "mapping_origem_rascunho": {},
        "mapeamento_retorno_preservado": False,
        "deposito_nome": "",
        "df_preview_mapeamento": None,
    }
    for chave, valor in defaults.items():
        if chave not in st.session_state:
            st.session_state[chave] = valor

    st.session_state["mapping_origem"] = _safe_dict(st.session_state.get("mapping_origem"))
    st.session_state["mapping_origem_rascunho"] = _safe_dict(
        st.session_state.get("mapping_origem_rascunho")
    )


def _persistir_df_saida(df_saida) -> None:
    if not _tem_estrutura_df(df_saida):
        return

    st.session_state["df_saida"] = _safe_copy_df(df_saida)
    st.session_state["df_final"] = _safe_copy_df(df_saida)
    st.session_state["df_preview_mapeamento"] = _safe_copy_df(df_saida)


def _persistir_mapping(mapping: dict) -> None:
    st.session_state["mapping_origem"] = _safe_dict(mapping)
    st.session_state["mapping_origem_rascunho"] = _safe_dict(mapping)


def _restaurar_mapping_inicial() -> dict:
    mapping_salvo = _safe_dict(st.session_state.get("mapping_origem"))
    if mapping_salvo:
        return mapping_salvo

    mapping_rascunho = _safe_dict(st.session_state.get("mapping_origem_rascunho"))
    if mapping_rascunho:
        return mapping_rascunho

    return {}


def _navegar(destino: str, callback: NavCallback = None) -> None:
    if callable(callback):
        callback()
        return
    set_etapa_mapeamento(destino)
    st.rerun()


def _voltar_preservando_estado(on_back: NavCallback = None) -> None:
    mapping_atual = _safe_dict(st.session_state.get("mapping_origem_rascunho"))
    if mapping_atual:
        st.session_state["mapping_origem"] = mapping_atual

    df_preview = st.session_state.get("df_preview_mapeamento")
    if _tem_estrutura_df(df_preview):
        st.session_state["df_saida"] = _safe_copy_df(df_preview)
        st.session_state["df_final"] = _safe_copy_df(df_preview)

    st.session_state["mapeamento_retorno_preservado"] = True
    _navegar("origem", on_back)


def _continuar_para_final(
    on_continue: NavCallback = None,
    *,
    erro: bool,
    df_saida=None,
) -> None:
    if erro:
        st.warning("Corrija os campos duplicados antes de continuar.")
        return

    if not _tem_estrutura_df(df_saida):
        st.warning("Nenhum preview válido foi gerado para continuar.")
        return

    _persistir_df_saida(df_saida)
    st.session_state["mapeamento_retorno_preservado"] = True
    _navegar("final", on_continue)


# =========================================================
# HELPERS VISUAIS
# =========================================================
def _inject_css_mapeamento() -> None:
    st.markdown(
        """
        <style>
        .map-topo-card {
            border: 1px solid rgba(128,128,128,0.16);
            border-radius: 18px;
            padding: 14px 16px;
            margin-bottom: 14px;
            background: rgba(255,255,255,0.02);
        }

        .map-kicker {
            font-size: 0.78rem;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            opacity: 0.72;
            font-weight: 700;
            margin-bottom: 6px;
        }

        .map-titulo {
            font-size: 1.16rem;
            font-weight: 700;
            line-height: 1.15;
            margin-bottom: 6px;
        }

        .map-subtitulo {
            font-size: 0.93rem;
            opacity: 0.82;
            line-height: 1.3;
        }

        .map-resumo-box {
            border: 1px solid rgba(128,128,128,0.14);
            border-radius: 14px;
            padding: 12px 14px;
            background: rgba(255,255,255,0.015);
            min-height: 82px;
        }

        .map-resumo-label {
            font-size: 0.75rem;
            opacity: 0.72;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            margin-bottom: 6px;
        }

        .map-resumo-value {
            font-size: 1rem;
            font-weight: 700;
            line-height: 1.2;
        }

        .map-bloco {
            border: 1px solid rgba(128,128,128,0.14);
            border-radius: 16px;
            padding: 14px;
            margin-bottom: 14px;
            background: rgba(255,255,255,0.015);
        }

        .map-bloco-titulo {
            font-size: 0.98rem;
            font-weight: 700;
            margin-bottom: 6px;
        }

        .map-bloco-desc {
            font-size: 0.90rem;
            opacity: 0.82;
            line-height: 1.28;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_topo_visual() -> None:
    st.markdown(
        """
        <div class="map-topo-card">
            <div class="map-kicker">Etapa 2</div>
            <div class="map-titulo">Mapeamento de colunas</div>
            <div class="map-subtitulo">
                Relacione a base de origem com o modelo final, evitando duplicidades e
                validando o preview antes de seguir para a etapa final.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_resumo_operacional(df_fonte: pd.DataFrame, df_modelo: pd.DataFrame) -> None:
    operacao = _safe_str(
        st.session_state.get("tipo_operacao")
        or st.session_state.get("tipo_operacao_bling")
        or st.session_state.get("tipo_operacao_radio")
    )

    origem = _safe_str(
        st.session_state.get("origem_dados_tipo")
        or st.session_state.get("origem_dados_radio")
    )

    linhas = 0
    colunas_origem = 0
    colunas_modelo = 0

    if _tem_estrutura_df(df_fonte):
        try:
            linhas = int(len(df_fonte))
            colunas_origem = int(len(df_fonte.columns))
        except Exception:
            pass

    if _tem_estrutura_df(df_modelo):
        try:
            colunas_modelo = int(len(df_modelo.columns))
        except Exception:
            pass

    c1, c2, c3 = st.columns(3, gap="small")

    with c1:
        st.markdown(
            f"""
            <div class="map-resumo-box">
                <div class="map-resumo-label">Operação</div>
                <div class="map-resumo-value">{operacao or "Não definida"}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with c2:
        st.markdown(
            f"""
            <div class="map-resumo-box">
                <div class="map-resumo-label">Origem</div>
                <div class="map-resumo-value">{origem or "Não definida"}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with c3:
        st.markdown(
            f"""
            <div class="map-resumo-box">
                <div class="map-resumo-label">Base</div>
                <div class="map-resumo-value">{linhas} linha(s) · {colunas_origem} origem · {colunas_modelo} modelo</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _render_bloco_info(titulo: str, descricao: str) -> None:
    st.markdown(
        f"""
        <div class="map-bloco">
            <div class="map-bloco-titulo">{titulo}</div>
            <div class="map-bloco-desc">{descricao}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_cabecalho_mapeamento_visual() -> None:
    deposito_atual = _safe_str(st.session_state.get("deposito_nome"))

    st.markdown("### Configuração do mapeamento")
    st.text_input(
        "Nome do Depósito (Bling)",
        value=deposito_atual,
        key="deposito_nome",
        placeholder="Ex: principal, ifood, loja 1",
        help="Esse valor pode ser usado no fluxo de estoque quando a coluna de depósito existir no modelo.",
    )


def _render_preview_curto(df_fonte: pd.DataFrame, df_modelo: pd.DataFrame) -> None:
    st.markdown("### Referência rápida")

    col1, col2 = st.columns(2, gap="small")

    with col1:
        with st.expander("Colunas da origem", expanded=False):
            st.write(list(df_fonte.columns))

    with col2:
        with st.expander("Colunas do modelo", expanded=False):
            st.write(list(df_modelo.columns))


def _render_alertas_duplicidade(duplicidades: dict[str, list[str]]) -> None:
    if not duplicidades:
        st.success("✅ Nenhuma duplicidade detectada no mapeamento atual.")
        return

    mensagens = []
    for coluna_origem, colunas_modelo in duplicidades.items():
        mensagens.append(
            f"'{coluna_origem}' usada em: {', '.join([str(c) for c in colunas_modelo])}"
        )

    st.error("❌ Existe coluna de origem sendo usada mais de uma vez.")
    for msg in mensagens:
        st.write(f"- {msg}")


def _render_preview_mapeamento_visual(
    df_saida: pd.DataFrame,
    duplicidades: dict[str, list[str]],
) -> None:
    st.markdown("### Preview do mapeamento")
    _render_alertas_duplicidade(duplicidades)

    with st.expander("Visualizar preview mapeado", expanded=True):
        st.dataframe(df_saida.head(15), use_container_width=True)


def _render_footer_nav(
    *,
    erro: bool,
    on_back: NavCallback = None,
    on_continue: NavCallback = None,
    df_saida=None,
) -> None:
    st.markdown("---")
    col1, col2 = st.columns(2, gap="small")

    with col1:
        if st.button(
            "⬅️ Voltar para origem",
            use_container_width=True,
            key="mapeamento_btn_voltar_footer",
        ):
            _voltar_preservando_estado(on_back)

    with col2:
        if st.button(
            "➡️ Continuar para preview final",
            use_container_width=True,
            type="primary",
            disabled=erro,
            key="mapeamento_btn_continuar_footer",
        ):
            _continuar_para_final(
                on_continue,
                erro=erro,
                df_saida=df_saida,
            )

        if erro:
            st.caption("Remova as duplicidades para liberar a próxima etapa.")


# =========================================================
# RENDER PRINCIPAL
# =========================================================
def render_origem_mapeamento(
    on_back: NavCallback = None,
    on_continue: NavCallback = None,
) -> None:
    garantir_estado_mapeamento()

    if get_etapa_mapeamento() != "mapeamento":
        return

    _inject_css_mapeamento()
    _render_topo_visual()

    df_fonte = obter_df_fonte_mapeamento()
    df_modelo = obter_df_modelo_mapeamento()

    if not _tem_estrutura_df(df_fonte) or not _tem_estrutura_df(df_modelo):
        st.warning("Dados inválidos para o mapeamento.")
        col1, col2 = st.columns(2, gap="small")

        with col1:
            if st.button(
                "⬅️ Voltar para origem",
                use_container_width=True,
                key="mapeamento_btn_voltar_erro",
            ):
                _voltar_preservando_estado(on_back)

        with col2:
            st.button(
                "➡️ Continuar para preview final",
                use_container_width=True,
                disabled=True,
                key="mapeamento_btn_continuar_erro",
            )
        return

    _render_resumo_operacional(df_fonte, df_modelo)
    _render_bloco_info(
        "Como usar esta etapa",
        "Mapeie cada coluna do modelo para uma coluna da origem. "
        "O campo ID permanece bloqueado e o preview abaixo mostra como a saída final ficará.",
    )
    _render_cabecalho_mapeamento_visual()
    _render_preview_curto(df_fonte, df_modelo)

    st.markdown("---")
    st.markdown("### Formulário de mapeamento")

    mapping_inicial = _restaurar_mapping_inicial()
    mapping_atualizado = render_formulario_mapeamento(
        df_fonte,
        df_modelo,
        mapping_inicial,
    )
    mapping_atualizado = _safe_dict(mapping_atualizado)
    st.session_state["mapping_origem_rascunho"] = _safe_dict(mapping_atualizado)

    duplicidades = detectar_duplicidades_mapping(mapping_atualizado)
    erro = bool(duplicidades)

    if not erro:
        _persistir_mapping(mapping_atualizado)

    df_saida = montar_df_saida_mapeado(df_fonte, df_modelo, mapping_atualizado)

    if _tem_estrutura_df(df_saida):
        _persistir_df_saida(df_saida)
        _render_preview_mapeamento_visual(df_saida, duplicidades)
    else:
        st.warning("Nenhum preview válido foi gerado com o mapeamento atual.")

    _render_footer_nav(
        erro=erro,
        on_back=on_back,
        on_continue=on_continue,
        df_saida=df_saida,
    )
  
