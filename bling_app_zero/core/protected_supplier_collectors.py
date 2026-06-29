from __future__ import annotations

import json
import zipfile
from dataclasses import dataclass
from io import BytesIO


@dataclass(frozen=True)
class ProtectedSupplierSpec:
    key: str
    name: str
    start_url: str
    default_pages: int = 25
    strategy: str = 'datatables'
    default_format: str = 'mhtml'
    description: str = ''


PROTECTED_SUPPLIERS: dict[str, ProtectedSupplierSpec] = {
    'obaobamix': ProtectedSupplierSpec(
        key='obaobamix',
        name='Oba Oba Mix',
        start_url='https://app.obaobamix.com.br/admin/products',
        default_pages=25,
        strategy='datatables',
        default_format='mhtml',
        description='Painel autenticado com DataTables. Captura produtos, estoque real em tooltip, fotos, marca, modelo e preço.',
    ),
    'datatables_generic': ProtectedSupplierSpec(
        key='datatables_generic',
        name='Genérico com paginação DataTables',
        start_url='',
        default_pages=25,
        strategy='datatables',
        default_format='mhtml',
        description='Fornecedor protegido que usa tabela paginada DataTables dentro do navegador logado.',
    ),
}


COLLECTOR_SCRIPT = r'''
from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
import zipfile
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except Exception:
    print('Playwright nao esta instalado.')
    print('Execute: python -m pip install playwright')
    print('Depois:   python -m playwright install chromium')
    raise

ERROR_LOG = 'ERRO_COLETOR.txt'


def load_config(path: str) -> dict:
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except Exception:
        return {}


def write_error_log(exc: BaseException) -> None:
    try:
        Path(ERROR_LOG).write_text(traceback.format_exc(), encoding='utf-8')
    except Exception:
        pass


def wait_for_datatable(page, timeout_ms: int = 120000) -> bool:
    deadline = time.time() + timeout_ms / 1000
    while time.time() < deadline:
        try:
            ok = page.evaluate(
                """() => !!(
                    window.jQuery &&
                    window.jQuery.fn &&
                    window.jQuery.fn.dataTable &&
                    window.jQuery.fn.dataTable.tables().length
                )"""
            )
            if ok:
                return True
        except Exception:
            pass
        time.sleep(1)
    return False


def datatable_info(page) -> dict:
    try:
        return page.evaluate(
            """() => {
                const tables = window.jQuery.fn.dataTable.tables();
                if (!tables.length) return {page: 0, pages: 0, recordsTotal: 0, recordsDisplay: 0};
                const dt = window.jQuery(tables[0]).DataTable();
                return dt.page.info();
            }"""
        ) or {}
    except Exception:
        return {'page': 0, 'pages': 0, 'recordsTotal': 0, 'recordsDisplay': 0}


def visible_table_rows(page) -> int:
    try:
        return int(page.evaluate("""() => document.querySelectorAll('table tbody tr').length""") or 0)
    except Exception:
        return 0


def wait_for_products_loaded(page, timeout_ms: int = 90000) -> dict:
    deadline = time.time() + timeout_ms / 1000
    last_info: dict = {}
    while time.time() < deadline:
        info = datatable_info(page)
        last_info = info
        total = int(info.get('recordsTotal') or info.get('recordsDisplay') or 0)
        rows = visible_table_rows(page)
        if total > 0 or rows > 1:
            return info
        time.sleep(1)
    return last_info


def goto_datatable_page(page, page_index: int) -> None:
    page.evaluate(
        """(pageIndex) => {
            const tables = window.jQuery.fn.dataTable.tables();
            const dt = window.jQuery(tables[0]).DataTable();
            dt.page(pageIndex).draw(false);
        }""",
        page_index,
    )
    page.wait_for_function(
        """(pageIndex) => {
            if (!(window.jQuery && window.jQuery.fn && window.jQuery.fn.dataTable)) return false;
            const tables = window.jQuery.fn.dataTable.tables();
            if (!tables.length) return false;
            const dt = window.jQuery(tables[0]).DataTable();
            const info = dt.page.info();
            const processing = document.querySelector('.dataTables_processing');
            const isProcessing = processing && getComputedStyle(processing).display !== 'none';
            return info.page === pageIndex && !isProcessing;
        }""",
        arg=page_index,
        timeout=90000,
    )
    try:
        page.wait_for_load_state('networkidle', timeout=90000)
    except Exception:
        pass
    page.wait_for_timeout(900)


def capture_mhtml(context, page) -> str:
    client = context.new_cdp_session(page)
    result = client.send('Page.captureSnapshot', {'format': 'mhtml'})
    return result.get('data', '')


def write_capture(context, page, out_dir: Path, page_number: int, capture_format: str, saved: list[Path]) -> None:
    if capture_format in {'html', 'both'}:
        html_path = out_dir / f'fornecedor_pagina_{page_number:03d}.html'
        html_path.write_text(page.content(), encoding='utf-8')
        saved.append(html_path)
    if capture_format in {'mhtml', 'both'}:
        mhtml_path = out_dir / f'fornecedor_pagina_{page_number:03d}.mhtml'
        mhtml_path.write_text(capture_mhtml(context, page), encoding='utf-8')
        saved.append(mhtml_path)


def make_zip(out_dir: Path, saved_files: list[Path]) -> Path:
    zip_path = out_dir / 'mapeiaai_capturas_fornecedor.zip'
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for file in saved_files:
            if file.exists():
                zf.write(file, file.name)
    return zip_path


def run_capture(args: argparse.Namespace, config: dict) -> int:
    url = args.url or config.get('start_url') or ''
    pages_requested = int(args.pages or config.get('pages') or 0)
    capture_format = args.format or config.get('format') or 'mhtml'
    provider_name = config.get('provider_name') or 'Fornecedor protegido'

    if not url:
        print('URL inicial vazia. Edite provider_config.json ou use --url.')
        return 2

    out_dir = Path(args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    profile_dir = Path(args.profile).resolve()
    profile_dir.mkdir(parents=True, exist_ok=True)

    saved_files: list[Path] = []

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=False,
            viewport={'width': 1366, 'height': 768},
            accept_downloads=True,
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.goto(url, wait_until='domcontentloaded', timeout=120000)

        if not wait_for_datatable(page, timeout_ms=45000):
            print('\nFaca login no navegador aberto e deixe a tabela de produtos carregada.')
            input('Quando a tabela aparecer, pressione ENTER aqui no terminal... ')
            if not wait_for_datatable(page, timeout_ms=180000):
                print('Nao encontrei DataTables. Vou salvar a pagina atual para diagnostico.')
                write_capture(context, page, out_dir, 1, capture_format, saved_files)
                zip_path = make_zip(out_dir, saved_files)
                print(f'ZIP gerado: {zip_path}')
                context.close()
                return 0

        info = wait_for_products_loaded(page, timeout_ms=90000)
        detected_pages = int(info.get('pages') or 0)
        total = int(info.get('recordsTotal') or info.get('recordsDisplay') or 0)

        if total <= 0 and visible_table_rows(page) <= 1:
            print('\nA tabela foi encontrada, mas ainda mostra 0 registros.')
            print('Verifique se voce esta logado, sem filtro ativo, e na tela correta de produtos.')
            input('Quando os produtos aparecerem na tela, pressione ENTER aqui no terminal... ')
            info = wait_for_products_loaded(page, timeout_ms=120000)
            detected_pages = int(info.get('pages') or 0)
            total = int(info.get('recordsTotal') or info.get('recordsDisplay') or 0)

        pages = pages_requested if pages_requested > 0 else detected_pages
        pages = min(pages, detected_pages or pages)
        if pages <= 0:
            pages = 1

        print(f'{provider_name}: {total} registro(s) detectado(s) | {pages} pagina(s) para capturar')
        meta = {
            'provider': provider_name,
            'url': url,
            'records_total': total,
            'pages_detected': detected_pages,
            'pages_captured': pages,
        }
        manifest = out_dir / 'mapeiaai_capture_manifest.json'
        manifest.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding='utf-8')
        saved_files.append(manifest)

        for page_index in range(pages):
            page_number = page_index + 1
            print(f'Capturando pagina {page_number}/{pages}...')
            try:
                goto_datatable_page(page, page_index)
            except Exception as exc:
                print(f'Aviso: nao consegui confirmar a pagina {page_number}. Vou salvar o HTML atual e continuar.')
                error_page = out_dir / f'erro_pagina_{page_number:03d}.txt'
                error_page.write_text(traceback.format_exc(), encoding='utf-8')
                saved_files.append(error_page)
            write_capture(context, page, out_dir, page_number, capture_format, saved_files)
            info_path = out_dir / f'fornecedor_pagina_{page_number:03d}.json'
            info_path.write_text(json.dumps(datatable_info(page), ensure_ascii=False, indent=2), encoding='utf-8')
            saved_files.append(info_path)

        zip_path = make_zip(out_dir, saved_files)
        context.close()
        print('\nPronto.')
        print(f'ZIP gerado: {zip_path}')
        print('Anexe esse ZIP no MapeiaAI em Painel protegido com login.')
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description='Coletor universal MapeiaAI para fornecedores protegidos por login.')
    parser.add_argument('--config', default='provider_config.json')
    parser.add_argument('--url', default='')
    parser.add_argument('--pages', type=int, default=0)
    parser.add_argument('--format', choices=['html', 'mhtml', 'both'], default='')
    parser.add_argument('--out', default='capturas_fornecedor')
    parser.add_argument('--profile', default='_mapeiaai_fornecedor_profile')
    args = parser.parse_args()
    config = load_config(args.config)
    return run_capture(args, config)


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        write_error_log(exc)
        print('\nERRO NO COLETOR:')
        print(str(exc))
        print(f'\nDetalhes salvos em: {ERROR_LOG}')
        input('Pressione ENTER para fechar...')
        raise
'''.strip() + '\n'


RUN_BAT = r'''
@echo off
setlocal
cd /d "%~dp0"

echo Instalando/atualizando Playwright...
py -m pip install --upgrade playwright
if errorlevel 1 (
  echo Falha ao instalar Playwright. Tente: python -m pip install playwright
  pause
  exit /b 1
)

echo Instalando Chromium do Playwright...
py -m playwright install chromium
if errorlevel 1 (
  echo Falha ao instalar Chromium do Playwright.
  pause
  exit /b 1
)

echo.
echo O navegador vai abrir. Se pedir login, entre normalmente no painel do fornecedor.
echo Deixe a tabela de produtos carregada. O coletor usa sua sessao local, sem exportar senha.
echo.
py coletor_fornecedor_protegido.py --config provider_config.json

echo.
echo Se houve erro, procure o arquivo ERRO_COLETOR.txt nesta mesma pasta.
pause
'''.strip() + '\n'


README_TEMPLATE = '''
COLETOR MAPEIAAI - FORNECEDOR PROTEGIDO

Fornecedor configurado: {provider_name}
URL inicial: {start_url}
Paginas: {pages}
Formato: {format}

Como usar no Windows:
1. Extraia este ZIP em uma pasta.
2. Dê dois cliques em RUN_COLETOR.bat.
3. Quando o navegador abrir, faça login no fornecedor se necessário.
4. Deixe a tabela de produtos carregada.
5. O coletor vai passar pelas páginas automaticamente e gerar:
   capturas_fornecedor/mapeiaai_capturas_fornecedor.zip
6. Anexe esse ZIP no MapeiaAI em: Painel protegido com login.

Segurança:
- O coletor roda localmente no seu computador.
- Não pede senha no terminal.
- Não envia cookie/token para o MapeiaAI.
- O MapeiaAI recebe apenas HTML/MHTML das páginas capturadas.

Observação:
- Se a tela mostrar 0 registros, o coletor vai pedir para você confirmar o login/tabela antes de continuar.
- Se houver erro, ele deixa o arquivo ERRO_COLETOR.txt na pasta do coletor.

Para outros fornecedores:
- Escolha Genérico com paginação DataTables no MapeiaAI.
- Informe a URL inicial do painel de produtos.
- Baixe um novo coletor configurado.
'''.strip() + '\n'


def supplier_options() -> list[ProtectedSupplierSpec]:
    return list(PROTECTED_SUPPLIERS.values())


def get_supplier(key: str) -> ProtectedSupplierSpec:
    return PROTECTED_SUPPLIERS.get(key) or PROTECTED_SUPPLIERS['datatables_generic']


def build_provider_config(provider_key: str, *, start_url: str = '', pages: int | None = None, capture_format: str = '') -> dict[str, object]:
    spec = get_supplier(provider_key)
    resolved_url = str(start_url or spec.start_url or '').strip()
    resolved_pages = int(pages or spec.default_pages or 25)
    resolved_format = str(capture_format or spec.default_format or 'mhtml').strip().lower()
    if resolved_format not in {'html', 'mhtml', 'both'}:
        resolved_format = 'mhtml'
    return {
        'schema_version': 'mapeiaai_protected_supplier_collector_v1',
        'provider_key': spec.key,
        'provider_name': spec.name,
        'start_url': resolved_url,
        'pages': resolved_pages,
        'strategy': spec.strategy,
        'format': resolved_format,
    }


def build_collector_zip(provider_key: str, *, start_url: str = '', pages: int | None = None, capture_format: str = '') -> bytes:
    config = build_provider_config(provider_key, start_url=start_url, pages=pages, capture_format=capture_format)
    readme = README_TEMPLATE.format(
        provider_name=config['provider_name'],
        start_url=config['start_url'],
        pages=config['pages'],
        format=config['format'],
    )
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('coletor_fornecedor_protegido.py', COLLECTOR_SCRIPT)
        zf.writestr('RUN_COLETOR.bat', RUN_BAT)
        zf.writestr('provider_config.json', json.dumps(config, ensure_ascii=False, indent=2))
        zf.writestr('README.txt', readme)
    return buffer.getvalue()


__all__ = [
    'ProtectedSupplierSpec',
    'PROTECTED_SUPPLIERS',
    'build_collector_zip',
    'build_provider_config',
    'get_supplier',
    'supplier_options',
]
