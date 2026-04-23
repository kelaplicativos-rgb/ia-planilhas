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


def _identificar_colunas_disponiveis(df: pd.DataFrame) -> list[str]:
    if not _df_valido(df):
        return []

    return [str(coluna) for coluna in df.columns if not _coluna_protegida(coluna)]


def _sugerir_coluna_titulo(colunas: list[str]) -> str:
    for alvo in ["Descrição", "Descricao", "Nome", "Produto", "Título", "Titulo"]:
        for coluna in colunas:
            if str(coluna).strip().lower() == alvo.lower():
                return coluna

    for coluna in colunas:
        if _eh_coluna_titulo(coluna):
            return coluna

    return "Não otimizar título"


def _sugerir_coluna_descricao(colunas: list[str], coluna_titulo: str = "") -> str:
    for alvo in [
        "Descrição Curta",
        "Descricao Curta",
        "Descrição complementar",
        "Descricao complementar",
        "Descrição Completa",
        "Descricao Completa",
    ]:
        for coluna in colunas:
            if str(coluna).strip().lower() == alvo.lower() and coluna != coluna_titulo:
                return coluna

    for coluna in colunas:
        if coluna != coluna_titulo and _eh_coluna_descricao(coluna):
            return coluna

    return "Não otimizar descrição completa"


def _get_secret_ou_env(*nomes: str) -> str:
    for nome in nomes:
        try:
            valor = st.secrets.get(nome, "")
        except Exception:
            valor = ""

        if valor:
            return str(valor).strip()

        valor_env = os.getenv(nome, "")
        if valor_env:
            return str(valor_env).strip()

    return ""


def _get_api_key() -> str:
    return _get_secret_ou_env("OPENAI_API_KEY", "openai_api_key", "api_key")


def _get_modelo() -> str:
    modelo = _get_secret_ou_env("OPENAI_MODEL", "model", "MODEL", "openai_model")
    return modelo or "gpt-4o-mini"


def _get_openai_client():
    try:
        from openai import OpenAI
    except Exception as exc:
        st.session_state["erro_copy"] = f"Pacote openai não importou: {exc}"
        return None

    key = _get_api_key()

    if not key:
        st.session_state["erro_copy"] = "OPENAI_API_KEY não configurada nos secrets."
        return None

    try:
        return OpenAI(api_key=key)
    except Exception as exc:
        st.session_state["erro_copy"] = f"Falha ao criar cliente OpenAI: {exc}"
        return None


def _status_ia() -> tuple[bool, str, str]:
    api_key = _get_api_key()
    modelo = _get_modelo()

    if not api_key:
        return False, modelo, "OPENAI_API_KEY não encontrada nos secrets."

    try:
        import openai  # noqa: F401
    except Exception as exc:
        return False, modelo, f"Pacote openai indisponível: {exc}"

    return True, modelo, "IA real configurada."


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


def _prompt_titulo(texto: str, contexto: str, limite: int) -> str:
    return f"""
Você é especialista em títulos de produtos para e-commerce brasileiro.

Objetivo:
Criar um título comercial, claro, direto e forte para venda.

Regras obrigatórias:
- Máximo de {limite} caracteres.
- Não invente características.
- Não invente marca, modelo, voltagem, medida, material, compatibilidade ou função.
- Use somente informações existentes no texto e no contexto.
- Não use emojis.
- Não use aspas.
- Não use ponto final.
- Retorne somente o título final.
- O título precisa ser diferente do texto original quando for possível melhorar.

Texto original:
{texto}

Contexto do produto:
{contexto}

Título final:
""".strip()


def _prompt_descricao(texto: str, contexto: str, limite: int, tamanho: str) -> str:
    return f"""
Você é especialista em copy para e-commerce brasileiro.

Objetivo:
Reformular a descrição completa do produto para ficar mais persuasiva, natural e vendedora.

Tamanho desejado:
{tamanho}

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
- A descrição precisa ser diferente do texto original quando for possível melhorar.

Texto original:
{texto}

Contexto do produto:
{contexto}

Descrição final:
""".strip()


def _fallback_local(texto: str, limite: int, tipo: str) -> str:
    texto = str(texto or "").strip()

    if not texto:
        return ""

    if tipo == "titulo":
        return _limpar_texto_ia(texto, limite)

    return _limpar_texto_ia(
        f"{texto}. Uma ótima opção para quem busca praticidade, qualidade e excelente custo-benefício.",
        limite,
    )


def _gerar_com_ia(
    texto: str,
    row: pd.Series,
    client,
    limite: int,
    tipo: str,
    tamanho_descricao: str = "Média",
) -> str:
    texto = str(texto or "").strip()

    if not texto:
        return ""

    if client is None:
        st.session_state["ia_copy_usou_fallback"] = True
        return _fallback_local(texto, limite, tipo)

    try:
        contexto = _contexto_row(row)

        if tipo == "titulo":
            prompt = _prompt_titulo(texto, contexto, limite)
            max_tokens = 80
        else:
            prompt = _prompt_descricao(texto, contexto, limite, tamanho_descricao)
            max_tokens = 280

        resposta = client.chat.completions.create(
            model=_get_modelo(),
            messages=[
                {
                    "role": "system",
                    "content": "Você cria títulos e descrições comerciais de alta conversão para e-commerce, sem inventar informações.",
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            temperature=0.75,
            max_tokens=max_tokens,
        )

        conteudo = resposta.choices[0].message.content if resposta.choices else ""
        saida = _limpar_texto_ia(conteudo, limite)

        if not saida:
            st.session_state["ia_copy_usou_fallback"] = True
            return _fallback_local(texto, limite, tipo)

        return saida

    except Exception as exc:
        st.session_state["erro_copy"] = str(exc)
        st.session_state["ia_copy_usou_fallback"] = True
        return _fallback_local(texto, limite, tipo)


def _linha_contem_palavras(row: pd.Series, palavras: list[str], colunas_busca: list[str]) -> bool:
    if not palavras:
        return True

    texto_linha = []

    for coluna in colunas_busca:
        if coluna and coluna in row.index:
            texto_linha.append(str(row[coluna] or "").lower())

    texto = " ".join(texto_linha)

    return any(palavra.lower().strip() in texto for palavra in palavras if palavra.strip())


def _contar_alteracoes(df_antes: pd.DataFrame, df_depois: pd.DataFrame, colunas: list[str]) -> int:
    if not _df_valido(df_antes) or not _df_valido(df_depois):
        return 0

    total = 0

    for coluna in colunas:
        if coluna not in df_antes.columns or coluna not in df_depois.columns:
            continue

        serie_antes = df_antes[coluna].astype(str).fillna("").str.strip()
        serie_depois = df_depois[coluna].astype(str).fillna("").str.strip()

        limite = min(len(serie_antes), len(serie_depois))
        total += int((serie_antes.iloc[:limite].values != serie_depois.iloc[:limite].values).sum())

    return int(total)


def _aplicar_copy(
    df: pd.DataFrame,
    coluna_titulo: str,
    coluna_descricao: str,
    palavras_chave: list[str],
    tamanho_descricao: str,
) -> pd.DataFrame:
    _fixar_etapa_preview_final()

    st.session_state["erro_copy"] = ""
    st.session_state["ia_copy_usou_fallback"] = False

    client = _get_openai_client()
    df_out = df.copy().fillna("")

    colunas_busca = []
    if coluna_titulo and coluna_titulo in df_out.columns:
        colunas_busca.append(coluna_titulo)
    if coluna_descricao and coluna_descricao in df_out.columns:
        colunas_busca.append(coluna_descricao)

    if not colunas_busca:
        st.warning("Selecione pelo menos uma coluna válida para otimizar.")
        return df_out

    indices_processar = [
        idx for idx in df_out.index
        if _linha_contem_palavras(df_out.loc[idx], palavras_chave, colunas_busca)
    ]

    total = len(indices_processar)

    if total <= 0:
        st.warning("Nenhum produto encontrado com as palavras-chave informadas.")
        return df_out

    barra = st.progress(0, text="Gerando títulos e descrições com IA...")

    limite_titulo = 60
    limite_desc = _limite_descricao(tamanho_descricao)

    for i, idx in enumerate(indices_processar):
        row = df_out.loc[idx]

        if coluna_titulo and coluna_titulo in df_out.columns and not _coluna_protegida(coluna_titulo):
            valor_titulo = str(df_out.at[idx, coluna_titulo] or "").strip()
            df_out.at[idx, coluna_titulo] = _gerar_com_ia(
                texto=valor_titulo,
                row=row,
                client=client,
                limite=limite_titulo,
                tipo="titulo",
            )

        if coluna_descricao and coluna_descricao in df_out.columns and not _coluna_protegida(coluna_descricao):
            valor_desc = str(df_out.at[idx, coluna_descricao] or "").strip()
            df_out.at[idx, coluna_descricao] = _gerar_com_ia(
                texto=valor_desc,
                row=row,
                client=client,
                limite=limite_desc,
                tipo="descricao",
                tamanho_descricao=tamanho_descricao,
            )

        pct = int(((i + 1) / total) * 100)
        barra.progress(pct, text=f"Gerando títulos e descrições com IA... {pct}%")

    barra.empty()
    return df_out.fillna("")


def _aplicar_somente_colunas_escolhidas(
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

    ia_ok, modelo, motivo = _status_ia()

    if ia_ok:
        st.success(f"✅ IA real conectada | Modelo: {modelo}")
    else:
        st.error(f"❌ IA real não conectada | {motivo}")
        st.caption("O sistema vai usar fallback local. Nesse modo, o título pode ficar quase igual ao original.")

    df_base_session = st.session_state.get("df_final")

    if _df_valido(df_base_session):
        df_base = df_base_session.copy().fillna("")
    else:
        df_base = df_final.copy().fillna("")

    colunas = _identificar_colunas_disponiveis(df_base)

    if not colunas:
        st.info("Nenhuma coluna disponível para otimização.")
        return df_base

    st.caption(
        "Selecione separadamente a coluna de título e a coluna de descrição completa. "
        "Código, GTIN, preço, estoque, depósito, imagens e vídeos ficam protegidos."
    )

    opcoes_titulo = ["Não otimizar título"] + colunas
    sugestao_titulo = _sugerir_coluna_titulo(colunas)
    index_titulo = opcoes_titulo.index(sugestao_titulo) if sugestao_titulo in opcoes_titulo else 0

    coluna_titulo_escolhida = st.selectbox(
        "Coluna do título do produto (máx. 60 caracteres)",
        options=opcoes_titulo,
        index=index_titulo,
        key="copy_pro_coluna_titulo",
        on_change=_fixar_etapa_preview_final,
    )

    opcoes_descricao = ["Não otimizar descrição completa"] + [
        c for c in colunas if c != coluna_titulo_escolhida
    ]
    sugestao_descricao = _sugerir_coluna_descricao(colunas, coluna_titulo_escolhida)
    index_descricao = opcoes_descricao.index(sugestao_descricao) if sugestao_descricao in opcoes_descricao else 0

    coluna_descricao_escolhida = st.selectbox(
        "Coluna da descrição completa do produto",
        options=opcoes_descricao,
        index=index_descricao,
        key="copy_pro_coluna_descricao",
        on_change=_fixar_etapa_preview_final,
    )

    tamanho_descricao = st.selectbox(
        "Tamanho da descrição completa",
        options=["Pequena", "Média", "Grande"],
        index=1,
        key="copy_pro_tamanho_descricao",
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
            "Palavras-chave no título/descrição",
            placeholder="Ex: fone, carregador, cabo usb",
            key="copy_pro_palavras_chave",
            on_change=_fixar_etapa_preview_final,
        )

        palavras_chave = [
            p.strip().lower()
            for p in str(texto_palavras or "").split(",")
            if p.strip()
        ]

    coluna_titulo = "" if coluna_titulo_escolhida == "Não otimizar título" else coluna_titulo_escolhida
    coluna_descricao = "" if coluna_descricao_escolhida == "Não otimizar descrição completa" else coluna_descricao_escolhida

    colunas_escolhidas = []
    if coluna_titulo:
        colunas_escolhidas.append(coluna_titulo)
    if coluna_descricao:
        colunas_escolhidas.append(coluna_descricao)

    st.caption(
        f"Produtos no arquivo: {len(df_base)} | "
        f"Título: até 60 caracteres | "
        f"Descrição {tamanho_descricao.lower()}: até {_limite_descricao(tamanho_descricao)} caracteres"
    )

    col_debug1, col_debug2, col_debug3 = st.columns(3)
    with col_debug1:
        st.metric("Modelo", modelo)
    with col_debug2:
        st.metric("Colunas escolhidas", len(colunas_escolhidas))
    with col_debug3:
        st.metric("Alterações na última prévia", int(st.session_state.get("copy_preview_total_alteracoes", 0) or 0))

    col_btn1, col_btn2 = st.columns(2)

    with col_btn1:
        if st.button("👁️ Gerar prévia IA", use_container_width=True, key="btn_copy_pro_gerar"):
            _fixar_etapa_preview_final()

            if not colunas_escolhidas:
                st.warning("Selecione a coluna de título, a coluna de descrição completa ou ambas.")
                return df_base

            if modo_filtro == "Somente produtos com palavras-chave" and not palavras_chave:
                st.warning("Informe pelo menos uma palavra-chave.")
                return df_base

            df_prev = _aplicar_copy(
                df=df_base,
                coluna_titulo=coluna_titulo,
                coluna_descricao=coluna_descricao,
                palavras_chave=palavras_chave,
                tamanho_descricao=tamanho_descricao,
            )

            total_alteracoes = _contar_alteracoes(df_base, df_prev, colunas_escolhidas)

            st.session_state["copy_preview"] = df_prev.copy()
            st.session_state["copy_preview_colunas"] = list(colunas_escolhidas)
            st.session_state["copy_preview_total_alteracoes"] = int(total_alteracoes)
            st.session_state["df_final"] = df_base.copy()
            _fixar_etapa_preview_final()

            if total_alteracoes > 0:
                st.success(f"Prévia gerada. {total_alteracoes} célula(s) foram alteradas.")
            else:
                st.warning("A prévia foi gerada, mas nenhuma célula mudou. Verifique se a IA real conectou e se as colunas escolhidas possuem texto.")

            st.rerun()

    with col_btn2:
        if st.button("🔥 Aplicar no resultado final", use_container_width=True, key="btn_copy_pro_aplicar"):
            _fixar_etapa_preview_final()

            df_prev = st.session_state.get("copy_preview")
            colunas_prev = st.session_state.get("copy_preview_colunas", colunas_escolhidas)

            if not _df_valido(df_prev):
                st.warning("Gere a prévia antes de aplicar.")
                return df_base

            df_resultado = _aplicar_somente_colunas_escolhidas(
                df_base=df_base,
                df_preview=df_prev,
                colunas=list(colunas_prev),
            )

            st.session_state["df_final"] = df_resultado.copy()
            st.session_state["df_final_manual_preservado"] = True
            st.session_state["ia_descricao_aplicada"] = True
            _fixar_etapa_preview_final()

            st.success("Título/descrição aplicados no resultado final.")
            st.rerun()

    if st.session_state.get("ia_copy_usou_fallback"):
        st.warning("⚠️ A última geração usou fallback local. Isso significa que a OpenAI não respondeu corretamente.")

    erro = st.session_state.get("erro_copy")
    if erro:
        with st.expander("⚠️ Erro/diagnóstico da IA", expanded=True):
            st.code(str(erro))

    df_prev = st.session_state.get("copy_preview")
    if _df_valido(df_prev):
        colunas_preview = st.session_state.get("copy_preview_colunas", colunas_escolhidas)
        colunas_preview = [c for c in colunas_preview if c in df_prev.columns]

        if colunas_preview:
            with st.expander("🔎 Prévia das alterações com IA", expanded=True):
                st.dataframe(df_prev[colunas_preview].head(10), use_container_width=True)

    _fixar_etapa_preview_final()
    return st.session_state.get("df_final", df_base)

