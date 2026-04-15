
from __future__ import annotations

import hashlib
from datetime import datetime

import pandas as pd
import streamlit as st

from bling_app_zero.ui.app_helpers import (
    ir_para_etapa,
    log_debug,
    safe_df_dados,
    safe_df_estrutura,
)


def safe_str(valor) -> str:
    try:
        if valor is None:
            return ""
        texto = str(valor).strip()
        if texto.lower() in {"none", "nan", "nat"}:
            return ""
        return texto
    except Exception:
        return ""


def safe_float(valor, default: float = 0.0) -> float:
    try:
        if valor is None or safe_str(valor) == "":
            return default
        texto = (
            safe_str(valor)
            .replace("R$", "")
            .replace(".", "")
            .replace(",", ".")
        )
        return float(texto)
    except Exception:
        return default


def safe_int(valor, default: int = 0) -> int:
    try:
        return int(float(valor))
    except Exception:
        return default


def _normalizar_nome_coluna(coluna) -> str:
    return (
        safe_str(coluna)
        .lower()
        .replace("ã", "a")
        .replace("á", "a")
        .replace("à", "a")
        .replace("â", "a")
        .replace("é", "e")
        .replace("ê", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ô", "o")
        .replace("õ", "o")
        .replace("ú", "u")
        .replace("ç", "c")
        .strip()
    )


def _normalizar_tipo_origem(valor: str) -> str:
    texto = _normalizar_nome_coluna(valor)
    if "site" in texto:
        return "site"
    if "xml" in texto:
        return "xml"
    if "pdf" in texto:
        return "pdf"
    if "planilha" in texto or "csv" in texto or "excel" in texto:
        return "planilha"
    return texto or "planilha"


def obter_origem_atual() -> str:
    return safe_str(
        st.session_state.get("origem_dados_tipo")
        or st.session_state.get("origem_dados_radio")
        or "Planilha fornecedora"
    )


def nome_coluna_preco_saida() -> str:
    tipo = safe_str(st.session_state.get("tipo_operacao_bling")).lower()
    return "Preço unitário (OBRIGATÓRIO)" if tipo == "estoque" else "Preço de venda"


def nome_coluna_descricao_saida() -> str:
    tipo = safe_str(st.session_state.get("tipo_operacao_bling")).lower()
    return "Descrição Produto" if tipo == "estoque" else "Descrição"


def _colunas_modelo_cadastro_padrao() -> list[str]:
    return [
        "Código",
        "Descrição",
        "Descrição Curta",
        "Preço de venda",
        "Situação",
        "Marca",
        "Categoria",
        "Unidade",
        "GTIN/EAN",
        "Imagens",
    ]


def _colunas_modelo_estoque_padrao() -> list[str]:
    return [
        "ID Produto",
        "Codigo produto *",
        "GTIN **",
        "Descrição Produto",
        "Deposito (OBRIGATÓRIO)",
        "Balanço (OBRIGATÓRIO)",
        "Preço unitário (OBRIGATÓRIO)",
        "Preço de Custo",
        "Observação",
        "Data",
    ]


def criar_modelo_vazio_para_operacao() -> pd.DataFrame:
    tipo = safe_str(st.session_state.get("tipo_operacao_bling")).lower()
    if tipo == "estoque":
        return pd.DataFrame(columns=_colunas_modelo_estoque_padrao())
    return pd.DataFrame(columns=_colunas_modelo_cadastro_padrao())


def obter_modelo_ativo() -> pd.DataFrame:
    tipo = safe_str(st.session_state.get("tipo_operacao_bling")).lower()

    chaves = (
        ["df_modelo_estoque", "df_modelo", "df_modelo_cadastro"]
        if tipo == "estoque"
        else ["df_modelo_cadastro", "df_modelo", "df_modelo_estoque"]
    )

    for chave in chaves:
        df_modelo = st.session_state.get(chave)
        if safe_df_estrutura(df_modelo):
            return df_modelo.copy()

    df_fallback = criar_modelo_vazio_para_operacao()
    if tipo == "estoque":
        st.session_state["df_modelo_estoque"] = df_fallback.copy()
    else:
        st.session_state["df_modelo_cadastro"] = df_fallback.copy()

    return df_fallback


def aplicar_normalizacao_basica(df: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame):
        return pd.DataFrame()

    df_out = df.copy()
    df_out.columns = [safe_str(c) for c in df_out.columns]
    df_out = df_out.replace({None: ""}).fillna("")

    for col in df_out.columns:
        df_out[col] = df_out[col].apply(lambda v: "" if safe_str(v).lower() == "nan" else v)

    return df_out


def fingerprint_df(df: pd.DataFrame) -> str:
    try:
        if not isinstance(df, pd.DataFrame):
            return ""
        payload = (
            "||".join([safe_str(c) for c in df.columns])
            + f"##{len(df)}##"
            + df.head(20).to_csv(index=False)
        )
        return hashlib.md5(payload.encode("utf-8", errors="ignore")).hexdigest()
    except Exception:
        return ""


def limpar_mapeamento_widgets() -> None:
    prefixos = (
        "map_src_",
        "map_default_",
        "map_obrig_",
        "map_preview_",
        "campo_destino_",
        "origem_destino_",
    )
    remover = []
    for chave in list(st.session_state.keys()):
        if any(str(chave).startswith(prefixo) for prefixo in prefixos):
            remover.append(chave)

    for chave in remover:
        st.session_state.pop(chave, None)

    st.session_state["mapping_origem"] = {}
    st.session_state["mapping_origem_rascunho"] = {}
    st.session_state["mapeamento_colunas_usadas"] = []
    st.session_state["mapeamento_alertas"] = []
    st.session_state["mapeamento_validado"] = False


def _limpar_estado_dependente_origem() -> None:
    for chave in [
        "df_saida",
        "df_final",
        "df_precificado",
        "df_calc_precificado",
        "df_preview_mapeamento",
        "origem_dados_fingerprint",
        "preview_final_valido",
        "campos_obrigatorios_faltantes",
        "campos_obrigatorios_alertas",
    ]:
        st.session_state.pop(chave, None)

    limpar_mapeamento_widgets()


def tratar_troca_origem(origem_atual: str) -> None:
    origem_anterior = safe_str(st.session_state.get("_origem_anterior_origem_dados"))
    origem_atual_norm = _normalizar_tipo_origem(origem_atual)
    origem_anterior_norm = _normalizar_tipo_origem(origem_anterior)

    if origem_anterior_norm and origem_anterior_norm != origem_atual_norm:
        log_debug(
            f"[ORIGEM_DADOS] origem alterada de '{origem_anterior_norm}' para "
            f"'{origem_atual_norm}'. Limpando saída e mapeamento.",
            "INFO",
        )
        _limpar_estado_dependente_origem()
        st.session_state["site_processado"] = False
        st.session_state["site_autoavanco_realizado"] = False

    st.session_state["_origem_anterior_origem_dados"] = origem_atual


def sincronizar_estado_com_origem(df_origem: pd.DataFrame, log_fn=None) -> None:
    try:
        df_limpo = aplicar_normalizacao_basica(df_origem)
        if not safe_df_dados(df_limpo):
            return

        fp_novo = fingerprint_df(df_limpo)
        fp_atual = safe_str(st.session_state.get("origem_dados_fingerprint"))

        if not fp_atual:
            st.session_state["origem_dados_fingerprint"] = fp_novo
            st.session_state["df_origem"] = df_limpo.copy()
            if not safe_df_estrutura(st.session_state.get("df_saida")):
                st.session_state["df_saida"] = df_limpo.copy()
            if not safe_df_estrutura(st.session_state.get("df_final")):
                st.session_state["df_final"] = df_limpo.copy()

            if "site" in _normalizar_tipo_origem(obter_origem_atual()):
                st.session_state["site_processado"] = True

            if callable(log_fn):
                log_fn(
                    f"[ORIGEM_DADOS] df_origem sincronizado com {len(df_limpo)} linha(s)",
                    "INFO",
                )
            return

        if fp_atual != fp_novo:
            if callable(log_fn):
                log_fn(
                    "[ORIGEM_DADOS] nova origem detectada. Limpando saída anterior.",
                    "INFO",
                )

            st.session_state["origem_dados_fingerprint"] = fp_novo
            st.session_state["df_origem"] = df_limpo.copy()

            for chave in ["df_saida", "df_final", "df_precificado", "df_calc_precificado"]:
                st.session_state.pop(chave, None)

            if "site" in _normalizar_tipo_origem(obter_origem_atual()):
                st.session_state["site_processado"] = True
                st.session_state["site_autoavanco_realizado"] = False

            limpar_mapeamento_widgets()

    except Exception as e:
        if callable(log_fn):
            log_fn(f"[ORIGEM_DADOS] erro ao sincronizar origem: {e}", "ERROR")
        else:
            log_debug(f"[ORIGEM_DADOS] erro ao sincronizar origem: {e}", "ERROR")


def encontrar_coluna_por_alias(df: pd.DataFrame, aliases: list[str]) -> str | None:
    if not isinstance(df, pd.DataFrame):
        return None

    normalizadas = {col: _normalizar_nome_coluna(col) for col in df.columns}
    aliases_norm = [_normalizar_nome_coluna(a) for a in aliases]

    for col, col_norm in normalizadas.items():
        if any(alias == col_norm for alias in aliases_norm):
            return col

    for col, col_norm in normalizadas.items():
        if any(alias in col_norm for alias in aliases_norm):
            return col

    return None


def aplicar_precificacao(
    df_origem: pd.DataFrame,
    coluna_custo: str,
    margem_lucro: float = 0.0,
    impostos: float = 0.0,
    custo_fixo: float = 0.0,
    taxa_extra: float = 0.0,
) -> pd.DataFrame:
    if not isinstance(df_origem, pd.DataFrame):
        return pd.DataFrame()

    df_out = df_origem.copy()
    coluna_saida = nome_coluna_preco_saida()

    if coluna_custo not in df_out.columns:
        if coluna_saida not in df_out.columns:
            df_out[coluna_saida] = ""
        return df_out

    def _calc(v):
        custo = safe_float(v, 0.0)
        preco = custo
        preco += custo * (margem_lucro / 100.0)
        preco += custo * (impostos / 100.0)
        preco += float(custo_fixo or 0.0)
        preco += float(taxa_extra or 0.0)
        return round(preco, 2)

    df_out[coluna_saida] = df_out[coluna_custo].apply(_calc)
    st.session_state["precificacao_coluna_custo"] = coluna_custo
    st.session_state["precificacao_coluna_resultado"] = coluna_saida
    return df_out


def aplicar_bloco_estoque(df_origem: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(df_origem, pd.DataFrame):
        return pd.DataFrame()

    df_out = df_origem.copy()
    tipo = safe_str(st.session_state.get("tipo_operacao_bling")).lower()

    if tipo != "estoque":
        return df_out

    deposito = safe_str(st.session_state.get("deposito_nome"))
    estoque_padrao = safe_int(st.session_state.get("estoque_padrao_manual"), 0)

    if "Deposito (OBRIGATÓRIO)" not in df_out.columns:
        df_out["Deposito (OBRIGATÓRIO)"] = deposito

    if "Balanço (OBRIGATÓRIO)" not in df_out.columns:
        df_out["Balanço (OBRIGATÓRIO)"] = estoque_padrao

    if "Data" not in df_out.columns:
        df_out["Data"] = datetime.now().strftime("%d/%m/%Y")

    return df_out


def consolidar_saida_da_origem(df_origem: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(df_origem, pd.DataFrame):
        return pd.DataFrame()

    df_base = aplicar_normalizacao_basica(df_origem)
    df_base = aplicar_bloco_estoque(df_base)

    st.session_state["df_origem"] = df_base.copy()
    st.session_state["df_saida"] = df_base.copy()
    st.session_state["df_final"] = df_base.copy()

    return df_base


def autoavancar_se_origem_pronta(df_origem: pd.DataFrame) -> bool:
    if safe_df_dados(df_origem):
        sincronizar_estado_com_origem(df_origem, log_debug)
        ir_para_etapa("precificacao")
        return True
    return False
