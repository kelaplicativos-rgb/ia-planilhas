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
    st.session_state["etapa"] = "preview_final"
    st.session_state["wizard_etapa_atual"] = "preview_final"
    st.session_state["wizard_etapa_maxima"] = "preview_final"
    st.session_state["_ultima_etapa_sincronizada_url"] = "preview_final"
    st.session_state["_preview_final_ia_ativa"] = True
    st.session_state["_flow_lock_preview_final"] = True


def _df_valido(df) -> bool:
    return isinstance(df, pd.DataFrame) and not df.empty and len(df.columns) > 0


def _coluna_protegida(coluna) -> bool:
    nome = str(coluna or "").lower()
    return any(k in nome for k in COLUNAS_PROTEGIDAS)


def _eh_coluna_titulo(coluna) -> bool:
    nome = str(coluna or "").lower()
    return any(k in nome for k in ["titulo", "título", "nome", "produto"]) and "descr" not in nome


def _eh_coluna_descricao(coluna) -> bool:
    nome = str(coluna or "").lower()
    return "descr" in nome


def _identificar_colunas(df: pd.DataFrame) -> list[str]:
    cols = []

    for coluna in df.columns:
        if _coluna_protegida(coluna):
            continue

        if _eh_coluna_titulo(coluna) or _eh_coluna_descricao(coluna):
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
            partes.append(f"{coluna}: {valor[:160]}")

    return " | ".join(partes[:12])


def _limpar_texto_ia(texto: str, limite: int) -> str:
    texto = str(texto or "").strip()
    texto = texto.replace("\n", " ").replace("\r", " ")
    texto = " ".join(texto.split())

    for prefixo in ["Descrição:", "Descricao:", "Título:", "Titulo:", "Texto:", "Resposta:", "Resultado:"]:
        if texto.lower().startswith(prefixo.lower()):
            texto = texto[len(prefixo):].strip()

    if len(texto) > limite:
        texto = texto[:limite].rstrip()

    return texto


def _limite_descricao(tamanho: str) -> int:
    if tamanho == "Pequena":
        return 180
    if tamanho == "Grande":
        return 600
    return 350


def _prompt_copy(texto: str, contexto: str, coluna: str, limite: int) -> str:
    if _eh_coluna_titulo(coluna):
        return f"""
Você é especialista em títulos para e-commerce brasileiro.

Objetivo:
Criar um título comercial, claro e forte para venda.

Regras obrigatórias:
- Máximo de {limite} caracteres.
- Não invente características.
- Não invente marca, modelo, voltagem, medida, material, compatibilidade ou função.
- Use somente informações existentes no texto e no contexto.
- Não use emojis.
- Não use aspas.
- Não use ponto final.
- Retorne somente o título final.

Texto original:
{texto}

Contexto do produto:
{contexto}

Título final:
""".strip()

    return f"""
Você é especialista em copy para e-commerce brasileiro.

Objetivo:
Reformular a descrição para ficar mais persuasiva e vender melhor.

Regras obrigatórias:
- Máximo de {limite} caracteres.
- Não invente características.
- Não invente marca, modelo, voltagem, medida, material, compatibilidade ou função.
- Use somente informações existentes no texto e no contexto.
- Não use emojis.
- Não use lista.
- Não use aspas.
- Não mencione IA.
- Retorne somente a descrição final.

Texto original:
{texto}

Contexto do produto:
{contexto}

Descrição final:
""".strip()


def _gerar_copy(texto: str, row: pd.Series, coluna: str, client, limite: int) -> str:
    texto = str(texto or "").strip()

    if not texto:
        return ""

    if client is None:
        if _eh_coluna_titulo(coluna):
            return _limpar_texto_ia(texto, limite)

        return _limpar_texto_ia(
            f"{texto}. Ideal para quem busca praticidade, qualidade e ótimo custo-benefício no dia a dia.",
            limite,
        )

    try:
        resposta = client.chat.completions.create(
            model=_get_modelo(),
            messages=[
                {
                    "role": "system",
                    "content": "Você cria títulos e descrições comerciais de alta conversão para e-commerce, sem inventar informações.",
                },
                {
                    "role": "user",
                    "content": _prompt_copy(texto, _contexto_row(row), str(coluna), limite),
                },
            ],
            temperature=0.65,
            max_tokens=260,
        )

        conteudo = resposta.choices[0].message.content if resposta.choices else ""
        saida = _limpar_texto_ia(conteudo, limite)

        return saida or texto

    except Exception as exc:
        st.session_state["erro_copy"] = str(exc)

        if _eh_coluna_titulo(coluna):
            return _limpar_texto_ia(texto, limite)

        return _limpar_texto_ia(
            f"{texto}. Ideal para quem busca praticidade, qualidade e ótimo custo-benefício no dia a dia.",
            limite,
        )


def _linha_contem_palavras(row: pd.Series, palavras: list[str], colunas: list[str]) -> bool:
    if not palavras:
        return True

    texto_linha = []

    for coluna in colunas:
        if coluna in row.index:
            texto_linha.append(str(row[coluna] or "").lower())

    texto = " ".join(texto_linha)

    return any(palavra.lower().strip() in texto for palavra in palavras if palavra.strip())


def _aplicar_copy(
    df: pd.DataFrame,
    colunas: list[str],
    palavras_chave: list[str],
    tamanho_descricao: str,
) -> pd.DataFrame:
    _fixar_etapa_preview_final()

    client = _get_openai_client()
    df_out = df.copy().fillna("")

    indices_processar = [
        idx for idx in df_out.index
        if _linha_contem_palavras(df_out.loc[idx], palavras_chave, colunas)
    ]

    total = len(indices_processar)

    if total <= 0:
        st.warning("Nenhum produto encontrado com as palavras-chave informadas.")
        return df_out

    barra = st.progress(0, text="Gerando descrições com IA...")

    for i, idx in enumerate(indices_processar):
        row = df_out.loc[idx]

        for coluna in colunas:
            if coluna not in df_out.columns or _coluna_protegida(coluna):
                continue

            limite = 59 if _eh_coluna_titulo(coluna) else _limite_descricao(tamanho_descricao)
            valor = str(df_out.at[idx, coluna] or "").strip()

            df_out.at[idx, coluna] = _gerar_copy(valor, row, str(coluna), client, limite)

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
        st.info("Nenhuma coluna de título ou descrição encontrada.")
        return df_base

    st.caption(
        "A IA altera apenas as colunas selecionadas. "
        "Título fica limitado a 59 caracteres. Descrições podem ser pequenas, médias ou grandes."
    )

    colunas_escolhidas = st.multiselect(
        "Colunas para otimizar",
        options=colunas,
        default=colunas[:2],
        key="copy_pro_colunas",
        on_change=_fixar_etapa_preview_final,
    )

    modo_filtro = st.radio(
        "Aplicar em quais produtos?",
        options=["Todos os produtos", "Somente produtos com palavras-chave"],
        horizontal=True,
        key="copy_pro_modo_filtro",
        on_change=_fixar_etapa_preview_final,
    )

    palavras_chave: list[str] = []

    if modo_filtro == "Somente produtos com palavras-chave":
        texto_palavras = st.text_input(
            "Palavras-chave nas descrições/títulos",
            placeholder="Ex: fone, carregador, cabo usb",
            key="copy_pro_palavras_chave",
            on_change=_fixar_etapa_preview_final,
        )

        palavras_chave = [
            p.strip().lower()
            for p in str(texto_palavras or "").split(",")
            if p.strip()
        ]

    tamanho_descricao = st.selectbox(
        "Tamanho das descrições",
        options=["Pequena", "Média", "Grande"],
        index=1,
        key="copy_pro_tamanho_descricao",
        on_change=_fixar_etapa_preview_final,
    )

    st.caption(
        f"Produtos no arquivo: {len(df_base)} | "
        f"Títulos: até 59 caracteres | "
        f"Descrição {tamanho_descricao.lower()}: até {_limite_descricao(tamanho_descricao)} caracteres"
    )

    col_btn1, col_btn2 = st.columns(2)

    with col_btn1:
        if st.button("👁️ Gerar prévia IA", use_container_width=True, key="btn_copy_pro_gerar"):
            _fixar_etapa_preview_final()

            if not colunas_escolhidas:
                st.warning("Selecione pelo menos uma coluna de título ou descrição.")
                return df_base

            if modo_filtro == "Somente produtos com palavras-chave" and not palavras_chave:
                st.warning("Informe pelo menos uma palavra-chave.")
                return df_base

            df_prev = _aplicar_copy(
                df=df_base,
                colunas=list(colunas_escolhidas),
                palavras_chave=palavras_chave,
                tamanho_descricao=tamanho_descricao,
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
