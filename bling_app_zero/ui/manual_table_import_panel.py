from __future__ import annotations

import re
from io import BytesIO

import pandas as pd
import streamlit as st
from bs4 import BeautifulSoup

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.ui.html_capture_helper import render_html_capture_helper
from bling_app_zero.ui.site_outputs import render_site_source_summary, save_site_source

RESPONSIBLE_FILE = 'bling_app_zero/ui/manual_table_import_panel.py'
PRICE_RE = re.compile(r'(?:R\$\s*)?\d{1,3}(?:\.\d{3})*,\d{2}|(?:R\$\s*)?\d+\.\d{2}')
SKU_RE = re.compile(r'\b(?:SKU|C[ÓO]D(?:IGO)?|REF(?:ER[ÊE]NCIA)?|ID)\s*[:#-]?\s*([A-Za-z0-9._/-]{2,})', re.IGNORECASE)
GTIN_RE = re.compile(r'\b(\d{8}|\d{12}|\d{13}|\d{14})\b')
STOCK_RE = re.compile(r'\b(?:estoque|saldo|qtd|quantidade)\s*[:#-]?\s*(-?\d+(?:[,.]\d+)?)', re.IGNORECASE)


def _clean(value: object) -> str:
    return ' '.join(str(value or '').replace('\xa0', ' ').split()).strip()


def _read_spreadsheet(file_bytes: bytes, file_name: str) -> pd.DataFrame:
    buffer = BytesIO(file_bytes)
    name = str(file_name or '').lower()
    if name.endswith('.csv'):
        try:
            return pd.read_csv(buffer, sep=';', dtype=str).fillna('')
        except Exception:
            buffer.seek(0)
            return pd.read_csv(buffer, dtype=str).fillna('')
    return pd.read_excel(buffer, dtype=str).fillna('')


def _extract_tables(soup: BeautifulSoup) -> list[pd.DataFrame]:
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
        frame = pd.DataFrame(rows[1:], columns=columns).fillna('')
        if not frame.empty:
            frames.append(frame)
    return frames


def _extract_plain_tabular(text: str) -> pd.DataFrame:
    plain_rows = []
    for line in str(text or '').splitlines():
        if '\t' in line:
            plain_rows.append([_clean(part) for part in line.split('\t')])
    if len(plain_rows) < 2:
        return pd.DataFrame()
    width = max(len(row) for row in plain_rows)
    plain_rows = [row + [''] * (width - len(row)) for row in plain_rows]
    columns = [_clean(value) or f'Coluna {idx + 1}' for idx, value in enumerate(plain_rows[0])]
    return pd.DataFrame(plain_rows[1:], columns=columns).fillna('').astype(str)


def _node_image(node) -> str:
    image = node.find('img')
    if not image:
        return ''
    return _clean(image.get('src') or image.get('data-src') or image.get('data-original') or '')


def _node_link(node) -> str:
    link = node.find('a')
    if not link:
        return ''
    return _clean(link.get('href') or '')


def _extract_cards(soup: BeautifulSoup) -> pd.DataFrame:
    selectors = [
        '[class*=produto]',
        '[class*=product]',
        '[class*=item]',
        '[class*=card]',
        '[data-product]',
        '[data-produto]',
        '[data-sku]',
        '[data-id]',
    ]
    rows: list[dict[str, str]] = []
    seen_nodes: set[int] = set()
    seen_texts: set[str] = set()

    for selector in selectors:
        for node in soup.select(selector):
            node_id = id(node)
            if node_id in seen_nodes:
                continue
            seen_nodes.add(node_id)

            text = _clean(node.get_text(' ', strip=True))
            if len(text) < 8 or text in seen_texts:
                continue
            seen_texts.add(text)

            price_match = PRICE_RE.search(text)
            sku_match = SKU_RE.search(text)
            gtin_match = GTIN_RE.search(text)
            stock_match = STOCK_RE.search(text)
            has_signal = bool(price_match or sku_match or stock_match or gtin_match)
            has_word = any(token in text.lower() for token in ('produto', 'preço', 'preco', 'estoque', 'sku', 'cód', 'codigo', 'ref'))
            if not has_signal and not has_word:
                continue

            name = text
            if price_match:
                name = _clean(text[:price_match.start()]) or text
            if len(name) > 260:
                name = name[:260]

            rows.append(
                {
                    'Descrição': name,
                    'Preço': price_match.group(0) if price_match else '',
                    'Código/SKU': sku_match.group(1) if sku_match else _clean(node.get('data-sku') or node.get('data-id') or ''),
                    'GTIN/EAN': gtin_match.group(1) if gtin_match else '',
                    'Estoque': stock_match.group(1) if stock_match else '',
                    'Imagem URL': _node_image(node),
                    'URL': _node_link(node),
                    'Texto capturado': text[:900],
                }
            )

    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).fillna('').astype(str)


def _html_to_table(text: str) -> pd.DataFrame:
    soup = BeautifulSoup(text or '', 'html.parser')
    frames = _extract_tables(soup)
    if frames:
        frames.sort(key=lambda df: len(df) * max(1, len(df.columns)), reverse=True)
        return frames[0].fillna('').astype(str)

    plain = _extract_plain_tabular(text)
    if isinstance(plain, pd.DataFrame) and not plain.empty:
        return plain

    cards = _extract_cards(soup)
    if isinstance(cards, pd.DataFrame) and not cards.empty:
        return cards

    return pd.DataFrame()


def _store_manual_source(
    df: pd.DataFrame,
    *,
    operation: str,
    raw_label: str,
    requested_columns: list[str] | None,
    df_modelo_cadastro: pd.DataFrame | None,
    df_modelo_estoque: pd.DataFrame | None,
    df_modelo: pd.DataFrame | None,
) -> None:
    operation = 'estoque' if str(operation).lower() == 'estoque' else 'cadastro'
    clean_df = df.copy().fillna('').astype(str) if isinstance(df, pd.DataFrame) else pd.DataFrame()
    if clean_df.empty:
        st.warning('Não encontrei uma tabela ou blocos de produtos no conteúdo enviado.')
        return

    st.session_state[f'df_site_bruto_{operation}'] = clean_df
    st.session_state['df_site_bruto'] = clean_df
    save_site_source(
        df_site=clean_df,
        raw_urls=raw_label,
        requested_columns=requested_columns,
        df_modelo_cadastro=df_modelo_cadastro,
        df_modelo_estoque=df_modelo_estoque,
        df_modelo=df_modelo,
        operation=operation,
    )
    add_audit_event(
        'manual_supplier_table_imported',
        area='SITE',
        status='OK',
        details={
            'operation': operation,
            'rows': len(clean_df),
            'columns': len(clean_df.columns),
            'raw_label': raw_label,
            'responsible_file': RESPONSIBLE_FILE,
        },
    )
    st.success(f'Origem criada com {len(clean_df)} linha(s) e {len(clean_df.columns)} coluna(s).')


def render_manual_table_import_panel(
    *,
    operation: str,
    requested_columns: list[str] | None = None,
    df_modelo_cadastro: pd.DataFrame | None = None,
    df_modelo_estoque: pd.DataFrame | None = None,
    df_modelo: pd.DataFrame | None = None,
) -> None:
    operation = 'estoque' if str(operation).lower() == 'estoque' else 'cadastro'
    st.markdown('###### Importar tabela do fornecedor')
    st.caption('Use quando você já abriu o fornecedor e consegue exportar, salvar ou copiar a lista de produtos.')

    with st.expander('🧲 Capturador de HTML da página aberta', expanded=False):
        render_html_capture_helper()

    uploaded = st.file_uploader(
        'Enviar HTML/CSV/XLSX exportado do fornecedor',
        type=['html', 'htm', 'csv', 'xlsx', 'xls', 'xlsm', 'xlsb'],
        key=f'manual_supplier_table_upload_{operation}',
    )
    pasted = st.text_area(
        'Ou cole aqui a tabela/HTML copiado',
        placeholder='Cole uma tabela, HTML da página ou blocos de produto copiados da página do fornecedor.',
        height=120,
        key=f'manual_supplier_table_pasted_{operation}',
    )

    if st.button('📥 Importar tabela para o fluxo', use_container_width=True, key=f'manual_supplier_table_import_{operation}'):
        if uploaded is not None:
            name = getattr(uploaded, 'name', 'fornecedor.html')
            file_bytes = uploaded.getvalue()
            if str(name).lower().endswith(('.csv', '.xlsx', '.xls', '.xlsm', '.xlsb')):
                df = _read_spreadsheet(file_bytes, name)
            else:
                df = _html_to_table(file_bytes.decode('utf-8', errors='ignore'))
            raw_label = f'tabela_fornecedor:{name}'
        elif pasted.strip():
            df = _html_to_table(pasted)
            raw_label = 'tabela_fornecedor:conteudo_colado'
        else:
            st.warning('Envie um arquivo ou cole uma tabela antes de importar.')
            return

        _store_manual_source(
            df,
            operation=operation,
            raw_label=raw_label,
            requested_columns=requested_columns,
            df_modelo_cadastro=df_modelo_cadastro,
            df_modelo_estoque=df_modelo_estoque,
            df_modelo=df_modelo,
        )

    df_current = st.session_state.get(f'df_site_bruto_{operation}')
    if isinstance(df_current, pd.DataFrame) and not df_current.empty:
        render_site_source_summary(df_current, operation, show_history=False)


__all__ = ['render_manual_table_import_panel']
