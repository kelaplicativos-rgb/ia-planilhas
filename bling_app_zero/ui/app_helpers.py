
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re
import unicodedata

import pandas as pd
import streamlit as st


# ============================================================
# CONFIG DE LOG
# ============================================================

LOG_PATH = Path("bling_app_zero/output/debug_log.txt")
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

ETAPAS_VALIDAS = ("origem", "precificacao", "mapeamento", "preview_final")


# ============================================================
# HELPERS GERAIS
# ============================================================

def normalizar_texto(valor: object) -> str:
    """
    Normaliza texto para comparações internas:
    - trim
    - remove acentos
    - lower
    """
    texto = str(valor or "").strip()
    if not texto:
        return ""

    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(ch for ch in texto if not unicodedata.combining(ch))
    return texto.strip().lower()


def safe_lower(valor: object) -> str:
    """Alias semântico usado por módulos antigos/atuais."""
    return normalizar_texto(valor)


def safe_df(df: object) -> bool:
    """Retorna True quando existe DataFrame com colunas e pelo menos 1 linha."""
    return isinstance(df, pd.DataFrame) and len(df.columns) > 0 and not df.empty


def safe_df_dados(df: object) -> bool:
    """Compatibilidade: DataFrame com estrutura e linhas."""
    return safe_df(df)


def safe_df_estrutura(df: object) -> bool:
    """Retorna True quando existe DataFrame com pelo menos colunas."""
    return isinstance(df, pd.DataFrame) and len(df.columns) > 0


def obter_df_sessao(*chaves: str) -> pd.DataFrame:
    """Retorna o primeiro DataFrame válido encontrado no session_state."""
    for chave in chaves:
        valor = st.session_state.get(chave)
        if isinstance(valor, pd.DataFrame):
            return valor
    return pd.DataFrame()


def limpar_chaves_sessao(*chaves: str) -> None:
    """Remove chaves do session_state sem erro."""
    for chave in chaves:
        st.session_state.pop(chave, None)


# ============================================================
# LOG DEBUG
# ============================================================

def log_debug(msg: object, nivel: str = "INFO") -> None:
    """Registra log em memória e em arquivo."""
    if "logs_debug" not in st.session_state:
        st.session_state["logs_debug"] = []

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    linha = f"[{timestamp}] [{str(nivel).upper()}] {msg}"

    st.session_state["logs_debug"].append(linha)

    try:
        with open(LOG_PATH, "a", encoding="utf-8") as arquivo:
            arquivo.write(linha + "\n")
    except Exception as exc:
        st.session_state["logs_debug"].append(
            f"[{timestamp}] [ERRO] Falha ao gravar log em arquivo: {exc}"
        )


def obter_logs() -> str:
    """Lê o log persistido; se falhar, usa memória da sessão."""
    try:
        if LOG_PATH.exists():
            return LOG_PATH.read_text(encoding="utf-8")
    except Exception:
        pass

    if "logs_debug" in st.session_state:
        return "\n".join(st.session_state["logs_debug"])

    return ""


def limpar_logs() -> None:
    """Limpa logs da sessão e do arquivo persistido."""
    st.session_state["logs_debug"] = []

    try:
        if LOG_PATH.exists():
            LOG_PATH.unlink()
    except Exception:
        pass


def render_botao_download_logs() -> None:
    """Renderiza apenas o botão de download do log quando houver conteúdo."""
    logs_txt = obter_logs()
    if not logs_txt.strip():
        return

    st.download_button(
        label="📥 Baixar log debug",
        data=logs_txt,
        file_name="debug_log.txt",
        mime="text/plain",
        use_container_width=True,
        key="btn_download_log_debug",
    )


# ============================================================
# NAVEGAÇÃO / ETAPAS
# ============================================================

def _coletar_query_param(nome: str) -> str:
    """Lê query param compatível com diferentes formatos do Streamlit."""
    try:
        valor = st.query_params.get(nome, "")
    except Exception:
        return ""

    if isinstance(valor, list):
        return str(valor[0]).strip() if valor else ""
    return str(valor or "").strip()


def _definir_query_param(nome: str, valor: str) -> None:
    """Define query param com fallback seguro."""
    try:
        st.query_params[nome] = valor
    except Exception:
        pass


def get_etapa() -> str:
    """Retorna a etapa válida atual do fluxo."""
    etapa = normalizar_texto(st.session_state.get("etapa", "origem"))
    if etapa not in ETAPAS_VALIDAS:
        etapa = "origem"
        st.session_state["etapa"] = etapa
    return etapa


def set_etapa(etapa: str) -> str:
    """Define a etapa atual com sanitização."""
    etapa_limpa = normalizar_texto(etapa)
    if etapa_limpa not in ETAPAS_VALIDAS:
        etapa_limpa = "origem"

    st.session_state["etapa"] = etapa_limpa
    _definir_query_param("etapa", etapa_limpa)
    return etapa_limpa


def ir_para_etapa(etapa: str) -> None:
    """Navega diretamente para uma etapa válida."""
    set_etapa(etapa)


def voltar_para_etapa(etapa: str) -> None:
    """Alias de compatibilidade com fluxo antigo."""
    set_etapa(etapa)


def sincronizar_etapa_da_url() -> None:
    """Sincroniza session_state com a etapa presente na URL."""
    etapa_url = normalizar_texto(_coletar_query_param("etapa"))
    etapa_state = normalizar_texto(st.session_state.get("etapa", ""))

    if etapa_url in ETAPAS_VALIDAS:
        st.session_state["etapa"] = etapa_url
        return

    if etapa_state in ETAPAS_VALIDAS:
        _definir_query_param("etapa", etapa_state)
        return

    st.session_state["etapa"] = "origem"
    _definir_query_param("etapa", "origem")


def sincronizar_etapa_global(etapa: str | None = None) -> None:
    """
    Compatibilidade com chamadas antigas e novas.
    - sem argumento: sincroniza pela URL
    - com argumento: força etapa específica
    """
    if etapa:
        set_etapa(etapa)
        return

    sincronizar_etapa_da_url()


def avancar_etapa() -> str:
    """Avança para a próxima etapa do fluxo principal."""
    etapa_atual = get_etapa()
    ordem = list(ETAPAS_VALIDAS)

    try:
        indice = ordem.index(etapa_atual)
    except ValueError:
        indice = 0

    proxima = ordem[min(indice + 1, len(ordem) - 1)]
    set_etapa(proxima)
    return proxima


def voltar_etapa() -> str:
    """Volta para a etapa anterior do fluxo principal."""
    etapa_atual = get_etapa()
    ordem = list(ETAPAS_VALIDAS)

    try:
        indice = ordem.index(etapa_atual)
    except ValueError:
        indice = 0

    anterior = ordem[max(indice - 1, 0)]
    set_etapa(anterior)
    return anterior


def voltar_etapa_anterior() -> str:
    """Alias usado pelos módulos de precificação, mapeamento e preview."""
    return voltar_etapa()


def _label_etapa(etapa: str) -> str:
    mapa = {
        "origem": "➡️ Origem",
        "precificacao": "Precificação",
        "mapeamento": "Mapeamento",
        "preview_final": "Preview final",
    }
    return mapa.get(etapa, etapa.title())


def render_topo_navegacao() -> None:
    """Renderiza o topo simples de navegação do app."""
    etapa_atual = get_etapa()
    colunas = st.columns(len(ETAPAS_VALIDAS))

    for coluna, etapa in zip(colunas, ETAPAS_VALIDAS):
        with coluna:
            clicou = st.button(
                _label_etapa(etapa),
                use_container_width=True,
                type="primary" if etapa_atual == etapa else "secondary",
                key=f"nav_topo_{etapa}",
            )
            if clicou and etapa != etapa_atual:
                set_etapa(etapa)
                st.rerun()


# ============================================================
# NORMALIZAÇÕES ESPECÍFICAS BLING
# ============================================================

def normalizar_imagens_pipe(valor: object) -> str:
    """
    Garante separação por pipe nas URLs de imagem.
    Aceita entradas separadas por vírgula, ponto e vírgula, quebra de linha ou pipe.
    """
    texto = str(valor or "").strip()
    if not texto:
        return ""

    partes = re.split(r"[|\n\r;,]+", texto)
    urls = []
    vistos = set()

    for parte in partes:
        item = str(parte or "").strip()
        if not item:
            continue
        if item not in vistos:
            vistos.add(item)
            urls.append(item)

    return "|".join(urls)


def _coluna_encontrada(df: pd.DataFrame, candidatos: list[str]) -> str:
    if not safe_df_estrutura(df):
        return ""

    colunas = [str(c) for c in df.columns.tolist()]
    mapa = {normalizar_texto(c): c for c in colunas}

    for candidato in candidatos:
        achado = mapa.get(normalizar_texto(candidato))
        if achado:
            return achado

    return ""


def _limpar_gtin(valor: object) -> str:
    """
    Mantém apenas GTINs possíveis.
    Se inválido por tamanho, devolve vazio.
    """
    texto = re.sub(r"\D+", "", str(valor or "").strip())
    if not texto:
        return ""

    if len(texto) not in {8, 12, 13, 14}:
        return ""

    return texto


def blindar_df_para_bling(
    df: pd.DataFrame,
    tipo_operacao_bling: str = "cadastro",
    deposito_nome: str = "",
) -> pd.DataFrame:
    """
    Blindagem final do DataFrame para exportação/preview:
    - fillna
    - normaliza imagens com pipe
    - limpa GTIN inválido por tamanho
    - injeta depósito quando operação for estoque
    """
    if not safe_df_estrutura(df):
        return pd.DataFrame()

    base = df.copy().fillna("")
    operacao = normalizar_texto(tipo_operacao_bling) or "cadastro"
    deposito_nome = str(deposito_nome or "").strip()

    for col in base.columns:
        nome = normalizar_texto(col)

        if "imagem" in nome or nome in {
            "url imagens",
            "url imagem",
            "imagens",
            "imagem",
        }:
            base[col] = base[col].apply(normalizar_imagens_pipe)

    coluna_gtin = _coluna_encontrada(base, ["GTIN/EAN", "GTIN", "EAN"])
    if coluna_gtin:
        base[coluna_gtin] = base[coluna_gtin].apply(_limpar_gtin)

    if operacao == "estoque" and deposito_nome:
        coluna_deposito = _coluna_encontrada(
            base,
            [
                "Depósito (OBRIGATÓRIO)",
                "Depósito",
                "Deposito (OBRIGATÓRIO)",
                "Deposito",
            ],
        )
        if coluna_deposito:
            base[coluna_deposito] = deposito_nome

    return base.fillna("")


def dataframe_para_csv_bytes(df: pd.DataFrame) -> bytes:
    """Exporta DataFrame como CSV UTF-8 BOM para melhor compatibilidade com Excel/Bling."""
    if not isinstance(df, pd.DataFrame):
        df = pd.DataFrame()

    return df.fillna("").to_csv(index=False).encode("utf-8-sig")


def validar_df_para_download(df: pd.DataFrame, tipo_operacao: str) -> tuple[bool, list[str]]:
    """
    Validação básica antes do download/envio.
    Não bloqueia por excesso; apenas sinaliza principais ausências.
    """
    erros: list[str] = []

    if not safe_df_estrutura(df):
        return False, ["O DataFrame final não foi gerado."]

    if len(df.columns) == 0:
        erros.append("A planilha final não possui colunas.")

    operacao = normalizar_texto(tipo_operacao) or "cadastro"

    coluna_codigo = _coluna_encontrada(df, ["Código", "codigo", "Código do produto", "SKU"])
    if coluna_codigo:
        preenchidos = (
            df[coluna_codigo]
            .astype(str)
            .str.strip()
            .replace({"nan": "", "None": "", "none": ""})
            .ne("")
            .sum()
        )
        if int(preenchidos) == 0:
            erros.append("Nenhum código foi preenchido na planilha final.")

    if operacao == "cadastro":
        coluna_descricao = _coluna_encontrada(df, ["Descrição", "Descricao"])
        if coluna_descricao:
            preenchidos = (
                df[coluna_descricao]
                .astype(str)
                .str.strip()
                .replace({"nan": "", "None": "", "none": ""})
                .ne("")
                .sum()
            )
            if int(preenchidos) == 0:
                erros.append("Nenhuma descrição foi preenchida na planilha final.")

    coluna_preco = _coluna_encontrada(
        df,
        [
            "Preço de venda",
            "Preço unitário (OBRIGATÓRIO)",
            "Preço",
            "Valor",
        ],
    )
    if coluna_preco:
        preenchidos = (
            df[coluna_preco]
            .astype(str)
            .str.strip()
            .replace({"nan": "", "None": "", "none": ""})
            .ne("")
            .sum()
        )
        if int(preenchidos) == 0:
            erros.append("Nenhum preço foi preenchido na planilha final.")

    return len(erros) == 0, erros


# ============================================================
# RESUMO DE FLUXO
# ============================================================

def montar_resumo_fluxo() -> dict:
    """Monta um resumo simples do andamento do fluxo."""
    df_origem = st.session_state.get("df_origem")
    df_precificado = st.session_state.get("df_precificado")
    df_mapeado = st.session_state.get("df_mapeado")
    df_final = st.session_state.get("df_final")

    return {
        "etapa": get_etapa(),
        "origem_linhas": len(df_origem) if isinstance(df_origem, pd.DataFrame) else 0,
        "precificado_linhas": len(df_precificado) if isinstance(df_precificado, pd.DataFrame) else 0,
        "mapeado_linhas": len(df_mapeado) if isinstance(df_mapeado, pd.DataFrame) else 0,
        "final_linhas": len(df_final) if isinstance(df_final, pd.DataFrame) else 0,
    }


def render_resumo_fluxo() -> None:
    """Renderiza um resumo compacto do fluxo."""
    resumo = montar_resumo_fluxo()

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Origem", resumo["origem_linhas"])
    with c2:
        st.metric("Precisificado", resumo["precificado_linhas"])
    with c3:
        st.metric("Mapeado", resumo["mapeado_linhas"])
    with c4:
        st.metric("Final", resumo["final_linhas"])
        
