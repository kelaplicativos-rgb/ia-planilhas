from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal, Mapping

RESPONSIBLE_FILE = 'bling_app_zero/core/intelligent_flow_decision.py'

DecisionAction = Literal[
    'AUTO_CONTINUAR',
    'REVISAR',
    'RECAPTURAR',
    'BLOQUEAR',
    'ENVIAR_API',
    'GERAR_PENDENCIAS',
]

STATUS_OK = 'OK'
STATUS_ATTENTION = 'ATENCAO'
STATUS_BLOCKED = 'BLOQUEADO'
UNIVERSAL_OPERATIONS = {'universal', 'modelo', 'modelo_destino', 'planilha', 'wizard_cadastro_estoque'}


@dataclass(frozen=True)
class IntelligentFlowDecision:
    action: DecisionAction
    status: str
    title: str
    message: str
    can_continue: bool
    should_auto_continue: bool
    should_send_api: bool
    should_review: bool
    should_recapture: bool
    should_block: bool
    reasons: tuple[str, ...]
    next_step: str
    responsible_file: str = RESPONSIBLE_FILE

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data['reasons'] = list(self.reasons)
        return data


def _int(value: object, default: int = 0) -> int:
    try:
        return int(value or default)
    except Exception:
        return default


def _bool(value: object) -> bool:
    return bool(value)


def _quality_value(quality: object, key: str, default: int = 0) -> int:
    if isinstance(quality, Mapping):
        return _int(quality.get(key), default)
    return _int(getattr(quality, key, default), default)


def _quality_warnings(quality: object) -> tuple[str, ...]:
    if isinstance(quality, Mapping):
        raw = quality.get('warnings') or []
    else:
        raw = getattr(quality, 'warnings', []) or []
    return tuple(str(item) for item in list(raw) if str(item).strip())


def _normalize_operation(operation: object) -> str:
    return str(operation or '').strip().lower()


def _is_stock_operation(operation: object) -> bool:
    text = _normalize_operation(operation)
    return text in {'estoque', 'stock', 'atualizacao_estoque', 'atualização de estoque', 'atualização_estoque'}


def _is_universal_operation(operation: object) -> bool:
    return _normalize_operation(operation) in UNIVERSAL_OPERATIONS


def _decision(
    *,
    action: DecisionAction,
    status: str,
    title: str,
    message: str,
    reasons: list[str],
    next_step: str,
) -> IntelligentFlowDecision:
    should_block = action == 'BLOQUEAR'
    should_review = action in {'REVISAR', 'GERAR_PENDENCIAS'}
    should_recapture = action == 'RECAPTURAR'
    should_send_api = action == 'ENVIAR_API'
    should_auto_continue = action in {'AUTO_CONTINUAR', 'ENVIAR_API'}
    can_continue = action in {'AUTO_CONTINUAR', 'REVISAR', 'ENVIAR_API', 'GERAR_PENDENCIAS'}
    return IntelligentFlowDecision(
        action=action,
        status=status,
        title=title,
        message=message,
        can_continue=can_continue,
        should_auto_continue=should_auto_continue,
        should_send_api=should_send_api,
        should_review=should_review,
        should_recapture=should_recapture,
        should_block=should_block,
        reasons=tuple(reasons),
        next_step=next_step,
    )


def decide_after_site_capture(
    *,
    operation: str,
    quality: object,
    used_api: bool = False,
    platform: str = '',
) -> IntelligentFlowDecision:
    """Decide automaticamente o próximo passo após captura e validação do site."""
    is_stock = _is_stock_operation(operation)
    is_universal = _is_universal_operation(operation)
    score = _quality_value(quality, 'score')
    rows = _quality_value(quality, 'rows')
    good_rows = _quality_value(quality, 'good_rows')
    missing_price = _quality_value(quality, 'missing_price')
    missing_description = _quality_value(quality, 'missing_description')
    missing_stock = _quality_value(quality, 'missing_stock')
    warnings = list(_quality_warnings(quality))
    reasons: list[str] = []

    if platform:
        reasons.append(f'Plataforma detectada: {platform}.')
    if used_api:
        reasons.append('API interna usada como fonte principal.')

    if rows <= 0:
        return _decision(
            action='RECAPTURAR',
            status=STATUS_BLOCKED,
            title='Captura sem produtos válidos',
            message='Não encontrei produtos suficientes para continuar. Faça nova captura com links mais específicos.',
            reasons=[*reasons, *warnings],
            next_step='origem_site',
        )

    # Fluxo universal usa o modelo anexado pelo usuário. Em modelos de estoque/saldo,
    # a qualidade pode vir com good_rows=0 só porque não existe preço de venda. Isso
    # não pode bloquear a origem: ela precisa seguir para revisão/mapeamento/download.
    if is_universal and good_rows <= 0 and (missing_stock < rows or missing_description < rows):
        return _decision(
            action='REVISAR',
            status=STATUS_ATTENTION,
            title='Origem capturada para revisão',
            message='A captura trouxe linhas aproveitáveis para o modelo anexado. Revise o mapeamento e os campos antes do download ou envio pelo fluxo Bling conectado.',
            reasons=[*reasons, *warnings],
            next_step='revisao_origem',
        )

    if good_rows <= 0:
        return _decision(
            action='BLOQUEAR',
            status=STATUS_BLOCKED,
            title='Dados capturados sem linhas aproveitáveis',
            message='A captura trouxe linhas, mas nenhuma parece pronta para o fluxo escolhido.',
            reasons=[*reasons, *warnings],
            next_step='revisao_origem',
        )

    if is_stock:
        if missing_stock >= rows:
            return _decision(
                action='BLOQUEAR',
                status=STATUS_BLOCKED,
                title='Estoque sem quantidade',
                message='Atualização de estoque precisa de quantidade/saldo para seguir.',
                reasons=[*reasons, *warnings],
                next_step='revisao_estoque',
            )
        if score < 60:
            return _decision(
                action='REVISAR',
                status=STATUS_ATTENTION,
                title='Estoque precisa de revisão',
                message='A captura de estoque tem qualidade baixa ou campos faltantes. Revise antes de enviar ao Bling.',
                reasons=[*reasons, *warnings],
                next_step='preflight_api',
            )
        return _decision(
            action='ENVIAR_API' if used_api and score >= 85 else 'AUTO_CONTINUAR',
            status=STATUS_OK,
            title='Estoque pronto para pré-varredura',
            message='A captura tem dados suficientes para seguir para pré-varredura e envio seguro.',
            reasons=[*reasons, *warnings],
            next_step='preflight_api',
        )

    if missing_description >= rows:
        return _decision(
            action='BLOQUEAR',
            status=STATUS_BLOCKED,
            title='Cadastro sem nome/descrição',
            message='Cadastro de produtos precisa de nome ou descrição para continuar.',
            reasons=[*reasons, *warnings],
            next_step='revisao_cadastro',
        )

    if score < 60:
        return _decision(
            action='RECAPTURAR',
            status=STATUS_ATTENTION,
            title='Qualidade baixa na captura',
            message='A captura ficou fraca. Recomendo recapturar ou revisar os links antes de cadastrar produtos.',
            reasons=[*reasons, *warnings],
            next_step='origem_site',
        )

    if missing_price > 0 or score < 85:
        return _decision(
            action='REVISAR',
            status=STATUS_ATTENTION,
            title='Cadastro precisa de revisão',
            message='Alguns produtos precisam de revisão de preço, descrição ou campos complementares antes do envio.',
            reasons=[*reasons, *warnings],
            next_step='preview_final',
        )

    return _decision(
        action='AUTO_CONTINUAR',
        status=STATUS_OK,
        title='Cadastro pronto para seguir',
        message='A captura tem qualidade boa para continuar automaticamente até a prévia final.',
        reasons=[*reasons, *warnings],
        next_step='preview_final',
    )


def decide_before_api_send(
    *,
    operation: str,
    preflight_report: Mapping[str, Any] | None,
) -> IntelligentFlowDecision:
    """Decide se o envio API deve continuar após a pré-varredura."""
    report = dict(preflight_report or {})
    total = _int(report.get('total_rows'))
    safe_rows = _int(report.get('safe_to_send_rows'))
    blocked_rows = _int(report.get('blocked_rows') or report.get('missing_required_rows'))
    block_send = _bool(report.get('block_send'))
    warnings = [str(item) for item in list(report.get('warnings') or []) if str(item).strip()]

    if total <= 0:
        return _decision(
            action='BLOQUEAR',
            status=STATUS_BLOCKED,
            title='Envio sem linhas',
            message='Não há linhas para enviar ao Bling.',
            reasons=warnings,
            next_step='preview_final',
        )

    if block_send or safe_rows <= 0:
        return _decision(
            action='BLOQUEAR',
            status=STATUS_BLOCKED,
            title='Envio bloqueado pela pré-varredura',
            message='Nenhuma linha tem os campos mínimos para a API do Bling.',
            reasons=warnings,
            next_step='pendencias_envio',
        )

    if blocked_rows > 0:
        return _decision(
            action='GERAR_PENDENCIAS',
            status=STATUS_ATTENTION,
            title='Envio com pendências separadas',
            message=f'{blocked_rows} linha(s) ficarão pendentes; o envio seguirá somente com {safe_rows} linha(s) apta(s).',
            reasons=warnings,
            next_step='envio_api',
        )

    return _decision(
        action='ENVIAR_API',
        status=STATUS_OK,
        title='Envio API liberado',
        message=f'{safe_rows} linha(s) apta(s) para envio seguro ao Bling.',
        reasons=warnings,
        next_step='envio_api',
    )


__all__ = [
    'DecisionAction',
    'IntelligentFlowDecision',
    'decide_after_site_capture',
    'decide_before_api_send',
]