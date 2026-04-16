
from __future__ import annotations

from datetime import datetime
import re
import unicodedata
from typing import Any

import pandas as pd
import streamlit as st

# ============================================================
# LOG / DEBUG
# ============================================================


def _agora_str() -> str:
    return datetime.now().strftime("%d/%m/%Y %H:%M:%S")


def inicializar_debug() -> None:
    if "debug_logs" not in st.session_state:
        st.session_state["debug_logs"] = []


def log_debug(mensagem: str, nivel: str = "INFO") -> None:
    inicializar_debug()
    linha = f"[{_agora_str()}] [{str(nivel).upper()}] {mensagem}"
    st.session_state["debug_logs"].append(linha)


def obter_logs_texto() -> str:
    inicializar_debug()
    return "\n".join(st.session_state.get("debug_logs", []))


def limpar_logs() -> None:
    st.session_state["debug_logs"] = []


def render_debug_panel(titulo: str = "🐞 Debug do sistema") -> None:
    inicializar_debug()

    with st.expander(titulo, expanded=False):
        logs = st.session_state.get("debug_logs", [])
        if logs:
            st.text_area(
                "Logs",
                value="\n".join(logs[-500:]),
                height=250,
                key="debug_logs_area",
            )
            col1, col2 = st.columns(2)

            with col1:
                st.download_button(
                    "⬇️ Baixar log TXT",
                    data=obter_logs_texto().encode("utf-8"),
                    file_name="debug_ia_planilhas.txt",
                    mime="text/plain",
                    use_container_width=True,
                )

            with col2:
                if st.button("🗑️ Limpar log", use_container_width=True):
                    limpar_logs()
                    st.rerun()
        else:
            st.caption("Nenhum log registrado até agora.")


# ============================================================
# HELPERS DE TEXTO
# ============================================================


def _valor_vazio(valor: Any) -> bool:
    if valor is None:
        return True
    texto = str(valor).strip()
    return texto == "" or texto.lower() in {"nan", "none", "nat", "<na>"}


def normalizar_texto(valor: Any) -> str:
    if _valor_vazio(valor):
        return ""
    return str(valor).strip()


def _remover_acentos(texto: str) -> str:
    texto_nfkd = unicodedata.normalize("NFKD", texto)
    return "".join(ch for ch in texto_nfkd if not unicodedata.combining(ch))


def normalizar_coluna_busca(valor: Any) -> str:
    texto = normalizar_texto(valor).lower()
    texto = _remover_acentos(texto)
    texto = re.sub(r"[_\-/().]+", " ", texto)
    texto = re.sub(r"\s+", " ", texto)
    return texto.strip()


def _safe_lower(valor: Any) -> str:
    return normalizar_texto(valor).lower()


# ============================================================
# DATAFRAME / ESTADO
# ============================================================


def safe_df(df: Any) -> pd.DataFrame:
    if isinstance(df, pd.DataFrame):
        return df.copy()
    return pd.DataFrame()


def safe_df_dados(df: Any) -> bool:
    return isinstance(df, pd.DataFrame) and not df.empty and len(df.columns) > 0


def garantir_dataframe(df: Any) -> pd.DataFrame:
    return safe_df(df) if safe_df_dados(df) else pd.DataFrame()


def _agent_state_disponivel() -> bool:
    try:
        import bling_app_zero.agent.agent_memory  # noqa: F401
        return True
    except Exception:
        return False


def _get_agent_state_safe():
    if not _agent_state_disponivel():
        return None
    try:
        from bling_app_zero.agent.agent_memory import get_agent_state
        return get_agent_state()
    except Exception:
        return None


def _safe_save_agent_state(state) -> None:
    if state is None:
        return
    try:
        from bling_app_zero.agent.agent_memory import save_agent_state
        save_agent_state(state)
    except Exception:
        pass


def _safe_set_agent_stage(etapa: str) -> None:
    state = _get_agent_state_safe()
    if state is None:
        return

    etapa_limpa = normalizar_texto(etapa) or "ia_orquestrador"
    state.etapa_atual = etapa_limpa

    if etapa_limpa == "final":
        state.status_execucao = "final_pronto"
    elif etapa_limpa == "mapeamento":
        state.status_execucao = "mapeamento_pronto"
    elif etapa_limpa == "validacao":
        state.status_execucao = "revisao"
    elif etapa_limpa == "ia_orquestrador":
        if normalizar_texto(getattr(state, "status_execucao", "")) == "":
            state.status_execucao = "idle"

    _safe_save_agent_state(state)


def sincronizar_etapa_global(etapa: str) -> None:
    """
    Centraliza a etapa no fluxo novo e mantém compatibilidade
    temporária com as chaves históricas do app.
    """
    etapa_limpa = normalizar_texto(etapa) or "ia_orquestrador"

    st.session_state["etapa"] = etapa_limpa
    st.session_state["etapa_origem"] = etapa_limpa
    st.session_state["etapa_fluxo"] = etapa_limpa

    if etapa_limpa == "ia_orquestrador":
        st.session_state["modo_execucao"] = "ia_orquestrador"

    _safe_set_agent_stage(etapa_limpa)


def voltar_para_etapa(etapa: str) -> None:
    sincronizar_etapa_global(etapa)


def limpar_estado_fluxo() -> None:
    for chave in [
        "df_origem",
        "df_normalizado",
        "df_precificado",
        "df_mapeado",
        "df_saida",
        "df_final",
        "df_calc_precificado",
        "df_preview_mapeamento",
    ]:
        if chave in st.session_state:
            st.session_state[chave] = None

    for chave in [
        "mapping_origem",
        "mapping_origem_rascunho",
        "mapping_origem_defaults",
        "ia_plano_preview",
        "ia_erro_execucao",
    ]:
        if chave in st.session_state:
            st.session_state[chave] = {} if "mapping" in chave else ""

    if _agent_state_disponivel():
        try:
            from bling_app_zero.agent.agent_memory import reset_agent_state

            reset_agent_state(
                preserve_dataframe_keys=False,
                preserve_operacao=False,
                preserve_deposito=False,
            )
        except Exception:
            pass

    sincronizar_etapa_global("ia_orquestrador")


def obter_df_fluxo_preferencial() -> pd.DataFrame:
    """
    Preferência endurecida:
    1) df_final
    2) df_saida
    3) df_mapeado
    4) df_precificado / df_calc_precificado
    5) df_normalizado
    Só cai em df_origem como último fallback técnico.
    """
    state = _get_agent_state_safe()

    if state is not None:
        for chave in [
            getattr(state, "df_final_key", ""),
            getattr(state, "df_mapeado_key", ""),
            getattr(state, "df_normalizado_key", ""),
            getattr(state, "df_origem_key", ""),
        ]:
            chave_limpa = normalizar_texto(chave)
            if not chave_limpa:
                continue
            df = st.session_state.get(chave_limpa)
            if safe_df_dados(df):
                return df.copy()

    for chave in [
        "df_final",
        "df_saida",
        "df_mapeado",
        "df_precificado",
        "df_calc_precificado",
        "df_normalizado",
        "df_origem",
    ]:
        df = st.session_state.get(chave)
        if safe_df_dados(df):
            return df.copy()

    return pd.DataFrame()


# ============================================================
# FORMATAÇÃO NUMÉRICA
# ============================================================


def to_float_brasil(valor: Any, default: float = 0.0) -> float:
    if valor is None:
        return default

    texto = str(valor).strip()
    if not texto:
        return default

    texto = texto.replace("R$", "").replace(" ", "")

    if "," in texto and "." in texto:
        texto = texto.replace(".", "").replace(",", ".")
    else:
        texto = texto.replace(",", ".")

    texto = re.sub(r"[^0-9.\-]", "", texto)

    try:
        return float(texto)
    except Exception:
        return default


def formatar_numero_bling(valor: Any) -> str:
    numero = to_float_brasil(valor, 0.0)
    return f"{numero:.2f}".replace(".", ",")


def formatar_inteiro_seguro(valor: Any, default: int = 0) -> int:
    try:
        numero = to_float_brasil(valor, float(default))
        return int(round(numero))
    except Exception:
        return default


# ============================================================
# GTIN / IMAGENS / LIMPEZAS FINAIS
# ============================================================


def _somente_digitos(valor: Any) -> str:
    return re.sub(r"\D+", "", normalizar_texto(valor))


def _gtin_checksum_valido(gtin: str) -> bool:
    if not gtin.isdigit() or len(gtin) not in {8, 12, 13, 14}:
        return False

    digitos = [int(d) for d in gtin]
    digito_verificador = digitos[-1]
    corpo = digitos[:-1][::-1]

    total = 0
    for indice, digito in enumerate(corpo, start=1):
        peso = 3 if indice % 2 == 1 else 1
        total += digito * peso

    calculado = (10 - (total % 10)) % 10
    return calculado == digito_verificador


def limpar_gtin_invalido(valor: Any) -> str:
    gtin = _somente_digitos(valor)
    if _gtin_checksum_valido(gtin):
        return gtin
    return ""


def normalizar_imagens_pipe(valor: Any) -> str:
    texto = normalizar_texto(valor)
    if not texto:
        return ""

    texto = texto.replace("\n", "|").replace(";", "|")
    texto = re.sub(r"\s*\|\s*", "|", texto)
    texto = re.sub(r",(?=https?://)", "|", texto)
    texto = re.sub(r"\|+", "|", texto)
    return texto.strip("| ")


def normalizar_situacao(valor: Any, default: str = "Ativo") -> str:
    texto = normalizar_texto(valor)
    return texto if texto else default


# ============================================================
# MODELO / COLUNAS
# ============================================================


def colunas_modelo_estoque() -> list[str]:
    return [
        "Código",
        "Descrição",
        "Depósito (OBRIGATÓRIO)",
        "Balanço (OBRIGATÓRIO)",
        "Preço unitário (OBRIGATÓRIO)",
        "Situação",
    ]


def colunas_modelo_cadastro() -> list[str]:
    return [
        "Código",
        "Descrição",
        "Descrição Curta",
        "Preço de venda",
        "GTIN/EAN",
        "Situação",
        "URL Imagens",
        "Categoria",
    ]


def obter_colunas_modelo_por_tipo(tipo_operacao_bling: str) -> list[str]:
    if _safe_lower(tipo_operacao_bling) == "estoque":
        return colunas_modelo_estoque()
    return colunas_modelo_cadastro()


def garantir_colunas_modelo(
    df: pd.DataFrame,
    tipo_operacao_bling: str,
) -> pd.DataFrame:
    base = garantir_dataframe(df)
    colunas = obter_colunas_modelo_por_tipo(tipo_operacao_bling)

    for coluna in colunas:
        if coluna not in base.columns:
            base[coluna] = ""

    base = base[colunas].copy()
    return base.fillna("")


# ============================================================
# VALIDAÇÃO FINAL
# ============================================================


def _coluna_vazia_ou_invalida(series: pd.Series) -> int:
    return (
        series.astype(str)
        .str.strip()
        .str.lower()
        .isin(["", "nan", "none", "nat", "<na>"])
        .sum()
    )


def validar_df_para_download(
    df: pd.DataFrame,
    tipo_operacao_bling: str,
) -> tuple[bool, list[str]]:
    base = garantir_dataframe(df)
    erros: list[str] = []

    if not safe_df_dados(base):
        erros.append("A planilha final está vazia.")
        return False, erros

    tipo = _safe_lower(tipo_operacao_bling)

    if tipo == "estoque":
        obrigatorias = [
            "Código",
            "Descrição",
            "Depósito (OBRIGATÓRIO)",
            "Balanço (OBRIGATÓRIO)",
            "Preço unitário (OBRIGATÓRIO)",
        ]
    else:
        obrigatorias = [
            "Código",
            "Descrição",
            "Preço de venda",
        ]

    for coluna in obrigatorias:
        if coluna not in base.columns:
            erros.append(f"Coluna obrigatória ausente: {coluna}")
            continue

        vazios = _coluna_vazia_ou_invalida(base[coluna])
        if vazios > 0:
            erros.append(f"Coluna obrigatória com valores vazios: {coluna} ({vazios})")

    if tipo == "estoque":
        if "Balanço (OBRIGATÓRIO)" in base.columns:
            invalidos = (
                pd.to_numeric(
                    base["Balanço (OBRIGATÓRIO)"].astype(str).str.replace(",", ".", regex=False),
                    errors="coerce",
                )
                .isna()
                .sum()
            )
            if invalidos > 0:
                erros.append(f"Balanço (OBRIGATÓRIO) contém valores inválidos ({invalidos})")

    else:
        if "Preço de venda" in base.columns:
            invalidos = (
                pd.to_numeric(
                    base["Preço de venda"].astype(str).str.replace(".", "", regex=False).str.replace(",", ".", regex=False),
                    errors="coerce",
                )
                .isna()
                .sum()
            )
            if invalidos > 0:
                erros.append(f"Preço de venda contém valores inválidos ({invalidos})")

    return len(erros) == 0, erros


# ============================================================
# BLINDAGEM FINAL
# ============================================================


def blindar_df_para_bling(
    df: pd.DataFrame,
    tipo_operacao_bling: str,
    deposito_nome: str = "",
) -> pd.DataFrame:
    base = garantir_dataframe(df)
    tipo = _safe_lower(tipo_operacao_bling)

    if tipo == "estoque":
        base = garantir_colunas_modelo(base, "estoque")

        if deposito_nome:
            base["Depósito (OBRIGATÓRIO)"] = normalizar_texto(deposito_nome)

        base["Código"] = base["Código"].apply(normalizar_texto)
        base["Descrição"] = base["Descrição"].apply(normalizar_texto)
        base["Depósito (OBRIGATÓRIO)"] = base["Depósito (OBRIGATÓRIO)"].apply(normalizar_texto)
        base["Balanço (OBRIGATÓRIO)"] = base["Balanço (OBRIGATÓRIO)"].apply(formatar_inteiro_seguro)
        base["Preço unitário (OBRIGATÓRIO)"] = base["Preço unitário (OBRIGATÓRIO)"].apply(formatar_numero_bling)
        base["Situação"] = base["Situação"].apply(normalizar_situacao)

    else:
        base = garantir_colunas_modelo(base, "cadastro")

        base["Código"] = base["Código"].apply(normalizar_texto)
        base["Descrição"] = base["Descrição"].apply(normalizar_texto)
        base["Descrição Curta"] = base["Descrição Curta"].apply(normalizar_texto)
        base["Preço de venda"] = base["Preço de venda"].apply(formatar_numero_bling)
        base["GTIN/EAN"] = base["GTIN/EAN"].apply(limpar_gtin_invalido)
        base["Situação"] = base["Situação"].apply(normalizar_situacao)
        base["URL Imagens"] = base["URL Imagens"].apply(normalizar_imagens_pipe)
        base["Categoria"] = base["Categoria"].apply(normalizar_texto)

    return base.fillna("")


# ============================================================
# EXPORTAÇÃO
# ============================================================


def dataframe_para_csv_bytes(df: pd.DataFrame) -> bytes:
    base = garantir_dataframe(df).fillna("")
    csv_texto = base.to_csv(index=False, sep=";")
    return csv_texto.encode("utf-8-sig")


# ============================================================
# RESUMO VISUAL
# ============================================================


def _label_etapa(etapa: str) -> str:
    mapa = {
        "ia_orquestrador": "IA Orquestrador",
        "origem": "Origem",
        "normalizacao": "Normalização",
        "precificacao": "Precificação",
        "mapeamento": "Mapeamento",
        "validacao": "Validação",
        "final": "Final",
    }
    return mapa.get(normalizar_texto(etapa).lower(), normalizar_texto(etapa) or "-")


def _status_legivel(status: str) -> str:
    mapa = {
        "idle": "Aguardando",
        "base_pronta": "Base pronta",
        "mapeamento_pronto": "Mapeamento pronto",
        "final_pronto": "Final pronto",
        "revisao": "Em revisão",
        "revisao_final": "Revisão final",
        "sucesso": "Concluído",
        "erro": "Erro",
        "validacao_pendente": "Validação pendente",
    }
    return mapa.get(normalizar_texto(status).lower(), normalizar_texto(status) or "-")


def render_resumo_fluxo() -> None:
    state = _get_agent_state_safe()

    if state is not None:
        etapa = _label_etapa(getattr(state, "etapa_atual", "ia_orquestrador"))
        operacao = normalizar_texto(getattr(state, "operacao", "")) or "-"
        status = _status_legivel(getattr(state, "status_execucao", "idle"))
        simulacao = "Aprovada" if bool(getattr(state, "simulacao_aprovada", False)) else "Pendente"

        st.caption(
            f"Etapa atual: {etapa} | Operação: {operacao} | Status: {status} | Simulação: {simulacao}"
        )
        return

    etapa = st.session_state.get("etapa", "ia_orquestrador")
    tipo_operacao = st.session_state.get("tipo_operacao", "")

    st.caption(
        f"Etapa atual: {_label_etapa(str(etapa))} | Operação: {tipo_operacao if tipo_operacao else '-'}"
        )
    
