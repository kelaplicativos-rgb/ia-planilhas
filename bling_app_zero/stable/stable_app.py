from __future__ import annotations

from io import BytesIO
import pandas as pd
import streamlit as st

from bling_app_zero.core.file_reader import read_uploaded_table
from bling_app_zero.stable.session_vault import guardar_df, limpar_vault, restaurar_chaves_df, restaurar_df
from bling_app_zero.stable.supplier_upload_v2 import render_supplier_upload_v2
from bling_app_zero.ui.app_helpers import dataframe_para_csv_bytes
from bling_app_zero.ui.flash_amplo_execution import executar_flash_amplo_pagina_por_pagina
from bling_app_zero.ui.mapeamento.conservative_auto import choose_safe_source
from bling_app_zero.ui.mapeamento.value_guard import clean_invalid_preview_mappings

FLASH_MAX_PRODUCTS = 5000
CAD_COLS = ["Código", "Descrição", "Descrição complementar", "Unidade", "GTIN/EAN", "Preço unitário", "Marca", "Categoria", "URL imagens externas", "Link Externo", "URL do Produto"]
EST_COLS = ["Código", "Descrição", "GTIN/EAN", "Depósito", "Estoque", "Quantidade"]


def _read_upload(file) -> pd.DataFrame | None:
    if file is None:
        return None
    return read_uploaded_table(file).dataframe.fillna("")


def _has_df(df) -> bool:
    return isinstance(df, pd.DataFrame) and not df.empty and len(df.columns) > 0


def _cols(tipo: str, modelo: pd.DataFrame | None) -> list[str]:
    if _has_df(modelo):
        return [str(c).strip() for c in modelo.columns if str(c).strip()]
    return EST_COLS if tipo == "estoque" else CAD_COLS


def _norm(v) -> str:
    text = str(v or "").strip().lower()
    text = text.translate(str.maketrans("áàãâéêíóôõúç", "aaaaeeiooouc"))
    return " ".join("".join(ch if ch.isalnum() else " " for ch in text).split())


def _is_deposito_col(col: object) -> bool:
    return "deposito" in _norm(col)


def _is_descricao_col(col: object) -> bool:
    n = _norm(col)
    return "descricao" in n or n in {"nome", "produto"}


def _is_preco_venda_col(col: object) -> bool:
    n = _norm(col)
    return ("preco" in n or "valor" in n) and "custo" not in n and "compra" not in n


def _safe_source(target: str, sources) -> str:
    try:
        return choose_safe_source(str(target), [str(c) for c in sources]) or ""
    except Exception:
        target_norm = _norm(target)
        exact = [str(c) for c in sources if _norm(c) == target_norm]
        return exact[0] if len(exact) == 1 else ""


def _force(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    out = df.copy() if isinstance(df, pd.DataFrame) else pd.DataFrame()
    for c in cols:
        if c not in out.columns:
            out[c] = ""
    return out[cols].fillna("")


def _mirror_preview(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    out = pd.DataFrame(index=df.index)
    for target in cols:
        src = _safe_source(target, df.columns)
        out[target] = df[src].astype(str).fillna("") if src else ""
    return clean_invalid_preview_mappings(_force(out, cols))


def _urls(raw: str) -> list[str]:
    seen, urls = set(), []
    for part in str(raw or "").replace("\r", "\n").replace(";", "\n").split("\n"):
        url = part.strip()
        if not url:
            continue
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        if url not in seen:
            seen.add(url); urls.append(url)
    return urls


def _excel(df: pd.DataFrame) -> bytes:
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="bling")
    return buf.getvalue()


def _col_with_data(df: pd.DataFrame, predicate) -> bool:
    for col in df.columns:
        if predicate(col) and df[col].astype(str).str.strip().ne("").any():
            return True
    return False


def _validar_saida(df: pd.DataFrame, tipo: str) -> bool:
    if not _has_df(df):
        st.error("A saída está vazia.")
        return False

    ok = True
    if tipo == "cadastro":
        if not _col_with_data(df, _is_descricao_col):
            st.error("Campo obrigatório sem dados: Descrição/Nome do produto.")
            ok = False
        if not _col_with_data(df, _is_preco_venda_col):
            st.error("Campo obrigatório sem dados: Preço unitário/preço de venda.")
            ok = False
    if tipo == "estoque":
        deposito_cols = [c for c in df.columns if _is_deposito_col(c)]
        if deposito_cols and not any(df[c].astype(str).str.strip().ne("").any() for c in deposito_cols):
            st.error("Campo obrigatório sem dados: Depósito.")
            ok = False
    return ok


def run_stable_app() -> None:
    restaurar_chaves_df(["stable_df_origem", "stable_df_modelo", "stable_df_export"])
    st.title("🚀 IA Planilhas → Bling")
    st.caption("Fluxo corrigido: Modelo Bling → Origem/site → Preview → Mapeamento manual/conservador → CSV.")

    with st.sidebar:
        if st.button("🧹 Reiniciar fluxo", use_container_width=True):
            limpar_vault(prefixes=("stable_", "supplier_")); st.rerun()

    tipo = st.radio("O que você quer gerar?", ["cadastro", "estoque"], format_func=lambda x: "Cadastro de produtos" if x == "cadastro" else "Atualização de estoque", horizontal=True, key="stable_tipo")
    modelo = restaurar_df("stable_df_modelo")

    with st.expander("1. Modelo Bling obrigatório para cadastro" if tipo == "cadastro" else "Modelo Bling opcional", expanded=(tipo == "cadastro" and not _has_df(modelo))):
        up_modelo = st.file_uploader("Anexar modelo Bling", type=None, key="stable_upload_modelo")
        if up_modelo is not None:
            try:
                modelo_lido = _read_upload(up_modelo)
                if _has_df(modelo_lido):
                    modelo = guardar_df("stable_df_modelo", modelo_lido)
                    st.success(f"Modelo lido: {len(modelo.columns)} colunas")
                else:
                    st.error("O modelo Bling foi lido, mas não possui linhas/colunas válidas.")
            except Exception as exc:
                st.error("Não consegui ler o modelo Bling anexado.")
                st.code(str(exc))
        elif _has_df(modelo):
            st.info(f"🔒 Modelo preservado: {len(modelo.columns)} colunas")

    if tipo == "cadastro" and not _has_df(modelo):
        st.warning("Anexe primeiro a planilha modelo Bling de cadastro.")
        st.info("Sem o modelo, o app não gera base, preview nem mapeamento para evitar coluna errada.")
        return

    cols = _cols(tipo, modelo)
    st.divider()
    df = restaurar_df("stable_df_origem")
    tab_file, tab_site = st.tabs(["📎 Arquivo", "🌐 Site"])

    with tab_file:
        df_up = render_supplier_upload_v2(state_key="stable_df_origem", key_prefix="supplier")
        if _has_df(df_up):
            df = guardar_df("stable_df_origem", df_up)

    with tab_site:
        raw = st.text_area("Links do fornecedor", key="stable_site_urls", height=120)
        links = _urls(raw)
        if st.button("Gerar base por site", disabled=not links, use_container_width=True):
            df = executar_flash_amplo_pagina_por_pagina(links, max_products=FLASH_MAX_PRODUCTS, max_workers=12, show_progress=True)
            if _has_df(df):
                df = guardar_df("stable_df_origem", df)

    if not _has_df(df):
        st.warning("Anexe/capture a origem para continuar.")
        return

    with st.expander("Preview da origem", expanded=False):
        prev = _mirror_preview(df, cols)
        st.caption("Espelhado no modelo. Só correspondências conservadoras e sem ambiguidade são preenchidas; o resto fica vazio para manual.")
        st.dataframe(prev.head(80), use_container_width=True, hide_index=True)

    st.subheader("Mapeamento manual/conservador")
    sources = [""] + [str(c) for c in df.columns]
    mapping = {}
    deposito_manual = ""
    for c in cols:
        if tipo == "estoque" and _is_deposito_col(c):
            deposito_manual = st.text_input(str(c), value=str(st.session_state.get("stable_deposito_mapeamento", "")), key="stable_deposito_mapeamento", placeholder="Ex.: Geral").strip()
            mapping[c] = ""
            continue
        default = _safe_source(c, df.columns)
        idx = sources.index(default) if default in sources else 0
        mapping[c] = st.selectbox(str(c), sources, index=idx, key=f"stable_map_{c}")

    out = pd.DataFrame(index=df.index)
    for c in cols:
        if tipo == "estoque" and _is_deposito_col(c):
            out[c] = deposito_manual
            continue
        src = mapping.get(c, "")
        out[c] = df[src].astype(str).fillna("") if src and src in df.columns else ""
    out = clean_invalid_preview_mappings(_force(out, cols))
    out = guardar_df("stable_df_export", out)

    with st.expander("Preview final", expanded=False):
        st.dataframe(out.head(100), use_container_width=True, hide_index=True)

    saida_ok = _validar_saida(out, tipo)
    if saida_ok:
        st.success(f"Arquivo pronto: {len(out)} linhas × {len(out.columns)} colunas")
    else:
        st.warning("Corrija o mapeamento obrigatório antes de baixar.")

    st.download_button("📥 Baixar CSV para Bling", data=dataframe_para_csv_bytes(out), file_name="bling_saida_final.csv", mime="text/csv", use_container_width=True, disabled=not saida_ok)
    st.download_button("📥 Baixar Excel de conferência", data=_excel(out), file_name="bling_saida_final_conferencia.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True, disabled=not saida_ok)
