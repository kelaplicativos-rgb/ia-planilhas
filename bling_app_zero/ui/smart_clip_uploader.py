from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import streamlit as st


SUPPORTED_EXTENSIONS = [
    "csv",
    "txt",
    "tsv",
    "tab",
    "xlsx",
    "xlsm",
    "xls",
    "xlsb",
    "ods",
    "html",
    "htm",
    "json",
    "xml",
]

SUPPORTED_LABEL = "Excel, CSV, TXT, TSV, ODS, HTML, JSON ou XML"


@dataclass
class PastedUpload:
    name: str
    content: str

    @property
    def size(self) -> int:
        return len(self.getvalue())

    def getvalue(self) -> bytes:
        return self.content.encode("utf-8-sig")

    def read(self) -> bytes:
        return self.getvalue()


_DEF_PASTE_HINT = "Se o Android deixar o arquivo cinza/não clicável, abra o arquivo, copie o conteúdo e cole aqui."


def _render_paste_fallback(*, key: str) -> PastedUpload | None:
    with st.expander("📋 Arquivo não ficou clicável? Colar conteúdo manualmente", expanded=False):
        st.caption(_DEF_PASTE_HINT)
        pasted_name = st.text_input(
            "Nome do arquivo colado",
            value="arquivo_colado.csv",
            key=f"{key}_pasted_name",
            help="Use .csv ou .txt no final para o sistema reconhecer como tabela.",
        )
        pasted = st.text_area(
            "Cole aqui o conteúdo do CSV/TXT/TSV",
            key=f"{key}_pasted_content",
            height=180,
            placeholder="Ex.: codigo;descricao;preco\n001;Produto teste;10,90",
        )
        if pasted.strip():
            st.success("Conteúdo colado detectado. Vou processar como arquivo anexado.")
            return PastedUpload(name=pasted_name or "arquivo_colado.csv", content=pasted)
    return None


def render_smart_clip_uploader(
    *,
    label: str,
    key: str,
    help_text: str | None = None,
) -> Any | None:
    """Renderiza um anexo estilo clipe com reforço para Android.

    Alguns seletores de arquivo no Android deixam CSV/TXT cinza quando o accept
    do navegador vem genérico. Por isso usamos uma lista explícita de extensões
    e também oferecemos fallback por colagem do conteúdo.
    """

    st.markdown(f"#### 📎 {label}")
    st.caption(f"Anexe qualquer arquivo tabular comum: {SUPPORTED_LABEL}.")

    uploaded = st.file_uploader(
        "📎 Tocar para anexar arquivo",
        type=SUPPORTED_EXTENSIONS,
        key=key,
        help=help_text or "Escolha o arquivo. O sistema tentará reconhecer automaticamente o formato.",
        label_visibility="visible",
    )

    if uploaded is not None:
        name = str(getattr(uploaded, "name", "arquivo"))
        size = int(getattr(uploaded, "size", 0) or 0)
        size_mb = size / (1024 * 1024) if size else 0
        st.success(f"Arquivo anexado: {name}")
        if size:
            st.caption(f"Tamanho: {size_mb:.2f} MB")
        return uploaded

    return _render_paste_fallback(key=key)
