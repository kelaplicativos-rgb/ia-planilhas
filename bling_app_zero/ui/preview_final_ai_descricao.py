from __future__ import annotations

import os
from typing import Any

import pandas as pd
import streamlit as st


COLUNAS_PROTEGIDAS_TRECHOS = [
    "codigo",
    "código",
    "sku",
    "gtin",
    "ean",
    "preco",
    "preço",
    "valor",
    "estoque",
    "deposito",
    "depósito",
    "saldo",
    "balanco",
    "balanço",
    "id",
    "url",
    "link",
    "imagem",
    "video",
    "vídeo",
]


def _df_valido(df: object) -> bool:
    return isinstance(df, pd.DataFrame) and not df.empty and len(df.columns) > 0


def _normalizar_nome_coluna(nome: object) -> str:
    return str(nome or "").strip().lower()


def _coluna_protegida(coluna: object) -> bool:
    nome = _normalizar_nome_coluna(coluna)
    return any(trecho in nome for trecho in COLUNAS_PROTEGIDAS_TRECHOS)


def _identificar_colunas_descricao(df: pd.DataFrame) -> list[str]:
    if not _df_valido(df):
        return []

    candidatas: list[str] = []

    for coluna in df.columns:
        nome = _normalizar_nome_coluna(coluna)

        if _coluna_protegida(coluna):
            continue

        if any(chave in nome for chave in ["descr", "titulo", "título", "nome", "produto"]):
            candidatas.append(str(coluna))

    preferidas = []
    for alvo in ["Descrição", "Descricao", "Descrição Curta", "Descricao Curta", "Nome", "Produto", "Título", "Titulo"]:
        for coluna in candidatas:
            if _normalizar_nome_coluna(coluna) == _normalizar_nome_coluna(alvo) and coluna not in preferidas:
                preferidas.append(coluna)

    for coluna in candidatas:
        if coluna not in preferidas:
            preferidas.append(coluna)

    return preferidas


def _obter_df_base(df_final: pd.DataFrame) -> pd.DataFrame:
    df_session = st.session_state.get("df_final")

    if _df_valido(df_session):
        return df_session.copy().fillna("")

    if _df_valido(df_final):
        return df_final.copy().fillna("")

    return pd.DataFrame()


def _obter_openai_api_key() -> str:
    try:
        chave = st.secrets.get("OPENAI_API_KEY", "")
    except Exception:
        chave = ""

    if not chave:
        chave = os.getenv("OPENAI_API_KEY", "")

    return str(chave or "").strip()


def _obter_openai_modelo() -> str:
    try:
        modelo = st.secrets.get("OPENAI_MODEL", "")
    except Exception:
        modelo = ""

    if not modelo:
        modelo = os.getenv("OPENAI_MODEL", "")

    return str(modelo or "gpt-4o-mini").strip()


def _openai_disponivel() -> tuple[bool, str]:
    if not _obter_openai_api_key():
        return False, "OPENAI_API_KEY não configurada."

    try:
        import openai  # noqa: F401
    except Exception:
        return False, "Pacote openai não instalado no ambiente."

    return True, ""


def _limpar_saida_ia(texto: str, limite: int = 450) -> str:
    texto = str(texto or "").strip()
    texto = texto.replace("\n", " ").replace("\r", " ")
    texto = " ".join(texto.split())

    prefixes = [
        "Descrição:",
        "Descricao:",
        "Texto:",
        "Resposta:",
        "Resultado:",
    ]

    for prefixo in prefixes:
        if texto.lower().startswith(prefixo.lower()):
            texto = texto[len(prefixo) :].strip()

    if len(texto) > limite:
        texto = texto[:limite].rstrip()
        ultimo_ponto = max(texto.rfind("."), texto.rfind("!"), texto.rfind("?"))
        if ultimo_ponto > 120:
            texto = texto[: ultimo_ponto + 1].strip()

    return texto


def _fallback_descricao(texto: str, estilo: str) -> str:
    texto = str(texto or "").strip()
    if not texto:
        return ""

    if estilo == "Mais técnico":
        return f"{texto}. Produto desenvolvido para oferecer praticidade, desempenho e confiabilidade no uso diário."

    if estilo == "Mais curto":
        return texto

    if estilo == "Mais marketplace":
        return f"{texto}. Uma ótima opção para quem busca praticidade, qualidade e bom custo-benefício."

    return f"{texto}. Ideal para quem procura uma opção prática, funcional e com excelente custo-benefício."


def _montar_contexto_linha(row: pd.Series) -> str:
    partes: list[str] = []

    for coluna, valor in row.items():
        if _coluna_protegida(coluna):
            continue

        valor_str = str(valor or "").strip()
        if not valor_str:
            continue

        if len(valor_str) > 180:
            valor_str = valor_str[:180].strip()

        partes.append(f"{coluna}: {valor_str}")

    return " | ".join(partes[:12])


def _chamar_openai_descricao(
    texto_original: str,
    contexto_produto: str,
    estilo: str,
    limite_caracteres: int,
) -> str:
    api_key = _obter_openai_api_key()
    modelo = _obter_openai_modelo()

    from openai import OpenAI

    client = OpenAI(api_key=api_key)

    estilo_instrucao = {
        "Mais vendedor": (
            "Reescreva com tom persuasivo e vendedor, despertando desejo de compra, "
            "mas sem exageros e sem prometer algo que não esteja no texto."
        ),
        "Mais técnico": (
            "Reescreva com tom mais técnico, claro e confiável, destacando utilidade e características existentes."
        ),
        "Mais marketplace": (
            "Reescreva em estilo marketplace, direto, comercial e fácil de entender."
        ),
        "Mais curto": (
            "Reescreva de forma curta, objetiva e comercial, mantendo apenas o essencial."
        ),
    }.get(estilo, "Reescreva com tom comercial, claro e persuasivo.")

    prompt_sistema = (
        "Você é um especialista em descrição de produtos para e-commerce brasileiro. "
        "Sua tarefa é melhorar descrições para vender melhor. "
        "Regras obrigatórias: "
        "não invente marca, voltagem, tamanho, compatibilidade, garantia, material, quantidade, certificação ou função; "
        "use somente informações existentes no texto original e no contexto da linha; "
        "não use emojis; "
        "não use aspas; "
        "não crie listas; "
        "não mencione que é IA; "
        "retorne somente a descrição final pronta."
    )

    prompt_usuario = f"""
Estilo desejado: {estilo}
Instrução: {estilo_instrucao}
Limite máximo: {limite_caracteres} caracteres.

Texto original:
{texto_original}

Contexto do produto:
{contexto_produto}

Retorne somente a nova descrição.
""".strip()

    resposta = client.chat.completions.create(
        model=modelo,
        messages=[
            {"role": "system", "content": prompt_sistema},
            {"role": "user", "content": prompt_usuario},
        ],
        temperature=0.55,
        max_tokens=180,
    )

    conteudo = resposta.choices[0].message.content if resposta.choices else ""
    return _limpar_saida_ia(conteudo, limite=limite_caracteres)


def _gerar_descricao_persuasiva(
    texto: str,
    row: pd.Series,
    estilo: str,
    limite_caracteres: int,
    usar_ia_real: bool,
) -> str:
    texto = str(texto or "").strip()

    if not texto:
        return ""

    if not usar_ia_real:
        return _limpar_saida_ia(_fallback_descricao(texto, estilo), limite=limite_caracteres)

    try:
        contexto = _montar_contexto_linha(row)
        resultado = _chamar_openai_descricao(
            texto_original=texto,
            contexto_produto=contexto,
            estilo=estilo,
            limite_caracteres=limite_caracteres,
        )

        if resultado:
            return resultado

        return _limpar_saida_ia(_fallback_descricao(texto, estilo), limite=limite_caracteres)

    except Exception as exc:
        st.session_state["ia_descricao_ultimo_erro"] = str(exc)
        return _limpar_saida_ia(_fallback_descricao(texto, estilo), limite=limite_caracteres)


def _aplicar_ia_em_colunas(
    df_base: pd.DataFrame,
    colunas: list[str],
    estilo: str,
    apenas_vazios: bool,
    limite_linhas: int,
    limite_caracteres: int,
    usar_ia_real: bool,
) -> pd.DataFrame:
    df_saida = df_base.copy().fillna("")

    if not colunas:
        return df_saida

    total_linhas = min(int(limite_linhas), len(df_saida.index))

    progresso = st.progress(0, text="Preparando descrições com IA...")

    for posicao, idx in enumerate(df_saida.index[:total_linhas]):
        row = df_saida.loc[idx]

        for coluna in colunas:
            if coluna not in df_saida.columns or _coluna_protegida(coluna):
                continue

            valor_atual = str(df_saida.at[idx, coluna] or "").strip()

            if apenas_vazios and valor_atual:
                continue

            novo_valor = _gerar_descricao_persuasiva(
                texto=valor_atual,
                row=row,
                estilo=estilo,
                limite_caracteres=limite_caracteres,
                usar_ia_real=usar_ia_real,
            )

            df_saida.at[idx, coluna] = novo_valor

        percentual = int(((posicao + 1) / max(total_linhas, 1)) * 100)
        progresso.progress(percentual, text=f"IA ajustando descrições... {percentual}%")

    progresso.empty()
    return df_saida.fillna("")


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
    df_base = _obter_df_base(df_final)

    if not _df_valido(df_base):
        return df_final

    st.markdown("### ✨ Otimização de descrição com IA")

    colunas_desc = _identificar_colunas_descricao(df_base)

    if not colunas_desc:
        st.info("Nenhuma coluna de descrição foi identificada para otimização.")
        return df_base

    disponivel, motivo_indisponivel = _openai_disponivel()

    if disponivel:
        st.caption("IA real ativada via OpenAI.")
    else:
        st.caption(f"IA real indisponível: {motivo_indisponivel} Será usado fallback local seguro.")

    colunas_escolhidas = st.multiselect(
        "Colunas que a IA pode melhorar",
        options=colunas_desc,
        default=colunas_desc[:2],
        key="ia_desc_colunas_escolhidas",
    )

    estilo = st.selectbox(
        "Estilo da descrição",
        options=[
            "Mais vendedor",
            "Mais técnico",
            "Mais marketplace",
            "Mais curto",
        ],
        index=0,
        key="ia_desc_estilo",
    )

    col_a, col_b, col_c = st.columns(3)

    with col_a:
        apenas_vazios = st.checkbox(
            "Aplicar apenas onde estiver vazio",
            value=False,
            key="ia_desc_apenas_vazios",
        )

    with col_b:
        limite_linhas = st.number_input(
            "Quantidade de linhas",
            min_value=1,
            max_value=max(len(df_base.index), 1),
            value=min(len(df_base.index), 20),
            step=1,
            key="ia_desc_limite_linhas",
        )

    with col_c:
        limite_caracteres = st.number_input(
            "Máx. caracteres",
            min_value=80,
            max_value=1000,
            value=350,
            step=10,
            key="ia_desc_limite_caracteres",
        )

    usar_ia_real = st.checkbox(
        "Usar OpenAI real quando disponível",
        value=disponivel,
        disabled=not disponivel,
        key="ia_desc_usar_openai_real",
    )

    st.caption(
        "Blindagem ativa: a IA só altera as colunas selecionadas de descrição. "
        "Código, GTIN, preço, estoque, depósito, imagens, vídeos e links ficam preservados."
    )

    col1, col2 = st.columns(2)

    with col1:
        if st.button("👁️ Gerar prévia com IA", use_container_width=True, key="btn_gerar_preview_ia_desc"):
            if not colunas_escolhidas:
                st.warning("Selecione pelo menos uma coluna de descrição.")
                return df_base

            df_preview = _aplicar_ia_em_colunas(
                df_base=df_base,
                colunas=colunas_escolhidas,
                estilo=estilo,
                apenas_vazios=apenas_vazios,
                limite_linhas=int(limite_linhas),
                limite_caracteres=int(limite_caracteres),
                usar_ia_real=bool(usar_ia_real and disponivel),
            )

            st.session_state["df_preview_ia_desc"] = df_preview.copy()
            st.session_state["ia_desc_colunas_preview"] = list(colunas_escolhidas)
            st.success("Prévia gerada com sucesso.")

    with col2:
        if st.button("✅ Aplicar IA nas descrições", use_container_width=True, key="btn_aplicar_ia_desc"):
            df_preview = st.session_state.get("df_preview_ia_desc")
            colunas_preview = st.session_state.get("ia_desc_colunas_preview", colunas_escolhidas)

            if not _df_valido(df_preview):
                st.warning("Gere a prévia antes de aplicar.")
                return df_base

            df_resultado = _aplicar_somente_colunas_descricao(
                df_base=_obter_df_base(df_base),
                df_preview=df_preview,
                colunas=list(colunas_preview),
            )

            st.session_state["df_final"] = df_resultado.copy()
            st.session_state["df_final_manual_preservado"] = True
            st.session_state["ia_descricao_aplicada"] = True
            st.success("Descrições atualizadas com IA.")
            st.rerun()

    erro = st.session_state.get("ia_descricao_ultimo_erro")
    if erro:
        with st.expander("⚠️ Último erro da IA real", expanded=False):
            st.code(str(erro))

    df_preview = st.session_state.get("df_preview_ia_desc")
    if _df_valido(df_preview):
        colunas_visualizacao = [c for c in colunas_escolhidas if c in df_preview.columns]
        if colunas_visualizacao:
            with st.expander("🔎 Visualizar prévia das descrições com IA", expanded=False):
                st.dataframe(df_preview[colunas_visualizacao].head(10), use_container_width=True)

    return _obter_df_base(df_base)
