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

    def seek(self, *_args: Any, **_kwargs: Any) -> None:
        return None

    def tell(self) -> int:
        return 0


_DEF_PASTE_HINT = "Se o Android deixar o arquivo cinza/não clicável, abra o arquivo, copie o conteúdo e cole aqui."


def _render_uploaded_feedback(uploaded: Any) -> None:
    name = str(getattr(uploaded, "name", "arquivo"))
    size = int(getattr(uploaded, "size", 0) or 0)
    size_mb = size / (1024 * 1024) if size else 0
    st.success(f"Arquivo anexado: {name}")
    if size:
        st.caption(f"Tamanho: {size_mb:.2f} MB")


def _render_paste_fallback(*, key: str) -> PastedUpload | None:
    with st.expander("📋 Arquivo ainda não clicou? Colar conteúdo manualmente", expanded=False):
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
    """Renderiza anexo estilo clipe com dois modos para celular.

    No Android, alguns gerenciadores deixam CSV cinza quando o navegador envia
    filtros de extensão/MIME. Por isso o primeiro botão é livre, sem filtro. O
    segundo botão é um fallback com extensões explícitas para casos em que o
    navegador exige filtro.
    """

    st.markdown(f"#### 📎 {label}")
    st.caption(f"Anexe qualquer arquivo tabular comum: {SUPPORTED_LABEL}.")

    uploaded_free = st.file_uploader(
        "📎 Anexar arquivo — modo livre para Android",
        type=None,
        key=f"{key}_free",
        help=help_text or "Escolha o arquivo. Este modo não filtra extensão e costuma funcionar melhor no Android.",
        label_visibility="visible",
    )

    if uploaded_free is not None:
        _render_uploaded_feedback(uploaded_free)
        return uploaded_free

    with st.expander("⚙️ Não apareceu? Tentar modo compatibilidade", expanded=False):
        uploaded_filtered = st.file_uploader(
            "📎 Anexar com filtro de compatibilidade",
            type=SUPPORTED_EXTENSIONS,
            key=f"{key}_filtered",
            help="Use este segundo botão se o primeiro não abrir corretamente no seu celular.",
            label_visibility="visible",
        )
        if uploaded_filtered is not None:
            _render_uploaded_feedback(uploaded_filtered)
            return uploaded_filtered

    return _render_paste_fallback(key=key)
