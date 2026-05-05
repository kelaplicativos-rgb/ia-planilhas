from __future__ import annotations

import re
from io import BytesIO
from urllib.parse import urlparse

import pandas as pd
import streamlit as st

from bling_app_zero.core.file_reader import read_uploaded_table
from bling_app_zero.stable.supplier_upload_v2 import render_supplier_upload_v2
from bling_app_zero.ui.app_helpers import blindar_df_para_bling, dataframe_para_csv_bytes


CALCULATED_PRICE_OPTION = "🧮 Preço calculado pela precificação"

CADASTRO_DEFAULT_COLUMNS = [
    "Código",
    "Descrição",
    "Descrição complementar",
    "Unidade",
    "NCM",
    "GTIN/EAN",
    "Preço unitário",
    "Preço de custo",
    "Marca",
    "Categoria",
    "URL imagens externas",
    "Estoque",
]

ESTOQUE_DEFAULT_COLUMNS = [
    "Código",
    "Descrição",
    "GTIN/EAN",
    "Depósito",
    "Estoque",
    "Quantidade",
]

ALIAS = {
    "Código": ["codigo", "código", "cod", "sku", "ref", "referencia", "referência", "id"],
    "Descrição": ["descricao", "descrição", "produto", "nome", "titulo", "título", "title"],
    "Descrição complementar": ["descricao complementar", "descrição complementar", "detalhes", "complemento", "observacao", "observação"],
    "Unidade": ["unidade", "un", "und"],
    "NCM": ["ncm"],
    "GTIN/EAN": ["gtin", "ean", "codigo de barras", "código de barras", "barcode", "barra", "barras"],
    "Preço unitário": ["preco", "preço", "valor", "preco venda", "preço venda", "preco unitario", "preço unitário"],
    "Preço de custo": ["custo", "preco custo", "preço custo", "valor custo"],
    "Marca": ["marca", "brand", "fabricante"],
    "Categoria": ["categoria", "grupo", "departamento"],
    "URL imagens externas": ["imagem", "imagens", "foto", "fotos", "url imagem", "image"],
    "Estoque": ["estoque", "saldo", "quantidade", "qtd", "stock"],
    "Quantidade": ["quantidade", "qtd", "estoque", "saldo", "stock"],
    "Depósito": ["deposito", "depósito", "warehouse", "local"],
}


def _norm(value: object) -> str:
    text = str(value or "").strip().lower()
    repl = str.maketrans("áàãâéêíóôõúç", "aaaaeeiooouc")
    text = text.translate(repl)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _is_deposito_target(target: object) -> bool:
    return "deposito" in _norm(target)


def _is_price_target(target: object) -> bool:
    name = _norm(target)
    return (
        "preco unitario" in name
        or "preco venda" in name
        or name == "preco"
        or "preco obrigatorio" in name
        or ("preco" in name and "custo" not in name)
    )


def _format_price_br(value: float) -> str:
    return f"{float(value):.2f}".replace(".", ",")


def _parse_money_value(value: object) -> float | None:
    text = str(value or "").strip()
    if not text:
        return None

    text = text.replace("R$", "").replace(" ", "")
    text = re.sub(r"[^0-9,.-]", "", text)
    if not text or text in {"-", ",", "."}:
        return None

    # Quando existem ponto e vírgula, o último separador é tratado como decimal.
    # Ex.: 1.234,56 -> 1234.56 | 1,234.56 -> 1234.56
    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        parts = text.split(",")
        if len(parts[-1]) in {1, 2}:
            text = "".join(parts[:-1]).replace(",", "") + "." + parts[-1]
        else:
            text = text.replace(",", "")
    elif "." in text:
        parts = text.split(".")
        if len(parts[-1]) in {1, 2}:
            text = "".join(parts[:-1]).replace(".", "") + "." + parts[-1]
        else:
            text = text.replace(".", "")

    try:
        return float(text)
    except Exception:
        return None


def _to_number_series(series: pd.Series) -> pd.Series:
    return series.apply(_parse_money_value).astype(float)


def _read_upload(uploaded) -> pd.DataFrame | None:
    if uploaded is None:
        return None
    result = read_uploaded_table(uploaded)
    return result.dataframe.fillna("")


def _split_urls(raw: str) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()
    for item in re.split(r"[\n,;\s]+", str(raw or "")):
        url = item.strip()
        if not url:
            continue
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        if url not in seen:
            seen.add(url)
            urls.append(url)
    return urls


def _site_df(raw_urls: str, estoque_padrao: int) -> pd.DataFrame:
    rows = []
    for idx, url in enumerate(_split_urls(raw_urls), start=1):
        parsed = urlparse(url)
        slug = [p for p in parsed.path.split("/") if p]
        last = slug[-1] if slug else parsed.netloc
        code = re.sub(r"[^A-Za-z0-9_-]+", "-", last).strip("-") or f"SITE-{idx:04d}"
        desc = re.sub(r"[-_]+", " ", last).strip().title() or f"Produto Site {idx}"
        rows.append({
            "Código": code[:60],
            "Descrição": desc,
            "URL do produto": url,
            "Estoque": int(estoque_padrao),
            "Quantidade": int(estoque_padrao),
        })
    return pd.DataFrame(rows).fillna("")


def _target_columns(tipo: str, modelo: pd.DataFrame | None) -> list[str]:
    if isinstance(modelo, pd.DataFrame) and not modelo.empty and len(modelo.columns) > 0:
        return [str(c).strip() for c in modelo.columns if str(c).strip()]
    return ESTOQUE_DEFAULT_COLUMNS.copy() if tipo == "estoque" else CADASTRO_DEFAULT_COLUMNS.copy()


def _suggest(target: str, source_columns: list[str]) -> str:
    nt = _norm(target)
    aliases = [_norm(a) for a in ALIAS.get(target, [target])]
    aliases.append(nt)
    best = ""
    best_score = 0
    for col in source_columns:
        nc = _norm(col)
        score = 0
        for alias in aliases:
            if nc == alias:
                score = max(score, 100)
            elif alias and (alias in nc or nc in alias):
                score = max(score, 85)
            elif alias and any(part in nc for part in alias.split()):
                score = max(score, 55)
        if score > best_score:
            best = col
            best_score = score
    return best if best_score >= 55 else ""


def _render_pricing_tool(df: pd.DataFrame, sources: list[str]) -> dict[str, object]:
    with st.expander("🧮 Precificação", expanded=False):
        st.caption("Fórmula: Preço = (Custo + Valor fixo) / (1 - ((Lucro % + Taxas %) / 100)).")
        usar_preco_calculado = st.checkbox(
            "Aplicar preço calculado automaticamente na coluna de preço",
            value=bool(st.session_state.get("stable_pricing_apply", True)),
            key="stable_pricing_apply",
        )
        custo_col = st.selectbox(
            "Coluna de custo/preço base",
            options=sources,
            index=0,
            key="stable_pricing_cost_col",
            help="Escolha a coluna do fornecedor usada como custo. Se deixar vazio, uso o custo manual.",
        )
        custo_manual = st.number_input(
            "Custo manual fallback",
            min_value=0.0,
            value=float(st.session_state.get("stable_pricing_manual_cost", 0.0) or 0.0),
            step=1.0,
            format="%.2f",
            key="stable_pricing_manual_cost",
        )
        lucro_percentual = st.number_input(
            "Lucro desejado (%)",
            min_value=0.0,
            max_value=99.99,
            value=float(st.session_state.get("stable_pricing_profit", 30.0) or 30.0),
            step=0.01,
            format="%.2f",
            key="stable_pricing_profit",
        )
        taxas_percentual = st.number_input(
            "Taxas/despesas (%)",
            min_value=0.0,
            max_value=99.99,
            value=float(st.session_state.get("stable_pricing_fees", 0.0) or 0.0),
            step=0.01,
            format="%.2f",
            key="stable_pricing_fees",
        )
        valor_fixo = st.number_input(
            "Valor fixo adicional por produto",
            min_value=0.0,
            value=float(st.session_state.get("stable_pricing_fixed", 0.0) or 0.0),
            step=0.5,
            format="%.2f",
            key="stable_pricing_fixed",
        )

        if custo_col and custo_col in df.columns:
            base = _to_number_series(df[custo_col]).fillna(float(custo_manual))
        else:
            base = pd.Series([float(custo_manual)] * len(df), index=df.index)

        total_percentual = float(lucro_percentual) + float(taxas_percentual)
        if total_percentual >= 95:
            st.error("Lucro + taxas está muito alto. Use menos de 95% para evitar preço explosivo.")
            calculated = pd.Series([0.0] * len(df), index=df.index)
        else:
            divisor = 1 - (total_percentual / 100.0)
            calculated = ((base + float(valor_fixo)) / divisor).round(2)

        st.session_state["stable_pricing_series"] = calculated
        st.success(f"Preço calculado pronto. Exemplo: R$ {_format_price_br(float(calculated.iloc[0])) if len(calculated) else '0,00'}")
        return {"enabled": bool(usar_preco_calculado), "series": calculated}


def _apply_calculated_price_to_price_columns(df: pd.DataFrame, calculated_price: pd.Series | None) -> pd.DataFrame:
    if not isinstance(calculated_price, pd.Series) or calculated_price.empty:
        return df
    out = df.copy()
    formatted = calculated_price.reindex(out.index).fillna(0).map(lambda v: _format_price_br(float(v)))
    applied_cols: list[str] = []
    for col in out.columns:
        if _is_price_target(col):
            out[col] = formatted
            applied_cols.append(str(col))
    if applied_cols:
        st.caption(f"Preço calculado aplicado em: {', '.join(applied_cols)}")
    return out


def _map_df(
    df: pd.DataFrame,
    targets: list[str],
    mapping: dict[str, str],
    deposito: str,
    calculated_price: pd.Series | None = None,
) -> pd.DataFrame:
    out = pd.DataFrame(index=df.index)
    for target in targets:
        if _is_deposito_target(target):
            out[target] = deposito
            continue
        source = mapping.get(target, "")
        if source == CALCULATED_PRICE_OPTION:
            if isinstance(calculated_price, pd.Series) and not calculated_price.empty:
                out[target] = calculated_price.reindex(df.index).fillna(0).map(lambda v: _format_price_br(float(v)))
            else:
                out[target] = ""
        elif source and source in df.columns:
            out[target] = df[source].astype(str).fillna("")
        else:
            out[target] = ""
    return out.fillna("")


def _reset_all() -> None:
    for key in list(st.session_state.keys()):
        if key.startswith("stable_") or key.startswith("supplier_"):
            st.session_state.pop(key, None)


def _download_excel(df: pd.DataFrame) -> bytes:
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="bling")
    return buffer.getvalue()


def _render_deposito_mapping_field(target_label: str = "Depósito (OBRIGATÓRIO)") -> str:
    deposito = st.text_input(
        target_label,
        value=str(st.session_state.get("stable_deposito_mapeamento", "")),
        key="stable_deposito_mapeamento",
        placeholder="Ex.: Geral",
        help="Digite aqui o depósito. O valor será aplicado em todas as linhas da coluna de depósito.",
    ).strip()
    if deposito:
        st.caption(f"Será aplicado na coluna de depósito: {deposito}")
    return deposito


def run_stable_app() -> None:
    st.title("🚀 IA Planilhas → Bling")
    st.caption("Núcleo estável: origem por arquivo ou site → mapeamento → exportação CSV.")

    with st.sidebar:
        st.caption("Painel recolhido por padrão")
        if st.button("🧹 Reiniciar fluxo", use_container_width=True):
            _reset_all()
            st.rerun()

    tipo = st.radio(
        "O que você quer gerar?",
        ["cadastro", "estoque"],
        format_func=lambda x: "Cadastro de produtos" if x == "cadastro" else "Atualização de estoque",
        horizontal=True,
        key="stable_tipo",
    )

    tab_arquivo, tab_site = st.tabs(["📎 Arquivo", "🌐 Site"])

    df_origem = st.session_state.get("stable_df_origem")

    with tab_arquivo:
        df_uploaded = render_supplier_upload_v2(state_key="stable_df_origem", key_prefix="supplier")
        if isinstance(df_uploaded, pd.DataFrame) and not df_uploaded.empty:
            df_origem = df_uploaded

    with tab_site:
        if tipo != "estoque":
            st.info("Captura por site está liberada neste núcleo para atualização de estoque.")
        raw_urls = st.text_area("Links do fornecedor", key="stable_site_urls", height=120)
        estoque_padrao = st.number_input("Estoque padrão", min_value=0, value=0, step=1, key="stable_estoque_padrao")
        urls = _split_urls(raw_urls)
        if st.button("Gerar base por site", disabled=(tipo != "estoque" or not urls), use_container_width=True):
            df_origem = _site_df(raw_urls, int(estoque_padrao))
            st.session_state["stable_df_origem"] = df_origem
            st.success(f"Base por site criada: {len(df_origem)} produtos")

    st.divider()

    modelo = None
    with st.expander("Modelo Bling opcional", expanded=False):
        uploaded_modelo = st.file_uploader("Anexar modelo Bling", type=None, key="stable_upload_modelo")
        if uploaded_modelo is not None:
            try:
                modelo = _read_upload(uploaded_modelo)
                st.session_state["stable_df_modelo"] = modelo
                st.success(f"Modelo lido: {len(modelo.columns)} colunas")
            except Exception as exc:
                st.error("Não consegui ler o modelo Bling.")
                st.code(str(exc))
        else:
            modelo = st.session_state.get("stable_df_modelo")

    if not isinstance(df_origem, pd.DataFrame) or df_origem.empty:
        st.warning("Anexe um arquivo, cole o CSV ou gere uma base por site para continuar.")
        return

    with st.expander("Preview da origem", expanded=False):
        st.dataframe(df_origem.head(50), use_container_width=True)

    targets = _target_columns(tipo, modelo)
    sources = [""] + [str(c) for c in df_origem.columns]

    st.subheader("Mapeamento")
    st.caption("A sugestão automática já vem preenchida, mas você pode corrigir antes de exportar.")

    has_price_target = any(_is_price_target(t) for t in targets)
    pricing_data = {"enabled": False, "series": None}
    if has_price_target:
        pricing_data = _render_pricing_tool(df_origem, sources)

    mapping: dict[str, str] = {}
    deposito = ""
    for target in targets:
        if tipo == "estoque" and _is_deposito_target(target):
            deposito = _render_deposito_mapping_field(str(target))
            mapping[target] = ""
            continue

        extra_sources = sources.copy()
        if _is_price_target(target):
            extra_sources = [CALCULATED_PRICE_OPTION] + extra_sources
            default_source = CALCULATED_PRICE_OPTION
        else:
            default_source = _suggest(target, list(df_origem.columns))

        idx = extra_sources.index(default_source) if default_source in extra_sources else 0
        mapping[target] = st.selectbox(target, extra_sources, index=idx, key=f"stable_map_{target}")

    if tipo == "estoque" and not deposito:
        st.warning("Preencha o campo de depósito obrigatório dentro do mapeamento para liberar a exportação.")
        return

    calculated_price = pricing_data.get("series") if isinstance(pricing_data, dict) and pricing_data.get("enabled") else None
    df_mapeado = _map_df(df_origem, targets, mapping, deposito, calculated_price=calculated_price)
    if tipo == "cadastro" and isinstance(calculated_price, pd.Series) and not calculated_price.empty:
        df_mapeado = _apply_calculated_price_to_price_columns(df_mapeado, calculated_price)

    df_export = blindar_df_para_bling(df_mapeado, tipo_operacao_bling=tipo, deposito_nome=deposito)
    if tipo == "cadastro" and isinstance(calculated_price, pd.Series) and not calculated_price.empty:
        df_export = _apply_calculated_price_to_price_columns(df_export, calculated_price)
    st.session_state["stable_df_export"] = df_export

    with st.expander("Preview final", expanded=False):
        st.dataframe(df_export.head(100), use_container_width=True)

    st.success(f"Arquivo pronto: {len(df_export)} linhas × {len(df_export.columns)} colunas")
    st.download_button(
        "📥 Baixar CSV para Bling",
        data=dataframe_para_csv_bytes(df_export),
        file_name="bling_saida_final.csv",
        mime="text/csv",
        use_container_width=True,
    )
    st.download_button(
        "📥 Baixar Excel de conferência",
        data=_download_excel(df_export),
        file_name="bling_saida_final_conferencia.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )
