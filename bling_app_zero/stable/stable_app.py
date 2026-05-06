from __future__ import annotations

from html import escape
from io import BytesIO
from math import ceil
from zipfile import ZIP_DEFLATED, ZipFile

import pandas as pd
import streamlit as st

from bling_app_zero.core.file_reader import read_uploaded_table
from bling_app_zero.core.product_data_quality import normalize_product_dataframe
from bling_app_zero.stable.session_vault import guardar_df, limpar_vault, restaurar_chaves_df, restaurar_df
from bling_app_zero.stable.supplier_upload_v2 import render_supplier_upload_v2
from bling_app_zero.ui.app_helpers import dataframe_para_csv_bytes
from bling_app_zero.ui.flash_amplo_execution import executar_flash_amplo_pagina_por_pagina
from bling_app_zero.ui.mapeamento.conservative_auto import choose_safe_source
from bling_app_zero.ui.mapeamento.source_columns import normalizar_nome_coluna
from bling_app_zero.ui.mapeamento.value_guard import clean_invalid_preview_mappings

FLASH_MAX_PRODUCTS = 5000
BLING_MAX_IMPORT_ROWS = 1000
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
    return normalizar_nome_coluna(v)


def _is_deposito_col(col: object) -> bool:
    return "deposito" in _norm(col)


def _is_departamento_col(col: object) -> bool:
    n = _norm(col)
    return n in {"departamento", "apartamento"} or "departamento" in n or "apartamento" in n


def _is_imagem_col(col: object) -> bool:
    n = _norm(col)
    return "imagem" in n or "image" in n or ("url" in n and "foto" in n)


def _is_imagem_target(col: object) -> bool:
    n = _norm(col)
    return "imagem" in n or "image" in n


def _is_descricao_col(col: object) -> bool:
    n = _norm(col)
    return "descricao" in n or n in {"nome", "produto"}


def _is_preco_venda_col(col: object) -> bool:
    n = _norm(col)
    return ("preco" in n or "valor" in n) and "custo" not in n and "compra" not in n


def _dedupe_source_columns(columns) -> list[str]:
    saida: list[str] = []
    vistos: set[str] = set()
    for col in columns:
        nome = str(col).strip()
        if not nome:
            continue
        chave = _norm(nome).replace(" ", "_")
        if chave in vistos:
            continue
        vistos.add(chave)
        saida.append(nome)
    return saida


def _is_model_or_final_column(col: object, model_cols: list[str]) -> bool:
    n = _norm(col)
    model_norms = {_norm(c) for c in model_cols}
    if not n:
        return True
    if n in model_norms:
        return True
    blocked_fragments = (
        "obrigatorio",
        "obrigatoria",
        "gtin ean da embalagem",
        "frete gratis",
        "url imagens externas",
        "preco unitario",
        "categoria do produto",
        "descricao complementar",
        "link externo",
        "url do produto",
        "deposito",
    )
    return any(fragment in n for fragment in blocked_fragments)


def _source_options_for_target(target: str, df: pd.DataFrame, model_cols: list[str]) -> list[str]:
    raw_cols = _dedupe_source_columns(df.columns if _has_df(df) else [])
    cols = [c for c in raw_cols if not _is_model_or_final_column(c, model_cols)]

    if _is_imagem_target(target):
        cols = [c for c in cols if _is_imagem_col(c)]

    return [""] + cols


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


def _normalize_for_final(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return _force(pd.DataFrame(), cols)
    normalized = normalize_product_dataframe(df.copy())
    cleaned = clean_invalid_preview_mappings(normalized.copy())
    return _force(cleaned, cols)


def _urls(raw: str) -> list[str]:
    seen, urls = set(), []
    for part in str(raw or "").replace("\r", "\n").replace(";", "\n").split("\n"):
        url = part.strip()
        if not url:
            continue
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        if url not in seen:
            seen.add(url)
            urls.append(url)
    return urls


def _excel(df: pd.DataFrame) -> bytes:
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="bling")
    return buf.getvalue()


def _df_chunks(df: pd.DataFrame, chunk_size: int = BLING_MAX_IMPORT_ROWS) -> list[pd.DataFrame]:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return []
    return [df.iloc[start:start + chunk_size].copy() for start in range(0, len(df), chunk_size)]


def _zip_csv_parts(df: pd.DataFrame, *, chunk_size: int = BLING_MAX_IMPORT_ROWS) -> bytes:
    buffer = BytesIO()
    parts = _df_chunks(df, chunk_size=chunk_size)
    total_parts = max(len(parts), 1)
    with ZipFile(buffer, mode="w", compression=ZIP_DEFLATED) as zip_file:
        for index, part in enumerate(parts, start=1):
            file_name = f"bling_saida_final_{len(df)}_linhas_parte_{index:02d}_de_{total_parts:02d}.csv"
            zip_file.writestr(file_name, dataframe_para_csv_bytes(part))
    return buffer.getvalue()


def _first_non_empty_value(df: pd.DataFrame, col: str) -> str:
    if not _has_df(df) or col not in df.columns:
        return ""
    try:
        for valor in df[col].astype(str).fillna(""):
            texto = str(valor or "").strip()
            if texto:
                return texto[:350]
    except Exception:
        return ""
    return ""


def _render_source_preview(df: pd.DataFrame, selected_col: str) -> None:
    if not selected_col:
        st.markdown(
            "<div style='margin-top:-0.65rem;margin-bottom:0.75rem;color:#b91c1c;font-size:0.88rem;'>"
            "⚠️ Nenhuma coluna da origem selecionada para este campo."
            "</div>",
            unsafe_allow_html=True,
        )
        return
    valor = _first_non_empty_value(df, selected_col) or "sem valor preenchido na coluna selecionada"
    st.markdown(
        "<div style='margin-top:-0.65rem;margin-bottom:0.75rem;line-height:1.35;'>"
        f"<div style='color:#b91c1c;font-size:0.86rem;font-weight:700;'>Coluna da origem: {escape(str(selected_col))}</div>"
        f"<div style='color:#047857;font-size:0.84rem;font-weight:700;'>{escape(str(valor))}</div>"
        "</div>",
        unsafe_allow_html=True,
    )


def _render_downloads(out: pd.DataFrame, saida_ok: bool) -> None:
    total_linhas = len(out) if isinstance(out, pd.DataFrame) else 0
    if total_linhas > BLING_MAX_IMPORT_ROWS:
        total_partes = ceil(total_linhas / BLING_MAX_IMPORT_ROWS)
        st.warning(f"O Bling aceita no máximo {BLING_MAX_IMPORT_ROWS} linhas por importação. Seu arquivo será dividido em {total_partes} partes.")
        st.download_button("📦 Baixar CSVs divididos", data=_zip_csv_parts(out), file_name=f"bling_saida_final_{total_linhas}_linhas_dividido.zip", mime="application/zip", use_container_width=True, disabled=not saida_ok)
    else:
        st.download_button(f"📥 Baixar CSV para Bling ({total_linhas} linhas)", data=dataframe_para_csv_bytes(out), file_name=f"bling_saida_final_{total_linhas}_linhas.csv", mime="text/csv", use_container_width=True, disabled=not saida_ok)
    st.download_button(f"📥 Baixar Excel de conferência ({total_linhas} linhas)", data=_excel(out), file_name=f"bling_saida_final_{total_linhas}_linhas_conferencia.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True, disabled=not saida_ok)


def _col_with_data(df: pd.DataFrame, predicate) -> bool:
    return any(predicate(col) and df[col].astype(str).str.strip().ne("").any() for col in df.columns)


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


def _show_line_metrics(df_origem: pd.DataFrame, df_final: pd.DataFrame | None = None) -> None:
    cols = st.columns(2)
    cols[0].metric("Linhas capturadas na origem", len(df_origem) if isinstance(df_origem, pd.DataFrame) else 0)
    cols[1].metric("Linhas no preview final", len(df_final) if isinstance(df_final, pd.DataFrame) else 0)


def run_stable_app() -> None:
    restaurar_chaves_df(["stable_df_origem", "stable_df_modelo", "stable_df_export"])
    st.title("🚀 IA Planilhas → Bling")
    st.caption("Fluxo corrigido: Modelo Bling → Origem/site → Mapeamento manual → Preview final → CSV.")

    with st.sidebar:
        if st.button("🧹 Reiniciar fluxo", use_container_width=True):
            limpar_vault(prefixes=("stable_", "supplier_"))
            st.rerun()

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

    _show_line_metrics(df, restaurar_df("stable_df_export"))
    st.subheader("Mapeamento manual")
    st.caption("Escolha apenas colunas reais da origem/captura. Colunas do modelo Bling e colunas finais não aparecem como origem.")

    mapping = {}
    deposito_manual = ""
    for c in cols:
        options = _source_options_for_target(str(c), df, cols)
        if tipo == "estoque" and _is_deposito_col(c):
            deposito_manual = st.text_input(str(c), value=str(st.session_state.get("stable_deposito_mapeamento", "")), key="stable_deposito_mapeamento", placeholder="Ex.: Geral").strip()
            mapping[c] = ""
            continue
        if _is_departamento_col(c):
            st.text_input(str(c), value="Unissex", disabled=True, key=f"stable_departamento_{c}")
            st.caption("Preenchido automaticamente com padrão Unissex.")
            mapping[c] = "__UNISSEX__"
            continue
        default = _safe_source(c, options)
        idx = options.index(default) if default in options else 0
        selecionada = st.selectbox(str(c), options, index=idx, key=f"stable_map_{c}")
        mapping[c] = selecionada
        _render_source_preview(df, selecionada)

    out = pd.DataFrame(index=df.index)
    for c in cols:
        if tipo == "estoque" and _is_deposito_col(c):
            out[c] = deposito_manual
            continue
        if _is_departamento_col(c):
            out[c] = "Unissex"
            continue
        src = mapping.get(c, "")
        out[c] = df[src].astype(str).fillna("") if src and src in df.columns else ""
    out = _normalize_for_final(out, cols)
    out = guardar_df("stable_df_export", out)

    _show_line_metrics(df, out)
    with st.expander("Preview final", expanded=False):
        st.caption(f"Total real do arquivo final: {len(out)} linhas.")
        st.dataframe(out, use_container_width=True, hide_index=True)

    saida_ok = _validar_saida(out, tipo)
    if saida_ok:
        st.success(f"Arquivo pronto: {len(out)} linhas × {len(out.columns)} colunas")
    else:
        st.warning("Corrija o mapeamento obrigatório antes de baixar.")
    _render_downloads(out, saida_ok)
