
from __future__ import annotations

from typing import Dict, List, Optional

import pandas as pd
import streamlit as st

from bling_app_zero.core.ia_mapper import (
    aplicar_mapeamento_df,
    normalizar_mapping_para_session,
    sugerir_mapeamento_ia,
)
from bling_app_zero.ui.app_helpers import ir_para_etapa


def _detectar_operacao() -> str:
    operacao = str(st.session_state.get("operacao", "cadastro")).strip().lower()
    if operacao not in {"cadastro", "estoque"}:
        operacao = "cadastro"
    return operacao


def _colunas_modelo_padrao(operacao: str) -> List[str]:
    if operacao == "estoque":
        return [
            "Código",
            "Depósito (OBRIGATÓRIO)",
            "Balanço (OBRIGATÓRIO)",
            "Estoque",
            "Preço unitário (OBRIGATÓRIO)",
        ]

    return [
        "Código",
        "Descrição",
        "Descrição Curta",
        "Marca",
        "NCM",
        "GTIN",
        "Categoria",
        "Unidade",
        "Preço de venda",
        "Peso Líquido",
        "Altura",
        "Largura",
        "Profundidade",
        "Imagens",
    ]


def _carregar_colunas_modelo(operacao: str) -> List[str]:
    colunas_session = st.session_state.get("colunas_modelo")

    if isinstance(colunas_session, list) and colunas_session:
        return [str(c) for c in colunas_session]

    df_modelo = st.session_state.get("df_modelo")
    if isinstance(df_modelo, pd.DataFrame) and not df_modelo.empty:
        cols = [str(c) for c in df_modelo.columns.tolist()]
        st.session_state["colunas_modelo"] = cols
        return cols

    cols = _colunas_modelo_padrao(operacao)
    st.session_state["colunas_modelo"] = cols
    return cols


def _obter_df_base() -> Optional[pd.DataFrame]:
    for chave in ["df_precificado", "df_origem"]:
        df = st.session_state.get(chave)
        if isinstance(df, pd.DataFrame) and not df.empty:
            return df.copy()
    return None


def _init_mapping_state(colunas_modelo: List[str]) -> None:
    if "mapeamento_manual" not in st.session_state:
        st.session_state["mapeamento_manual"] = {c: None for c in colunas_modelo}

    atual = st.session_state["mapeamento_manual"]
    for coluna in colunas_modelo:
        atual.setdefault(coluna, None)

    if "mapeamento_ia_meta" not in st.session_state:
        st.session_state["mapeamento_ia_meta"] = {
            "provider": "",
            "model": "",
            "erro": "",
            "bruto": "",
        }


def _render_header(operacao: str, total_origem: int, total_modelo: int) -> None:
    st.title("🧠 Mapeamento com IA")

    c1, c2, c3 = st.columns(3)
    c1.metric("Operação", operacao.capitalize())
    c2.metric("Colunas origem", total_origem)
    c3.metric("Colunas modelo", total_modelo)

    st.caption(
        "A IA sugere o DE → PARA automaticamente. "
        "Você revisa, ajusta o que quiser e aplica antes do preview final."
    )


def _render_config_ia() -> str:
    with st.expander("Configuração da IA", expanded=False):
        contexto_extra = st.text_area(
            "Contexto extra para a IA",
            value=st.session_state.get("ia_contexto_mapeamento", ""),
            height=120,
            placeholder=(
                "Ex.: esta planilha é de fornecedor de eletrônicos; "
                "SKU vem em 'Ref'; preço custo vem em 'Valor atacado'; "
                "nome do produto vem em 'Descrição completa'."
            ),
        )
        st.session_state["ia_contexto_mapeamento"] = contexto_extra

        st.info(
            "A sugestão automática usa OpenAI quando OPENAI_API_KEY "
            "ou st.secrets['openai']['api_key'] estiver configurado. "
            "Sem isso, o sistema cai no modo heurístico local."
        )

    return contexto_extra


def _executar_sugestao_ia(
    df_base: pd.DataFrame,
    colunas_modelo: List[str],
    operacao: str,
    contexto_extra: str,
) -> None:
    resultado = sugerir_mapeamento_ia(
        df_origem=df_base,
        colunas_modelo=colunas_modelo,
        operacao=operacao,
        contexto_extra=contexto_extra,
        forcar_ia=False,
    )

    st.session_state["mapeamento_manual"] = normalizar_mapping_para_session(
        resultado.mapeamento
    )
    st.session_state["mapeamento_ia_meta"] = {
        "provider": resultado.provider,
        "model": resultado.model,
        "erro": resultado.erro,
        "bruto": resultado.bruto,
    }

    if resultado.provider == "openai":
        st.success(f"Sugestão gerada com IA real ({resultado.model}).")
    else:
        st.warning(resultado.erro or "Usando fallback heurístico local.")


def _render_botoes_topo(
    df_base: pd.DataFrame,
    colunas_modelo: List[str],
    operacao: str,
    contexto_extra: str,
) -> None:
    c1, c2, c3 = st.columns([1.2, 1.2, 1])

    with c1:
        if st.button("✨ Sugerir mapeamento com IA", use_container_width=True):
            _executar_sugestao_ia(df_base, colunas_modelo, operacao, contexto_extra)
            st.rerun()

    with c2:
        if st.button("🧹 Zerar mapeamento", use_container_width=True):
            st.session_state["mapeamento_manual"] = {c: None for c in colunas_modelo}
            st.rerun()

    with c3:
        if st.button("➡️ Ir para preview", use_container_width=True):
            _aplicar_e_ir_preview(df_base, colunas_modelo)


def _render_origem_preview(df_base: pd.DataFrame) -> None:
    with st.expander("Preview da origem", expanded=False):
        st.dataframe(df_base.head(10), use_container_width=True)


def _render_meta_ia() -> None:
    meta = st.session_state.get("mapeamento_ia_meta", {})
    provider = meta.get("provider", "")
    model = meta.get("model", "")
    erro = meta.get("erro", "")
    bruto = meta.get("bruto", "")

    if provider or erro:
        with st.expander("Diagnóstico da sugestão", expanded=False):
            st.write(f"**Provider:** {provider or '-'}")
            st.write(f"**Model:** {model or '-'}")
            if erro:
                st.write(f"**Observação:** {erro}")
            if bruto:
                st.code(bruto, language="json")


def _render_grid_mapeamento(df_base: pd.DataFrame, colunas_modelo: List[str]) -> None:
    opcoes = [""] + [str(c) for c in df_base.columns.tolist()]
    mapping = st.session_state["mapeamento_manual"]

    st.subheader("Revisão manual do mapeamento")

    usados = {v for v in mapping.values() if v}
    linhas_info = []

    for coluna_modelo in colunas_modelo:
        atual = mapping.get(coluna_modelo)
        possiveis = [""] + sorted(
            set(
                [c for c in df_base.columns.tolist() if c == atual or c not in usados]
                + [c for c in df_base.columns.tolist()]
            )
        )

        index = 0
        if atual in possiveis:
            index = possiveis.index(atual)

        c1, c2 = st.columns([1.1, 1.4])

        with c1:
            st.markdown(f"**{coluna_modelo}**")

        with c2:
            escolhido = st.selectbox(
                f"Mapear {coluna_modelo}",
                options=possiveis,
                index=index,
                key=f"map_{coluna_modelo}",
                label_visibility="collapsed",
            )

        mapping[coluna_modelo] = escolhido or None

        exemplo = ""
        if escolhido and escolhido in df_base.columns:
            serie = df_base[escolhido].dropna().astype(str)
            exemplo = serie.iloc[0] if not serie.empty else ""

        linhas_info.append(
            {
                "coluna_modelo": coluna_modelo,
                "coluna_origem": mapping[coluna_modelo] or "",
                "exemplo": exemplo,
            }
        )

    st.session_state["mapeamento_manual"] = mapping

    with st.expander("Resumo do mapeamento atual", expanded=False):
        st.dataframe(pd.DataFrame(linhas_info), use_container_width=True)


def _aplicar_defaults_operacao(df_saida: pd.DataFrame, operacao: str) -> pd.DataFrame:
    df_saida = df_saida.copy()

    if operacao == "estoque":
        deposito_nome = str(st.session_state.get("deposito_nome", "")).strip()
        if "Depósito (OBRIGATÓRIO)" in df_saida.columns and deposito_nome:
            vazios = df_saida["Depósito (OBRIGATÓRIO)"].astype(str).str.strip().eq("")
            df_saida.loc[vazios, "Depósito (OBRIGATÓRIO)"] = deposito_nome

        if "Balanço (OBRIGATÓRIO)" in df_saida.columns:
            vazios = df_saida["Balanço (OBRIGATÓRIO)"].astype(str).str.strip().eq("")
            df_saida.loc[vazios, "Balanço (OBRIGATÓRIO)"] = "S"

    else:
        if "Descrição Curta" in df_saida.columns and "Descrição" in df_saida.columns:
            vazios = df_saida["Descrição Curta"].astype(str).str.strip().eq("")
            df_saida.loc[vazios, "Descrição Curta"] = df_saida.loc[vazios, "Descrição"]

        if "Unidade" in df_saida.columns:
            vazios = df_saida["Unidade"].astype(str).str.strip().eq("")
            df_saida.loc[vazios, "Unidade"] = "UN"

    return df_saida


def _aplicar_e_ir_preview(df_base: pd.DataFrame, colunas_modelo: List[str]) -> None:
    mapping = st.session_state.get("mapeamento_manual", {})
    mapping_limpo: Dict[str, Optional[str]] = {
        coluna_modelo: mapping.get(coluna_modelo) for coluna_modelo in colunas_modelo
    }

    df_mapeado = aplicar_mapeamento_df(
        df_origem=df_base,
        mapeamento=mapping_limpo,
        manter_colunas_nao_mapeadas=False,
    )

    operacao = _detectar_operacao()
    df_mapeado = _aplicar_defaults_operacao(df_mapeado, operacao)

    st.session_state["df_mapeado"] = df_mapeado
    st.session_state["df_final"] = df_mapeado.copy()

    ir_para_etapa("final")


def render_origem_mapeamento() -> None:
    operacao = _detectar_operacao()
    df_base = _obter_df_base()

    if df_base is None or df_base.empty:
        st.title("🧠 Mapeamento com IA")
        st.warning("Nenhum dado disponível para mapear.")
        if st.button("⬅️ Voltar para origem"):
            ir_para_etapa("origem")
        return

    colunas_modelo = _carregar_colunas_modelo(operacao)
    _init_mapping_state(colunas_modelo)

    _render_header(
        operacao=operacao,
        total_origem=len(df_base.columns),
        total_modelo=len(colunas_modelo),
    )

    contexto_extra = _render_config_ia()
    _render_botoes_topo(df_base, colunas_modelo, operacao, contexto_extra)
    _render_meta_ia()
    _render_origem_preview(df_base)
    _render_grid_mapeamento(df_base, colunas_modelo)

    st.divider()

    c1, c2 = st.columns(2)

    with c1:
        if st.button("⬅️ Voltar para precificação", use_container_width=True):
            ir_para_etapa("precificacao")

    with c2:
        if st.button("✅ Aplicar mapeamento e continuar", use_container_width=True):
            _aplicar_e_ir_preview(df_base, colunas_modelo)
