from __future__ import annotations

import re
from io import BytesIO, StringIO

import pandas as pd
import streamlit as st
from bs4 import BeautifulSoup

from bling_app_zero.flows.site_operation_router import run_site_engine
from bling_app_zero.ui.home_shared import load_site_pipeline
from bling_app_zero.v2.price_multistore.site_source import get_site_capture_source_df, source_origin_label, suggest_price_column
from bling_app_zero.v2.session_store import get_state, pop_state, set_state, widget_key

SOURCE_DF_KEY = 'multistore_source_origin_df'
SOURCE_LABEL_KEY = 'multistore_source_origin_label'
SOURCE_MODE_KEY = 'multistore_source_origin_mode'
SOURCE_USAGE_KEY = 'multistore_source_usage_mode'
SOURCE_SUGGESTED_PRICE_COLUMN_KEY = 'multistore_source_suggested_price_column'

USAGE_UPLOAD = 'Usar upload normal da Planilha 2'
USAGE_SITE = 'Usar captura/busca por site como Planilha 2'
USAGE_MANUAL = 'Usar tabela/exportação importada como Planilha 2'

PRICE_RE = re.compile(r'(?:R\$\s*)?\d{1,3}(?:\.\d{3})*,\d{2}|(?:R\$\s*)?\d+\.\d{2}')
SKU_RE = re.compile(r'\b(?:SKU|C[ÓO]D(?:IGO)?|REF(?:ER[ÊE]NCIA)?|ID)\s*[:#-]?\s*([A-Za-z0-9._/-]{2,})', re.IGNORECASE)
STOCK_RE = re.compile(r'\b(?:estoque|saldo|qtd|quantidade)\s*[:#-]?\s*(-?\d+(?:[,.]\d+)?)', re.IGNORECASE)


def _clean(value: object) -> str:
    return ' '.join(str(value or '').replace('\xa0', ' ').split()).strip()


def _decode(raw: bytes) -> str:
    for encoding in ('utf-8-sig', 'utf-8', 'cp1252', 'latin1'):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode('utf-8', errors='ignore')


def _read_table_file(raw: bytes, file_name: str) -> pd.DataFrame:
    name = str(file_name or '').lower()
    if name.endswith('.csv'):
        text = _decode(raw)
        sep = ';' if text.count(';') >= text.count(',') else ','
        if '\t' in text[:4096] and text.count('\t') > max(text.count(';'), text.count(',')):
            sep = '\t'
        return pd.read_csv(StringIO(text), sep=sep, dtype=str).fillna('')
    if name.endswith(('.xlsx', '.xls', '.xlsm', '.xlsb')):
        return pd.read_excel(BytesIO(raw), dtype=str).fillna('')
    return _html_to_df(_decode(raw))


def _table_frames(soup: BeautifulSoup) -> list[pd.DataFrame]:
    frames: list[pd.DataFrame] = []
    for table in soup.find_all('table'):
        rows: list[list[str]] = []
        for tr in table.find_all('tr'):
            cells = tr.find_all(['th', 'td'])
            row = [_clean(cell.get_text(' ', strip=True)) for cell in cells]
            if any(row):
                rows.append(row)
        if len(rows) < 2:
            continue
        width = max(len(row) for row in rows)
        rows = [row + [''] * (width - len(row)) for row in rows]
        columns = [_clean(value) or f'Coluna {idx + 1}' for idx, value in enumerate(rows[0])]
        frames.append(pd.DataFrame(rows[1:], columns=columns).fillna(''))
    return frames


def _plain_tabular(text: str) -> pd.DataFrame:
    rows: list[list[str]] = []
    for line in str(text or '').splitlines():
        if '\t' in line:
            rows.append([_clean(part) for part in line.split('\t')])
    if len(rows) < 2:
        return pd.DataFrame()
    width = max(len(row) for row in rows)
    rows = [row + [''] * (width - len(row)) for row in rows]
    columns = [_clean(value) or f'Coluna {idx + 1}' for idx, value in enumerate(rows[0])]
    return pd.DataFrame(rows[1:], columns=columns).fillna('')


def _cards_to_df(soup: BeautifulSoup) -> pd.DataFrame:
    selectors = ['[class*=produto]', '[class*=product]', '[class*=item]', '[class*=card]', '[data-product]', '[data-produto]', '[data-sku]', '[data-id]']
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for selector in selectors:
        for node in soup.select(selector):
            text = _clean(node.get_text(' ', strip=True))
            if len(text) < 8 or text in seen:
                continue
            seen.add(text)
            price = PRICE_RE.search(text)
            sku = SKU_RE.search(text)
            stock = STOCK_RE.search(text)
            if not (price or sku or stock or any(token in text.lower() for token in ('preço', 'preco', 'custo', 'produto', 'sku', 'estoque'))):
                continue
            img = node.find('img')
            link = node.find('a')
            name = _clean(text[:price.start()]) if price else text
            rows.append(
                {
                    'Descrição': name[:260],
                    'Preço de custo': price.group(0) if price else '',
                    'Código/SKU': sku.group(1) if sku else _clean(node.get('data-sku') or node.get('data-id') or ''),
                    'Estoque': stock.group(1) if stock else '',
                    'Imagem URL': _clean(img.get('src') or img.get('data-src') or '') if img else '',
                    'URL': _clean(link.get('href') or '') if link else '',
                    'Texto capturado': text[:900],
                }
            )
    return pd.DataFrame(rows).fillna('') if rows else pd.DataFrame()


def _html_to_df(text: str) -> pd.DataFrame:
    soup = BeautifulSoup(text or '', 'html.parser')
    frames = _table_frames(soup)
    if frames:
        frames.sort(key=lambda df: len(df) * max(1, len(df.columns)), reverse=True)
        return frames[0].fillna('').astype(str)
    plain = _plain_tabular(text)
    if isinstance(plain, pd.DataFrame) and not plain.empty:
        return plain.fillna('').astype(str)
    cards = _cards_to_df(soup)
    if isinstance(cards, pd.DataFrame) and not cards.empty:
        return cards.fillna('').astype(str)
    return pd.DataFrame()


def _store_source(df: pd.DataFrame, label: str, mode: str) -> None:
    clean = df.copy().fillna('').astype(str) if isinstance(df, pd.DataFrame) else pd.DataFrame()
    if clean.empty:
        st.warning('Não encontrei produtos/custos na origem informada.')
        return
    set_state(SOURCE_DF_KEY, clean)
    set_state(SOURCE_LABEL_KEY, label)
    set_state(SOURCE_MODE_KEY, mode)
    suggested = suggest_price_column(clean)
    if suggested:
        set_state(SOURCE_SUGGESTED_PRICE_COLUMN_KEY, suggested)
    st.success(f'Origem complementar criada: {len(clean)} linha(s) × {len(clean.columns)} coluna(s).')


def get_multistore_source_origin_df() -> pd.DataFrame | None:
    df = get_state(SOURCE_DF_KEY)
    if isinstance(df, pd.DataFrame) and not df.empty:
        return df.copy().fillna('')
    return None


def get_multistore_source_usage_mode() -> str:
    mode = str(get_state(SOURCE_USAGE_KEY) or USAGE_UPLOAD)
    if mode not in {USAGE_UPLOAD, USAGE_SITE, USAGE_MANUAL}:
        return USAGE_UPLOAD
    return mode


def should_use_multistore_complementary_source() -> bool:
    mode = get_multistore_source_usage_mode()
    return mode in {USAGE_SITE, USAGE_MANUAL}


def _render_saved_source() -> None:
    df = get_multistore_source_origin_df()
    if not isinstance(df, pd.DataFrame) or df.empty:
        return
    label = str(get_state(SOURCE_LABEL_KEY) or 'origem complementar')
    mode = str(get_state(SOURCE_MODE_KEY) or '')
    suggested = str(get_state(SOURCE_SUGGESTED_PRICE_COLUMN_KEY) or '')
    st.success(f'Origem complementar disponível: {label}')
    if mode:
        st.caption(f'Modo: {mode}')
    if suggested:
        st.caption(f'Coluna provável de custo/preço: {suggested}')
    with st.expander(f'Preview da origem complementar · {len(df)} linha(s) × {len(df.columns)} coluna(s)', expanded=False):
        st.dataframe(df.head(30).fillna(''), use_container_width=True, height=220)
    if st.button('Limpar origem complementar', use_container_width=True, key=widget_key('clear_multistore_source_origin')):
        pop_state(SOURCE_DF_KEY, None)
        pop_state(SOURCE_LABEL_KEY, None)
        pop_state(SOURCE_MODE_KEY, None)
        pop_state(SOURCE_SUGGESTED_PRICE_COLUMN_KEY, None)
        set_state(SOURCE_USAGE_KEY, USAGE_UPLOAD)
        st.rerun()


def _render_existing_site_capture() -> None:
    df_capture, source_key = get_site_capture_source_df()
    if not isinstance(df_capture, pd.DataFrame) or df_capture.empty:
        st.caption('Nenhuma captura por site anterior foi encontrada nesta sessão. Você pode buscar pelos links abaixo.')
        return
    label = source_origin_label(source_key)
    st.info(f'Captura por site encontrada na sessão: {label} · {len(df_capture)} linha(s) × {len(df_capture.columns)} coluna(s).')
    with st.expander('Conferir captura por site encontrada', expanded=False):
        st.dataframe(df_capture.head(25).fillna(''), use_container_width=True, height=220)
    if st.button('Usar esta captura por site como Planilha 2', use_container_width=True, key=widget_key('use_existing_site_capture_as_multistore_source')):
        _store_source(df_capture, label, 'Captura por site existente')
        st.rerun()


def _render_public_site_capture() -> None:
    _render_existing_site_capture()
    st.divider()
    urls = st.text_area(
        'Links do fornecedor para buscar custo/preço',
        placeholder='https://site.com.br/categoria\nhttps://site.com.br/produto-1',
        height=110,
        key=widget_key('multistore_source_site_urls'),
    )
    if st.button('🌐 Buscar origem complementar no site', use_container_width=True, key=widget_key('multistore_source_site_fetch')):
        raw_urls = str(urls or '').strip()
        if not raw_urls:
            st.warning('Informe pelo menos um link do fornecedor.')
            return
        with st.spinner('Buscando origem complementar no site...'):
            df = run_site_engine(
                operation='cadastro',
                pipeline=load_site_pipeline(),
                raw_urls=raw_urls,
                requested_columns=None,
                all_products=True,
                max_pages=1000000,
                max_products=1000000,
                progress_callback=None,
            )
        _store_source(df, 'busca por site público', 'Busca por site público')


def _render_manual_import() -> None:
    st.caption('Use arquivo exportado do fornecedor, tabela copiada ou HTML salvo da página de produtos.')
    uploaded = st.file_uploader(
        'Enviar HTML/CSV/XLSX do fornecedor',
        type=['html', 'htm', 'csv', 'xlsx', 'xls', 'xlsm', 'xlsb'],
        key=widget_key('multistore_source_manual_upload'),
    )
    pasted = st.text_area(
        'Ou cole tabela/HTML copiado do fornecedor',
        placeholder='Cole a tabela copiada, HTML da página ou blocos de produtos.',
        height=110,
        key=widget_key('multistore_source_manual_paste'),
    )
    if st.button('📥 Importar origem complementar', use_container_width=True, key=widget_key('multistore_source_manual_import')):
        if uploaded is not None:
            name = getattr(uploaded, 'name', 'origem_fornecedor.html')
            df = _read_table_file(uploaded.getvalue(), name)
            _store_source(df, f'importação do fornecedor: {name}', 'Importação do fornecedor')
        elif pasted.strip():
            df = _html_to_df(pasted)
            _store_source(df, 'conteúdo colado do fornecedor', 'Conteúdo colado')
        else:
            st.warning('Envie um arquivo ou cole a tabela/HTML do fornecedor.')


def render_multistore_source_origin_panel() -> pd.DataFrame | None:
    with st.container(border=True):
        st.markdown('##### Origem complementar de custo/preço')
        st.caption('Use planilha, captura por site ou importação do fornecedor. Nenhuma origem substitui a outra automaticamente: você escolhe qual será usada como Planilha 2 no cálculo.')
        mode = st.radio(
            'Qual origem deseja usar como Planilha 2 neste cálculo?',
            [USAGE_UPLOAD, USAGE_SITE, USAGE_MANUAL],
            horizontal=False,
            key=widget_key(SOURCE_USAGE_KEY),
        )
        set_state(SOURCE_USAGE_KEY, mode)
        if mode == USAGE_SITE:
            _render_public_site_capture()
        elif mode == USAGE_MANUAL:
            _render_manual_import()
        else:
            st.caption('A Planilha 2 virá do upload normal abaixo. Você ainda pode manter uma captura por site salva para usar depois.')
        _render_saved_source()
    return get_multistore_source_origin_df()


__all__ = [
    'USAGE_MANUAL',
    'USAGE_SITE',
    'USAGE_UPLOAD',
    'get_multistore_source_origin_df',
    'get_multistore_source_usage_mode',
    'render_multistore_source_origin_panel',
    'should_use_multistore_complementary_source',
]
