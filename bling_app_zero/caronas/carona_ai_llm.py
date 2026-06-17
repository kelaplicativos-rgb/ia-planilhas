from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

import httpx

OPENAI_RESPONSES_URL = 'https://api.openai.com/v1/responses'
DEFAULT_MODEL = os.getenv('OPENAI_MODEL', 'gpt-5.5')


@dataclass(frozen=True)
class AIDemandInsight:
    enabled: bool
    status: str
    summary: str
    recommended_dates: tuple[str, ...]
    raw: dict[str, Any]


def _extract_text_from_response(payload: dict[str, Any]) -> str:
    direct = payload.get('output_text')
    if isinstance(direct, str) and direct.strip():
        return direct.strip()
    chunks: list[str] = []
    for item in payload.get('output') or []:
        if not isinstance(item, dict):
            continue
        for content in item.get('content') or []:
            if not isinstance(content, dict):
                continue
            text = content.get('text') or content.get('output_text')
            if isinstance(text, str) and text.strip():
                chunks.append(text.strip())
    return '\n'.join(chunks).strip()


def _parse_json_text(text: str) -> dict[str, Any]:
    if not text:
        return {}
    try:
        value = json.loads(text)
        return value if isinstance(value, dict) else {}
    except Exception:
        pass
    start = text.find('{')
    end = text.rfind('}')
    if start >= 0 and end > start:
        try:
            value = json.loads(text[start : end + 1])
            return value if isinstance(value, dict) else {}
        except Exception:
            return {}
    return {}


def is_openai_configured() -> bool:
    return bool(os.getenv('OPENAI_API_KEY'))


def analyze_destination_demand_with_ai(
    *,
    origin: str,
    destination: str,
    horizon_days: int,
    events_text: str,
    public_signals: list[dict[str, Any]],
    model: str | None = None,
    timeout: float = 25.0,
) -> AIDemandInsight:
    """Refina a previsão de demanda quando OPENAI_API_KEY estiver configurada.

    O retorno da IA nunca libera ação operacional sozinho. As ações CRIAR/PUBLICAR/MANTER
    continuam dependendo da validação pública por data na BlaBlaCar.
    """
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        return AIDemandInsight(
            enabled=False,
            status='IA externa desativada: OPENAI_API_KEY não configurada.',
            summary='',
            recommended_dates=(),
            raw={},
        )

    prompt = {
        'role': 'user',
        'content': [
            {
                'type': 'input_text',
                'text': (
                    'Você é o motor Carona AI para prever alta demanda de passageiros em caronas públicas. '\
                    'Analise origem, destino, horizonte, eventos informados e sinais públicos já coletados. '\
                    'Responda somente JSON válido com as chaves: summary, recommended_dates, reasoning. '\
                    'recommended_dates deve conter datas ISO YYYY-MM-DD, ordenadas da melhor para a pior. '\
                    'Não recomende criar/publicar sem validação pública por data; use apenas previsão de demanda.\n\n'
                    f'Origem: {origin}\nDestino: {destination}\nHorizonte: {horizon_days} dias\n'
                    f'Eventos informados:\n{events_text or "sem eventos informados"}\n\n'
                    f'Sinais públicos coletados JSON:\n{json.dumps(public_signals[:40], ensure_ascii=False)}'
                ),
            }
        ],
    }
    payload = {
        'model': model or DEFAULT_MODEL,
        'input': [prompt],
        'max_output_tokens': 900,
    }
    try:
        response = httpx.post(
            OPENAI_RESPONSES_URL,
            headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
            json=payload,
            timeout=timeout,
        )
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        return AIDemandInsight(
            enabled=True,
            status=f'IA externa indisponível: {exc}',
            summary='',
            recommended_dates=(),
            raw={},
        )

    text = _extract_text_from_response(data)
    parsed = _parse_json_text(text)
    dates = parsed.get('recommended_dates') if isinstance(parsed, dict) else []
    if not isinstance(dates, list):
        dates = []
    clean_dates = tuple(str(item).strip() for item in dates if str(item).strip())[:20]
    summary = str(parsed.get('summary') or text or '').strip()
    return AIDemandInsight(
        enabled=True,
        status='IA externa aplicada à previsão de demanda.',
        summary=summary[:1200],
        recommended_dates=clean_dates,
        raw=parsed if parsed else {'text': text[:2000]},
    )


__all__ = ['AIDemandInsight', 'analyze_destination_demand_with_ai', 'is_openai_configured']
