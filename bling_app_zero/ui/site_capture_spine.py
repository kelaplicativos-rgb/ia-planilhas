from __future__ import annotations

from dataclasses import dataclass

RESPONSIBLE_FILE = 'bling_app_zero/ui/site_capture_spine.py'


@dataclass(frozen=True)
class SiteCaptureProfile:
    operation: str
    stock_balance_only: bool
    title: str
    kicker: str
    button_label: str
    running_title: str
    running_notice: str
    initial_progress_text: str
    started_message: str
    stage_1: str
    stage_2: str
    stage_3: str
    empty_message: str
    success_prefix: str
    scan_goal: str


def capture_profile(operation: str, *, stock_balance_only: bool = False) -> SiteCaptureProfile:
    op = str(operation or '').strip().lower() or 'cadastro'
    if stock_balance_only:
        return SiteCaptureProfile(
            operation=op,
            stock_balance_only=True,
            title='Buscar produtos no site',
            kicker='Entrada por site',
            button_label='🚀 Buscar produtos agora',
            running_title='Busca em andamento',
            running_notice='Busca por site em andamento. O sistema usa a mesma captura inteligente para cadastro e estoque, mudando apenas os campos finais que serão salvos.',
            initial_progress_text='BLINGSMARTSCAN buscando produtos com IA...',
            started_message='Captura iniciada. Validando operação, contrato ativo, depósito e limites seguros.',
            stage_1='Localizando links/produtos no site.',
            stage_2='Extraindo dados dos produtos localizados.',
            stage_3='Validando colunas, depósito, saldos e salvando resultado final.',
            empty_message='O BLINGSMARTSCAN não encontrou dados válidos nesse lote.',
            success_prefix='BLINGSMARTSCAN concluiu e salvou',
            scan_goal='blingsmartscan_site_unificado_estoque',
        )
    return SiteCaptureProfile(
        operation=op,
        stock_balance_only=False,
        title='Buscar produtos no site',
        kicker='Entrada por site',
        button_label='🚀 Buscar produtos agora',
        running_title='Busca em andamento',
        running_notice='Busca por site em andamento. O sistema está capturando produtos, imagens, descrições, preços e dados técnicos em uma medula única.',
        initial_progress_text='BLINGSMARTSCAN buscando produtos com IA...',
        started_message='Captura iniciada. Validando operação, contrato ativo e limites seguros.',
        stage_1='Localizando links/produtos no site.',
        stage_2='Extraindo dados dos produtos localizados.',
        stage_3='Validando colunas e salvando resultado final.',
        empty_message='O BLINGSMARTSCAN não encontrou dados válidos nesse lote.',
        success_prefix='BLINGSMARTSCAN concluiu e salvou',
        scan_goal='blingsmartscan_site_unificado_cadastro',
    )


def progress_mode() -> str:
    return 'unified_live_progress'


def found_products_message(found: int) -> str:
    total = int(found or 0)
    return f'Foram localizados {total} link(s) de produto. Agora o sistema vai extrair os dados.'


def extracting_message(found: int) -> str:
    total = int(found or 0)
    return f'Extraindo dados dos produtos localizados ({total} encontrado(s)).'


__all__ = ['SiteCaptureProfile', 'capture_profile', 'extracting_message', 'found_products_message', 'progress_mode']
