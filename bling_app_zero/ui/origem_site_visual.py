from __future__ import annotations

import re
from typing import Any

import pandas as pd
import streamlit as st

from bling_app_zero.core.instant_scraper.self_healing import diagnosticar_dataframe


COLUNAS_PRIORIDADE_VISUAL = [
    "Código",
    "SKU",
    "Descrição",
    "Descrição complementar",
    "Preço unitário (OBRIGATÓRIO)",
    "Preço unitário",
    "Preço",
    "Estoque",
    "GTIN/EAN",
    "GTIN",
    "Marca",
    "Categoria",
    "NCM",
    "URL do produto",
    "URL origem da busca",
    "URL das imagens",
    "Imagens",
    "agente_estrategia",
    "agente_score",
    "origem_site_motor",
    "origem_site_status",
]

PAPEIS_VISUAIS = {
    "Ignorar": "",
    "Código/SKU": "codigo",
    "Descrição/Nome": "descricao",
    "Preço": "preco",
    "Estoque/Quantidade": "estoque",
    "GTIN/EAN": "gtin",
    "Imagem/URL imagens": "imagens",
    "URL do produto": "url_produto",
    "Marca": "marca",
    "Categoria": "categoria",
    "NCM": "ncm",
}

COLUNAS_CANONICAS = {
    "codigo": "Código",
    "descricao": "Descrição",
    "preco": "Preço unitário (OBRIGATÓRIO)",
    "estoque": "Estoque",
    "gtin": "GTIN/EAN",
    "imagens": "URL das imagens",
    "url_produto": "URL do produto",
    "marca": "Marca",
    "categoria": "Categoria",
    "ncm": "NCM",
}

RUINS_COLUNAS_VISUAIS = {
    "",
    "unnamed: 0",
    "index",
    "level_0",
}


def _txt(valor: Any) -> str:
    if valor is None:
        return ""
    if isinstance(valor, float) and pd.isna(valor):
        return ""
    return " ".join(str(valor).replace("\x00", " ").split()).strip()


def _norm(valor: Any) -> str:
    texto = _txt(valor).lower()
    texto = texto.translate(str.maketrans("áàãâéêíóôõúç", "aaaaeeiooouc"))
    return re.sub(r"[^a-z0-9]+", " ", texto).strip()


def _safe_df(df: Any) -> pd.DataFrame:
    if isinstance(df, pd.DataFrame) and not df.empty:
        return df.copy().fillna("").reset_index(drop=True)
    return pd.DataFrame()


def _parece_preco(valor: Any) -> bool:
    texto = _txt(valor)
    return bool(re.search(r"R\$\s*\d|\d{1,3}(?:\.\d{3})*,\d{2}|\d+\.\d{2}", texto, flags=re.I))


def _parece_gtin(valor: Any) -> bool:
    digitos = re.sub(r"\D+", "", _txt(valor))
    return len(digitos) in {8, 12, 13, 14}


def _parece_url(valor: Any) -> bool:
    texto = _txt(valor).lower()
    return texto.startswith(("http://", "https://"))


def _parece_imagem(valor: Any) -> bool:
    texto = _txt(valor).lower()
    return _parece_url(texto) and any(ext in texto for ext in [".jpg", ".jpeg", ".png", ".webp", ".gif"])


def _inferir_papel_coluna(nome_coluna: str, serie: pd.Series) -> str:
    nome = _norm(nome_coluna)
    amostras = [_txt(v) for v in serie.astype(str).head(30).tolist() if _txt(v)]

    if any(t in nome for t in ["preco", "price", "valor"]):
        return "preco"
    if any(t in nome for t in ["descricao", "descrição", "nome", "produto", "title"]):
        return "descricao"
    if any(t in nome for t in ["sku", "codigo", "código", "referencia", "referência", "cod"]):
        return "codigo"
    if any(t in nome for t in ["gtin", "ean", "barcode", "barra"]):
        return "gtin"
    if any(t in nome for t in ["imagem", "image", "foto", "img"]):
        return "imagens"
    if any(t in nome for t in ["url produto", "link produto", "url produto", "url_produto"]):
        return "url_produto"
    if any(t in nome for t in ["estoque", "stock", "quantidade", "qtd", "saldo"]):
        return "estoque"
    if "marca" in nome or "brand" in nome:
        return "marca"
    if "categoria" in nome or "category" in nome or "breadcrumb" in nome:
        return "categoria"
    if "ncm" in nome:
        return "ncm"

    pontos = {papel: 0 for papel in COLUNAS_CANONICAS}
    for valor in amostras:
        if _parece_preco(valor):
            pontos["preco"] += 4
        if _parece_gtin(valor):
            pontos["gtin"] += 4
        if _parece_imagem(valor):
            pontos["imagens"] += 4
        elif _parece_url(valor):
            pontos["url_produto"] += 3
        if valor.strip().isdigit():
            pontos["estoque"] += 2
        if len(valor) >= 8 and not _parece_url(valor) and not _parece_preco(valor):
            pontos["descricao"] += 1
        if re.fullmatch(r"[A-Za-z0-9._/\-]{3,60}", valor) and not _parece_gtin(valor):
            pontos["codigo"] += 1

    papel, score = max(pontos.items(), key=lambda item: item[1])
    return papel if score > 0 else ""


def _score_visual(df: pd.DataFrame) -> dict[str, Any]:
    base = _safe_df(df)
    if base.empty:
        return {"score": 0, "status": "sem_dados", "linhas": 0}

    try:
        diag = diagnosticar_dataframe(base)
        score = int(diag.get("score", 0) or 0)
        status = str(diag.get("status", "") or "")
    except Exception:
        score = 0
        status = "sem_diagnostico"

    colunas_norm = {_norm(c) for c in base.columns}
    if "descricao" in colunas_norm:
        score += 12
    if "preco unitario obrigatorio" in colunas_norm or "preco unitario" in colunas_norm:
        score += 12
    if "url das imagens" in colunas_norm or "imagens" in colunas_norm:
        score += 8
    if "gtin ean" in colunas_norm or "gtin" in colunas_norm:
        score += 5

    score = min(max(score, 0), 100)
    if score >= 80:
        status = "excelente"
    elif score >= 60:
        status = "bom"
    elif score >= 40:
        status = "revisar"
    else:
        status = "fraco"

    return {"score": score, "status": status, "linhas": len(base)}


def _colunas_ordenadas(df: pd.DataFrame) -> list[str]:
    colunas = [str(c) for c in df.columns.tolist() if _norm(c) not in RUINS_COLUNAS_VISUAIS]
    prioridade = []
    for alvo in COLUNAS_PRIORIDADE_VISUAL:
        for col in colunas:
            if col not in prioridade and _norm(col) == _norm(alvo):
                prioridade.append(col)

    restantes = [c for c in colunas if c not in prioridade]
    return prioridade + restantes


def _resumo_colunas(df: pd.DataFrame) -> pd.DataFrame:
    base = _safe_df(df)
    if base.empty:
        return pd.DataFrame(columns=["Coluna", "Papel sugerido", "Preenchidos", "Exemplo"])

    linhas = []
    total = max(len(base), 1)
    for col in _colunas_ordenadas(base):
        serie = base[col].astype(str).fillna("")
        preenchidos = int(serie.str.strip().ne("").sum())
        exemplo = ""
        for valor in serie.tolist():
            texto = _txt(valor)
            if texto:
                exemplo = texto[:120]
                break
        papel = _inferir_papel_coluna(col, serie)
        linhas.append(
            {
                "Coluna": col,
                "Papel sugerido": papel or "-",
                "Preenchidos": f"{preenchidos}/{total}",
                "Exemplo": exemplo,
            }
        )
    return pd.DataFrame(linhas)


def _papel_para_label(papel: str) -> str:
    for label, valor in PAPEIS_VISUAIS.items():
        if valor == papel:
            return label
    return "Ignorar"


def _normalizar_colunas_por_papel(base: pd.DataFrame, papeis: dict[str, str]) -> pd.DataFrame:
    saida = base.copy().fillna("")
    for coluna_origem, papel in papeis.items():
        if not papel or coluna_origem not in saida.columns:
            continue
        destino = COLUNAS_CANONICAS.get(papel)
        if not destino:
            continue
        if destino in saida.columns and destino != coluna_origem:
            # Preserva a coluna existente e só preenche vazios.
            serie_destino = saida[destino].astype(str).str.strip()
            saida.loc[serie_destino.eq(""), destino] = saida[coluna_origem]
        elif destino != coluna_origem:
            saida = saida.rename(columns={coluna_origem: destino})
    return saida.fillna("")


def render_origem_site_visual_preview(df: Any, *, expanded: bool = True) -> None:
    base = _safe_df(df)
    if base.empty:
        return

    diag = _score_visual(base)
    score = int(diag.get("score", 0) or 0)
    status = str(diag.get("status", "") or "")

    st.markdown("### 👁️ Preview visual da captura")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Produtos", len(base))
    with c2:
        st.metric("Colunas", len(base.columns))
    with c3:
        st.metric("Score IA", f"{score}/100")
    with c4:
        st.metric("Status", status.title())

    if score >= 80:
        st.success("Captura forte: estrutura parece pronta para o mapeamento Bling.")
    elif score >= 60:
        st.info("Captura boa: revise rapidamente as colunas antes de avançar.")
    else:
        st.warning("Captura fraca/revisar: confira se o site carregou os produtos certos.")

    colunas = _colunas_ordenadas(base)
    preview = base[colunas].head(80)

    with st.expander("Tabela detectada automaticamente", expanded=expanded):
        st.dataframe(preview, use_container_width=True, hide_index=True)

    with st.expander("Resumo das colunas detectadas", expanded=False):
        st.dataframe(_resumo_colunas(base), use_container_width=True, hide_index=True)

    with st.expander("BLINGAI PRO: marcar colunas", expanded=True):
        st.caption("Marque o papel de cada coluna importante. Isso salva a decisão para o mapeamento e renomeia a base para o padrão Bling.")
        papeis_escolhidos: dict[str, str] = {}
        for col in colunas:
            serie = base[col].astype(str).fillna("")
            sugerido = _inferir_papel_coluna(col, serie)
            label_sugerido = _papel_para_label(sugerido)
            opcoes = list(PAPEIS_VISUAIS.keys())
            idx = opcoes.index(label_sugerido) if label_sugerido in opcoes else 0
            escolha = st.selectbox(
                f"{col}",
                options=opcoes,
                index=idx,
                key=f"blingai_pro_papel_{_norm(col)}",
            )
            papel = PAPEIS_VISUAIS.get(escolha, "")
            if papel:
                papeis_escolhidos[col] = papel

        if st.button("Aplicar marcações BLINGAI PRO", key="btn_blingai_pro_aplicar_papeis", use_container_width=True):
            normalizado = _normalizar_colunas_por_papel(base, papeis_escolhidos)
            st.session_state["origem_site_visual_papeis"] = papeis_escolhidos
            st.session_state["df_origem"] = normalizado
            st.session_state["df_saida"] = normalizado.copy()
            st.session_state["_ia_auto_mapping_executado"] = False
            st.success("Marcações aplicadas. O mapeamento será recalculado com essas decisões.")
            st.rerun()

    with st.expander("Ações visuais", expanded=False):
        st.caption("Use isso quando a captura trouxe colunas claramente inúteis antes de seguir para o modelo Bling.")
        colunas_remover = st.multiselect(
            "Ocultar/remover colunas da base capturada",
            options=colunas,
            default=[],
            key="origem_site_visual_cols_remover",
        )
        if st.button("Aplicar limpeza visual", key="btn_origem_site_aplicar_limpeza_visual", use_container_width=True):
            limpo = base.drop(columns=[c for c in colunas_remover if c in base.columns], errors="ignore")
            st.session_state["df_origem"] = limpo
            st.session_state["df_saida"] = limpo.copy()
            st.session_state["_ia_auto_mapping_executado"] = False
            st.success("Base visual limpa aplicada ao fluxo.")
            st.rerun()


__all__ = ["render_origem_site_visual_preview"]
