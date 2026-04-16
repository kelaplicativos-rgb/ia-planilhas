
from __future__ import annotations

import io
import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

import pandas as pd
import streamlit as st

from bling_app_zero.agent.agent_memory import (
    get_agent_state,
    save_agent_state,
    sync_agent_with_session,
    update_agent_state,
)
from bling_app_zero.ui.app_helpers import (
    blindar_df_para_bling,
    garantir_colunas_modelo,
    safe_df_dados,
    validar_df_para_download,
)


# ============================================================
# HELPERS BÁSICOS
# ============================================================


def _safe_str(valor: Any) -> str:
    if valor is None:
        return ""
    texto = str(valor).strip()
    if texto.lower() in {"none", "nan", "nat", "<na>"}:
        return ""
    return texto


def _safe_lower(valor: Any) -> str:
    return _safe_str(valor).lower()


def _is_df_valido(df: Any) -> bool:
    return isinstance(df, pd.DataFrame) and not df.empty and len(df.columns) > 0


def _log(
    log_func: Optional[Callable[[str, str], None]],
    mensagem: str,
    nivel: str = "INFO",
) -> None:
    if callable(log_func):
        try:
            log_func(mensagem, nivel)
        except Exception:
            pass


def _normalizar_nome_coluna(texto: Any) -> str:
    base = unicodedata.normalize("NFKD", _safe_str(texto))
    base = "".join(ch for ch in base if not unicodedata.combining(ch))
    base = base.lower()
    base = re.sub(r"[^a-z0-9]+", "_", base)
    base = re.sub(r"_+", "_", base).strip("_")
    return base


def _deduplicar_colunas(df: pd.DataFrame) -> pd.DataFrame:
    if not _is_df_valido(df):
        return pd.DataFrame()

    base = df.copy()
    novas_colunas = []
    usados: Dict[str, int] = {}

    for coluna in base.columns:
        nome = _safe_str(coluna) or "coluna"
        if nome not in usados:
            usados[nome] = 0
            novas_colunas.append(nome)
            continue

        usados[nome] += 1
        novas_colunas.append(f"{nome}_{usados[nome]}")

    base.columns = novas_colunas
    return base


def _limpar_strings_df(df: pd.DataFrame) -> pd.DataFrame:
    base = df.copy()

    for coluna in base.columns:
        try:
            if base[coluna].dtype == object:
                base[coluna] = base[coluna].apply(
                    lambda v: ""
                    if str(v).strip().lower() in {"nan", "nat", "none", "<na>"}
                    else _safe_str(v)
                )
        except Exception:
            continue

    return base


def normalizar_dataframe(
    df: pd.DataFrame,
    log_func: Optional[Callable[[str, str], None]] = None,
) -> pd.DataFrame:
    if not _is_df_valido(df):
        _log(log_func, "[AGENT_TOOLS] normalizar_dataframe recebeu DataFrame vazio.", "WARNING")
        return pd.DataFrame()

    base = df.copy()
    base = _deduplicar_colunas(base)
    base = _limpar_strings_df(base)
    base = base.reset_index(drop=True)

    _log(
        log_func,
        f"[AGENT_TOOLS] base normalizada com {len(base)} linhas e {len(base.columns)} colunas.",
        "INFO",
    )
    return base


# ============================================================
# DETECÇÃO DE COMANDO
# ============================================================


def detectar_origem_por_entrada(comando: str, arquivo_upload: Any = None) -> str:
    texto = _safe_lower(comando)

    if arquivo_upload is not None:
        nome = _safe_lower(getattr(arquivo_upload, "name", ""))
        if nome.endswith(".xml"):
            return "xml"
        if nome.endswith(".csv") or nome.endswith(".xlsx") or nome.endswith(".xls"):
            return "planilha"

    if "xml" in texto or "nfe" in texto or "nota fiscal" in texto:
        return "xml"
    if "site" in texto or "url" in texto or "http://" in texto or "https://" in texto:
        return "site"
    if (
        "fornecedor" in texto
        or "mega center" in texto
        or "atacadum" in texto
        or "oba oba" in texto
    ):
        return "fornecedor"
    return "planilha"


def detectar_operacao(comando: str) -> str:
    texto = _safe_lower(comando)
    chaves_estoque = [
        "estoque",
        "atualiza estoque",
        "atualizar estoque",
        "balanco",
        "balanço",
        "depósito",
        "deposito",
    ]
    for chave in chaves_estoque:
        if chave in texto:
            return "estoque"
    return "cadastro"


def detectar_fornecedor(comando: str) -> str:
    texto = _safe_lower(comando)

    mapas = {
        "Mega Center": [
            "mega center eletrônicos",
            "mega center eletronicos",
            "mega center",
            "megacenter",
        ],
        "Atacadum": ["atacadum"],
        "Oba Oba Mix": ["oba oba mix", "obaoba mix", "oba oba"],
    }

    for nome, apelidos in mapas.items():
        if any(apelido in texto for apelido in apelidos):
            return nome

    return ""


def detectar_deposito(comando: str) -> str:
    texto_original = _safe_str(comando)
    padroes = [
        r"dep[oó]sito\s+([A-Za-z0-9_\-./ ]+)",
        r"no\s+dep[oó]sito\s+([A-Za-z0-9_\-./ ]+)",
        r"para\s+o\s+dep[oó]sito\s+([A-Za-z0-9_\-./ ]+)",
    ]
    for padrao in padroes:
        match = re.search(padrao, texto_original, flags=re.IGNORECASE)
        if match:
            return _safe_str(match.group(1)).strip(" .,-")

    for candidato in ["iFood", "principal", "geral"]:
        if candidato.lower() in texto_original.lower():
            return candidato

    return ""


# ============================================================
# LEITURA DE ORIGENS
# ============================================================


def _ler_csv_seguro(arquivo_upload: Any) -> pd.DataFrame:
    try:
        bruto = arquivo_upload.getvalue()
    except Exception:
        try:
            bruto = arquivo_upload.read()
        except Exception:
            bruto = None

    if bruto is None:
        return pd.DataFrame()

    for encoding in ("utf-8", "utf-8-sig", "latin1"):
        for sep in (None, ";", ",", "\t", "|"):
            try:
                return pd.read_csv(
                    io.BytesIO(bruto),
                    sep=sep,
                    engine="python",
                    encoding=encoding,
                )
            except Exception:
                continue

    return pd.DataFrame()


def ler_planilha_origem(
    arquivo_upload: Any,
    log_func: Optional[Callable[[str, str], None]] = None,
) -> pd.DataFrame:
    if arquivo_upload is None:
        _log(log_func, "[AGENT_TOOLS] nenhum arquivo de planilha enviado.", "WARNING")
        return pd.DataFrame()

    nome = _safe_lower(getattr(arquivo_upload, "name", ""))

    try:
        if nome.endswith(".csv"):
            df = _ler_csv_seguro(arquivo_upload)
            if _is_df_valido(df):
                _log(log_func, f"[AGENT_TOOLS] CSV lido com sucesso: {nome}", "INFO")
                return df

        if nome.endswith(".xlsx") or nome.endswith(".xls"):
            try:
                bruto = arquivo_upload.getvalue()
            except Exception:
                bruto = None

            if bruto is None:
                _log(log_func, f"[AGENT_TOOLS] arquivo Excel sem conteúdo: {nome}", "ERROR")
                return pd.DataFrame()

            for engine in (None, "openpyxl", "xlrd"):
                try:
                    kwargs = {}
                    if engine:
                        kwargs["engine"] = engine
                    df = pd.read_excel(io.BytesIO(bruto), **kwargs)
                    if _is_df_valido(df):
                        _log(log_func, f"[AGENT_TOOLS] Excel lido com sucesso: {nome}", "INFO")
                        return df
                except Exception:
                    continue

    except Exception as exc:
        _log(log_func, f"[AGENT_TOOLS] falha lendo planilha: {exc}", "ERROR")
        return pd.DataFrame()

    _log(log_func, f"[AGENT_TOOLS] formato de planilha não suportado ou vazio: {nome}", "ERROR")
    return pd.DataFrame()


def ler_xml_nfe(
    arquivo_upload: Any,
    xml_reader_func: Optional[Callable[[Any], pd.DataFrame]] = None,
    log_func: Optional[Callable[[str, str], None]] = None,
) -> pd.DataFrame:
    if arquivo_upload is None:
        _log(log_func, "[AGENT_TOOLS] XML não enviado.", "WARNING")
        return pd.DataFrame()

    if not callable(xml_reader_func):
        _log(log_func, "[AGENT_TOOLS] xml_reader_func indisponível.", "ERROR")
        return pd.DataFrame()

    try:
        df = xml_reader_func(arquivo_upload)
    except Exception as exc:
        _log(log_func, f"[AGENT_TOOLS] erro ao converter XML: {exc}", "ERROR")
        return pd.DataFrame()

    if _is_df_valido(df):
        _log(log_func, f"[AGENT_TOOLS] XML convertido com {len(df)} linhas.", "INFO")
        return df

    _log(log_func, "[AGENT_TOOLS] XML convertido sem dados.", "WARNING")
    return pd.DataFrame()


def buscar_dados_fornecedor(
    fornecedor: str,
    operacao: str,
    fetch_router_func: Optional[Callable[..., pd.DataFrame]] = None,
    log_func: Optional[Callable[[str, str], None]] = None,
) -> pd.DataFrame:
    fornecedor_limpo = _safe_str(fornecedor)
    if not fornecedor_limpo:
        _log(log_func, "[AGENT_TOOLS] fornecedor ausente.", "WARNING")
        return pd.DataFrame()

    if not callable(fetch_router_func):
        _log(log_func, "[AGENT_TOOLS] fetch_router_func indisponível.", "ERROR")
        return pd.DataFrame()

    try:
        df = fetch_router_func(
            fornecedor=fornecedor_limpo,
            categoria="",
            operacao=operacao,
            extra_config={},
        )
    except TypeError:
        try:
            df = fetch_router_func(fornecedor_limpo, operacao)
        except Exception as exc:
            _log(log_func, f"[AGENT_TOOLS] erro buscando fornecedor: {exc}", "ERROR")
            return pd.DataFrame()
    except Exception as exc:
        _log(log_func, f"[AGENT_TOOLS] erro buscando fornecedor: {exc}", "ERROR")
        return pd.DataFrame()

    if _is_df_valido(df):
        _log(
            log_func,
            f"[AGENT_TOOLS] fornecedor '{fornecedor_limpo}' retornou {len(df)} linhas.",
            "INFO",
        )
        return df

    _log(log_func, f"[AGENT_TOOLS] fornecedor '{fornecedor_limpo}' sem dados.", "WARNING")
    return pd.DataFrame()


def buscar_dados_site(
    comando: str,
    crawler_func: Optional[Callable[..., pd.DataFrame]] = None,
    log_func: Optional[Callable[[str, str], None]] = None,
) -> pd.DataFrame:
    if not callable(crawler_func):
        _log(log_func, "[AGENT_TOOLS] crawler_func indisponível.", "ERROR")
        return pd.DataFrame()

    url = ""
    match = re.search(r"(https?://\S+)", _safe_str(comando), flags=re.IGNORECASE)
    if match:
        url = match.group(1)

    try:
        if url:
            try:
                df = crawler_func(url=url)
            except TypeError:
                df = crawler_func(url)
        else:
            try:
                df = crawler_func(comando=_safe_str(comando))
            except TypeError:
                df = crawler_func(_safe_str(comando))
    except Exception as exc:
        _log(log_func, f"[AGENT_TOOLS] erro no crawler: {exc}", "ERROR")
        return pd.DataFrame()

    if _is_df_valido(df):
        _log(log_func, f"[AGENT_TOOLS] crawler retornou {len(df)} linhas.", "INFO")
        return df

    _log(log_func, "[AGENT_TOOLS] crawler sem retorno útil.", "WARNING")
    return pd.DataFrame()


# ============================================================
# MAPEAMENTO PARA MODELO BLING
# ============================================================


def _colunas_normalizadas(df: pd.DataFrame) -> Dict[str, str]:
    return {_normalizar_nome_coluna(col): col for col in df.columns}


def _achar_coluna(df: pd.DataFrame, candidatos: list[str]) -> str:
    mapa = _colunas_normalizadas(df)
    for candidato in candidatos:
        chave = _normalizar_nome_coluna(candidato)
        if chave in mapa:
            return mapa[chave]
    return ""


def _primeiro_valido(row: pd.Series, colunas: list[str]) -> str:
    for coluna in colunas:
        if coluna and coluna in row.index:
            valor = _safe_str(row[coluna])
            if valor:
                return valor
    return ""


def _somente_digitos(valor: Any) -> str:
    return re.sub(r"\D+", "", _safe_str(valor))


def _gtin_checksum_valido(gtin: str) -> bool:
    if not gtin.isdigit() or len(gtin) not in {8, 12, 13, 14}:
        return False

    digitos = [int(d) for d in gtin]
    check = digitos[-1]
    corpo = digitos[:-1][::-1]

    total = 0
    for i, d in enumerate(corpo, start=1):
        total += d * (3 if i % 2 == 1 else 1)

    calculado = (10 - (total % 10)) % 10
    return calculado == check


def _limpar_gtin(valor: Any) -> str:
    gtin = _somente_digitos(valor)
    if _gtin_checksum_valido(gtin):
        return gtin
    return ""


def _numero_float(valor: Any, default: float = 0.0) -> float:
    texto = _safe_str(valor)
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


def _numero_bling(valor: Any) -> str:
    return f"{_numero_float(valor, 0.0):.2f}".replace(".", ",")


def _inteiro_seguro(valor: Any, default: int = 0) -> str:
    try:
        return str(int(round(_numero_float(valor, float(default)))))
    except Exception:
        return str(default)


def _limpar_imagens(valor: Any) -> str:
    texto = _safe_str(valor)
    if not texto:
        return ""
    texto = texto.replace("\n", "|").replace(";", "|")
    texto = re.sub(r",(?=https?://)", "|", texto)
    texto = re.sub(r"\s*\|\s*", "|", texto)
    texto = re.sub(r"\|+", "|", texto)
    return texto.strip("| ")


def _descricao_base(row: pd.Series, colunas: list[str]) -> str:
    return _primeiro_valido(row, colunas)


def _gerar_df_final_cadastro(df: pd.DataFrame) -> pd.DataFrame:
    base = df.copy()

    col_codigo = _achar_coluna(base, ["Código", "codigo", "SKU", "sku", "referencia", "ref", "id", "cod"])
    col_titulo = _achar_coluna(base, ["titulo", "nome", "produto", "descricao", "descrição", "title"])
    col_desc_curta = _achar_coluna(base, ["descricao_curta", "descrição curta", "resumo", "short_description"])
    col_preco = _achar_coluna(base, ["preco_venda", "preço de venda", "preco", "valor", "price", "preco_unitario"])
    col_gtin = _achar_coluna(base, ["gtin", "ean", "gtin_ean", "codigo_barras", "codbarras"])
    col_situacao = _achar_coluna(base, ["situacao", "situação", "status", "condicao", "condição"])
    col_imagens = _achar_coluna(base, ["url_imagens", "url imagens", "imagens", "imagem", "image", "fotos", "foto"])
    col_categoria = _achar_coluna(base, ["categoria", "departamento", "grupo", "family", "breadcrumb"])

    saida = garantir_colunas_modelo(pd.DataFrame(index=base.index), "cadastro")

    for idx, row in base.iterrows():
        descricao = _descricao_base(row, [col_titulo, col_desc_curta, col_codigo])
        descricao_curta = _descricao_base(row, [col_desc_curta, col_titulo, col_codigo])
        codigo = _primeiro_valido(row, [col_codigo])
        if not codigo:
            codigo = descricao[:60] if descricao else f"ITEM-{idx+1}"

        saida.at[idx, "Código"] = codigo
        saida.at[idx, "Descrição"] = descricao
        saida.at[idx, "Descrição Curta"] = descricao_curta or descricao
        saida.at[idx, "Preço de venda"] = _numero_bling(row.get(col_preco, ""))
        saida.at[idx, "GTIN/EAN"] = _limpar_gtin(row.get(col_gtin, ""))
        saida.at[idx, "Situação"] = _safe_str(row.get(col_situacao, "")) or "Ativo"
        saida.at[idx, "URL Imagens"] = _limpar_imagens(row.get(col_imagens, ""))
        saida.at[idx, "Categoria"] = _safe_str(row.get(col_categoria, ""))

    return saida.fillna("")


def _gerar_df_final_estoque(df: pd.DataFrame, deposito_nome: str = "") -> pd.DataFrame:
    base = df.copy()

    col_codigo = _achar_coluna(base, ["Código", "codigo", "SKU", "sku", "referencia", "ref", "id", "cod"])
    col_desc = _achar_coluna(base, ["descricao", "descrição", "nome", "produto", "titulo"])
    col_estoque = _achar_coluna(base, ["estoque", "saldo", "quantidade", "qtd", "balanco", "balanço"])
    col_preco = _achar_coluna(base, ["preco_unitario", "preço unitário", "preco", "valor", "price"])
    col_dep = _achar_coluna(base, ["deposito", "depósito"])
    col_situacao = _achar_coluna(base, ["situacao", "situação", "status"])

    saida = garantir_colunas_modelo(pd.DataFrame(index=base.index), "estoque")

    for idx, row in base.iterrows():
        codigo = _primeiro_valido(row, [col_codigo])
        descricao = _descricao_base(row, [col_desc, col_codigo])
        deposito = _safe_str(deposito_nome) or _primeiro_valido(row, [col_dep])
        balanco = _inteiro_seguro(row.get(col_estoque, ""), default=0)
        preco = _numero_bling(row.get(col_preco, ""))

        saida.at[idx, "Código"] = codigo or (descricao[:60] if descricao else f"ITEM-{idx+1}")
        saida.at[idx, "Descrição"] = descricao
        saida.at[idx, "Depósito (OBRIGATÓRIO)"] = deposito
        saida.at[idx, "Balanço (OBRIGATÓRIO)"] = balanco
        saida.at[idx, "Preço unitário (OBRIGATÓRIO)"] = preco
        saida.at[idx, "Situação"] = _safe_str(row.get(col_situacao, "")) or "Ativo"

    return saida.fillna("")


def aplicar_defaults_fluxo(df: pd.DataFrame, operacao: str, deposito_nome: str = "") -> pd.DataFrame:
    if not _is_df_valido(df):
        return pd.DataFrame()

    tipo = _safe_lower(operacao)
    if tipo == "estoque":
        return _gerar_df_final_estoque(df, deposito_nome=deposito_nome)

    return _gerar_df_final_cadastro(df)


# ============================================================
# ESTADO
# ============================================================


def registrar_base_no_estado(
    df: pd.DataFrame,
    origem_tipo: str,
    operacao: str,
    fornecedor: str = "",
    deposito_nome: str = "",
    log_func: Optional[Callable[[str, str], None]] = None,
) -> None:
    state = sync_agent_with_session()

    st.session_state["df_origem"] = df.copy()
    st.session_state["df_normalizado"] = df.copy()
    st.session_state["df_mapeado"] = df.copy()
    st.session_state["df_precificado"] = df.copy()

    state.origem_tipo = origem_tipo
    state.operacao = operacao
    state.fornecedor = fornecedor
    state.deposito_nome = deposito_nome
    state.df_origem_key = "df_origem"
    state.df_normalizado_key = "df_normalizado"
    state.df_mapeado_key = "df_mapeado"
    state.df_precificado_key = "df_precificado"
    state.etapa_atual = "mapeamento"
    state.status_execucao = "base_pronta"

    if fornecedor:
        state.defaults_aplicados["fornecedor"] = fornecedor
    if deposito_nome:
        state.defaults_aplicados["deposito_nome"] = deposito_nome

    state.metricas["linhas_base"] = len(df)
    state.add_log(f"Base registrada pelo agente. origem={origem_tipo} operacao={operacao}")
    save_agent_state(state)

    _log(log_func, "[AGENT_TOOLS] base registrada no estado do app.", "INFO")


# ============================================================
# VALIDAÇÃO / PREVIEW FINAL
# ============================================================


class ResultadoValidacao:
    def __init__(self, aprovado: bool, df_resultado: pd.DataFrame, erros: list[str], avisos: list[str]):
        self.aprovado = aprovado
        self.df_resultado = df_resultado
        self.erros = erros
        self.avisos = avisos

    def to_dict(self) -> Dict[str, Any]:
        return {
            "aprovado": self.aprovado,
            "erros": list(self.erros),
            "avisos": list(self.avisos),
            "linhas_validas": len(self.df_resultado) if _is_df_valido(self.df_resultado) else 0,
            "linhas_invalidas": 0 if self.aprovado else len(self.df_resultado) if _is_df_valido(self.df_resultado) else 0,
            "corrigido_automaticamente": [
                "colunas do modelo garantidas",
                "GTIN inválido removido",
                "imagens padronizadas com pipe",
                "campos numéricos blindados",
            ],
        }


def validar_dataframe_bling(df: pd.DataFrame, operacao: str) -> ResultadoValidacao:
    tipo = _safe_lower(operacao) or "cadastro"
    deposito_nome = _safe_str(st.session_state.get("deposito_nome"))

    blindado = blindar_df_para_bling(df, tipo, deposito_nome=deposito_nome)
    aprovado, erros = validar_df_para_download(blindado, tipo)

    avisos: list[str] = []
    if not safe_df_dados(blindado):
        avisos.append("Nenhuma linha útil restou após a blindagem final.")
    elif len(blindado) != len(df):
        avisos.append("A quantidade de linhas mudou durante a blindagem final.")

    return ResultadoValidacao(
        aprovado=bool(aprovado),
        df_resultado=blindado.copy(),
        erros=erros,
        avisos=avisos,
    )


def gerar_preview_final(
    df: pd.DataFrame,
    operacao: str,
    log_func: Optional[Callable[[str, str], None]] = None,
) -> Dict[str, Any]:
    validacao = validar_dataframe_bling(df=df, operacao=operacao)

    st.session_state["df_final"] = (
        validacao.df_resultado.copy()
        if isinstance(validacao.df_resultado, pd.DataFrame)
        else pd.DataFrame()
    )
    st.session_state["df_saida"] = st.session_state["df_final"].copy()

    update_agent_state(
        df_final_key="df_final",
        etapa_atual="final" if validacao.aprovado else "validacao",
        status_execucao="final_pronto" if validacao.aprovado else "validacao_pendente",
        simulacao_aprovada=bool(validacao.aprovado),
    )

    state = get_agent_state()
    state.clear_erros()
    state.clear_avisos()
    state.clear_pendencias()

    for aviso in validacao.avisos:
        state.add_aviso(aviso)
    for erro in validacao.erros:
        state.add_erro(erro)

    state.metricas["linhas_final"] = len(st.session_state["df_final"])
    save_agent_state(state)

    _log(
        log_func,
        f"[AGENT_TOOLS] preview final gerado. aprovado={validacao.aprovado} linhas={len(df) if _is_df_valido(df) else 0}",
        "INFO",
    )

    return {
        "aprovado": validacao.aprovado,
        "df_final": st.session_state.get("df_final", pd.DataFrame()),
        "validacao": validacao.to_dict(),
    }


# ============================================================
# CONTAINER DE DEPENDÊNCIAS
# ============================================================


@dataclass
class FerramentasAgente:
    fetch_router_func: Optional[Callable[..., pd.DataFrame]] = None
    crawler_func: Optional[Callable[..., pd.DataFrame]] = None
    xml_reader_func: Optional[Callable[[Any], pd.DataFrame]] = None
    log_func: Optional[Callable[[str, str], None]] = None


