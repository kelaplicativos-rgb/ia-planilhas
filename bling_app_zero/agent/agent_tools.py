

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd
import streamlit as st

from bling_app_zero.ui.app_helpers import normalizar_texto, safe_df_dados, safe_df_estrutura


# ============================================================
# MODELO DE RETORNO
# ============================================================

@dataclass
class AgentResult:
    ok: bool
    mapping: dict[str, str] = field(default_factory=dict)
    provider: str = ""
    model: str = ""
    erro: str = ""
    diagnostico: dict[str, Any] = field(default_factory=dict)


# ============================================================
# HELPERS DE TEXTO
# ============================================================

def _texto(valor: object) -> str:
    return str(valor or "").strip()


def _norm(valor: object) -> str:
    return normalizar_texto(valor)


def _eh_vazio(valor: object) -> bool:
    return _texto(valor) == ""


def _pontuar_semelhanca_simples(a: str, b: str) -> int:
    """
    Similaridade leve por tokens normalizados.
    """
    aa = _norm(a)
    bb = _norm(b)

    if not aa or not bb:
        return 0

    if aa == bb:
        return 100

    score = 0

    if aa in bb or bb in aa:
        score += 50

    tokens_a = set(aa.replace("_", " ").replace("-", " ").split())
    tokens_b = set(bb.replace("_", " ").replace("-", " ").split())

    inter = tokens_a.intersection(tokens_b)
    score += len(inter) * 10

    if "descricao" in aa and "descricao" in bb:
        score += 20
    if "preco" in aa and "preco" in bb:
        score += 20
    if "codigo" in aa and "codigo" in bb:
        score += 20
    if "gtin" in aa and "gtin" in bb:
        score += 20
    if "ean" in aa and "ean" in bb:
        score += 20
    if "marca" in aa and "marca" in bb:
        score += 20
    if "imagem" in aa and "imagem" in bb:
        score += 20
    if "deposito" in aa and "deposito" in bb:
        score += 20

    return score


# ============================================================
# LEITURA DE MODELO / ORIGEM
# ============================================================

def extrair_colunas_modelo(df_modelo: pd.DataFrame) -> list[str]:
    if not safe_df_estrutura(df_modelo):
        return []
    return [str(c) for c in df_modelo.columns.tolist()]


def extrair_colunas_origem(df_base: pd.DataFrame) -> list[str]:
    if not safe_df_estrutura(df_base):
        return []
    return [str(c) for c in df_base.columns.tolist()]


def construir_resumo_colunas_origem(df_base: pd.DataFrame) -> list[dict[str, Any]]:
    if not safe_df_estrutura(df_base):
        return []

    resumo: list[dict[str, Any]] = []

    for coluna in df_base.columns:
        nome = str(coluna)
        serie = df_base[coluna] if coluna in df_base.columns else pd.Series(dtype="object")

        amostras = []
        try:
            valores = (
                serie.fillna("")
                .astype(str)
                .str.strip()
            )
            valores = valores[valores.ne("")]
            amostras = valores.head(3).tolist()
        except Exception:
            amostras = []

        resumo.append(
            {
                "coluna": nome,
                "normalizada": _norm(nome),
                "amostras": amostras,
            }
        )

    return resumo


def detectar_campos_obrigatorios_modelo(df_modelo: pd.DataFrame, operacao: str) -> list[str]:
    if not safe_df_estrutura(df_modelo):
        return []

    operacao = _norm(operacao) or "cadastro"
    colunas = [str(c) for c in df_modelo.columns.tolist()]
    obrigatorios: list[str] = []

    for coluna in colunas:
        nome_norm = _norm(coluna)

        if "obrigatorio" in nome_norm:
            obrigatorios.append(coluna)
            continue

        if nome_norm in {"codigo", "descricao"}:
            obrigatorios.append(coluna)
            continue

        if operacao == "cadastro" and nome_norm in {"preco de venda", "preco"}:
            obrigatorios.append(coluna)
            continue

        if operacao == "estoque" and nome_norm in {"preco unitario", "deposito", "deposito obrigatorio"}:
            obrigatorios.append(coluna)
            continue

    vistos = set()
    saida = []
    for item in obrigatorios:
        if item not in vistos:
            vistos.add(item)
            saida.append(item)

    return saida


# ============================================================
# NORMALIZAÇÃO DO MAPPING
# ============================================================

def limpar_mapping_para_modelo(
    mapping: dict[str, str],
    df_modelo: pd.DataFrame,
    df_base: pd.DataFrame,
) -> dict[str, str]:
    colunas_modelo = set(extrair_colunas_modelo(df_modelo))
    colunas_origem = set(extrair_colunas_origem(df_base))

    limpo: dict[str, str] = {}

    if not isinstance(mapping, dict):
        mapping = {}

    for coluna_modelo in colunas_modelo:
        valor = _texto(mapping.get(coluna_modelo, ""))
        if valor and valor in colunas_origem:
            limpo[coluna_modelo] = valor
        else:
            limpo[coluna_modelo] = ""

    return limpo


def mapping_tem_duplicidade(mapping: dict[str, str]) -> bool:
    usados = [str(v).strip() for v in (mapping or {}).values() if str(v).strip()]
    return len(usados) != len(set(usados))


def _remover_duplicidades_priorizando_primeiro(mapping: dict[str, str]) -> dict[str, str]:
    usados: set[str] = set()
    saida: dict[str, str] = {}

    for coluna_modelo, coluna_origem in (mapping or {}).items():
        origem = _texto(coluna_origem)
        if not origem:
            saida[str(coluna_modelo)] = ""
            continue

        if origem in usados:
            saida[str(coluna_modelo)] = ""
            continue

        usados.add(origem)
        saida[str(coluna_modelo)] = origem

    return saida


# ============================================================
# FALLBACK LOCAL
# ============================================================

def _mapa_sinonimos_modelo(operacao: str) -> dict[str, list[str]]:
    operacao = _norm(operacao) or "cadastro"

    base = {
        "Código": ["codigo", "sku", "referencia", "id produto", "cod"],
        "Descrição": ["descricao", "nome", "titulo", "produto", "descricao produto"],
        "Descrição Curta": ["descricao curta", "resumo", "descricao resumida"],
        "Marca": ["marca", "fabricante"],
        "GTIN/EAN": ["gtin", "ean", "codigo de barras"],
        "NCM": ["ncm"],
        "URL Imagens": ["imagem", "imagens", "url imagem", "url imagens", "foto", "fotos"],
        "Categoria": ["categoria", "departamento", "secao"],
    }

    if operacao == "cadastro":
        base["Preço de venda"] = ["preco venda", "preco", "valor", "valor venda", "preco final"]

    if operacao == "estoque":
        base["Preço unitário (OBRIGATÓRIO)"] = ["preco", "valor", "preco unitario", "valor unitario"]
        base["Depósito (OBRIGATÓRIO)"] = ["deposito", "almoxarifado", "local estoque"]
        base["Balanço (OBRIGATÓRIO)"] = ["estoque", "saldo", "quantidade", "qtd"]

    return base


def gerar_mapping_fallback(
    df_base: pd.DataFrame,
    df_modelo: pd.DataFrame,
    operacao: str,
) -> dict[str, str]:
    if not safe_df_estrutura(df_base) or not safe_df_estrutura(df_modelo):
        return {}

    colunas_origem = extrair_colunas_origem(df_base)
    colunas_modelo = extrair_colunas_modelo(df_modelo)
    sinonimos = _mapa_sinonimos_modelo(operacao)

    resultado: dict[str, str] = {col: "" for col in colunas_modelo}
    usados: set[str] = set()

    for coluna_modelo in colunas_modelo:
        melhor_coluna = ""
        melhor_score = -1

        candidatos_textuais = sinonimos.get(coluna_modelo, [])

        for coluna_origem in colunas_origem:
            if coluna_origem in usados:
                continue

            score = _pontuar_semelhanca_simples(coluna_modelo, coluna_origem)

            for candidato in candidatos_textuais:
                score = max(score, _pontuar_semelhanca_simples(candidato, coluna_origem))

            if score > melhor_score:
                melhor_score = score
                melhor_coluna = coluna_origem

        if melhor_score >= 20 and melhor_coluna:
            resultado[coluna_modelo] = melhor_coluna
            usados.add(melhor_coluna)

    return resultado


# ============================================================
# PÓS-PROCESSAMENTO
# ============================================================

def aplicar_regras_pos_processamento(
    mapping: dict[str, str],
    df_base: pd.DataFrame,
    df_modelo: pd.DataFrame,
    operacao: str,
) -> dict[str, str]:
    saida = limpar_mapping_para_modelo(mapping, df_modelo, df_base)
    saida = _remover_duplicidades_priorizando_primeiro(saida)

    colunas_modelo = extrair_colunas_modelo(df_modelo)
    colunas_origem = extrair_colunas_origem(df_base)

    usados = {v for v in saida.values() if _texto(v)}

    def tentar_preencher(col_modelo: str, candidatos: list[str]) -> None:
        if col_modelo not in colunas_modelo:
            return
        if _texto(saida.get(col_modelo)):
            return

        melhor = ""
        melhor_score = -1

        for origem in colunas_origem:
            if origem in usados:
                continue

            score = 0
            for candidato in candidatos:
                score = max(score, _pontuar_semelhanca_simples(candidato, origem))

            if score > melhor_score:
                melhor_score = score
                melhor = origem

        if melhor and melhor_score >= 20:
            saida[col_modelo] = melhor
            usados.add(melhor)

    if _norm(operacao) == "cadastro":
        tentar_preencher("Descrição", ["descricao", "nome", "titulo", "produto"])
        tentar_preencher("Preço de venda", ["preco", "valor", "preco venda"])
        tentar_preencher("Código", ["codigo", "sku", "referencia"])
        tentar_preencher("GTIN/EAN", ["gtin", "ean", "codigo barras"])
        tentar_preencher("URL Imagens", ["imagem", "imagens", "foto", "url imagens"])

    if _norm(operacao) == "estoque":
        tentar_preencher("Código", ["codigo", "sku", "referencia"])
        tentar_preencher("Preço unitário (OBRIGATÓRIO)", ["preco", "valor", "preco unitario"])
        tentar_preencher("Balanço (OBRIGATÓRIO)", ["estoque", "saldo", "quantidade", "qtd"])

    return saida


# ============================================================
# DIAGNÓSTICO
# ============================================================

def gerar_diagnostico_mapping(
    mapping: dict[str, str],
    colunas_modelo: list[str],
    obrigatorios: list[str],
) -> dict[str, Any]:
    mapping = mapping or {}
    colunas_modelo = colunas_modelo or []
    obrigatorios = obrigatorios or []

    mapeados = 0
    faltando_obrigatorios: list[str] = []

    for coluna in colunas_modelo:
        if _texto(mapping.get(coluna)):
            mapeados += 1

    for campo in obrigatorios:
        if not _texto(mapping.get(campo)):
            faltando_obrigatorios.append(campo)

    return {
        "total_modelo": len(colunas_modelo),
        "mapeados": mapeados,
        "faltando": max(len(colunas_modelo) - mapeados, 0),
        "obrigatorios": list(obrigatorios),
        "faltando_obrigatorios": faltando_obrigatorios,
        "tem_duplicidade": mapping_tem_duplicidade(mapping),
    }


# ============================================================
# OPENAI / GPT
# ============================================================

def _safe_import_gpt_mapper():
    try:
        from bling_app_zero.core.gpt_mapper import sugerir_mapping_gpt  # type: ignore
        return sugerir_mapping_gpt
    except Exception:
        return None


def tentar_mapping_openai(
    df_base: pd.DataFrame,
    df_modelo: pd.DataFrame,
    operacao: str,
    resumo_origem: list[dict[str, Any]] | None = None,
) -> AgentResult:
    """
    Tenta usar o mapper GPT já existente no projeto.
    Se não existir ou falhar, devolve erro estruturado.
    """
    if not safe_df_dados(df_base):
        return AgentResult(
            ok=False,
            mapping={},
            provider="none",
            model="",
            erro="df_base ausente ou vazio.",
            diagnostico={},
        )

    if not safe_df_estrutura(df_modelo):
        return AgentResult(
            ok=False,
            mapping={},
            provider="none",
            model="",
            erro="df_modelo ausente.",
            diagnostico={},
        )

    func = _safe_import_gpt_mapper()
    if func is None:
        return AgentResult(
            ok=False,
            mapping={},
            provider="none",
            model="",
            erro="gpt_mapper não disponível nesta execução.",
            diagnostico={},
        )

    try:
        resultado = func(
            df_base=df_base,
            df_modelo=df_modelo,
            operacao=operacao,
        )

        if not isinstance(resultado, dict):
            return AgentResult(
                ok=False,
                mapping={},
                provider="openai",
                model="",
                erro="Resposta do GPT em formato inválido.",
                diagnostico={},
            )

        mapping = dict(resultado.get("mapping", {}) or {})
        provider = str(resultado.get("provider", "") or "openai")
        model = str(resultado.get("model", "") or "")
        erro = str(resultado.get("erro", "") or "")

        return AgentResult(
            ok=bool(any(_texto(v) for v in mapping.values())),
            mapping=mapping,
            provider=provider,
            model=model,
            erro=erro,
            diagnostico={
                "resumo_origem": resumo_origem or [],
            },
        )

    except Exception as exc:
        return AgentResult(
            ok=False,
            mapping={},
            provider="openai",
            model="",
            erro=f"Falha ao executar sugerir_mapping_gpt: {exc}",
            diagnostico={},
        )


# ============================================================
# APOIO DE SESSÃO
# ============================================================

def salvar_resultado_agente_em_sessao(chave: str, valor: Any) -> None:
    try:
        st.session_state[chave] = valor
    except Exception:
        pass
