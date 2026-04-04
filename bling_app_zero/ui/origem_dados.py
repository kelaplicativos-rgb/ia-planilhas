from __future__ import annotations

from typing import Dict, List, Tuple

import pandas as pd
import streamlit as st


# =========================================================
# CONFIG
# =========================================================

CAMPOS_BLING: List[Dict[str, object]] = [
    {"key": "codigo", "label": "Código", "required_cadastro": True, "required_estoque": True},
    {"key": "nome", "label": "Nome", "required_cadastro": True, "required_estoque": False},
    {"key": "descricao_curta", "label": "Descrição curta", "required_cadastro": False, "required_estoque": False},
    {"key": "preco", "label": "Preço", "required_cadastro": False, "required_estoque": False},
    {"key": "preco_custo", "label": "Preço de custo", "required_cadastro": False, "required_estoque": False},
    {"key": "estoque", "label": "Estoque", "required_cadastro": False, "required_estoque": True},
    {"key": "gtin", "label": "GTIN / EAN", "required_cadastro": False, "required_estoque": False},
    {"key": "marca", "label": "Marca", "required_cadastro": False, "required_estoque": False},
    {"key": "categoria", "label": "Categoria", "required_cadastro": False, "required_estoque": False},
    {"key": "ncm", "label": "NCM", "required_cadastro": False, "required_estoque": False},
    {"key": "origem", "label": "Origem", "required_cadastro": False, "required_estoque": False},
    {"key": "unidade", "label": "Unidade", "required_cadastro": False, "required_estoque": False},
    {"key": "deposito_id", "label": "Depósito ID", "required_cadastro": False, "required_estoque": True},
]

OPCAO_NAO_MAPEAR = "— Não mapear —"


# =========================================================
# ESTADO
# =========================================================

def _init_local_state() -> None:
    defaults = {
        "df_origem": None,
        "mapeamento_manual": {},           # fornecedor_col -> campo_bling_key
        "preview_row_index": 0,
        "auto_map_applied": False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


# =========================================================
# UTIL
# =========================================================

def normalizar_df(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    df = df.fillna("")
    return df


def carregar_planilha(file) -> pd.DataFrame:
    nome = str(getattr(file, "name", "")).lower()

    try:
        if nome.endswith(".csv"):
            df = pd.read_csv(file, dtype=str)
        else:
            df = pd.read_excel(file, dtype=str, engine="openpyxl")
    except Exception:
        file.seek(0)
        try:
            df = pd.read_csv(file, dtype=str, sep=";")
        except Exception:
            file.seek(0)
            df = pd.read_excel(file, dtype=str, engine="openpyxl")

    return normalizar_df(df)


def _normalize_text(value: object) -> str:
    texto = str(value or "").strip().lower()
    substituicoes = {
        "ç": "c",
        "ã": "a",
        "á": "a",
        "à": "a",
        "â": "a",
        "é": "e",
        "ê": "e",
        "í": "i",
        "ó": "o",
        "ô": "o",
        "õ": "o",
        "ú": "u",
        "-": " ",
        "_": " ",
        "/": " ",
        ".": " ",
    }
    for antigo, novo in substituicoes.items():
        texto = texto.replace(antigo, novo)
    return " ".join(texto.split())


def _campo_meta(campo_key: str) -> Dict[str, object]:
    for item in CAMPOS_BLING:
        if item["key"] == campo_key:
            return item
    return {"key": campo_key, "label": campo_key, "required_cadastro": False, "required_estoque": False}


def _campos_disponiveis() -> List[Tuple[str, str]]:
    return [(str(c["key"]), str(c["label"])) for c in CAMPOS_BLING]


def _campos_obrigatorios_por_modo() -> set[str]:
    modo = st.session_state.get("modo_operacao", "Cadastro de produtos")
    if modo == "Atualização de estoque":
        return {str(c["key"]) for c in CAMPOS_BLING if bool(c.get("required_estoque"))}
    return {str(c["key"]) for c in CAMPOS_BLING if bool(c.get("required_cadastro"))}


def _status_campo_destino(campo_key: str, mapeamento: Dict[str, str]) -> str:
    obrigatorios = _campos_obrigatorios_por_modo()
    ja_usado = campo_key in set(mapeamento.values())
    if ja_usado:
        return "ok"
    if campo_key in obrigatorios:
        return "erro"
    return "pendente"


def _status_coluna_fornecedor(coluna: str, mapeamento: Dict[str, str]) -> str:
    destino = mapeamento.get(coluna)
    if destino:
        return "ok"
    return "pendente"


def _status_badge_html(status: str, texto: str) -> str:
    estilos = {
        "ok": ("#e8f7ee", "#1f7a3d", "🟢"),
        "pendente": ("#fff7db", "#9a6a00", "🟡"),
        "erro": ("#fdeaea", "#b42318", "🔴"),
    }
    bg, fg, emoji = estilos.get(status, estilos["pendente"])
    return (
        f"<span style='display:inline-block;padding:4px 10px;border-radius:999px;"
        f"background:{bg};color:{fg};font-size:12px;font-weight:700;'>"
        f"{emoji} {texto}</span>"
    )


def _valor_preview(row: pd.Series, coluna: str) -> str:
    if coluna not in row.index:
        return ""
    valor = str(row[coluna] if row[coluna] is not None else "").strip()
    return valor[:120] + ("..." if len(valor) > 120 else "")


def _sugerir_destino_para_coluna(coluna: str) -> str:
    nome = _normalize_text(coluna)

    regras = [
        (["codigo sku referencia cod ref"], "codigo"),
        (["nome titulo produto descricao nome produto"], "nome"),
        (["descricao curta desc curta descricao produto"], "descricao_curta"),
        (["preco venda valor venda preco"], "preco"),
        (["custo preco custo custo produto"], "preco_custo"),
        (["estoque qtd quantidade saldo"], "estoque"),
        (["ean gtin codigo barras cod barras"], "gtin"),
        (["marca fabricante"], "marca"),
        (["categoria departamento secao"], "categoria"),
        (["ncm"], "ncm"),
        (["origem"], "origem"),
        (["unidade und un med medida"], "unidade"),
        (["deposito deposito id id deposito"], "deposito_id"),
    ]

    for grupos, destino in regras:
        for grupo in grupos:
            for palavra in grupo.split():
                if palavra in nome:
                    return destino
    return ""


def _aplicar_sugestoes_iniciais(df: pd.DataFrame) -> None:
    if st.session_state.get("auto_map_applied"):
        return

    atual = dict(st.session_state.get("mapeamento_manual", {}))
    usados = set(atual.values())

    for coluna in df.columns:
        if coluna in atual:
            continue
        sugerido = _sugerir_destino_para_coluna(coluna)
        if sugerido and sugerido not in usados:
            atual[coluna] = sugerido
            usados.add(sugerido)

    st.session_state.mapeamento_manual = atual
    st.session_state.auto_map_applied = True


def _resumo_status(mapeamento: Dict[str, str]) -> Tuple[int, int, int]:
    obrigatorios = _campos_obrigatorios_por_modo()
    usados = set(mapeamento.values())

    ok = len(usados)
    faltando_obrigatorio = sum(1 for c in obrigatorios if c not in usados)
    pendente = max(len(CAMPOS_BLING) - ok - faltando_obrigatorio, 0)
    return ok, pendente, faltando_obrigatorio


# =========================================================
# CSS
# =========================================================

def _inject_css() -> None:
    st.markdown(
        """
        <style>
        .mm-wrap {
            border: 1px solid rgba(120, 120, 120, 0.18);
            border-radius: 16px;
            padding: 14px;
            background: rgba(255, 255, 255, 0.02);
            margin-bottom: 12px;
        }
        .mm-title {
            font-size: 14px;
            font-weight: 700;
            margin-bottom: 6px;
            line-height: 1.2;
        }
        .mm-sub {
            font-size: 12px;
            color: #666;
            margin-bottom: 8px;
        }
        .mm-value {
            background: rgba(120, 120, 120, 0.08);
            border-radius: 10px;
            padding: 8px 10px;
            font-size: 12px;
            min-height: 56px;
            margin: 8px 0 10px 0;
            overflow-wrap: anywhere;
        }
        .mm-legend {
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
            margin: 8px 0 14px 0;
        }
        .mm-note {
            font-size: 12px;
            color: #666;
        }
        .mm-section-title {
            font-size: 18px;
            font-weight: 700;
            margin: 12px 0 6px 0;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# =========================================================
# PREVIEW
# =========================================================

def _get_preview_df(df: pd.DataFrame, limite: int = 20) -> pd.DataFrame:
    preview = df.head(limite).copy()
    preview.insert(0, "Linha", range(1, len(preview) + 1))
    return preview


def _render_preview_selecionavel(df: pd.DataFrame) -> int:
    st.markdown("<div class='mm-section-title'>Preview da planilha</div>", unsafe_allow_html=True)
    st.caption("Clique em uma linha do preview para carregar os valores daquela linha no painel de mapeamento.")

    preview_df = _get_preview_df(df, limite=20)

    try:
        event = st.dataframe(
            preview_df,
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
            key="preview_dataframe_select",
            row_height=38,
        )

        selecionadas = []
        if hasattr(event, "selection"):
            selecionadas = list(getattr(event.selection, "rows", []) or [])
        elif isinstance(event, dict):
            selecionadas = list(event.get("selection", {}).get("rows", []) or [])

        if selecionadas:
            st.session_state.preview_row_index = int(selecionadas[0])

    except TypeError:
        st.dataframe(preview_df, use_container_width=True, hide_index=True)
        max_idx = max(len(df) - 1, 0)
        st.session_state.preview_row_index = int(
            st.number_input(
                "Linha para inspecionar",
                min_value=0,
                max_value=max_idx,
                value=min(int(st.session_state.get("preview_row_index", 0)), max_idx),
                step=1,
            )
        )

    idx = int(st.session_state.get("preview_row_index", 0))
    idx = max(0, min(idx, len(df) - 1))
    st.session_state.preview_row_index = idx
    return idx


# =========================================================
# MAPEAMENTO
# =========================================================

def _render_resumo_mapeamento(mapeamento: Dict[str, str]) -> None:
    ok, pendente, erro = _resumo_status(mapeamento)
    total = len(CAMPOS_BLING)
    progresso = ok / total if total else 0

    c1, c2, c3, c4 = st.columns([1, 1, 1, 2])
    c1.metric("Mapeados", ok)
    c2.metric("Pendentes", pendente)
    c3.metric("Obrigatórios faltando", erro)
    c4.progress(progresso, text=f"{ok}/{total} campos Bling relacionados")

    st.markdown(
        "<div class='mm-legend'>"
        f"{_status_badge_html('ok', 'Mapeado')}"
        f"{_status_badge_html('pendente', 'Pendente')}"
        f"{_status_badge_html('erro', 'Obrigatório faltando')}"
        "</div>",
        unsafe_allow_html=True,
    )


def _render_status_destinos(mapeamento: Dict[str, str]) -> None:
    st.markdown("<div class='mm-section-title'>Status dos campos do Bling</div>", unsafe_allow_html=True)

    cols = st.columns(4)
    for i, campo in enumerate(CAMPOS_BLING):
        key = str(campo["key"])
        label = str(campo["label"])
        status = _status_campo_destino(key, mapeamento)
        obrigatorio = key in _campos_obrigatorios_por_modo()

        with cols[i % 4]:
            st.markdown(
                (
                    "<div class='mm-wrap'>"
                    f"<div class='mm-title'>{label}</div>"
                    f"<div class='mm-sub'>{'Obrigatório' if obrigatorio else 'Opcional'}</div>"
                    f"{_status_badge_html(status, 'Relacionado' if status == 'ok' else ('Sem vínculo' if status == 'erro' else 'Disponível'))}"
                    "</div>"
                ),
                unsafe_allow_html=True,
            )


def _render_card_coluna(
    coluna: str,
    valor_exemplo: str,
    mapeamento: Dict[str, str],
    indice: int,
) -> None:
    destino_atual = mapeamento.get(coluna, "")
    usados_por_outras = {v for k, v in mapeamento.items() if k != coluna and v}

    opcoes = [OPCAO_NAO_MAPEAR]
    labels_por_valor = {OPCAO_NAO_MAPEAR: OPCAO_NAO_MAPEAR}

    for key, label in _campos_disponiveis():
        if key not in usados_por_outras or key == destino_atual:
            opcoes.append(key)
            labels_por_valor[key] = label

    status = _status_coluna_fornecedor(coluna, mapeamento)
    badge_texto = "Mapeada" if status == "ok" else "Sem vínculo"

    st.markdown(
        (
            "<div class='mm-wrap'>"
            f"<div class='mm-title'>{coluna}</div>"
            f"<div class='mm-sub'>Coluna do fornecedor</div>"
            f"{_status_badge_html(status, badge_texto)}"
            f"<div class='mm-value'>{valor_exemplo or '— vazio —'}</div>"
            "</div>"
        ),
        unsafe_allow_html=True,
    )

    selecionado = st.selectbox(
        "Relacionar com campo do Bling",
        options=opcoes,
        index=opcoes.index(destino_atual) if destino_atual in opcoes else 0,
        key=f"map_fornecedor_{indice}_{coluna}",
        format_func=lambda x: labels_por_valor.get(x, x),
    )

    if selecionado == OPCAO_NAO_MAPEAR:
        mapeamento.pop(coluna, None)
    else:
        mapeamento[coluna] = selecionado


def render_mapeamento(df: pd.DataFrame, row_idx: int) -> None:
    st.markdown("<div class='mm-section-title'>Relacionamento visual</div>", unsafe_allow_html=True)
    st.caption("A linha clicada no preview aparece abaixo. Cada cartão representa uma coluna da planilha do fornecedor.")

    mapeamento = dict(st.session_state.get("mapeamento_manual", {}))
    linha = df.iloc[row_idx]

    _render_resumo_mapeamento(mapeamento)
    _render_status_destinos(mapeamento)

    st.markdown("<div class='mm-section-title'>Colunas da linha selecionada</div>", unsafe_allow_html=True)
    st.markdown(
        "<div class='mm-note'>Clique no select de cada cartão para escolher o campo correspondente do Bling. "
        "Um mesmo campo do Bling não pode ser usado duas vezes.</div>",
        unsafe_allow_html=True,
    )

    colunas_visuais = st.columns(4)
    for i, coluna in enumerate(df.columns):
        with colunas_visuais[i % 4]:
            _render_card_coluna(
                coluna=coluna,
                valor_exemplo=_valor_preview(linha, coluna),
                mapeamento=mapeamento,
                indice=i,
            )

    st.session_state.mapeamento_manual = mapeamento

    with st.expander("Ver mapeamento salvo", expanded=False):
        st.json(mapeamento)


# =========================================================
# MAIN
# =========================================================

def render_origem_dados() -> None:
    _init_local_state()
    _inject_css()

    st.subheader("Origem de Dados")

    arquivo = st.file_uploader(
        "Anexar planilha",
        type=["xlsx", "xls", "csv"],
        help="Envie a planilha do fornecedor para visualizar, clicar em uma linha e fazer o relacionamento visual com os campos do Bling.",
    )

    if not arquivo:
        st.info("Envie uma planilha para iniciar o preview e o relacionamento visual.")
        return

    df = carregar_planilha(arquivo)
    st.session_state.df_origem = df

    if df.empty:
        st.warning("A planilha foi carregada, mas não possui linhas.")
        return

    _aplicar_sugestoes_iniciais(df)

    st.success(f"✅ Planilha carregada: {df.shape[0]} linhas x {df.shape[1]} colunas")

    row_idx = _render_preview_selecionavel(df)

    st.caption(
        f"Linha ativa para inspeção: **{row_idx + 1}** de **{len(df)}**. "
        "Se a sua versão do Streamlit não permitir clique na linha, o app usa seleção manual por número."
    )

    render_mapeamento(df, row_idx)
