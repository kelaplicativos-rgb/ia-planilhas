from __future__ import annotations

import argparse
import sys
from pathlib import Path

from bling_app_zero.browser_capture.playwright_capture import (
    BrowserCaptureConfig,
    capture_html_with_saved_session,
    manual_login_and_save_session,
    session_debug,
)


def _build_config(args: argparse.Namespace) -> BrowserCaptureConfig:
    return BrowserCaptureConfig(
        supplier_url=str(args.url or '').strip(),
        supplier_key=str(args.key or 'fornecedor').strip(),
        state_dir=Path(str(args.state_dir or '.bling_browser_state')),
        headless=bool(getattr(args, 'headless', False)),
        max_pages=int(getattr(args, 'max_pages', 80) or 80),
        wait_after_action_ms=int(getattr(args, 'wait_ms', 1800) or 1800),
    )


def _progress(payload: dict) -> None:
    message = payload.get('message') or payload.get('stage') or payload
    print(f'[BLINGPLAYWRIGHT] {message}')


def cmd_login(args: argparse.Namespace) -> int:
    config = _build_config(args)
    result = manual_login_and_save_session(config, progress_callback=_progress)
    if result.ok:
        print(f'Sessão salva em: {result.file_path}')
        print(f'URL final: {result.final_url}')
        return 0
    print('Falha ao salvar sessão:')
    for error in result.errors:
        print(f'- {error}')
    return 1


def cmd_capture(args: argparse.Namespace) -> int:
    config = _build_config(args)
    result = capture_html_with_saved_session(config, progress_callback=_progress)
    for warning in result.warnings:
        print(f'AVISO: {warning}')
    if result.ok:
        print(f'HTML capturado em: {result.file_path}')
        print(f'Páginas/blocos: {result.pages_captured}')
        print(f'URL final: {result.final_url}')
        return 0
    print('Falha ao capturar HTML:')
    for error in result.errors:
        print(f'- {error}')
    return 1


def cmd_debug(args: argparse.Namespace) -> int:
    config = _build_config(args)
    print(session_debug(config))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='BLINGPLAYWRIGHT - login manual e captura HTML de fornecedor')
    sub = parser.add_subparsers(dest='command', required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument('--url', required=True, help='URL da tela de produtos/login do fornecedor')
    common.add_argument('--key', default='fornecedor', help='Identificador da sessão salva')
    common.add_argument('--state-dir', default='.bling_browser_state', help='Pasta para salvar sessão e HTMLs')

    login = sub.add_parser('login', parents=[common], help='Abrir Chromium visível para login manual e salvar sessão')
    login.set_defaults(func=cmd_login)

    capture = sub.add_parser('capture', parents=[common], help='Capturar HTML usando sessão salva')
    capture.add_argument('--max-pages', type=int, default=80, help='Máximo de páginas/cliques a tentar')
    capture.add_argument('--wait-ms', type=int, default=1800, help='Espera entre ações em ms')
    capture.add_argument('--headless', action='store_true', help='Rodar captura sem janela gráfica')
    capture.set_defaults(func=cmd_capture)

    debug = sub.add_parser('debug', parents=[common], help='Mostrar diagnóstico da sessão salva')
    debug.set_defaults(func=cmd_debug)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
