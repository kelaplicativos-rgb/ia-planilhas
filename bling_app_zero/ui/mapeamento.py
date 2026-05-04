from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.core.auto_mapper import (
    build_mapped_dataframe,
    suggest_mapping,
    supplier_signature,
)
from bling_app_zero.core.auto_map_memory import (
    get_supplier_memory,
    load_memory,
)
from bling_app_zero.core.bling_validator import validar_df_bling

from bling_app_zero.core.stock_intelligence import (
    build_stock_dataframe,
    build_stock_mapping,
    validate_stock_dataframe,
)

from bling_app_zero.core.stock_pro import (
    apply_stock_mode,
    add_stock_delta,
    stock_risk_summary,
    block_stock_export,
)


def _avancar() -> None:
    st.session_state["wizard_etapa_atual"] = "preview_final"
    st.session_state["wizard_etapa_maxima"] = "preview_final"
    st.rerun()


def _voltar() -> None:
    st.session_state["wizard_etapa_atual"] = "origem"
    st.rerun()


def _modelo_key(tipo_operacao: str) -> str:
    return "df_modelo_estoque" if tipo_operacao == "estoque" else "df_modelo_cadastro"


def _modelo_columns(tipo_operacao: str) -> list[str]:
    modelo = st.session_state.get(_modelo_key(tipo_operacao))
    if isinstance(modelo, pd.DataFrame) and not modelo.empty:
        return [str(c).strip() for c in modelo.columns if str(c).strip()]
    return []


def _aplicar_preco_calculado(df_final: pd.DataFrame) -> pd.DataFrame:
    if df_final is None or df_final.empty:
        return df_final

    usar = st.session_state.get("usar_precificacao", False)
    preco = st.session_state.get("preco_unitario_calculado")
    if not usar or preco in (None, ""):
        return df_final

    out = df_final.copy()
    for col in out.columns:
        col_norm = str(col).lower().replace("á", "a").replace("é", "e").replace("ç", "c")
        if "preco unitario" in col_norm or "preço unitário" in str(col).lower():
            out[col] = str(preco).replace(".", ",")
            st.caption(f"Preço calculado aplicado automaticamente na coluna: {col}")
            break
    return out


def _render_ferramentas(df: pd.DataFrame) -> None:
    with st.expander("🧰 Ferramentas opcionais antes do preview final", expanded=False):
        usar = st.checkbox(
            "Aplicar preço calculado em todos os produtos",
            value=bool(st.session_state.get("usar_precificacao", False)),
            help="A ferramenta não é mais uma etapa obrigatória. Use apenas quando quiser substituir/preencher o preço unitário.",
        )
        st.session_state["usar_precificacao"] = usar

        if usar:
            colunas = [str(c) for c in df.columns]
            coluna_custo = st.selectbox(
                "Coluna de custo/base da planilha",
                options=[""] + colunas,
                index=0,
                help="Escolha a coluna de onde vem o custo/preço base. Se deixar vazio, use o custo manual abaixo.",
            )
            custo_manual = st.number_input(
                "Custo manual fallback",
                min_value=0.0,
                value=float(st.session_state.get("preco_custo_base", 0.0)),
                step=1.0,
            )
            lucro = st.number_input(
                "Lucro desejado (%)",
                min_value=0.0,
                value=float(st.session_state.get("lucro_percentual", 30.0)),
                step=1.0,
            )
            taxas = st.number_input(
                "Taxas/despesas (%)",
                min_value=0.0,
                value=float(st.session_state.get("taxas_percentual", 0.0)),
                step=1.0,
            )

            base = custo_manual
            if coluna_custo:
                serie = pd.to_numeric(
                    df[coluna_custo].astype(str).str.replace("R$", "", regex=False).str.replace(".", "", regex=False).str.replace(",", ".", regex=False),
                    errors="coerce",
                )
                base = float(serie.dropna().median()) if not serie.dropna().empty else custo_manual

            preco = round(base * (1 + (lucro + taxas) / 100), 2)
            st.session_state["preco_custo_base"] = custo_manual
            st.session_state["lucro_percentual"] = lucro
            st.session_state["taxas_percentual"] = taxas
            st.session_state["preco_unitario_calculado"] = preco
            st.success(f"Preço calculado para aplicar no mapeamento: R$ {preco:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        else:
            st.session_state.pop("preco_unitario_calculado", None)


def render_origem_mapeamento() -> None:
    st.title("2. Mapeamento")
    st.caption("Revise o resultado logo após anexar a planilha. Se um modelo Bling foi anexado, as colunas dele são usadas como destino.")

    df = st.session_state.get("df_origem")
    if df is None or df.empty:
        st.error("Nenhuma planilha carregada.")
        if st.button("⬅️ Voltar para origem", use_container_width=True):
            _voltar()
        return

    tipo_operacao = st.session_state.get("tipo_operacao", "cadastro")
    deposito = st.session_state.get("deposito_nome")
    modelo_cols = _modelo_columns(tipo_operacao)

    if modelo_cols:
        st.success(f"Modelo Bling anexado detectado: {len(modelo_cols)} colunas serão respeitadas no arquivo final.")
    else:
        st.info("Nenhum modelo Bling anexado. Vou usar o modelo padrão interno do fluxo selecionado.")

    with st.expander("👀 Planilha de origem", expanded=False):
        st.dataframe(df.head(30), use_container_width=True)

    _render_ferramentas(df)

    if tipo_operacao == "estoque" and not modelo_cols:
        st.subheader("🧠 Estoque PRO")

        modo = st.radio("Modo", ["substituir", "entrada", "saida"], horizontal=True)

        mapping = build_stock_mapping(df, deposito)
        df_final = build_stock_dataframe(df, mapping, deposito)
        df_final = apply_stock_mode(df_final, modo)
        df_final = add_stock_delta(df_final)

        resumo = stock_risk_summary(df_final)

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Linhas", resumo["linhas"])
        c2.metric("Negativos", resumo["negativos"])
        c3.metric("Vazios", resumo["vazios"])
        c4.metric("Risco", resumo["variacao_alta"])

        erros = validate_stock_dataframe(df_final)
        bloqueios = block_stock_export(df_final)

        if erros:
            st.warning("⚠️ Problemas:")
            for e in erros:
                st.write("-", e)

        if bloqueios:
            st.error("🚫 BLOQUEADO:")
            for b in bloqueios:
                st.write("-", b)

        st.session_state["df_mapeado"] = df_final

        with st.expander("Preview de estoque mapeado", expanded=False):
            st.dataframe(df_final.head(50), use_container_width=True)

        col1, col2 = st.columns(2)
        with col1:
            if st.button("⬅️ Voltar", use_container_width=True):
                _voltar()
        with col2:
            if st.button("Avançar para exportação ➡️", disabled=bool(bloqueios), use_container_width=True):
                _avancar()

        return

    fornecedor_id = supplier_signature(df)
    memoria = load_memory()
    aprendido = get_supplier_memory(memoria, fornecedor_id)

    sugestoes = suggest_mapping(
        df,
        tipo_operacao,
        learned_mapping=aprendido,
        modelo_columns=modelo_cols,
    )
    mapping: dict[str, str] = {s.target: s.source for s in sugestoes}

    df_final = build_mapped_dataframe(
        df,
        mapping,
        tipo_operacao,
        deposito,
        modelo_columns=modelo_cols,
    )
    df_final = _aplicar_preco_calculado(df_final)

    erros = validar_df_bling(df_final) if tipo_operacao == "cadastro" else []
    if erros:
        st.error("⚠️ Problemas encontrados antes da exportação:")
        for e in erros:
            st.write("-", e)
    else:
        st.success("✔️ Mapeamento pronto para preview final")

    st.session_state["df_mapeado"] = df_final

    with st.expander("🔎 Sugestões aplicadas", expanded=False):
        if sugestoes:
            st.dataframe(
                pd.DataFrame([
                    {"Destino Bling": s.target, "Origem fornecedor": s.source, "Confiança": s.confidence, "Motivo": s.reason}
                    for s in sugestoes
                ]),
                use_container_width=True,
            )
        else:
            st.warning("Nenhuma sugestão automática forte foi encontrada. O preview será gerado com as colunas do modelo e campos vazios onde não houve correspondência.")

    with st.expander("Preview mapeado", expanded=False):
        st.dataframe(df_final.head(50), use_container_width=True)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("⬅️ Voltar para origem", use_container_width=True):
            _voltar()
    with col2:
        if st.button("Avançar para exportação ➡️", use_container_width=True):
            _avancar()
