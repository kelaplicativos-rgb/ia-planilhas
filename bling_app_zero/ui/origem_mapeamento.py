from typing import Dict, List

import pandas as pd
import streamlit as st


def _to_text(valor) -> str:
    if valor is None:
        return ""
    try:
        if pd.isna(valor):
            return ""
    except Exception:
        pass
    texto = str(valor).strip()
    return "" if texto.lower() == "nan" else texto


def _normalizar_texto(texto: str) -> str:
    import re
    import unicodedata

    texto = str(texto or "").strip().lower()
    texto = unicodedata.normalize("NFKD", texto)
    texto = texto.encode("ascii", "ignore").decode("utf-8")
    texto = re.sub(r"[^a-z0-9]+", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def _mapa_colunas_normalizadas(colunas: List[str]) -> Dict[str, str]:
    return {_normalizar_texto(col): col for col in colunas}


def _serie_texto(df: pd.DataFrame, coluna: str) -> pd.Series:
    if coluna not in df.columns:
        return pd.Series([""] * len(df), index=df.index, dtype="string")

    return (
        df[coluna]
        .apply(_to_text)
        .astype("string")
        .fillna("")
        .str.strip()
    )


def _sugerir_por_nome_modelo(colunas_origem: List[str], colunas_modelo: List[str]) -> Dict[str, str]:
    mapa_origem = _mapa_colunas_normalizadas(colunas_origem)
    resultado: Dict[str, str] = {}

    sinonimos = {
        "codigo": ["codigo", "código", "sku", "referencia", "ref"],
        "descricao": ["descricao", "descrição", "nome", "produto", "titulo"],
        "unidade": ["unidade", "un", "und"],
        "ncm": ["ncm"],
        "marca": ["marca", "fabricante"],
        "categoria": ["categoria", "departamento", "grupo"],
        "gtin": ["gtin", "ean", "codigo barras", "codigo de barras", "cean", "ceantrib"],
        "preco unitario": ["preco", "preço", "valor", "valor venda", "preco venda", "preco de venda"],
        "preco de custo": ["custo", "preco custo", "preço custo", "valor custo", "preco de custo"],
        "balanco": ["estoque", "quantidade", "qtd", "saldo", "balanco", "balanço"],
        "deposito": ["deposito", "depósito"],
        "peso": ["peso", "peso liquido", "peso líquido", "peso bruto"],
    }

    for col_modelo in colunas_modelo:
        chave = _normalizar_texto(col_modelo)

        if chave in mapa_origem:
            resultado[col_modelo] = mapa_origem[chave]
            continue

        for destino, termos in sinonimos.items():
            if destino in chave:
                for termo in termos:
                    termo_norm = _normalizar_texto(termo)
                    if termo_norm in mapa_origem:
                        resultado[col_modelo] = mapa_origem[termo_norm]
                        break
            if col_modelo in resultado:
                break

        if col_modelo not in resultado:
            for origem in colunas_origem:
                origem_norm = _normalizar_texto(origem)
                if origem_norm in chave or chave in origem_norm:
                    resultado[col_modelo] = origem
                    break

    return resultado


def render_mapeamento_manual(
    df_origem: pd.DataFrame,
    colunas_destino: List[str],
    state_key: str,
) -> Dict[str, str]:
    st.subheader("Mapeamento manual")
    st.caption("Relacione manualmente as colunas da origem com as colunas reais do modelo final.")

    if state_key not in st.session_state:
        st.session_state[state_key] = _sugerir_por_nome_modelo(list(df_origem.columns), colunas_destino)

    mapeamento = dict(st.session_state.get(state_key, {}))
    colunas_origem = list(df_origem.columns)
    usados = set()

    cab1, cab2, cab3 = st.columns([1.3, 1.7, 2.0])
    with cab1:
        st.markdown("**Coluna do modelo**")
    with cab2:
        st.markdown("**Coluna da origem**")
    with cab3:
        st.markdown("**Exemplo**")

    for destino in colunas_destino:
        atual = str(mapeamento.get(destino, "") or "").strip()
        if atual:
            usados.add(atual)

        c1, c2, c3 = st.columns([1.3, 1.7, 2.0])

        with c1:
            st.markdown(f"`{destino}`")

        with c2:
            opcoes = [""]
            for col in colunas_origem:
                if col == atual or col not in (usados - ({atual} if atual else set())):
                    opcoes.append(col)

            indice = opcoes.index(atual) if atual in opcoes else 0

            novo_valor = st.selectbox(
                f"Origem para {destino}",
                opcoes,
                index=indice,
                key=f"map_{state_key}_{destino}",
                label_visibility="collapsed",
            )
            mapeamento[destino] = novo_valor or ""

        with c3:
            origem_exemplo = mapeamento.get(destino, "")
            if origem_exemplo and origem_exemplo in df_origem.columns:
                serie = _serie_texto(df_origem, origem_exemplo)
                serie = serie[serie != ""]
                exemplo = serie.iloc[0] if not serie.empty else ""
                st.caption(str(exemplo)[:120] if exemplo else "—")
            else:
                st.caption("—")

    st.session_state[state_key] = mapeamento
    return mapeamento
