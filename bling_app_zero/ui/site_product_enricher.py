from __future__ import annotations

import re
from typing import Any


BRANDS = [
    "Aiwa", "Altomex", "Baseus", "Bright", "C3Tech", "Casio", "Dazz", "Exbom", "Geonav", "Goldentec",
    "Hayom", "Hrebos", "Intelbras", "JBL", "Knup", "Lelong", "Lenovo", "Logitech", "Multilaser", "OEX",
    "Philco", "Samsung", "Sony", "Tomate", "TP-Link", "Ugreen", "Xiaomi", "X-Cell", "Xtrad", "Yealink",
]

CATEGORY_RULES = [
    ("Áudio > Fones de ouvido", ["fone", "headset", "earphone", "bluetooth", "auricular"]),
    ("Áudio > Caixas de som", ["caixa de som", "speaker", "soundbar"]),
    ("Informática > Teclados", ["teclado", "keyboard"]),
    ("Informática > Mouses", ["mouse", "mouses"]),
    ("Informática > Webcams", ["webcam", "camera usb"]),
    ("Informática > Cabos e Adaptadores", ["cabo", "adaptador", "hub", "conversor", "hdmi", "usb", "tipo c", "type-c"]),
    ("Telefonia > Carregadores", ["carregador", "fonte usb", "turbo", "tomada usb"]),
    ("Telefonia > Cabos", ["cabo iphone", "cabo lightning", "cabo tipo c", "cabo micro usb"]),
    ("Energia > Pilhas e Baterias", ["pilha", "bateria", "recarregavel", "recarregável"]),
    ("Casa Inteligente > Câmeras", ["camera wifi", "câmera wifi", "camera ip", "câmera ip", "seguranca", "segurança"]),
    ("Games > Acessórios", ["gamer", "controle", "joystick", "gamepad"]),
    ("Eletrônicos > Antenas e TV", ["antena", "tv box", "conversor digital"]),
    ("Eletrônicos > Iluminação", ["lampada", "lâmpada", "led", "refletor", "ring light"]),
]

NCM_RULES = [
    ("85183000", ["fone", "headset", "earphone", "auricular"]),
    ("85182200", ["caixa de som", "speaker", "alto falante", "soundbar"]),
    ("84716052", ["teclado", "keyboard"]),
    ("84716053", ["mouse"]),
    ("85258929", ["webcam", "camera usb", "camera ip", "câmera ip"]),
    ("85444200", ["cabo usb", "cabo hdmi", "cabo tipo c", "cabo type-c", "cabo lightning", "cabo micro usb"]),
    ("85044010", ["carregador", "fonte usb", "adaptador de tomada"]),
    ("85061020", ["pilha alcalina", "pilha"]),
    ("85076000", ["bateria", "power bank"]),
    ("85395000", ["lampada led", "lâmpada led"]),
    ("94054200", ["refletor led", "luminaria", "luminária", "ring light"]),
    ("85287190", ["tv box", "conversor digital"]),
]

KEYWORD_TAGS = [
    ("Gamer", ["gamer", "rgb", "jogo", "game"]),
    ("Bluetooth", ["bluetooth", "bt"]),
    ("USB", ["usb", "tipo c", "type-c", "micro usb"]),
    ("LED", ["led", "luminaria", "luminária", "lampada", "lâmpada"]),
    ("Áudio", ["fone", "headset", "speaker", "caixa de som"]),
]


def _txt(value: Any) -> str:
    return " ".join(str(value or "").replace("\x00", " ").split()).strip()


def _norm(value: Any) -> str:
    text = _txt(value).lower()
    return text.translate(str.maketrans("áàãâéêíóôõúç", "aaaaeeiooouc"))


def infer_brand(description: Any, existing: Any = "") -> str:
    current = _txt(existing)
    if current:
        return current
    text = f" {_norm(description)} "
    for brand in BRANDS:
        b = _norm(brand)
        if re.search(rf"(^|\W){re.escape(b)}(\W|$)", text, flags=re.I):
            return brand
    return ""


def infer_category(description: Any, existing: Any = "") -> str:
    current = _txt(existing)
    if current:
        return current
    text = _norm(description)
    for category, terms in CATEGORY_RULES:
        if any(_norm(term) in text for term in terms):
            return category
    return "Eletrônicos > Acessórios"


def infer_ncm(description: Any, existing: Any = "") -> str:
    current = re.sub(r"\D+", "", _txt(existing))
    if len(current) == 8:
        return current
    text = _norm(description)
    for ncm, terms in NCM_RULES:
        if any(_norm(term) in text for term in terms):
            return ncm
    return ""


def infer_tags(description: Any) -> str:
    text = _norm(description)
    tags = []
    for tag, terms in KEYWORD_TAGS:
        if any(_norm(term) in text for term in terms):
            tags.append(tag)
    return ", ".join(dict.fromkeys(tags))


def infer_department(category: Any) -> str:
    cat = _txt(category)
    if ">" in cat:
        return _txt(cat.split(">")[0])
    return cat


def infer_additional_info(description: Any, ncm: str, category: str, brand: str) -> str:
    parts = []
    if brand:
        parts.append(f"Marca inferida: {brand}")
    if category:
        parts.append(f"Categoria inferida: {category}")
    if ncm:
        parts.append(f"NCM sugerido: {ncm}")
    if parts:
        return " | ".join(parts)
    return ""
