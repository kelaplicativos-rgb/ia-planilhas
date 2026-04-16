from __future__ import annotations

import io
from pathlib import Path

import pandas as pd
import streamlit as st


ETAPAS_VALIDAS = ["origem", "precificacao", "mapeamento", "preview_final"]


def safe_df(df):
    return isinstance(df, pd.DataFrame) and not df.empty


def safe_df_estrutura(df):
    return isinstance(df, pd.DataFrame) and len(df.columns) > 0


def nome_etapa_amigavel(etapa: str) -> str:
    mapa = {
        "origem": "Origem dos dados",
        "precificacao": "Precificação",
        "mapeamento": "Mapeamento",
        "preview_final": "Preview final",
    }
    return mapa.get(str(etapa), str(etapa).capitalize())


def _ler_query_params() -> dict:
    try:
        return dict(st.query_params)
    except Exception:
        try:
            return st.experimental_get_query_params()
        except Exception:
            return {}


def _set_query_param_etapa(etapa: str) -> None:
    try:
        st.query_params["etapa"] = etapa
    except Exception:
        try:
            st.experimental_set_query_params(etapa=etapa)
        except Exception:
            pass


def sincronizar_etapa_da_url() -> None:
    params = _ler_query_params()
    etapa_url = params.get("etapa")

    if isinstance(etapa_url, list):
        etapa_url = etapa_url[0] if etapa_url else None

    if etapa_url in ETAPAS_VALIDAS:
        st.session_state["etapa"] = etapa_url

        historico = st.session_state.get("historico_etapas", ["origem"])
        if not historico or historico[-1] != etapa_url:
            historico.append(etapa_url)
            st.session_state["historico_etapas"] = historico


def get_etapa() -> str:
    etapa = st.session_state.get("etapa", "origem")
    if etapa not in ETAPAS_VALIDAS:
        etapa = "origem"
        st.session_state["etapa"] = etapa
    return etapa


def ir_para_etapa(etapa: str) -> None:
    if etapa not in ETAPAS_VALIDAS:
        return

    etapa_atual = st.session_state.get("etapa", "origem")
    historico = st.session_state.get("historico_etapas", ["origem"]).copy()

    if etapa_atual != etapa:
        if not historico or historico[-1] != etapa_atual:
            historico.append(etapa_atual)

        if not historico or historico[-1] != etapa:
            historico.append(etapa)

    st.session_state["historico_etapas"] = historico
    st.session_state["etapa"] = etapa
    _set_query_param_etapa(etapa)
    st.rerun()


def pode_voltar() -> bool:
    etapa = st.session_state.get("etapa", "origem")
    historico = st.session_state.get("historico_etapas", ["origem"])

    if etapa == "origem":
        return False

    return bool(historico)


def voltar_etapa_anterior() -> None:
    historico = st.session_state.get("historico_etapas", ["origem"]).copy()
    etapa_atual = st.session_state.get("etapa", "origem")

    if etapa_atual == "origem":
        st.session_state["historico_etapas"] = ["origem"]
        st.session_state["etapa"] = "origem"
        _set_query_param_etapa("origem")
        st.rerun()
        return

    while historico and historico[-1] == etapa_atual:
        historico.pop()

    etapa_destino = historico[-1] if historico else "origem"

    if historico:
        st.session_state["historico_etapas"] = historico
    else:
        st.session_state["historico_etapas"] = ["origem"]

    st.session_state["etapa"] = etapa_destino
    _set_query_param_etapa(etapa_destino)
    st.rerun()


def render_topo_navegacao() -> None:
    etapa = get_etapa()

    col1, col2 = st.columns([1, 3])

    with col1:
        if etapa != "origem":
            if st.button(
                "⬅️ Voltar",
                use_container_width=True,
                key="btn_voltar_topo",
            ):
                voltar_etapa_anterior()

    with col2:
        st.markdown(f"**Etapa atual:** {nome_etapa_amigavel(etapa)}")


def _extensao(upload) -> str:
    nome = str(getattr(upload, "name", "") or "").strip().lower()
    return Path(nome).suffix.lower()


def _eh_excel_familia(ext: str) -> bool:
    return ext in {".csv", ".xlsx", ".xls"}


def _ler_tabular(upload):
    nome = str(upload.name).lower()

    if nome.endswith(".csv"):
        bruto = upload.getvalue()

        for sep in [";", ",", "\t", "|"]:
            try:
                df = pd.read_csv(
                    io.BytesIO(bruto),
                    sep=sep,
                    dtype=str,
                    encoding="utf-8",
                    engine="python",
                ).fillna("")

                df.columns = [str(c).strip() for c in df.columns if str(c).strip()]

                if len(df.columns) > 0:
                    return df

            except Exception:
                continue

        raise ValueError("Não foi possível ler o CSV.")

    if nome.endswith(".xlsx") or nome.endswith(".xls"):
        try:
            df = pd.read_excel(upload, dtype=str).fillna("")

            df.columns = [str(c).strip() for c in df.columns if str(c).strip()]
            df = df.loc[:, df.columns.notna()]
            df = df[[c for c in df.columns if str(c).strip() != ""]]

            if len(df.columns) > 0:
                return df

        except Exception as e:
            raise ValueError(f"Não foi possível ler o Excel: {e}")

    raise ValueError("Arquivo tabular inválido.")
