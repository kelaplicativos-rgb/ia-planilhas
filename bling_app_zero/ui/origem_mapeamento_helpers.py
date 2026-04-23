from __future__ import annotations

import hashlib
import re
from collections import Counter

import pandas as pd
import streamlit as st

from bling_app_zero.agent.agent_orchestrator import construir_pacote_agente_para_ui
from bling_app_zero.ui.app_helpers import (
    blindar_df_para_bling,
    get_etapa,
    log_debug,
    normalizar_imagens_pipe,
    normalizar_texto,
    safe_df_dados,
    safe_df_estrutura,
    safe_lower,
    sincronizar_etapa_global,
)


ANTI_LIXO_VALORES = {
    "",
    "entrando...",
    "entrando",
    "loading...",
    "loading",
    "carregando...",
    "carregando",
    "dark",
    "light",
    "theme",
    "ers-color-scheme",
    "color-scheme",
    "undefined",
    "null",
    "none",
    "nan",
}

MAP_DESTINOS_SEMANTICOS = {
    "codigo": [
        "codigo",
        "código",
        "sku",
        "referencia",
        "referência",
        "ref",
        "product id",
        "id produto",
    ],
    "descricao": [
        "descricao",
        "descrição",
        "titulo",
        "título",
        "nome",
        "produto",
        "product name",
    ],
    "descricao_curta": [
        "descricao curta",
        "descrição curta",
        "short description",
        "resumo",
    ],
    "categoria": [
        "categoria",
        "category",
        "departamento",
        "segmento",
    ],
    "marca": [
        "marca",
        "brand",
        "fabricante",
    ],
    "gtin": [
        "gtin",
        "ean",
        "codigo de barras",
        "código de barras",
        "barcode",
    ],
    "ncm": [
        "ncm",
    ],
    "preco": [
        "preco",
        "preço",
        "valor",
        "price",
        "preco de custo",
        "preço de custo",
        "preco venda",
        "preço venda",
        "preco unitario",
        "preço unitário",
    ],
    "quantidade": [
        "quantidade",
        "estoque",
        "qtd",
        "saldo",
        "inventory",
        "stock",
    ],
    "url_imagens": [
        "imagem",
        "imagens",
        "image",
        "images",
        "url imagem",
        "url imagens",
        "foto",
        "fotos",
    ],
}


def _garantir_etapa_mapeamento_ativa() -> None:
    if get_etapa() != "mapeamento":
        sincronizar_etapa_global("mapeamento")

    st.session_state["_etapa_url_inicializada"] = True
    st.session_state["_ultima_etapa_sincronizada_url"] = "mapeamento"


def _normalizar_texto_busca(valor) -> str:
    texto = str(valor or "").strip().lower()
    texto = re.sub(r"\s+", " ", texto)
    return texto


def _eh_coluna_video(nome_coluna) -> bool:
    nome = _normalizar_texto_busca(nome_coluna)
    return bool(nome and any(token in nome for token in ["video", "vídeo", "youtube"]))


def _hash_df(df: pd.DataFrame) -> str:
    if not isinstance(df, pd.DataFrame):
        return ""

    try:
        partes = []
        partes.append("|".join([str(c).strip() for c in df.columns.tolist()]))
        amostra = df.head(20).fillna("").astype(str)
        for _, row in amostra.iterrows():
            partes.append("|".join(row.tolist()))
        bruto = "\n".join(partes)
        return hashlib.sha256(bruto.encode("utf-8")).hexdigest()
    except Exception:
        return ""


def _detectar_operacao() -> str:
    operacao = safe_lower(
        st.session_state.get("tipo_operacao")
        or st.session_state.get("tipo_operacao_bling")
        or ""
    )
    if operacao not in {"cadastro", "estoque"}:
        return "cadastro"
    return operacao


def _obter_df_base() -> pd.DataFrame:
    for chave in ["df_precificado", "df_saida", "df_origem"]:
        df = st.session_state.get(chave)
        if safe_df_dados(df):
            return df.copy()
    return pd.DataFrame()


def _obter_df_modelo() -> pd.DataFrame:
    df_modelo = st.session_state.get("df_modelo")
    if safe_df_estrutura(df_modelo):
        return df_modelo.copy()
    return pd.DataFrame()


def _colunas_preco_modelo(df_modelo: pd.DataFrame) -> list[str]:
    candidatos: list[str] = []

    for col in df_modelo.columns:
        nome = str(col)
        n = _normalizar_texto_busca(nome)

        if n in {
            "preco",
            "preço",
            "preco de venda",
            "preço de venda",
            "preco unitario obrigatorio",
            "preço unitário obrigatório",
            "preco unitario",
            "preço unitário",
            "valor",
            "valor venda",
            "valor unitario",
            "valor unitário",
        }:
            candidatos.append(nome)
            continue

        if "preco" in n or "preço" in n or "valor" in n:
            candidatos.append(nome)

    vistos = set()
    saida = []
    for c in candidatos:
        if c not in vistos:
            vistos.add(c)
            saida.append(c)

    return saida


def _coluna_preco_prioritaria(df_modelo: pd.DataFrame, operacao: str) -> str:
    prioridades_estoque = [
        "Preço unitário (OBRIGATÓRIO)",
        "Preço unitário",
        "Preço",
        "Valor",
    ]
    prioridades_cadastro = [
        "Preço de venda",
        "Preço",
        "Valor",
    ]

    colunas = [str(c) for c in df_modelo.columns.tolist()]
    prioridades = prioridades_estoque if operacao == "estoque" else prioridades_cadastro

    for prioridade in prioridades:
        if prioridade in colunas:
            return prioridade

    candidatas = _colunas_preco_modelo(df_modelo)
    return candidatas[0] if candidatas else ""


def _coluna_imagens_modelo(df_modelo: pd.DataFrame) -> str:
    colunas = [str(c) for c in df_modelo.columns.tolist()]

    for prioridade in ["URL Imagens", "Url Imagens", "Imagens", "Imagem"]:
        if prioridade in colunas:
            return prioridade

    for col in colunas:
        n = _normalizar_texto_busca(col)
        if "imagem" in n or "image" in n:
            return col

    return ""


def _colunas_deposito_modelo(df_modelo: pd.DataFrame) -> list[str]:
    colunas = [str(c) for c in df_modelo.columns.tolist()]
    encontrados: list[str] = []

    for prioridade in [
        "Depósito (OBRIGATÓRIO)",
        "Depósito",
        "Deposito (OBRIGATÓRIO)",
        "Deposito",
    ]:
        if prioridade in colunas and prioridade not in encontrados:
            encontrados.append(prioridade)

    for col in colunas:
        n = _normalizar_texto_busca(col)
        if ("deposito" in n or "depósito" in n) and col not in encontrados:
            encontrados.append(col)

    return encontrados


def _coluna_deposito_modelo(df_modelo: pd.DataFrame) -> str:
    colunas = _colunas_deposito_modelo(df_modelo)
    return colunas[0] if colunas else ""


def _coluna_situacao_modelo(df_modelo: pd.DataFrame) -> str:
    colunas = [str(c) for c in df_modelo.columns.tolist()]

    for prioridade in ["Situação", "Situacao"]:
        if prioridade in colunas:
            return prioridade

    for col in colunas:
        n = _normalizar_texto_busca(col)
        if "situacao" in n or "situação" in n:
            return col

    return ""


def _coluna_descricao_modelo(df_modelo: pd.DataFrame) -> str:
    for prioridade in ["Descrição", "Descricao"]:
        if prioridade in df_modelo.columns:
            return prioridade

    for col in df_modelo.columns:
        n = _normalizar_texto_busca(col)
        if n == "descricao" or n == "descrição":
            return str(col)

    return ""


def _resetar_mapping_para_modelo(df_modelo: pd.DataFrame) -> dict[str, str]:
    mapping = {str(c): "" for c in df_modelo.columns.tolist()}
    for coluna in list(mapping.keys()):
        if _eh_coluna_video(coluna):
            mapping[coluna] = ""
    return mapping


def _inicializar_mapping(df_base: pd.DataFrame, df_modelo: pd.DataFrame) -> dict[str, str]:
    hash_base = _hash_df(df_base)
    hash_modelo = _hash_df(df_modelo)

    hash_base_anterior = normalizar_texto(st.session_state.get("mapping_hash_base", ""))
    hash_modelo_anterior = normalizar_texto(st.session_state.get("mapping_hash_modelo", ""))

    precisa_resetar = (
        hash_base != hash_base_anterior
        or hash_modelo != hash_modelo_anterior
        or not isinstance(st.session_state.get("mapping_manual"), dict)
    )

    if precisa_resetar:
        st.session_state["mapping_manual"] = _resetar_mapping_para_modelo(df_modelo)
        st.session_state["mapping_sugerido"] = {}
        st.session_state["agent_ui_package"] = {}
        st.session_state["df_final"] = None
        st.session_state["_ia_auto_mapping_executado"] = False

    mapping_salvo = st.session_state.get("mapping_manual", {})
    colunas_modelo = [str(c) for c in df_modelo.columns.tolist()]

    if not isinstance(mapping_salvo, dict):
        mapping_salvo = {}

    mapping_salvo = {k: v for k, v in mapping_salvo.items() if k in colunas_modelo}

    for coluna in colunas_modelo:
        mapping_salvo.setdefault(coluna, "")
        if _eh_coluna_video(coluna):
            mapping_salvo[coluna] = ""

    st.session_state["mapping_manual"] = mapping_salvo
    st.session_state["mapping_hash_base"] = hash_base
    st.session_state["mapping_hash_modelo"] = hash_modelo

    return mapping_salvo


def _obter_deposito_nome_persistido() -> str:
    candidatos = [
        st.session_state.get("deposito_nome"),
        st.session_state.get("deposito_nome_widget"),
        st.session_state.get("deposito"),
    ]

    for valor in candidatos:
        texto = str(valor or "").strip()
        if texto:
            return texto

    return ""


def _sincronizar_deposito_nome() -> str:
    deposito = _obter_deposito_nome_persistido()
    st.session_state["deposito_nome"] = deposito
    st.session_state["deposito_nome_widget"] = deposito
    return deposito


def _campos_bloqueados_automaticos(df_modelo: pd.DataFrame, operacao: str) -> set[str]:
    bloqueados = set()

    coluna_preco = _coluna_preco_prioritaria(df_modelo, operacao)
    if coluna_preco:
        bloqueados.add(coluna_preco)

    coluna_deposito = _coluna_deposito_modelo(df_modelo)
    if operacao == "estoque" and coluna_deposito:
        bloqueados.add(coluna_deposito)

    for coluna in [str(c) for c in df_modelo.columns.tolist()]:
        if _eh_coluna_video(coluna):
            bloqueados.add(coluna)

    return bloqueados


def _amostra_valores_validos(serie: pd.Series, limite: int = 12) -> list[str]:
    valores = []
    for valor in serie.fillna("").astype(str).tolist():
        texto = str(valor or "").strip()
        texto_n = texto.lower()
        if not texto:
            continue
        if texto_n in ANTI_LIXO_VALORES:
            continue
        valores.append(texto)
        if len(valores) >= limite:
            break
    return valores


def _parece_preco(texto: str) -> bool:
    texto = str(texto or "").strip()
    if not texto:
        return False
    if re.search(r"R\$\s*\d", texto, flags=re.I):
        return True
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})*,\d{2}", texto):
        return True
    if re.fullmatch(r"\d+\.\d{2}", texto):
        return True
    return False


def _parece_gtin(texto: str) -> bool:
    dig = re.sub(r"\D+", "", str(texto or ""))
    return len(dig) in {8, 12, 13, 14}


def _parece_url_imagem(texto: str) -> bool:
    texto = str(texto or "").strip().lower()
    return texto.startswith(("http://", "https://")) and any(
        texto.endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".webp", ".gif"]
    )


def _parece_codigo(texto: str) -> bool:
    texto = str(texto or "").strip()
    if not texto:
        return False
    texto_n = texto.lower()
    if texto_n in ANTI_LIXO_VALORES:
        return False
    if len(texto) < 3:
        return False
    if " " in texto and len(texto.split()) > 4:
        return False
    if re.search(r"\d", texto):
        return True
    if re.fullmatch(r"[A-Za-z0-9._/\-]{3,60}", texto):
        return True
    return False


def _parece_marca(texto: str) -> bool:
    texto = str(texto or "").strip()
    if not texto:
        return False
    texto_n = texto.lower()
    if texto_n in ANTI_LIXO_VALORES:
        return False
    if len(texto.split()) > 3:
        return False
    if len(texto) > 40:
        return False
    return bool(re.search(r"[A-Za-zÀ-ÿ]", texto))


def _parece_categoria(texto: str) -> bool:
    texto = str(texto or "").strip()
    if not texto:
        return False
    texto_n = texto.lower()
    if texto_n in ANTI_LIXO_VALORES:
        return False
    if " > " in texto:
        return True
    if len(texto) >= 4 and len(texto) <= 120:
        return True
    return False


def _parece_descricao(texto: str) -> bool:
    texto = str(texto or "").strip()
    if not texto:
        return False
    texto_n = texto.lower()
    if texto_n in ANTI_LIXO_VALORES:
        return False
    if "entrando" in texto_n or "loading" in texto_n or "carregando" in texto_n:
        return False
    return len(texto) >= 6


def _inferir_tipo_coluna(nome_coluna: str, serie: pd.Series) -> str:
    if _eh_coluna_video(nome_coluna):
        return ""

    nome_n = _normalizar_texto_busca(nome_coluna)
    amostras = _amostra_valores_validos(serie, limite=15)

    cont = Counter()

    for chave, aliases in MAP_DESTINOS_SEMANTICOS.items():
        if any(alias in nome_n for alias in aliases):
            cont[chave] += 5

    for valor in amostras:
        if _parece_preco(valor):
            cont["preco"] += 3
        if _parece_gtin(valor):
            cont["gtin"] += 3
        if _parece_url_imagem(valor):
            cont["url_imagens"] += 4
        if _parece_codigo(valor):
            cont["codigo"] += 2
        if _parece_marca(valor):
            cont["marca"] += 1
        if _parece_categoria(valor):
            cont["categoria"] += 1
        if _parece_descricao(valor):
            cont["descricao"] += 1

        if str(valor).strip().isdigit():
            cont["quantidade"] += 2

    if not cont:
        return ""

    tipo, score = cont.most_common(1)[0]
    return tipo if score > 0 else ""


def _score_coluna_para_destino(nome_coluna: str, serie: pd.Series, destino: str) -> int:
    if _eh_coluna_video(nome_coluna):
        return -999

    nome_n = _normalizar_texto_busca(nome_coluna)
    score = 0

    for alias in MAP_DESTINOS_SEMANTICOS.get(destino, []):
        if alias in nome_n:
            score += 8

    amostras = _amostra_valores_validos(serie, limite=15)
    if not amostras:
        return score - 10

    for valor in amostras:
        if destino == "preco" and _parece_preco(valor):
            score += 4
        elif destino == "gtin" and _parece_gtin(valor):
            score += 5
        elif destino == "url_imagens" and _parece_url_imagem(valor):
            score += 5
        elif destino == "codigo" and _parece_codigo(valor):
            score += 3
        elif destino == "marca" and _parece_marca(valor):
            score += 2
        elif destino == "categoria" and _parece_categoria(valor):
            score += 2
        elif destino in {"descricao", "descricao_curta"} and _parece_descricao(valor):
            score += 2
        elif destino == "quantidade" and str(valor).strip().isdigit():
            score += 4

    return score


def _destino_modelo_semantico(coluna_modelo: str) -> str:
    nome_n = _normalizar_texto_busca(coluna_modelo)

    if _eh_coluna_video(nome_n):
        return ""
    if "gtin" in nome_n or "ean" in nome_n or "barra" in nome_n:
        return "gtin"
    if "ncm" in nome_n:
        return "ncm"
    if "marca" in nome_n:
        return "marca"
    if "categoria" in nome_n:
        return "categoria"
    if "imagem" in nome_n or "image" in nome_n:
        return "url_imagens"
    if "quantidade" in nome_n or "estoque" in nome_n or "saldo" in nome_n:
        return "quantidade"
    if "preco" in nome_n or "preço" in nome_n or "valor" in nome_n:
        return "preco"
    if "descrição curta" in nome_n or "descricao curta" in nome_n:
        return "descricao_curta"
    if nome_n in {"descrição", "descricao"} or "descricao" in nome_n or "descrição" in nome_n:
        return "descricao"
    if "codigo" in nome_n or "código" in nome_n or "sku" in nome_n or "refer" in nome_n:
        return "codigo"

    return ""


def _mapping_semantico(
    df_base: pd.DataFrame,
    df_modelo: pd.DataFrame,
    mapping_atual: dict[str, str],
) -> dict[str, str]:
    mapping_final = dict(mapping_atual or {})
    colunas_origem = [str(c) for c in df_base.columns.tolist()]
    bloqueados = _campos_bloqueados_automaticos(df_modelo, _detectar_operacao())
    usados = {
        str(v).strip()
        for k, v in mapping_final.items()
        if str(k) not in bloqueados and str(v).strip()
    }

    inferencias_origem = {
        coluna: _inferir_tipo_coluna(coluna, df_base[coluna]) for coluna in colunas_origem
    }

    for coluna_modelo in [str(c) for c in df_modelo.columns.tolist()]:
        if coluna_modelo in bloqueados or _eh_coluna_video(coluna_modelo):
            mapping_final[coluna_modelo] = ""
            continue

        atual = str(mapping_final.get(coluna_modelo, "") or "").strip()
        if atual in df_base.columns and not _eh_coluna_video(atual):
            continue

        destino = _destino_modelo_semantico(coluna_modelo)
        if not destino:
            continue

        candidatos = []
        for coluna_origem in colunas_origem:
            if coluna_origem in usados:
                continue
            if _eh_coluna_video(coluna_origem):
                continue

            score = _score_coluna_para_destino(coluna_origem, df_base[coluna_origem], destino)
            if inferencias_origem.get(coluna_origem) == destino:
                score += 6

            if score > 0:
                candidatos.append((score, coluna_origem))

        candidatos.sort(key=lambda x: x[0], reverse=True)
        if candidatos:
            melhor = candidatos[0][1]
            mapping_final[coluna_modelo] = melhor
            usados.add(melhor)

    for coluna_modelo in [str(c) for c in df_modelo.columns.tolist()]:
        if _eh_coluna_video(coluna_modelo):
            mapping_final[coluna_modelo] = ""

    return mapping_final


def _limpar_mapeamento_por_status(
    df_base: pd.DataFrame,
    df_modelo: pd.DataFrame,
    mapping_atual: dict[str, str],
    operacao: str,
    modo: str = "erros_revisar",
) -> dict[str, str]:
    novo_mapping = dict(mapping_atual or {})
    bloqueados = _campos_bloqueados_automaticos(df_modelo, operacao)

    for coluna_modelo in [str(c) for c in df_modelo.columns.tolist()]:
        if coluna_modelo in bloqueados:
            continue

        if _eh_coluna_video(coluna_modelo):
            novo_mapping[coluna_modelo] = ""
            continue

        if modo == "tudo":
            novo_mapping[coluna_modelo] = ""
            continue

        from bling_app_zero.ui.origem_mapeamento_confidence import _detalhe_confianca_mapeamento

        detalhe = _detalhe_confianca_mapeamento(
            df_base=df_base,
            coluna_modelo=coluna_modelo,
            coluna_origem=str(novo_mapping.get(coluna_modelo, "") or "").strip(),
        )

        if detalhe.get("status") in {"erro", "revisar"}:
            novo_mapping[coluna_modelo] = ""

    for coluna_modelo in [str(c) for c in df_modelo.columns.tolist()]:
        if _eh_coluna_video(coluna_modelo):
            novo_mapping[coluna_modelo] = ""

    return novo_mapping


def _limpar_valores_preview(df: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame):
        return pd.DataFrame()

    base = df.copy().fillna("")
    for col in base.columns:
        base[col] = (
            base[col]
            .astype(str)
            .replace({valor: "" for valor in ANTI_LIXO_VALORES})
            .replace(r"(?i)^entrando\.{0,3}$", "", regex=True)
            .replace(r"(?i)^loading\.{0,3}$", "", regex=True)
            .replace(r"(?i)^carregando\.{0,3}$", "", regex=True)
        )
    return base.fillna("")


def _aplicar_defaults_pos_mapping(
    saida: pd.DataFrame,
    df_modelo: pd.DataFrame,
    operacao: str,
) -> pd.DataFrame:
    base = _limpar_valores_preview(saida.copy())

    coluna_preco = _coluna_preco_prioritaria(df_modelo, operacao)
    if coluna_preco and "_preco_calculado" in st.session_state.get(
        "df_precificado",
        pd.DataFrame(),
    ).columns:
        df_precificado = st.session_state.get("df_precificado")
        if safe_df_dados(df_precificado):
            base[coluna_preco] = df_precificado["_preco_calculado"]

    if operacao == "estoque":
        deposito = _obter_deposito_nome_persistido()
        if deposito:
            colunas_deposito = _colunas_deposito_modelo(df_modelo)
            if not colunas_deposito:
                colunas_deposito = [
                    str(col)
                    for col in base.columns
                    if "deposito" in _normalizar_texto_busca(col)
                    or "depósito" in _normalizar_texto_busca(col)
                ]

            for coluna_deposito in colunas_deposito:
                if coluna_deposito in base.columns:
                    base[coluna_deposito] = deposito

            if colunas_deposito:
                log_debug(
                    f"Depósito aplicado automaticamente nas colunas: {', '.join(colunas_deposito)} | valor={deposito}",
                    nivel="INFO",
                )
            else:
                log_debug(
                    "Operação de estoque detectada, mas nenhuma coluna de depósito foi encontrada no modelo/saída.",
                    nivel="ERRO",
                )
        else:
            log_debug("Operação de estoque sem depósito preenchido no session_state.", nivel="ERRO")

    coluna_situacao = _coluna_situacao_modelo(df_modelo)
    if coluna_situacao and coluna_situacao in base.columns:
        serie = base[coluna_situacao].astype(str).str.strip()
        base.loc[serie.eq(""), coluna_situacao] = "Ativo"

    coluna_imagens = _coluna_imagens_modelo(df_modelo)
    if coluna_imagens and coluna_imagens in base.columns:
        base[coluna_imagens] = base[coluna_imagens].apply(normalizar_imagens_pipe)

    for coluna in [str(c) for c in base.columns.tolist()]:
        if _eh_coluna_video(coluna):
            base[coluna] = ""

    return base.fillna("")


def _aplicar_mapping(
    df_base: pd.DataFrame,
    df_modelo: pd.DataFrame,
    mapping: dict[str, str],
) -> pd.DataFrame:
    operacao = _detectar_operacao()
    saida = pd.DataFrame(index=df_base.index)

    for coluna_modelo in df_modelo.columns:
        coluna_modelo = str(coluna_modelo)
        coluna_origem = str(mapping.get(coluna_modelo, "") or "").strip()

        if _eh_coluna_video(coluna_modelo):
            saida[coluna_modelo] = ""
            continue

        if coluna_origem and coluna_origem in df_base.columns and not _eh_coluna_video(coluna_origem):
            saida[coluna_modelo] = df_base[coluna_origem]
        else:
            saida[coluna_modelo] = ""

    saida = _aplicar_defaults_pos_mapping(saida, df_modelo, operacao)

    tipo_operacao_bling = normalizar_texto(st.session_state.get("tipo_operacao_bling", operacao)) or operacao
    deposito_nome = _obter_deposito_nome_persistido()

    saida = blindar_df_para_bling(
        df=saida,
        tipo_operacao_bling=tipo_operacao_bling,
        deposito_nome=deposito_nome,
    )

    for coluna in [str(c) for c in saida.columns.tolist()]:
        if _eh_coluna_video(coluna):
            saida[coluna] = ""

    return _limpar_valores_preview(saida.fillna(""))


def _preview_mapping(df_final: pd.DataFrame) -> None:
    if not safe_df_estrutura(df_final):
        return

    st.markdown("### Preview do resultado mapeado")

    preview = _limpar_valores_preview(df_final)

    if preview.empty:
        st.dataframe(pd.DataFrame(columns=preview.columns), use_container_width=True)
    else:
        st.dataframe(preview.head(40), use_container_width=True)

    with st.expander("Ver preview ampliado", expanded=False):
        st.dataframe(preview.head(150), use_container_width=True)


def _render_status_base(df_base: pd.DataFrame, df_modelo: pd.DataFrame) -> None:
    c1, c2, c3 = st.columns(3)

    with c1:
        st.metric("Linhas base", len(df_base.index) if isinstance(df_base, pd.DataFrame) else 0)

    with c2:
        st.metric("Colunas origem", len(df_base.columns) if isinstance(df_base, pd.DataFrame) else 0)

    with c3:
        st.metric("Colunas modelo", len(df_modelo.columns) if isinstance(df_modelo, pd.DataFrame) else 0)


def _executar_ia_autonoma(df_base: pd.DataFrame, df_modelo: pd.DataFrame, operacao: str) -> None:
    if st.session_state.get("_ia_auto_mapping_executado", False):
        return

    pacote = construir_pacote_agente_para_ui(
        df_base=df_base,
        df_modelo=df_modelo,
        operacao=operacao,
    )

    mapping_recebido = pacote.get("mapping", {}) if isinstance(pacote, dict) else {}
    if not isinstance(mapping_recebido, dict):
        mapping_recebido = {}

    mapping_final = _resetar_mapping_para_modelo(df_modelo)

    for coluna_modelo in df_modelo.columns:
        coluna_modelo = str(coluna_modelo)
        valor = str(mapping_recebido.get(coluna_modelo, "") or "").strip()

        if _eh_coluna_video(coluna_modelo):
            mapping_final[coluna_modelo] = ""
            continue

        if valor in df_base.columns and not _eh_coluna_video(valor):
            mapping_final[coluna_modelo] = valor

    mapping_final = _mapping_semantico(df_base, df_modelo, mapping_final)

    for coluna_modelo in [str(c) for c in df_modelo.columns.tolist()]:
        if _eh_coluna_video(coluna_modelo):
            mapping_final[coluna_modelo] = ""

    st.session_state["mapping_manual"] = mapping_final
    st.session_state["mapping_sugerido"] = mapping_recebido
    st.session_state["agent_ui_package"] = pacote
    st.session_state["df_final"] = _aplicar_mapping(df_base, df_modelo, mapping_final)
    st.session_state["_ia_auto_mapping_executado"] = True

    log_debug("IA aplicou mapeamento automático completo com reforço semântico.", nivel="INFO")
