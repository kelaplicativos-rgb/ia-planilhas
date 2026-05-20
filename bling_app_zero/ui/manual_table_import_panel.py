from __future__ import annotations

import re
from io import BytesIO

import pandas as pd
import streamlit as st
from bs4 import BeautifulSoup

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.origin_recovery import recover_from_file, recover_from_plain_text
from bling_app_zero.ui.html_capture_helper import render_html_capture_helper
from bling_app_zero.ui.site_outputs import render_site_source_summary, save_site_source

RESPONSIBLE_FILE = 'bling_app_zero/ui/manual_table_import_panel.py'
UNIVERSAL_OPERATION = 'universal'
PRICE_RE = re.compile(r'(?:R\$\s*)?\d{1,3}(?:\.\d{3})*,\d{2}|(?:R\$\s*)?\d+\.\d{2}')
SKU_RE = re.compile(r'\b(?:SKU|C[ÓO]D(?:IGO)?|REF(?:ER[ÊE]NCIA)?|ID)\s*[:#-]?\s*([A-Za-z0-9._/-]{2,})', re.IGNORECASE)
GTIN_RE = re.compile(r'\b(\d{8}|\d{12}|\d{13}|\d{14})\b')
STOCK_RE = re.compile(r'\b(?:estoque|saldo|qtd|quantidade)\s*[:#-]?\s*(-?\d+(?:[,.]\d+)?)', re.IGNORECASE)


def _clean(value: object) -> str:
    return ' '.join(str(value or '').replace('\xa0', ' ').split()).strip()


def _normalize_operation(value: object) -> str:
    text = str(value or '').strip().lower()
    if text in {'estoque', 'stock', 'estoque_site', 'atualizacao_estoque', 'atualização de estoque'}:
        return UNIVERSAL_OPERATION
    if text in {'cadastro', 'cadastro_site', 'produtos', 'produto'}:
        return UNIVERSAL_OPERATION
    return UNIVERSAL_OPERATION


def _orange_info(message: str) -> None:
    st.markdown(
        f'<div style="background:#fff3e0;border:1px solid #ffcc80;border-left:6px solid #fb8c00;color:#5d3200;border-radius:12px;padding:12px 14px;margin:8px 0;font-size:0.95rem;">⚠️ {message}</div>',
        unsafe_allow_html=True,
    )


def _render_copy_steps_box() -> None:
    st.markdown(
        '''
<div style="background:#fff8ed;border:1px solid #ffd59b;border-left:6px solid #fb8c00;border-radius:12px;padding:14px 16px;margin:10px 0;color:#4b2800;">
  <div style="font-weight:800;margin-bottom:6px;">🔐 Captura segura para site protegido, PDF, XML, HTML difícil ou tabela copiada</div>
  <div style="font-size:0.94rem;line-height:1.55;">
    <b>Desktop ou notebook:</b><br>
    1. Abra o fornecedor em outra aba pelo Chrome, Edge ou navegador normal.<br>
    2. Se houver login, entre normalmente pelo seu navegador.<br>
    3. Entre na tela/listagem dos produtos.<br>
    4. Se existir filtro de quantidade por página, selecione a maior quantidade disponível.<br>
    5. Copie a tabela, cole o HTML ou envie o arquivo exportado/salvo.<br><br>
    <b>Mobile/celular:</b><br>
    1. Abra o fornecedor no Chrome do celular.<br>
    2. Vá até a página de produtos, categoria, listagem ou produto atual.<br>
    3. Baixe a página atual ou envie PDF/XML/HTML/CSV/XLSX quando disponível.<br>
    4. Se os produtos estiverem em várias páginas, envie os arquivos em conjunto.<br><br>
    <b>Fallback inteligente:</b> se a tabela normal não for encontrada, o sistema tenta recuperar nome, preço, SKU, GTIN, estoque, imagem e NCM apenas com base no conteúdo enviado e nas colunas do modelo.
  </div>
</div>
        ''',
        unsafe_allow_html=True,
    )


def _render_safety_notes(operation: str) -> None:
    _ = operation
    _orange_info('Este fallback respeita o modelo anexado: busca apenas os campos solicitados e deixa vazio o que não conseguir encontrar. O sistema não pede senha nem cookies.')


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


def _combine_frames(frames: list[pd.DataFrame]) -> pd.DataFrame:
    clean_frames = [frame.fillna('').astype(str) for frame in frames if isinstance(frame, pd.DataFrame) and not frame.empty]
    if not clean_frames:
        return pd.DataFrame()
    combined = pd.concat(clean_frames, ignore_index=True, sort=False).fillna('').astype(str)
    if combined.empty:
        return combined
    text_columns = [column for column in combined.columns if combined[column].astype(str).str.strip().any()]
    if text_columns:
        combined = combined.drop_duplicates(subset=text_columns, keep='first').reset_index(drop=True)
    return combined


def _read_uploaded_files(uploaded_files: list[object], requested_columns: list[str] | None = None) -> tuple[pd.DataFrame, str, list[str]]:
    frames: list[pd.DataFrame] = []
    labels: list[str] = []
    recovery_messages: list[str] = []
    for uploaded in uploaded_files:
        name = getattr(uploaded, 'name', 'fornecedor.html')
        labels.append(str(name))
        file_bytes = uploaded.getvalue()
        lower_name = str(name).lower()
        if lower_name.endswith(('.csv', '.xlsx', '.xls', '.xlsm', '.xlsb')):
            frame = _read_spreadsheet(file_bytes, name)
        elif lower_name.endswith(('.pdf', '.xml', '.nfe')):
            recovered = recover_from_file(file_bytes, name, requested_columns=requested_columns)
            frame = recovered.df
            recovery_messages.append(recovered.message)
        else:
            text = file_bytes.decode('utf-8', errors='ignore')
            frame = _html_to_table(text)
            if frame.empty:
                recovered = recover_from_file(file_bytes, name, requested_columns=requested_columns)
                frame = recovered.df
                recovery_messages.append(recovered.message)
        frames.append(frame)
    return _combine_frames(frames), 'tabela_fornecedor:' + ','.join(labels), recovery_messages


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
    operation = _normalize_operation(operation)
    clean_df = df.copy().fillna('').astype(str) if isinstance(df, pd.DataFrame) else pd.DataFrame()
    if clean_df.empty:
        st.warning('Não encontrei uma tabela ou blocos de produtos no conteúdo enviado.')
        return

    st.session_state[f'df_site_bruto_{operation}'] = clean_df
    st.session_state['df_site_bruto'] = clean_df
    st.session_state['operation_site'] = operation
    st.session_state['tipo_operacao_site'] = operation
    st.session_state['operacao_final'] = operation
    st.session_state['tipo_operacao_final'] = operation
    st.session_state['origem_final'] = 'site'
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
    st.success(f'Origem universal criada com {len(clean_df)} linha(s) e {len(clean_df.columns)} coluna(s).')


def _render_html_capture_toggle(operation: str) -> None:
    show_helper = st.checkbox(
        '🧲 Mostrar capturador guiado de HTML / varrer páginas protegidas',
        value=False,
        key=f'show_html_capture_helper_{operation}',
        help='Use quando o fornecedor não tem botão de exportar. Não usa expander para evitar erro de expander aninhado.',
    )
    if show_helper:
        render_html_capture_helper()


def render_manual_table_import_panel(
    *,
    operation: str,
    requested_columns: list[str] | None = None,
    df_modelo_cadastro: pd.DataFrame | None = None,
    df_modelo_estoque: pd.DataFrame | None = None,
    df_modelo: pd.DataFrame | None = None,
) -> None:
    operation = _normalize_operation(operation)
    st.markdown('###### Fallback inteligente de origem difícil')
    st.caption('Use quando site, HTML, PDF, XML ou tabela copiada não forem lidos corretamente pela captura normal.')

    _render_safety_notes(operation)
    _render_copy_steps_box()
    _render_html_capture_toggle(operation)

    uploaded_files = st.file_uploader(
        'Enviar HTML/XML/PDF/CSV/XLSX exportado ou salvo do fornecedor',
        type=['html', 'htm', 'xml', 'nfe', 'pdf', 'csv', 'xlsx', 'xls', 'xlsm', 'xlsb'],
        key=f'manual_supplier_table_upload_{operation}',
        accept_multiple_files=True,
        help='Pode enviar arquivos difíceis. O fallback tenta recuperar apenas os campos solicitados pelo modelo.',
    )
    pasted = st.text_area(
        'Ou cole aqui a tabela/HTML/XML/texto copiado',
        placeholder='Cole HTML, XML, tabela, texto de PDF ou blocos de produtos copiados do fornecedor.',
        height=180,
        key=f'manual_supplier_table_pasted_{operation}',
        help='Se a tabela normal não for detectada, o fallback tenta recuperar produtos pelo texto.',
    )

    if st.button('📥 Importar origem difícil para o fluxo', use_container_width=True, key=f'manual_supplier_table_import_{operation}'):
        recovery_messages: list[str] = []
        if uploaded_files:
            df, raw_label, recovery_messages = _read_uploaded_files(list(uploaded_files), requested_columns=requested_columns)
        elif pasted.strip():
            df = _html_to_table(pasted)
            raw_label = 'origem_dificil:conteudo_colado'
            if df.empty:
                recovered_df = recover_from_plain_text(pasted, requested_columns=requested_columns)
                df = recovered_df
                recovery_messages.append(f'{len(df)} linha(s) recuperada(s) do conteúdo colado.')
        else:
            st.warning('Envie um arquivo ou cole uma tabela/HTML/XML/texto antes de importar.')
            return

        for message in recovery_messages[:5]:
            if message:
                st.info(message)
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
        render_site_source_summary(df_current, operation, show_history=False, sample_in_expander=False)


__all__ = ['render_manual_table_import_panel']