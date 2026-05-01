from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher
from typing import Any

import pandas as pd
import streamlit as st


CANONICAL_SOURCE_ALIASES = {
    "id": ["id", "id produto", "id_produto", "identificador interno"],
    "url_produto": ["url produto", "url do produto", "link produto", "link do produto", "url_produto", "produto url"],
    "descricao": [
        "descricao",
        "descrição",
        "nome",
        "nome produto",
        "produto",
        "titulo",
        "title",
        "name",
        "xprod",
    ],
    "descricao_complementar": [
        "descricao complementar",
        "descrição complementar",
        "descricao longa",
        "detalhes",
        "complemento",
        "informacoes",
        "informações",
    ],
    "codigo": ["codigo", "código", "codigo produto", "código produto", "sku", "referencia", "referência", "ref", "cod", "cprod"],
    "gtin": ["gtin", "ean", "codigo de barras", "código de barras", "barcode", "cean"],
    "preco": ["preco", "preço", "valor", "price", "preco venda", "preço venda", "preco unitario", "preço unitário"],
    "preco_custo": ["preco custo", "preço custo", "custo", "valor custo", "vuncom"],
    "estoque": ["estoque", "quantidade", "saldo", "qtd", "stock", "available", "qcom", "status", "disponibilidade", "balanco", "balanço"],
    "imagem": ["imagem", "imagens", "image", "images", "foto", "fotos", "url imagem", "url imagens"],
    "marca": ["marca", "brand", "fabricante"],
    "categoria": ["categoria", "category", "departamento", "breadcrumb"],
    "ncm": ["ncm"],
    "deposito": ["deposito", "depósito", "localizacao", "localização", "almoxarifado"],
}

TARGET_HINTS = {
    "id": ["id", "id produto"],
    "url_produto": ["url produto", "url do produto", "link produto", "link do produto"],
    "descricao_complementar": ["complementar", "detalhada", "longa"],
    "descricao": ["descricao", "descrição", "nome", "produto"],
    "codigo": ["codigo", "código", "sku", "referencia", "referência"],
    "gtin": ["gtin", "ean", "barras"],
    "preco_custo": ["custo"],
    "preco": ["preco", "preço", "valor", "unitario", "unitário", "venda"],
    "estoque": ["estoque", "quantidade", "saldo", "balanco", "balanço", "status", "disponibilidade"],
    "imagem": ["imagem", "imagens", "foto", "fotos"],
    "marca": ["marca", "fabricante"],
    "categoria": ["categoria", "departamento"],
    "ncm": ["ncm"],
    "deposito": ["deposito", "depósito"],
}

DESTINOS_NUNCA_PREENCHER = {
    "id",
    "id produto",
    "idproduto",
    "id bling",
    "codigo id",
    "codigo interno bling",
}


def normalizar_texto(valor: Any) -> str:
    texto = str(valor or "").strip().lower()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(ch for ch in texto if not unicodedata.combining(ch))
    texto = re.sub(r"[^a-z0-9]+", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def modelo_bling_valido(df_modelo: object) -> bool:
    return isinstance(df_modelo, pd.DataFrame) and len(df_modelo.columns) > 0


def origem_valida(df_origem: object) -> bool:
    return isinstance(df_origem, pd.DataFrame) and len(df_origem.columns) > 0 and not df_origem.empty


def _canonical_from_name(nome: str) -> str:
    norm = normalizar_texto(nome)
    compacto = norm.replace(" ", "")

    if not norm or norm.startswith("unnamed") or norm in {"index", "level 0"}:
        return "ignorar"

    if norm in DESTINOS_NUNCA_PREENCHER or compacto in DESTINOS_NUNCA_PREENCHER:
        return "id"

    if "url" in norm and any(x in norm for x in ["produto", "product", "link"]):
        return "url_produto"

    if "gtin" in norm or "ean" in norm or "barra" in norm or "barcode" in norm:
        return "gtin"

    if "ncm" in norm:
        return "ncm"

    if "custo" in norm:
        return "preco_custo"

    if any(x in norm for x in ["preco", "valor", "price", "unitario", "unitário"]):
        return "preco"

    if any(x in norm for x in ["estoque", "quantidade", "saldo", "qtd", "qtde", "balanco", "balanço", "stock", "disponibilidade"]):
        return "estoque"

    if any(x in norm for x in ["imagem", "image", "foto", "img"]):
        return "imagem"

    if "deposito" in norm or "depósito" in norm:
        return "deposito"

    if "marca" in norm or "brand" in norm or "fabricante" in norm:
        return "marca"

    if "categoria" in norm or "category" in norm or "departamento" in norm or "breadcrumb" in norm:
        return "categoria"

    if any(x in norm for x in ["codigo", "código", "sku", "referencia", "referência", "ref", "cod", "cprod"]):
        return "codigo"

    if any(x in norm for x in ["complementar", "detalhada", "longa", "detalhes", "complemento"]):
        return "descricao_complementar"

    if any(x in norm for x in ["descricao", "descrição", "nome", "produto", "titulo", "title", "name", "xprod"]):
        return "descricao"

    for canonical, aliases in CANONICAL_SOURCE_ALIASES.items():
        for alias in aliases:
            alias_norm = normalizar_texto(alias)
            if norm == alias_norm or alias_norm in norm or norm in alias_norm:
                return canonical
    return norm


def _valores_amostra(serie: pd.Series) -> list[str]:
    return [str(v or "").strip() for v in serie.astype(str).head(40).tolist() if str(v or "").strip()]


def _parece_url(valor: Any) -> bool:
    texto = str(valor or "").strip().lower()
    return texto.startswith(("http://", "https://", "www."))


def _parece_preco(valor: Any) -> bool:
    texto = str(valor or "")
    return bool(re.search(r"R\$\s*\d|\d{1,3}(?:\.\d{3})*,\d{2}|\d+\.\d{2}", texto, flags=re.I))


def _parece_gtin(valor: Any) -> bool:
    digitos = re.sub(r"\D+", "", str(valor or ""))
    return len(digitos) in {8, 12, 13, 14}


def _parece_texto_longo(valor: Any) -> bool:
    texto = str(valor or "").strip()
    return len(texto) > 35 and not _parece_url(texto) and not _parece_preco(texto)


def _conteudo_compativel(col_destino: str, col_origem: str, serie_origem: pd.Series) -> bool:
    destino_can = _canonical_from_name(col_destino)
    origem_can = _canonical_from_name(col_origem)
    amostras = _valores_amostra(serie_origem)

    if destino_can == "id":
        return False

    if origem_can == "ignorar":
        return False

    urls = sum(1 for v in amostras if _parece_url(v))
    precos = sum(1 for v in amostras if _parece_preco(v))
    gtins = sum(1 for v in amostras if _parece_gtin(v))
    longos = sum(1 for v in amostras if _parece_texto_longo(v))
    total = max(len(amostras), 1)

    if destino_can == "codigo":
        if origem_can in {"descricao", "descricao_complementar", "url_produto", "imagem", "preco", "gtin"}:
            return False
        if longos / total >= 0.35 or urls / total >= 0.20:
            return False

    if destino_can in {"descricao", "descricao_complementar"}:
        if origem_can in {"url_produto", "imagem", "preco", "gtin", "estoque", "deposito"}:
            return False
        if urls / total >= 0.20 or precos / total >= 0.35 or gtins / total >= 0.60:
            return False

    if destino_can == "url_produto":
        if origem_can not in {"url_produto"} and urls / total < 0.30:
            return False

    if destino_can == "gtin":
        if origem_can != "gtin" and gtins / total < 0.30:
            return False

    if destino_can in {"preco", "preco_custo"}:
        if origem_can not in {"preco", "preco_custo"} and precos / total < 0.20:
            return False
        if urls / total >= 0.20:
            return False

    return True


def _score_coluna_destino_para_origem(col_destino: str, col_origem: str) -> float:
    destino_norm = normalizar_texto(col_destino)
    origem_norm = normalizar_texto(col_origem)
    destino_can = _canonical_from_name(destino_norm)
    origem_can = _canonical_from_name(origem_norm)

    if destino_can == "id" or origem_can == "ignorar":
        return 0.0

    if destino_can == origem_can:
        return 1.0

    if destino_can == "codigo" and origem_can != "codigo":
        return 0.0

    if destino_can in {"descricao", "descricao_complementar"} and origem_can in {"url_produto", "imagem", "preco", "gtin", "estoque"}:
        return 0.0

    if destino_can == "url_produto" and origem_can != "url_produto":
        return 0.0

    score = SequenceMatcher(None, destino_norm, origem_norm).ratio()

    for canonical, hints in TARGET_HINTS.items():
        if any(normalizar_texto(h) in destino_norm for h in hints):
            aliases = CANONICAL_SOURCE_ALIASES.get(canonical, [])
            if origem_can == canonical or any(normalizar_texto(a) in origem_norm for a in aliases):
                score = max(score, 0.92)

    if "complement" in destino_norm and origem_can == "descricao":
        score = min(score, 0.40)

    if any(x in destino_norm for x in ["video", "youtube", "propaganda"]):
        score = 0.0

    return float(score)


def _classificar_score(score: float) -> tuple[str, str]:
    if score >= 0.90:
        return "🟢", "Alta"
    if score >= 0.72:
        return "🟡", "Média"
    return "🔴", "Baixa"


def _texto_para_estoque(valor: Any, estoque_disponivel: int, estoque_baixo: int) -> str:
    """Converte status textual em estoque somente quando há sinal claro.

    Blindagem importante: vazio/indefinido NÃO vira mais estoque padrão 5. O valor
    padrão deve ser usado apenas para texto explícito como 'Disponível' ou 'Baixo'.
    Se o fornecedor não trouxe quantidade real, deixamos em branco para a etapa de
    estoque real/sitemap ou revisão manual resolver, evitando falso estoque.
    """
    raw = str(valor or "").strip()
    texto = normalizar_texto(raw)

    if not texto:
        return ""

    if re.fullmatch(r"\d+", texto):
        return texto

    if any(token in texto for token in ["esgotado", "indisponivel", "sem estoque", "zerado", "fora estoque", "outofstock", "soldout"]):
        return "0"

    if any(token in texto for token in ["baixo", "poucas", "ultimas", "ultimas unidades", "limitado"]):
        return str(estoque_baixo)

    if any(token in texto for token in ["disponivel", "em estoque", "pronta entrega", "comprar", "instock", "in stock"]):
        return str(estoque_disponivel)

    return ""


def _destino_eh_estoque(coluna_destino: str) -> bool:
    destino_norm = normalizar_texto(coluna_destino)
    return any(token in destino_norm for token in ["estoque", "quantidade", "saldo", "balanco", "qtd", "qtde"])


def _destino_nunca_preencher(coluna_destino: str) -> bool:
    destino_norm = normalizar_texto(coluna_destino)
    compacto = destino_norm.replace(" ", "")
    return destino_norm in DESTINOS_NUNCA_PREENCHER or compacto in DESTINOS_NUNCA_PREENCHER or _canonical_from_name(coluna_destino) == "id"


def encontrar_melhor_coluna(col_destino: str, df_origem: pd.DataFrame, usadas: set[str]) -> tuple[str, float]:
    candidatos: list[tuple[str, float]] = []
    for col_origem in list(df_origem.columns):
        if col_origem in usadas:
            continue
        if not _conteudo_compativel(col_destino, col_origem, df_origem[col_origem]):
            candidatos.append((col_origem, 0.0))
            continue
        score = _score_coluna_destino_para_origem(col_destino, col_origem)
        candidatos.append((col_origem, score))
    if not candidatos:
        return "", 0.0
    candidatos.sort(key=lambda item: item[1], reverse=True)
    melhor_coluna, melhor_score = candidatos[0]
    if melhor_score < 0.55:
        return "", melhor_score
    return melhor_coluna, melhor_score


def montar_preview_inteligente(df_origem: pd.DataFrame, df_modelo: pd.DataFrame, operacao: str = "cadastro") -> tuple[pd.DataFrame, pd.DataFrame]:
    origem = df_origem.copy().fillna("") if origem_valida(df_origem) else pd.DataFrame()
    modelo = df_modelo.copy().fillna("") if modelo_bling_valido(df_modelo) else pd.DataFrame()

    if origem.empty or len(modelo.columns) == 0:
        return pd.DataFrame(), pd.DataFrame()

    resultado = pd.DataFrame(index=origem.index, columns=[str(c).strip() for c in modelo.columns]).fillna("")
    usadas: set[str] = set()
    linhas_mapa = []
    deposito_nome = str(st.session_state.get("deposito_nome", "") or "").strip()
    estoque_disponivel = int(st.session_state.get("estoque_padrao_disponivel", 5) or 5)
    estoque_baixo = int(st.session_state.get("estoque_padrao_baixo", 1) or 1)

    for col_destino in resultado.columns:
        destino_norm = normalizar_texto(col_destino)

        if destino_norm.startswith("unnamed") or destino_norm in {"index", "level 0"}:
            linhas_mapa.append({"Campo Bling": col_destino, "Origem usada": "", "Confiança": "🔴 Ignorado", "Score": 0.0})
            continue

        if _destino_nunca_preencher(col_destino):
            linhas_mapa.append({"Campo Bling": col_destino, "Origem usada": "", "Confiança": "🟢 Protegido em branco", "Score": 1.0})
            continue

        if "video" in destino_norm or "youtube" in destino_norm:
            linhas_mapa.append({"Campo Bling": col_destino, "Origem usada": "", "Confiança": "🔴 Ignorado", "Score": 0.0})
            continue

        if operacao == "estoque" and deposito_nome and "deposito" in destino_norm:
            resultado[col_destino] = deposito_nome
            linhas_mapa.append({"Campo Bling": col_destino, "Origem usada": "Depósito informado", "Confiança": "🟢 Automático", "Score": 1.0})
            continue

        col_origem, score = encontrar_melhor_coluna(col_destino, origem, usadas)
        emoji, nivel = _classificar_score(score)

        if col_origem and score >= 0.55:
            serie = origem[col_origem].astype(str).fillna("")
            if _destino_eh_estoque(col_destino):
                resultado[col_destino] = serie.apply(lambda v: _texto_para_estoque(v, estoque_disponivel, estoque_baixo))
            else:
                resultado[col_destino] = serie
            if score >= 0.72:
                usadas.add(col_origem)
            linhas_mapa.append({"Campo Bling": col_destino, "Origem usada": col_origem, "Confiança": f"{emoji} {nivel}", "Score": round(score, 2)})
        else:
            linhas_mapa.append({"Campo Bling": col_destino, "Origem usada": "", "Confiança": "🔴 Sem mapa", "Score": round(score, 2)})

    mapa = pd.DataFrame(linhas_mapa)
    return resultado.fillna(""), mapa


def render_preview_inteligente(df_origem: pd.DataFrame, df_modelo: pd.DataFrame, titulo: str = "Preview inteligente no modelo do Bling") -> pd.DataFrame:
    if not origem_valida(df_origem):
        st.info("Carregue ou capture os dados do fornecedor antes de gerar o preview.")
        return pd.DataFrame()

    if not modelo_bling_valido(df_modelo):
        st.warning("Envie primeiro o modelo do Bling. O preview oficial só será gerado nas colunas do modelo anexado.")
        return pd.DataFrame()

    operacao = str(st.session_state.get("tipo_operacao", "cadastro") or "cadastro").strip().lower()
    df_preview, df_mapa = montar_preview_inteligente(df_origem, df_modelo, operacao=operacao)

    if df_preview.empty:
        st.info("Preview inteligente ainda não disponível.")
        return df_preview

    st.markdown(f"#### 🧠 {titulo}")
    st.caption("A tabela abaixo já usa exatamente as colunas do modelo Bling anexado. Campos de ID do Bling ficam em branco e não são preenchidos automaticamente.")
    st.dataframe(df_preview.head(30), use_container_width=True)

    with st.expander("Mapa automático de colunas", expanded=False):
        st.dataframe(df_mapa, use_container_width=True)

    st.session_state["df_preview_inteligente"] = df_preview.copy()
    st.session_state["df_auto_mapa"] = df_mapa.copy()
    return df_preview
