
from __future__ import annotations

from typing import Any, Optional

import pandas as pd
import streamlit as st

from bling_app_zero.ui.ia_panel import render_ia_panel
from bling_app_zero.ui.origem_mapeamento import render_origem_mapeamento
from bling_app_zero.ui.origem_precificacao import render_origem_precificacao
from bling_app_zero.ui.preview_final import render_preview_final

APP_VERSION = "2.4.1"


# ============================================================
# ESTADO BASE
# ============================================================


def _init_state() -> None:
    defaults = {
        "fluxo_etapa": "origem",
        "tipo_operacao": "",
        "tipo_operacao_bling": "",
        "origem_tipo": "",
        "deposito_nome": "",
        "ia_prompt_home": "",
        "url_site_origem": "",
        "arquivo_origem_nome": "",
        "modelo_cadastro_nome": "",
        "modelo_estoque_nome": "",
        "df_origem": None,
        "df_modelo_base": None,
        "df_base_mapeamento": None,
        "df_origem_precificado": None,
        "df_final": None,
        "mapeamento_colunas": {},
        "campos_pendentes": [],
        "agent_plan": {},
        "agent_outputs": {},
        "preco_coluna_origem": "",
        "preco_imposto_pct": "",
        "preco_margem_pct": "",
        "preco_custo_fixo": "",
        "preco_taxa_fixa": "",
    }

    for chave, valor in defaults.items():
        if chave not in st.session_state:
            st.session_state[chave] = valor


def _go(etapa: str) -> None:
    st.session_state["fluxo_etapa"] = etapa
    st.rerun()


# ============================================================
# HELPERS
# ============================================================


def _has_df(value: Any) -> bool:
    try:
        return value is not None and hasattr(value, "empty") and not value.empty
    except Exception:
        return False


def _has_text(value: Any) -> bool:
    return isinstance(value, str) and value.strip() != ""


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"none", "nan", "nat"}:
        return ""
    return text


def _read_uploaded_table(uploaded_file) -> Optional[pd.DataFrame]:
    if uploaded_file is None:
        return None

    file_name = (uploaded_file.name or "").lower()

    try:
        if file_name.endswith(".csv"):
            for encoding in ("utf-8", "utf-8-sig", "latin1"):
                for sep in (None, ";", ",", "\t", "|"):
                    try:
                        uploaded_file.seek(0)
                        df = pd.read_csv(
                            uploaded_file,
                            encoding=encoding,
                            sep=sep,
                            engine="python",
                        )
                        if df is not None and hasattr(df, "columns"):
                            return df
                    except Exception:
                        continue

        uploaded_file.seek(0)

        if file_name.endswith(".xlsx") or file_name.endswith(".xls"):
            try:
                return pd.read_excel(uploaded_file, engine="openpyxl")
            except Exception:
                uploaded_file.seek(0)
                return pd.read_excel(uploaded_file)

    except Exception:
        return None

    return None


def _modelo_stage_ready() -> bool:
    return _has_df(st.session_state.get("df_modelo_base"))


def _origem_stage_ready() -> bool:
    plan = st.session_state.get("agent_plan")
    return isinstance(plan, dict) and len(plan) > 0


def _can_go_to_modelo() -> bool:
    return _origem_stage_ready()


def _can_go_to_precificacao() -> bool:
    return _modelo_stage_ready()


def _can_go_to_mapeamento() -> bool:
    return _has_df(st.session_state.get("df_origem_precificado")) or _has_df(
        st.session_state.get("df_base_mapeamento")
    )


def _can_go_to_preview() -> bool:
    return _has_df(st.session_state.get("df_final"))


# ============================================================
# ESTILO
# ============================================================


def _render_css() -> None:
    st.markdown(
        """
        <style>
            .block-container {
                max-width: 760px;
                padding-top: 1rem;
                padding-bottom: 2rem;
            }

            .bx-hero {
                border: 1px solid rgba(20, 22, 28, 0.10);
                border-radius: 22px;
                padding: 18px 16px;
                margin-bottom: 18px;
                background: #ffffff;
            }

            .bx-title {
                font-size: 2rem;
                line-height: 1.05;
                font-weight: 800;
                letter-spacing: -0.02em;
                color: #222531;
                margin: 0 0 10px 0;
            }

            .bx-subtitle {
                font-size: 1rem;
                color: #5d6472;
                margin: 0 0 16px 0;
            }

            .bx-pills {
                display: flex;
                flex-wrap: wrap;
                gap: 10px;
                margin-top: 4px;
            }

            .bx-pill {
                display: inline-flex;
                align-items: center;
                justify-content: center;
                padding: 10px 18px;
                border-radius: 999px;
                border: 1px solid #d8dbe3;
                background: #f2f3f7;
                color: #2d3240;
                font-size: 0.94rem;
                font-weight: 700;
            }

            .bx-pill.active {
                background: #0d2e6f;
                color: #ffffff;
                border-color: #0d2e6f;
            }

            div[data-testid="stButton"] > button {
                border-radius: 14px;
                min-height: 46px;
                font-weight: 700;
            }

            div[data-testid="stFileUploader"] section {
                border-radius: 16px;
            }

            .bx-card-title {
                font-size: 1.75rem;
                font-weight: 800;
                margin: 0 0 8px 0;
                color: #232633;
            }

            .bx-card-desc {
                color: #6b7280;
                margin: 0 0 14px 0;
                font-size: 1rem;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# HEADER
# ============================================================


def _render_header() -> None:
    etapa = st.session_state["fluxo_etapa"]

    labels = {
        "origem": "1. Origem",
        "modelo": "2. Modelo",
        "precificacao_ia": "3. Precificação",
        "mapeamento": "4. Mapeamento",
        "preview": "5. Preview",
    }

    pills = []
    for chave, label in labels.items():
        css = "bx-pill active" if etapa == chave else "bx-pill"
        pills.append(f'<div class="{css}">{label}</div>')

    st.markdown(
        f"""
        <div class="bx-hero">
            <div class="bx-title">IA Planilhas → Bling</div>
            <div class="bx-subtitle">
                Fluxo por tela para origem, modelo, precificação, mapeamento e visualização final.
            </div>
            <div class="bx-pills">
                {''.join(pills)}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# TELA 2 - MODELO
# ============================================================


def _render_modelo_stage() -> None:
    operacao = _safe_str(
        st.session_state.get("tipo_operacao_bling") or st.session_state.get("tipo_operacao")
    ).lower()

    if operacao not in {"cadastro", "estoque"}:
        operacao = "cadastro"

    titulo = "Modelo do Bling"
    descricao = "Anexe apenas o modelo da operação escolhida."

    st.markdown(
        f"""
        <div class="bx-card-title">{titulo}</div>
        <div class="bx-card-desc">{descricao}</div>
        """,
        unsafe_allow_html=True,
    )

    with st.container(border=True):
        st.markdown(
            f"**Operação selecionada:** {'Cadastro de produtos' if operacao == 'cadastro' else 'Atualização de estoque'}"
        )

        if operacao == "cadastro":
            uploaded = st.file_uploader(
                "Modelo do Bling para cadastro",
                type=["csv", "xlsx", "xls"],
                key="modelo_cadastro_upload",
            )

            if uploaded is not None:
                df_modelo = _read_uploaded_table(uploaded)
                if df_modelo is not None:
                    st.session_state["modelo_cadastro_nome"] = uploaded.name
                    st.session_state["df_modelo_base"] = df_modelo.head(0).copy()
                    st.success("Modelo de cadastro carregado.")
                else:
                    st.error("Não foi possível ler o modelo de cadastro.")
        else:
            uploaded = st.file_uploader(
                "Modelo do Bling para estoque",
                type=["csv", "xlsx", "xls"],
                key="modelo_estoque_upload",
            )

            if uploaded is not None:
                df_modelo = _read_uploaded_table(uploaded)
                if df_modelo is not None:
                    st.session_state["modelo_estoque_nome"] = uploaded.name
                    st.session_state["df_modelo_base"] = df_modelo.head(0).copy()
                    st.success("Modelo de estoque carregado.")
                else:
                    st.error("Não foi possível ler o modelo de estoque.")

        if _has_df(st.session_state.get("df_modelo_base")):
            with st.expander("Ver colunas do modelo", expanded=False):
                df_modelo_view = st.session_state["df_modelo_base"]
                st.dataframe(
                    pd.DataFrame({"Colunas do modelo": list(df_modelo_view.columns)}),
                    use_container_width=True,
                )


# ============================================================
# ETAPA ATUAL
# ============================================================


def _render_etapa_atual() -> None:
    etapa = st.session_state["fluxo_etapa"]

    if etapa == "origem":
        render_ia_panel()
        return

    if etapa == "modelo":
        _render_modelo_stage()
        return

    if etapa == "precificacao_ia":
        render_origem_precificacao()
        return

    if etapa == "mapeamento":
        render_origem_mapeamento()
        return

    render_preview_final()


# ============================================================
# NAVEGAÇÃO
# ============================================================


def _render_footer_nav() -> None:
    etapa = st.session_state["fluxo_etapa"]

    # A etapa "origem" é controlada pelo próprio ia_panel.py
    # para evitar botão duplicado e conflito de widget.
    if etapa == "origem":
        return

    col1, col2 = st.columns(2)

    with col1:
        if etapa == "modelo":
            if st.button("← Voltar para origem", use_container_width=True, key="footer_back_modelo"):
                _go("origem")

        elif etapa == "precificacao_ia":
            if st.button(
                "← Voltar para modelo",
                use_container_width=True,
                key="footer_back_precificacao",
            ):
                _go("modelo")

        elif etapa == "mapeamento":
            if st.button(
                "← Voltar para precificação",
                use_container_width=True,
                key="footer_back_mapeamento",
            ):
                _go("precificacao_ia")

        elif etapa == "preview":
            if st.button(
                "← Voltar para mapeamento",
                use_container_width=True,
                key="footer_back_preview",
            ):
                _go("mapeamento")

    with col2:
        if etapa == "modelo":
            if st.button(
                "Próximo →",
                use_container_width=True,
                disabled=not _can_go_to_precificacao(),
                key="footer_next_modelo",
            ):
                _go("precificacao_ia")

        elif etapa == "precificacao_ia":
            if st.button(
                "Próximo →",
                use_container_width=True,
                disabled=not _can_go_to_mapeamento(),
                key="footer_next_precificacao",
            ):
                _go("mapeamento")

        elif etapa == "mapeamento":
            if st.button(
                "Próximo →",
                use_container_width=True,
                disabled=not _can_go_to_preview(),
                key="footer_next_mapeamento",
            ):
                _go("preview")


# ============================================================
# APP
# ============================================================


def main() -> None:
    st.set_page_config(
        page_title="IA Planilhas → Bling",
        layout="centered",
    )

    _init_state()
    _render_css()
    _render_header()
    _render_etapa_atual()
    _render_footer_nav()
    st.caption(f"Versão: {APP_VERSION}")


if __name__ == "__main__":
    main()

