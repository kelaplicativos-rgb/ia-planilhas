from __future__ import annotations

import re
import unicodedata

import pandas as pd
import streamlit as st

from bling_app_zero.core.product_data_quality import normalize_product_dataframe
from bling_app_zero.ui.app_helpers import log_debug, normalizar_texto
from bling_app_zero.ui.mapeamento.value_guard import clean_invalid_preview_mappings
from bling_app_zero.ui.preview_final_data import remover_colunas_artificiais, zerar_colunas_video
from bling_app_zero.utils.gtin import contar_gtins_invalidos_df, contar_gtins_suspeitos_df


LINHAS_LIXO_DESCRICAO = {
    "mega center eletronicos",
    "mega center eletrônicos",
    "loja de eletronicos",
    "loja de eletrônicos",
    "catalogo de produtos",
    "catálogo de produtos",
    "produtos",
    "todos os produtos",
    "conecte se conosco",
    "conecte-se conosco",
    "conecte conosco",
    "esgotado",
    "paginas",
    "páginas",
    "stoqui",
    "home",
    "inicio",
    "início",
    "atendimento",
    "contato",
}

TRECHOS_LIXO_DESCRICAO = (
    "loja fisica e virtual",
    "loja física e virtual",
    "atendimento de segunda",
    "av mateo bei",
    "mateo bei",
    "conecte se conosco",
    "conecte-se conosco",
    "redes sociais",
    "todos os direitos reservados",
)


def _norm_lixo(valor: object) -> str:
    texto = str(valor or "").strip().lower()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(ch for ch in texto if not unicodedata.combining(ch))
    texto = re.sub(r"[^a-z0-9]+", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def _limpar_texto_celula(valor: object) -> str:
    texto = str(valor or "")
    texto = texto.replace("\ufeff", "").replace("\u200b", "").replace("\xa0", " ")
    texto = re.sub(r"[\r\n\t]+", " ", texto)
    texto = re.sub(r"\s{2,}", " ", texto)
    return texto.strip()


def _limpar_titulo_produto(valor: object) -> str:
    texto = _limpar_texto_celula(valor)
    if not texto:
        return ""

    texto = re.sub(
        r"^\s*(?:C[ÓO]D(?:IGO)?|SKU|REF(?:ER[ÊE]NCIA)?|MODELO|ITEM)\s*[:#-]?\s*[A-Za-z0-9._/-]{3,40}\s+",
        "",
        texto,
        flags=re.I,
    )
    texto = re.sub(r"\s*R\$\s*\d[\s\S]*$", "", texto, flags=re.I)
    texto = re.sub(
        r"\s+(?:no pix|ou no pix|ou r\$.*|cart[aã]o|boleto|comprar|adicionar ao carrinho).*$",
        "",
        texto,
        flags=re.I,
    )
    texto = _limpar_texto_celula(texto).strip(" -|•–—")
    return _limpar_texto_celula(texto)


def _coluna_descricao_produto(df: pd.DataFrame) -> str:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return ""
    prioridades = ["Descrição Produto", "Descricao Produto", "Descrição", "Descricao", "Nome", "Produto"]
    mapa = {normalizar_texto(c): str(c) for c in df.columns}
    for nome in prioridades:
        achado = mapa.get(normalizar_texto(nome))
        if achado:
            return achado
    for col in df.columns:
        n = normalizar_texto(col)
        if "descricao" in n or "descrição" in n or "produto" in n or "nome" in n:
            return str(col)
    return ""


def _coluna_codigo_produto(df: pd.DataFrame) -> str:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return ""
    mapa = {normalizar_texto(c): str(c) for c in df.columns}
    for nome in ["Codigo produto *", "Código produto *", "Código", "Codigo", "SKU", "GTIN **", "GTIN"]:
        achado = mapa.get(normalizar_texto(nome))
        if achado:
            return achado
    return ""


def _coluna_gtin_produto(df: pd.DataFrame) -> str:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return ""
    mapa = {normalizar_texto(c): str(c) for c in df.columns}
    for nome in ["GTIN **", "GTIN", "GTIN/EAN", "EAN"]:
        achado = mapa.get(normalizar_texto(nome))
        if achado:
            return achado
    return ""


def _coluna_preco_produto(df: pd.DataFrame) -> str:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return ""
    mapa = {normalizar_texto(c): str(c) for c in df.columns}
    for nome in ["Preço unitário (OBRIGATÓRIO)", "Preco unitario (OBRIGATORIO)", "Preço unitário", "Preco unitario", "Preço", "Preco", "Valor"]:
        achado = mapa.get(normalizar_texto(nome))
        if achado:
            return achado
    return ""


def _tem_preco(valor: object) -> bool:
    texto = _limpar_texto_celula(valor)
    if not texto:
        return False
    texto = texto.replace("R$", "").replace("r$", "").replace(" ", "")
    if "," in texto and "." in texto:
        texto = texto.replace(".", "").replace(",", ".")
    else:
        texto = texto.replace(",", ".")
    texto = re.sub(r"[^0-9.\-]", "", texto)
    try:
        return float(texto) > 0
    except Exception:
        return False


def _codigo_parece_produto(valor: object) -> bool:
    texto = re.sub(r"\D+", "", str(valor or ""))
    return len(texto) in {8, 12, 13, 14} or len(texto) >= 4


def _descricao_lixo(valor: object) -> bool:
    texto = _limpar_texto_celula(valor)
    if not texto:
        return True
    norm = _norm_lixo(texto)
    lixos_norm = {_norm_lixo(v) for v in LINHAS_LIXO_DESCRICAO}
    trechos_norm = tuple(_norm_lixo(v) for v in TRECHOS_LIXO_DESCRICAO)
    if norm in lixos_norm:
        return True
    if any(trecho and trecho in norm for trecho in trechos_norm):
        return True
    if re.fullmatch(r"(?:r\$)?\s*[0-9\.,%\s]+", texto.lower()):
        return True
    if re.search(r"R\$\s*\d", texto, flags=re.I) and any(t in texto.lower() for t in ["pix", "cart", "boleto", "desconto"]):
        return True
    if len(texto) > 130 and any(t in norm for t in ["loja", "atendimento", "segunda", "sabado", "avenida", "av"]):
        return True
    return False


def _linha_tem_sinal_item(row: pd.Series, desc_col: str, cod_col: str, preco_col: str) -> bool:
    descricao = _limpar_texto_celula(row.get(desc_col, "")) if desc_col else ""
    codigo = _limpar_texto_celula(row.get(cod_col, "")) if cod_col else ""
    preco = row.get(preco_col, "") if preco_col else ""

    if _descricao_lixo(descricao):
        return False
    if _codigo_parece_produto(codigo):
        return True
    if _tem_preco(preco) and len(descricao) >= 8:
        return True
    palavras_item = re.findall(r"[A-Za-zÀ-ÿ0-9]+", descricao)
    return len(palavras_item) >= 3


def _deduplicar_itens_finais(df: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return pd.DataFrame()
    base = df.copy().fillna("")
    antes = len(base)
    for col in [_coluna_gtin_produto(base), _coluna_codigo_produto(base), _coluna_descricao_produto(base)]:
        if col and col in base.columns:
            serie = base[col].astype(str).str.strip()
            com_valor = base[serie.ne("")].drop_duplicates(subset=[col], keep="first")
            sem_valor = base[serie.eq("")]
            base = pd.concat([com_valor, sem_valor], ignore_index=True, sort=False)
    removidas = antes - len(base)
    if removidas > 0:
        log_debug(f"{removidas} linha(s) duplicada(s) removida(s) do preview/download final.", nivel="INFO")
    return base.reset_index(drop=True).fillna("")


def _blindar_mapeamento_final(df: pd.DataFrame) -> pd.DataFrame:
    """Aplica a mesma blindagem do preview no DataFrame final padrão Bling."""
    if not isinstance(df, pd.DataFrame) or df.empty:
        return df
    antes = df.copy().fillna("").astype(str)
    base = normalize_product_dataframe(df.copy())
    base = clean_invalid_preview_mappings(base).fillna("")
    try:
        comparavel = antes.reindex(columns=base.columns).fillna("").astype(str)
        alteradas = int((comparavel != base.astype(str)).to_numpy().sum())
    except Exception:
        alteradas = 0
    if alteradas > 0:
        log_debug(f"{alteradas} célula(s) com mapeamento incompatível corrigida(s) antes do preview/download final.", nivel="INFO")
    return base


def _limpar_df_para_download(df: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame):
        return pd.DataFrame()

    base = df.copy().fillna("")
    base = remover_colunas_artificiais(base)
    base = zerar_colunas_video(base).fillna("")
    base = _blindar_mapeamento_final(base).fillna("")

    for coluna in base.columns:
        base[coluna] = base[coluna].map(_limpar_texto_celula)

    desc_col = _coluna_descricao_produto(base)
    cod_col = _coluna_codigo_produto(base)
    preco_col = _coluna_preco_produto(base)

    if desc_col and desc_col in base.columns:
        base[desc_col] = base[desc_col].map(_limpar_titulo_produto)
        antes = len(base)
        base = base[base.apply(lambda row: _linha_tem_sinal_item(row, desc_col, cod_col, preco_col), axis=1)].copy().reset_index(drop=True)
        removidas = antes - len(base)
        if removidas > 0:
            log_debug(f"{removidas} linha(s) lixo removida(s) do preview/download final.", nivel="INFO")

    base = _deduplicar_itens_finais(base)
    return base.fillna("")


def _csv_bling_bytes(df: pd.DataFrame) -> bytes:
    """Gera CSV no padrão de importação do Bling."""
    base = _limpar_df_para_download(df)
    return base.to_csv(index=False, sep=";").encode("utf-8-sig")


def render_preview_dataframe(df_final: pd.DataFrame) -> None:
    st.markdown("### Preview final")

    df_final = _limpar_df_para_download(df_final)
    st.session_state["df_final"] = df_final.copy()

    if df_final.empty:
        st.dataframe(pd.DataFrame(columns=df_final.columns), use_container_width=True, hide_index=True)
        return

    st.caption("Use o botão oficial **Baixar CSV final** abaixo. O botão de exportação da grade é apenas visual e pode gerar CSV fora do padrão Bling.")
    st.dataframe(df_final.head(80), use_container_width=True, hide_index=True)
    with st.expander("Ver preview ampliado", expanded=False):
        st.dataframe(df_final.head(250), use_container_width=True, hide_index=True)


def render_download(df_final: pd.DataFrame, validacao_ok: bool) -> None:
    st.markdown("### Download da planilha padrão Bling")

    df_final = _limpar_df_para_download(df_final)
    st.session_state["df_final"] = df_final.copy()
    csv_bytes = _csv_bling_bytes(df_final)

    gtins_invalidos_total = contar_gtins_invalidos_df(df_final)
    gtins_suspeitos = contar_gtins_suspeitos_df(df_final)
    gtins_invalidos_reais = max(int(gtins_invalidos_total) - int(gtins_suspeitos), 0)

    download_liberado = bool(validacao_ok)

    st.caption("CSV padrão Bling: separador ;, UTF-8-SIG, sem coluna de índice, sem espaços no título, sem linhas lixo e sem duplicados.")

    st.download_button(
        label="📥 Baixar CSV final",
        data=csv_bytes,
        file_name="bling_saida_final.csv",
        mime="text/csv",
        use_container_width=True,
        disabled=not download_liberado,
        key="btn_download_csv_final_preview",
    )

    if download_liberado:
        if gtins_invalidos_reais > 0 or gtins_suspeitos > 0:
            st.info(
                f"O download está liberado. Ainda existem {gtins_invalidos_reais} GTIN(s) inválido(s) "
                f"e {gtins_suspeitos} GTIN(s) suspeito(s), mas essa correção ficou centralizada na etapa anterior."
            )

        if st.session_state.get("preview_download_realizado", False):
            st.success("Download já confirmado. Conexão e envio ao Bling liberados.")
        elif st.button(
            "✅ Já baixei / seguir para conexão e envio",
            use_container_width=True,
            key="btn_confirmar_download_preview",
        ):
            st.session_state["preview_download_realizado"] = True
            log_debug("Usuário confirmou a etapa de download e avançou para conexão/envio.", nivel="INFO")
            st.rerun()
    else:
        st.info("Ajuste a validação principal antes de liberar o download e o envio.")
