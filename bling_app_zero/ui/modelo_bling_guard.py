from __future__ import annotations

"""Guarda para exigir modelo Bling antes do preview/mapeamento.

Regra de fluxo:
- Para cadastro de produtos por busca/captura via site, o Preview da origem só
  deve abrir após o modelo de cadastro do Bling estar anexado/carregado.
- O modelo é o reflexo das colunas finais; sem ele, o preview/mapeamento fica em
  contradição e pode gerar correspondências erradas.
"""

from typing import Iterable

import pandas as pd
import streamlit as st


CADASTRO_KEYS: tuple[str, ...] = (
    "df_modelo_cadastro",
    "modelo_cadastro",
    "df_template_cadastro",
    "template_cadastro",
    "df_bling_cadastro",
    "bling_modelo_cadastro",
    "modelo_bling_cadastro",
)

SITE_ORIGIN_KEYS: tuple[str, ...] = (
    "df_origem_site",
    "df_capturado_site",
    "df_site",
    "site_df",
)

CADASTRO_HINT_KEYS: tuple[str, ...] = (
    "tipo_operacao",
    "operacao",
    "modo_operacao",
    "tipo_fluxo",
    "fluxo_tipo",
    "tipo_importacao",
    "modelo_tipo",
)

ORIGEM_HINT_KEYS: tuple[str, ...] = (
    "origem_dados",
    "origem",
    "tipo_origem",
    "fonte_dados",
    "fonte",
)


def _is_valid_dataframe(value: object) -> bool:
    return isinstance(value, pd.DataFrame) and not value.empty


def _state_text(keys: Iterable[str]) -> str:
    values: list[str] = []
    for key in keys:
        value = st.session_state.get(key)
        if value is not None:
            values.append(str(value).lower())
    return " ".join(values)


def has_modelo_cadastro_bling() -> bool:
    """Retorna True se algum modelo de cadastro Bling estiver carregado."""
    for key in CADASTRO_KEYS:
        value = st.session_state.get(key)
        if _is_valid_dataframe(value):
            return True
        if value is not None and not isinstance(value, pd.DataFrame):
            # Alguns fluxos antigos salvam objeto/lista/arquivo em vez de DataFrame.
            return True
    return False


def is_site_origin_flow() -> bool:
    if any(_is_valid_dataframe(st.session_state.get(key)) for key in SITE_ORIGIN_KEYS):
        return True
    text = _state_text(ORIGEM_HINT_KEYS)
    return any(token in text for token in ("site", "url", "crawler", "flash", "scraper"))


def is_cadastro_flow() -> bool:
    text = _state_text(CADASTRO_HINT_KEYS)
    if any(token in text for token in ("cadastro", "produto", "produtos")):
        return True
    if any(token in text for token in ("estoque", "atualizacao", "atualização")):
        return False
    # Na dúvida, captura via site trabalha como cadastro de produto, não estoque.
    return is_site_origin_flow()


def requires_modelo_cadastro_for_preview() -> bool:
    return is_site_origin_flow() and is_cadastro_flow() and not has_modelo_cadastro_bling()


def render_modelo_cadastro_required_message() -> None:
    st.warning(
        "Antes do Preview da origem, anexe/carregue o modelo de cadastro do Bling. "
        "Esse modelo é o espelho das colunas finais e evita mapeamento automático errado."
    )
    st.info(
        "Fluxo correto: 1) Origem por site → 2) Modelo Bling de cadastro → "
        "3) Captura/preview da origem → 4) Mapeamento manual/conservador."
    )
