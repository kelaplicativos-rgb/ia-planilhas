from __future__ import annotations

from bling_app_zero.engines.brand_title_detector import detect_brand_from_title


def test_detects_known_and_new_brand_from_title() -> None:
    assert detect_brand_from_title('Mouse Gamer Redragon Cobra M711 RGB') == 'Redragon'
    assert detect_brand_from_title('Cabo USB Imenso IM-21 Tipo C') == 'Imenso'
    assert detect_brand_from_title('Carregador Turbo Marca: Baseus Modelo CATKLF') == 'Baseus'


def test_rejects_model_code_as_brand() -> None:
    assert detect_brand_from_title('Controle Sem Fio KP-4015') == ''
    assert detect_brand_from_title('Fone Bluetooth Airdots Pro XP-900') == ''
    assert detect_brand_from_title('Carregador Turbo V8 20W') == ''
    assert detect_brand_from_title('Fone Bluetooth XP-900', fallback='XP-900') == ''


def test_keeps_real_hyphenated_brands() -> None:
    assert detect_brand_from_title('Suporte Universal para TV B-Max BMG-49') == 'B-Max'
    assert detect_brand_from_title('Mouse com fio C3TECH MS-35') == 'C3Tech'
