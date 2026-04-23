from __future__ import annotations

import os

import pandas as pd
import streamlit as st


COLUNAS_PROTEGIDAS = [
    "codigo", "código", "sku", "gtin", "ean",
    "preco", "preço", "valor",
    "estoque", "deposito", "depósito",
    "saldo", "balanco", "balanço",
    "id", "url", "link", "imagem", "video", "vídeo",
]


def _fixar_etapa_preview_final() -> None:
    """
    Impede que qualquer interação neste módulo volte o fluxo para mapeamento.
    """
    st.session_state["etapa_origem"] = "preview_final"
    st.session_state["etapa_atual"] = "preview_final"
    st.session_state["_ultima_etapa_sincronizada_url"] = "preview_final"
    st.session_state["_preview_final_ia_ativa"] = True


def _df_valido(df) -> bool:
    return isinstance(df, pd.DataFrame) and not df.empty and len(df.columns) > 0


def _coluna_protegida(coluna) -> bool:
    nome = str(coluna or "").lower()
    return any(k in nome for k in COLUNAS_PROTEGIDAS)


def _identificar_colunas(df: pd.DataFrame) -> list[str]:
    cols = []

    for coluna in df.columns:
        nome = str(coluna or "").lower()

        if _coluna_protegida(coluna):
            continue

        if any(k in nome for k in ["descr", "nome", "titulo", "título", "produto"]):
            cols.append(coluna)

    return cols


def _get_openai_client():
    try:
        from openai import OpenAI
    except Exception:
        return None

    try:
        key = st.secrets.get("OPENAI_API_KEY", "") or os.getenv("OPENAI_API_KEY", "")
    except Exception:
        key = os.getenv("OPENAI_API_KEY", "")

    key = str(key or "").strip()

    if not key:
        return None

    try:
        return OpenAI(api_key=key)
    except Exception:
        return None


def _get_modelo() -> str:
    try:
        modelo = st.secrets.get("OPENAI_MODEL", "") or os.getenv("OPENAI_MODEL", "")
    except Exception:
        modelo = os.getenv("OPENAI_MODEL", "")

    return str(modelo or "gpt-4o-mini").strip()


def _contexto_row(row: pd.Series) -> str:
    partes = []

    for coluna, valor in row.items():
        if _coluna_protegida(coluna):
            continue

        valor = str(valor or "").strip()

        if valor:
            partes.append(f"{coluna}: {valor[:140]}")

    return " | ".join(partes[:10])


def _limpar_texto_ia(texto: str, limite: int = 350) -> str:
    texto = str(texto or "").strip()
    texto = texto.replace("\n", " ").replace("\r", " ")
    texto = " ".join(texto.split())

    for prefixo in ["Descrição:", "Descricao:", "Texto:", "Resposta:", "Resultado:"]:
        if texto.lower().startswith(prefixo.lower()):
            texto = texto[len(prefixo):].strip()

    if len(texto) > limite:
        texto = texto[:limite].rstrip()

    return texto


def _prompt_copy(texto: str, contexto: str, limite: int) -> str:
    return f"""
Você é especialista em copy para e-commerce brasileiro.

Objetivo:
Reformular a descrição para ficar mais persuasiva e vender melhor.

Regras obrigatórias:
- Não invente características.
- Não invente marca, modelo, voltagem, medida, material, compatibilidade ou função.
- Use somente informações existentes no texto e no contexto.
- Não use emojis.
- Não use lista.
- Não use aspas.
- Não mencione IA.
- Retorne somente a descrição final.
- Máximo de {limite} caracteres.

Texto original:
{texto}

Contexto do produto:
{contexto}

Descrição final:
""".strip()


def _gerar_copy(texto: str, row: pd.Series, client, limite: int) -> str:
    texto = str(texto or "").strip()

    if not texto:
        return ""

    if client is None:
        return _limpar_texto_ia(
            f"{texto}. Ideal para quem busca praticidade, qualidade e ótimo custo-benefício no dia a dia.",
            limite=limite,
        )

    try:
        resposta = client.chat.completions.create(
            model=_get_modelo(),
            messages=[
                {
                    "role": "system",
                    "content": "Você cria descrições comerciais de alta conversão para e-commerce, sem inventar informações.",
                },
                {
                    "role": "user",
                    "content": _prompt_copy(texto, _contexto_row(row), limite),
                },
            ],
            temperature=0.65,
            max_tokens=180,
        )

        conteudo = resposta.choices[0].message.content if resposta.choices else ""
        saida = _limpar_texto_ia(conteudo, limite=limite)

        return saida or texto

    except Exception as exc:
        st.session_state["erro_copy"] = str(exc)
        return _limpar_texto_ia(
            f"{texto}. Ideal para quem busca praticidade, qualidade e ótimo custo-benefício no dia a dia.",
            limite=limite,
        )


def _aplicar_copy(df: pd.DataFrame, colunas: list[str], limite_linhas: int, limite_chars: int) -> pd.DataFrame:
    _fixar_etapa_preview_final()

    client = _get_openai_client()
    df_out = df.copy().fillna("")

    total = min(int(limite_linhas), len(df_out.index))

    if total <= 0:
        return df_out

    barra = st.progress(0, text="Gerando descrições com IA...")

    for i, idx in enumerate(df_out.index[:total]):
        row = df_out.loc[idx]

        for coluna in colunas:
            if coluna not in df_out.columns or _coluna_protegida(coluna):
                continue

            valor = str(df_out.at[idx, coluna] or "").strip()
            df_out.at[idx, coluna] = _gerar_copy(valor, row, client, limite_chars)

        pct = int(((i + 1) / total) * 100)
        barra.progress(pct, text=f"Gerando descrições com IA... {pct}%")

    barra.empty()
    return df_out.fillna("")


def _aplicar_somente_colunas_descricao(
    df_base: pd.DataFrame,
    df_preview: pd.DataFrame,
    colunas: list[str],
) -> pd.DataFrame:
    df_resultado = df_base.copy().fillna("")

    if not _df_valido(df_preview):
        return df_resultado

    for coluna in colunas:
        if coluna in df_resultado.columns and coluna in df_preview.columns and not _coluna_protegida(coluna):
            limite = min(len(df_resultado.index), len(df_preview.index))
            df_resultado.loc[df_resultado.index[:limite], coluna] = df_preview[coluna].iloc[:limite].values

    return df_resultado.fillna("")


def render_ai_descricao(df_final: pd.DataFrame) -> pd.DataFrame:
    _fixar_etapa_preview_final()

    if not _df_valido(df_final):
        return df_final

    st.markdown("### 🚀 Otimização de descrição com IA")

    df_base_session = st.session_state.get("df_final")

    if _df_valido(df_base_session):
        df_base = df_base_session.copy().fillna("")
    else:
        df_base = df_final.copy().fillna("")

    colunas = _identificar_colunas(df_base)

    if not colunas:
        st.info("Nenhuma coluna de descrição encontrada.")
        return df_base

    st.caption("A IA só altera as colunas de descrição selecionadas. Código, GTIN, preço, estoque, depósito, imagens e vídeos ficam protegidos.")

    colunas_escolhidas = st.multiselect(
        "Colunas para otimizar",
        options=colunas,
        default=colunas[:2],
        key="copy_pro_colunas",
        on_change=_fixar_etapa_preview_final,
    )

    col1, col2 = st.columns(2)

    with col1:
        limite = st.number_input(
            "Quantidade de produtos",
            min_value=1,
            max_value=max(len(df_base.index), 1),
            value=min(20, len(df_base.index)),
            step=1,
            key="copy_pro_limite",
            on_change=_fixar_etapa_preview_final,
        )

    with col2:
        limite_chars = st.number_input(
            "Máx. caracteres",
            min_value=120,
            max_value=800,
            value=350,
            step=10,
            key="copy_pro_limite_chars",
            on_change=_fixar_etapa_preview_final,
        )

    col_btn1, col_btn2 = st.columns(2)

    with col_btn1:
        if st.button("👁️ Gerar prévia IA", use_container_width=True, key="btn_copy_pro_gerar"):
            _fixar_etapa_preview_final()

            if not colunas_escolhidas:
                st.warning("Selecione pelo menos uma coluna de descrição.")
                return df_base

            df_prev = _aplicar_copy(
                df=df_base,
                colunas=list(colunas_escolhidas),
                limite_linhas=int(limite),
                limite_chars=int(limite_chars),
            )

            st.session_state["copy_preview"] = df_prev.copy()
            st.session_state["copy_preview_colunas"] = list(colunas_escolhidas)
            st.session_state["df_final"] = df_base.copy()
            _fixar_etapa_preview_final()

            st.success("Prévia de descrição gerada com sucesso.")
            st.rerun()

    with col_btn2:
        if st.button("🔥 Aplicar no resultado final", use_container_width=True, key="btn_copy_pro_aplicar"):
            _fixar_etapa_preview_final()

            df_prev = st.session_state.get("copy_preview")
            colunas_prev = st.session_state.get("copy_preview_colunas", colunas_escolhidas)

            if not _df_valido(df_prev):
                st.warning("Gere a prévia antes de aplicar.")
                return df_base

            df_resultado = _aplicar_somente_colunas_descricao(
                df_base=df_base,
                df_preview=df_prev,
                colunas=list(colunas_prev),
            )

            st.session_state["df_final"] = df_resultado.copy()
            st.session_state["df_final_manual_preservado"] = True
            st.session_state["ia_descricao_aplicada"] = True
            _fixar_etapa_preview_final()

            st.success("Descrições aplicadas no resultado final.")
            st.rerun()

    erro = st.session_state.get("erro_copy")
    if erro:
        with st.expander("⚠️ Erro da IA", expanded=False):
            st.code(str(erro))

    df_prev = st.session_state.get("copy_preview")
    if _df_valido(df_prev):
        colunas_preview = st.session_state.get("copy_preview_colunas", colunas_escolhidas)
        colunas_preview = [c for c in colunas_preview if c in df_prev.columns]

        if colunas_preview:
            with st.expander("🔎 Prévia das descrições com IA", expanded=False):
                st.dataframe(df_prev[colunas_preview].head(10), use_container_width=True)

    _fixar_etapa_preview_final()
    return st.session_state.get("df_final", df_base)
