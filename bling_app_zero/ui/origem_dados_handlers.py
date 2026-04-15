
from __future__ import annotations

import io
import xml.etree.ElementTree as ET

import pandas as pd
import streamlit as st

from bling_app_zero.ui.app_helpers import (
    log_debug,
    safe_df_dados,
    safe_df_estrutura,
)
from bling_app_zero.ui.origem_dados_estado import (
    fingerprint_df,
    limpar_mapeamento_widgets,
    obter_origem_atual,
    safe_int,
    safe_str,
)


# ==========================================================
# NORMALIZAÇÃO
# ==========================================================
def aplicar_normalizacao_basica(df: pd.DataFrame) -> pd.DataFrame:
    try:
        if not isinstance(df, pd.DataFrame):
            return pd.DataFrame()

        df_out = df.copy()

        for coluna in list(df_out.columns):
            nome = safe_str(coluna).strip().lower()
            if nome in {"unnamed: 0", "unnamed:0", "index"}:
                df_out = df_out.drop(columns=[coluna], errors="ignore")

        colunas_finais: list[str] = []
        for col in df_out.columns:
            nome = (
                safe_str(col)
                .replace("\ufeff", "")
                .replace("\n", " ")
                .replace("\r", " ")
                .strip()
            )
            colunas_finais.append(nome or "Coluna")

        df_out.columns = colunas_finais
        return df_out.replace({None: ""}).fillna("")
    except Exception as e:
        log_debug(f"[ORIGEM_DADOS] erro na normalização básica: {e}", "ERROR")
        return df if isinstance(df, pd.DataFrame) else pd.DataFrame()


# ==========================================================
# LEITURA ROBUSTA
# ==========================================================
def _ler_csv_robusto(upload) -> pd.DataFrame | None:
    try:
        conteudo = upload.read()
        if not conteudo:
            return None

        candidatos = [
            ("utf-8-sig", None),
            ("utf-8", None),
            ("latin1", None),
            ("cp1252", None),
            ("utf-8-sig", ";"),
            ("utf-8", ";"),
            ("latin1", ";"),
            ("cp1252", ";"),
        ]

        for encoding, sep in candidatos:
            try:
                buffer = io.BytesIO(conteudo)
                if sep is None:
                    df = pd.read_csv(
                        buffer,
                        sep=None,
                        engine="python",
                        encoding=encoding,
                    )
                else:
                    df = pd.read_csv(buffer, sep=sep, encoding=encoding)
                return aplicar_normalizacao_basica(df)
            except Exception:
                continue

        return None
    except Exception as e:
        log_debug(f"[ORIGEM_DADOS] erro ao ler CSV: {e}", "ERROR")
        return None


def _ler_excel_robusto(upload) -> pd.DataFrame | None:
    try:
        conteudo = upload.read()
        if not conteudo:
            return None

        for engine in [None, "openpyxl", "xlrd"]:
            try:
                buffer = io.BytesIO(conteudo)
                if engine:
                    df = pd.read_excel(buffer, engine=engine)
                else:
                    df = pd.read_excel(buffer)
                return aplicar_normalizacao_basica(df)
            except Exception:
                continue

        return None
    except Exception as e:
        log_debug(f"[ORIGEM_DADOS] erro ao ler Excel: {e}", "ERROR")
        return None


def _text_or_empty(node: ET.Element | None, tag_name: str) -> str:
    if node is None:
        return ""
    for child in node.iter():
        tag = child.tag.split("}")[-1]
        if tag == tag_name:
            return (child.text or "").strip()
    return ""


def _parse_nfe_xml_produtos(conteudo: bytes) -> pd.DataFrame | None:
    try:
        root = ET.fromstring(conteudo)
    except Exception:
        return None

    ide = None
    emit = None

    for child in root.iter():
        tag = child.tag.split("}")[-1]
        if tag == "ide" and ide is None:
            ide = child
        elif tag == "emit" and emit is None:
            emit = child

    numero_nota = _text_or_empty(ide, "nNF")
    serie = _text_or_empty(ide, "serie")
    fornecedor = _text_or_empty(emit, "xNome")
    cnpj_emit = _text_or_empty(emit, "CNPJ")

    rows: list[dict] = []

    for det in root.iter():
        if det.tag.split("}")[-1] != "det":
            continue

        prod = None
        imposto = None

        for child in det:
            tag = child.tag.split("}")[-1]
            if tag == "prod":
                prod = child
            elif tag == "imposto":
                imposto = child

        if prod is None:
            continue

        row = {
            "numero_nota": numero_nota,
            "serie_nota": serie,
            "fornecedor": fornecedor,
            "cnpj_fornecedor": cnpj_emit,
            "item": det.attrib.get("nItem", ""),
            "codigo_produto": _text_or_empty(prod, "cProd"),
            "descricao": _text_or_empty(prod, "xProd"),
            "descricao_curta": _text_or_empty(prod, "xProd"),
            "ean": _text_or_empty(prod, "cEAN"),
            "ncm": _text_or_empty(prod, "NCM"),
            "cfop": _text_or_empty(prod, "CFOP"),
            "unidade": _text_or_empty(prod, "uCom"),
            "quantidade": _text_or_empty(prod, "qCom"),
            "preco_unitario": _text_or_empty(prod, "vUnCom"),
            "valor_total": _text_or_empty(prod, "vProd"),
            "codigo_barras_tributavel": _text_or_empty(prod, "cEANTrib"),
            "unidade_tributavel": _text_or_empty(prod, "uTrib"),
            "quantidade_tributavel": _text_or_empty(prod, "qTrib"),
            "preco_unitario_tributavel": _text_or_empty(prod, "vUnTrib"),
        }

        if imposto is not None:
            row["origem_icms"] = _text_or_empty(imposto, "orig")
            row["cst_icms"] = _text_or_empty(imposto, "CST") or _text_or_empty(imposto, "CSOSN")
            row["aliquota_icms"] = _text_or_empty(imposto, "pICMS")
            row["valor_icms"] = _text_or_empty(imposto, "vICMS")
            row["aliquota_ipi"] = _text_or_empty(imposto, "pIPI")
            row["valor_ipi"] = _text_or_empty(imposto, "vIPI")
            row["aliquota_pis"] = _text_or_empty(imposto, "pPIS")
            row["valor_pis"] = _text_or_empty(imposto, "vPIS")
            row["aliquota_cofins"] = _text_or_empty(imposto, "pCOFINS")
            row["valor_cofins"] = _text_or_empty(imposto, "vCOFINS")

        rows.append(row)

    if not rows:
        return None

    return aplicar_normalizacao_basica(pd.DataFrame(rows))


def _ler_xml_robusto(upload) -> pd.DataFrame | None:
    try:
        conteudo = upload.read()
        if not conteudo:
            return None

        df_nfe = _parse_nfe_xml_produtos(conteudo)
        if safe_df_dados(df_nfe):
            return df_nfe

        for parser in [None, "lxml", "etree"]:
            try:
                buffer = io.BytesIO(conteudo)
                if parser:
                    df = pd.read_xml(buffer, parser=parser)
                else:
                    df = pd.read_xml(buffer)

                if isinstance(df, pd.DataFrame) and not df.empty:
                    return aplicar_normalizacao_basica(df)
            except Exception:
                continue

        return None
    except Exception as e:
        log_debug(f"[ORIGEM_DADOS] erro ao ler XML: {e}", "ERROR")
        return None


def ler_planilha(upload) -> pd.DataFrame | None:
    if upload is None:
        return None

    nome = safe_str(getattr(upload, "name", "")).lower()

    try:
        if nome.endswith(".csv"):
            return _ler_csv_robusto(upload)

        if nome.endswith((".xlsx", ".xls")):
            return _ler_excel_robusto(upload)

        if nome.endswith(".xml"):
            return _ler_xml_robusto(upload)
    except Exception as e:
        log_debug(f"[ORIGEM_DADOS] erro ao ler arquivo: {e}", "ERROR")

    return None


# ==========================================================
# ESTADO / TROCAS
# ==========================================================
def _normalizar_tipo_origem(origem: str) -> str:
    valor = safe_str(origem).strip().lower()
    mapa = {
        "site": "site",
        "buscar em site": "site",
        "busca em site": "site",
        "planilha": "planilha",
        "planilha / csv / xml": "planilha",
        "planilha/csv/xml": "planilha",
        "arquivo": "planilha",
        "upload": "planilha",
    }
    return mapa.get(valor, valor or "planilha")


def _limpar_estado_dependente_origem() -> None:
    for chave in [
        "df_origem",
        "df_saida",
        "df_final",
        "df_precificado",
        "df_calc_precificado",
        "origem_dados_fingerprint",
        "site_processado",
        "site_autoavanco_realizado",
    ]:
        st.session_state.pop(chave, None)

    limpar_mapeamento_widgets()


def controlar_troca_origem(origem: str, log_fn=None) -> None:
    origem_atual = _normalizar_tipo_origem(origem)
    origem_anterior = _normalizar_tipo_origem(
        st.session_state.get("_origem_anterior_origem_dados")
    )

    st.session_state["origem_dados_tipo"] = origem_atual
    st.session_state["origem_dados"] = origem_atual

    if not safe_str(st.session_state.get("_origem_anterior_origem_dados")).strip():
        st.session_state["_origem_anterior_origem_dados"] = origem_atual
        st.session_state["site_processado"] = False
        st.session_state["site_autoavanco_realizado"] = False
        if callable(log_fn):
            log_fn(f"[ORIGEM_DADOS] origem inicial definida: {origem_atual}", "INFO")
        return

    if origem_anterior == origem_atual:
        return

    if callable(log_fn):
        log_fn(
            f"[ORIGEM_DADOS] origem alterada: {origem_anterior} → {origem_atual}. "
            "Limpando saída e mapeamento.",
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
                log_fn("[ORIGEM_DADOS] nova origem detectada. Limpando saída anterior.", "INFO")

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


# ==========================================================
# MODELO / BASE
# ==========================================================
def _colunas_modelo_cadastro_padrao() -> list[str]:
    return [
        "Código",
        "Descrição",
        "Descrição Curta",
        "Preço de venda",
        "Situação",
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


def _criar_modelo_fallback(tipo_operacao: str) -> pd.DataFrame:
    tipo = safe_str(tipo_operacao).lower()
    if tipo == "estoque":
        return pd.DataFrame(columns=_colunas_modelo_estoque_padrao())
    return pd.DataFrame(columns=_colunas_modelo_cadastro_padrao())


def _resolver_tipo_operacao_modelo() -> str:
    tipo = safe_str(st.session_state.get("tipo_operacao_bling")).lower()
    return "estoque" if tipo == "estoque" else "cadastro"


def _resolver_candidatos_modelo(tipo_operacao: str) -> list[str]:
    if tipo_operacao == "estoque":
        return [
            "df_modelo_estoque",
            "df_modelo",
            "df_modelo_cadastro",
        ]
    return [
        "df_modelo_cadastro",
        "df_modelo",
        "df_modelo_estoque",
    ]


def _sincronizar_alias_modelo(tipo_operacao: str, df_modelo: pd.DataFrame) -> pd.DataFrame:
    df_ok = df_modelo.copy()

    if tipo_operacao == "estoque":
        st.session_state["df_modelo_estoque"] = df_ok.copy()
    else:
        st.session_state["df_modelo_cadastro"] = df_ok.copy()

    if not safe_df_estrutura(st.session_state.get("df_modelo")):
        st.session_state["df_modelo"] = df_ok.copy()

    return df_ok


def _padronizar_modelo_estoque(df_modelo: pd.DataFrame) -> pd.DataFrame:
    colunas_esperadas = _colunas_modelo_estoque_padrao()

    if not safe_df_estrutura(df_modelo):
        return pd.DataFrame(columns=colunas_esperadas)

    atuais = [safe_str(c) for c in df_modelo.columns]
    atuais_norm = {safe_str(c).strip().lower(): c for c in atuais}

    if set(colunas_esperadas).issubset(set(atuais)):
        return df_modelo[colunas_esperadas].copy()

    df_out = pd.DataFrame(columns=colunas_esperadas)

    mapa_legado = {
        "id produto": atuais_norm.get("id produto"),
        "codigo produto *": atuais_norm.get("codigo produto *") or atuais_norm.get("código") or atuais_norm.get("codigo"),
        "gtin **": atuais_norm.get("gtin **") or atuais_norm.get("ean") or atuais_norm.get("gtin"),
        "descrição produto": atuais_norm.get("descrição produto") or atuais_norm.get("descricao produto") or atuais_norm.get("descricao") or atuais_norm.get("descrição"),
        "deposito (obrigatório)": atuais_norm.get("deposito (obrigatório)") or atuais_norm.get("depósito (obrigatório)"),
        "balanço (obrigatório)": atuais_norm.get("balanço (obrigatório)") or atuais_norm.get("balanco (obrigatório)") or atuais_norm.get("quantidade"),
        "preço unitário (obrigatório)": atuais_norm.get("preço unitário (obrigatório)") or atuais_norm.get("preco unitario (obrigatório)") or atuais_norm.get("preço unitário (obrigatorio)"),
        "preço de custo": atuais_norm.get("preço de custo") or atuais_norm.get("preco de custo") or atuais_norm.get("custo"),
        "observação": atuais_norm.get("observação") or atuais_norm.get("observacao"),
        "data": atuais_norm.get("data"),
    }

    for col_esperada in colunas_esperadas:
        chave = col_esperada.strip().lower()
        col_origem = mapa_legado.get(chave)
        if col_origem and col_origem in df_modelo.columns:
            df_out[col_esperada] = df_modelo[col_origem]
        else:
            df_out[col_esperada] = ""

    return df_out


def obter_modelo_ativo():
    tipo_operacao = _resolver_tipo_operacao_modelo()

    for chave in _resolver_candidatos_modelo(tipo_operacao):
        df_modelo = st.session_state.get(chave)
        if safe_df_estrutura(df_modelo):
            try:
                log_debug(f"[ORIGEM_DADOS] modelo ativo encontrado em '{chave}'", "INFO")
            except Exception:
                pass

            if tipo_operacao == "estoque":
                df_modelo = _padronizar_modelo_estoque(df_modelo)

            return _sincronizar_alias_modelo(tipo_operacao, df_modelo)

    df_fallback = _criar_modelo_fallback(tipo_operacao)
    try:
        log_debug(
            f"[ORIGEM_DADOS] nenhum modelo carregado na sessão. "
            f"Usando fallback interno para '{tipo_operacao}'.",
            "WARNING",
        )
    except Exception:
        pass

    return _sincronizar_alias_modelo(tipo_operacao, df_fallback)


def modelo_tem_estrutura(df_modelo) -> bool:
    if safe_df_estrutura(df_modelo):
        return True

    try:
        df_resolvido = obter_modelo_ativo()
        return safe_df_estrutura(df_resolvido)
    except Exception as e:
        log_debug(f"[ORIGEM_DADOS] erro ao validar estrutura do modelo: {e}", "ERROR")
        return False


def obter_df_base_prioritaria(df_origem: pd.DataFrame) -> pd.DataFrame:
    df_prec = st.session_state.get("df_precificado")
    df_calc = st.session_state.get("df_calc_precificado")

    if safe_df_estrutura(df_prec):
        return df_prec.copy()

    if safe_df_estrutura(df_calc):
        return df_calc.copy()

    return df_origem.copy()


# ==========================================================
# ESTOQUE
# ==========================================================
def aplicar_bloco_estoque(df_saida: pd.DataFrame, origem_atual: str) -> pd.DataFrame:
    try:
        df_out = df_saida.copy()

        qtd_padrao = 0 if "site" in safe_str(origem_atual).lower() else 1
        qtd_padrao = safe_int(
            st.session_state.get("site_estoque_padrao_disponivel"),
            qtd_padrao,
        )

        if "Balanço (OBRIGATÓRIO)" not in df_out.columns:
            df_out["Balanço (OBRIGATÓRIO)"] = qtd_padrao
        else:
            serie_balanco = pd.to_numeric(df_out["Balanço (OBRIGATÓRIO)"], errors="coerce")
            df_out["Balanço (OBRIGATÓRIO)"] = serie_balanco.fillna(qtd_padrao)

        deposito_nome = safe_str(st.session_state.get("deposito_nome"))
        if deposito_nome:
            if "Deposito (OBRIGATÓRIO)" not in df_out.columns:
                df_out["Deposito (OBRIGATÓRIO)"] = deposito_nome
            else:
                coluna = (
                    df_out["Deposito (OBRIGATÓRIO)"]
                    .replace({None: ""})
                    .fillna("")
                    .astype(str)
                    .str.strip()
                )
                df_out["Deposito (OBRIGATÓRIO)"] = coluna
                df_out.loc[coluna.eq(""), "Deposito (OBRIGATÓRIO)"] = deposito_nome

        if "ID Produto" not in df_out.columns:
            df_out["ID Produto"] = ""

        if "Observação" not in df_out.columns:
            df_out["Observação"] = ""

        if "Data" not in df_out.columns:
            df_out["Data"] = ""

        return df_out
    except Exception as e:
        log_debug(f"[ORIGEM_DADOS] erro bloco estoque: {e}", "ERROR")
        return df_saida.copy() if isinstance(df_saida, pd.DataFrame) else pd.DataFrame()


# ==========================================================
# PRECIFICAÇÃO OLIST
# ==========================================================
def nome_coluna_preco_saida() -> str:
    return (
        "Preço unitário (OBRIGATÓRIO)"
        if st.session_state.get("tipo_operacao_bling") == "estoque"
        else "Preço de venda"
    )


def to_numeric_series(serie: pd.Series) -> pd.Series:
    try:
        texto = (
            serie.replace({None: ""})
            .fillna("")
            .astype(str)
            .str.replace("R$", "", regex=False)
            .str.replace(" ", "", regex=False)
        
