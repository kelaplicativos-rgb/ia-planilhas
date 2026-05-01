from __future__ import annotations

import re

import pandas as pd
import streamlit as st

from bling_app_zero.ui.app_helpers import log_debug, normalizar_texto
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
}


def _coluna_descricao_produto(df: pd.DataFrame) -> str:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return ""
    prioridades = [
        "Descrição Produto",
        "Descricao Produto",
        "Descrição",
        "Descricao",
        "Nome",
        "Produto",
    ]
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


def _coluna_preco_produto(df: pd.DataFrame) -> str:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return ""
    mapa = {normalizar_texto(c): str(c) for c in df.columns}
    for nome in ["Preço unitário (OBRIGATÓRIO)", "Preco unitario (OBRIGATORIO)", "Preço unitário", "Preco unitario", "Preço", "Preco", "Valor"]:
        achado = mapa.get(normalizar_texto(nome))
        if achado:
            return achado
    return ""


def _tem_texto(valor: object) -> bool:
    texto = str(valor or "").strip()
    return bool(texto and texto.lower() not in {"nan", "none", "null"})


def _tem_preco(valor: object) -> bool:
    texto = str(valor or "").strip()
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


def _descricao_lixo(valor: object) -> bool:
    texto = str(valor or "").strip()
    if not texto:
        return True
    norm = normalizar_texto(texto)
    if norm in LINHAS_LIXO_DESCRICAO:
        return True
    if any(lixo and lixo == norm for lixo in LINHAS_LIXO_DESCRICAO):
        return True
    if re.fullmatch(r"(?:r\$)?\s*[0-9\.,%\s]+", texto.lower()):
        return True
    if re.search(r"R\$\s*\d", texto, flags=re.I) and any(t in texto.lower() for t in ["pix", "cart", "boleto", "desconto"]):
        return True
    return False


def _limpar_df_para_download(df: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame):
        return pd.DataFrame()

    base = df.copy().fillna("")
    base = remover_colunas_artificiais(base)
    base = zerar_colunas_video(base).fillna("")

    desc_col = _coluna_descricao_produto(base)
    cod_col = _coluna_codigo_produto(base)
    preco_col = _coluna_preco_produto(base)

    if desc_col and desc_col in base.columns:
        antes = len(base)

        def manter_linha(row: pd.Series) -> bool:
            descricao = row.get(desc_col, "")
            if _descricao_lixo(descricao):
                codigo_ok = _tem_texto(row.get(cod_col, "")) if cod_col else False
                preco_ok = _tem_preco(row.get(preco_col, "")) if preco_col else False
                # Linha sem produto real, sem código e sem preço válido é lixo de cabeçalho/site.
                return bool(codigo_ok and preco_ok and not str(descricao or "").strip().lower().startswith("mega center"))
            return True

        base = base[base.apply(manter_linha, axis=1)].copy().reset_index(drop=True)
        removidas = antes - len(base)
        if removidas > 0:
            log_debug(f"{removidas} linha(s) lixo removida(s) do preview/download final.", nivel="INFO")

    return base.fillna("")


def _csv_bling_bytes(df: pd.DataFrame) -> bytes:
    """Gera CSV no padrão de importação do Bling.

    - separador ponto e vírgula;
    - UTF-8 com BOM para abrir corretamente no Excel;
    - sem índice artificial;
    - colunas de vídeo zeradas;
    - linhas de cabeçalho/site removidas.
    """
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

    st.caption("CSV padrão Bling: separador ;, UTF-8-SIG, sem coluna de índice e sem linha lixo de cabeçalho/site.")

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

