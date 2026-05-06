from __future__ import annotations

"""Limpeza de descrições capturadas em páginas de produto.

Remove blocos de rodapé, endereço da loja, atendimento, redes sociais e textos
institucionais que podem entrar junto quando o scraper lê o corpo inteiro da página.
"""

import re

import pandas as pd


DESCRIPTION_COLUMNS = (
    "Descrição complementar",
    "Descrição Complementar",
    "Descricao complementar",
    "Descricao Complementar",
    "Descrição Curta",
    "Descrição curta",
    "Descricao curta",
    "Descrição detalhada",
    "Descricao detalhada",
    "Descrição do Produto no Fornecedor",
    "Informações Adicionais",
)

TITLE_COLUMNS = ("Descrição", "Descricao", "Nome", "Produto", "Título", "Titulo", "Title")

BAD_TERMS = (
    "mega center eletronicos",
    "mega center eletrônicos",
    "megacenter eletronicos",
    "megacenter eletrônicos",
    "todos os direitos reservados",
    "redes sociais",
    "facebook",
    "instagram",
    "whatsapp",
    "youtube",
    "tiktok",
    "atendimento",
    "central de atendimento",
    "fale conosco",
    "formas de pagamento",
    "forma de pagamento",
    "trocas e devoluções",
    "trocas e devolucoes",
    "política de privacidade",
    "politica de privacidade",
    "termos de uso",
    "newsletter",
    "cadastre seu email",
    "minha conta",
    "login",
    "carrinho",
    "comprar",
    "adicionar ao carrinho",
    "quem somos",
    "sobre nós",
    "sobre nos",
    "loja física",
    "loja fisica",
    "nossa loja",
    "endereço",
    "endereco",
    "cep",
    "cnpj",
    "telefone",
    "sac",
    "e-mail",
    "email",
    "horário de atendimento",
    "horario de atendimento",
    "segunda a sexta",
    "sábado",
    "sabado",
    "domingo",
    "feriado",
    "mapa do site",
    "institucional",
)

STOP_MARKERS = (
    "produtos relacionados",
    "produto relacionado",
    "veja também",
    "veja tambem",
    "quem viu viu também",
    "quem viu viu tambem",
    "avaliações",
    "avaliacoes",
    "formas de pagamento",
    "atendimento",
    "loja física",
    "loja fisica",
    "nossa loja",
    "fale conosco",
    "newsletter",
    "trocas e devoluções",
    "trocas e devolucoes",
    "política de privacidade",
    "politica de privacidade",
    "todos os direitos reservados",
)

ADDRESS_RE = re.compile(
    r"\b(rua|avenida|av\.?|rodovia|estrada|travessa|alameda|praça|praca)\b.*?\b(cep|bairro|cnpj|telefone|fone|whatsapp|sp|mg|rj|pr|sc|rs|ba|pe|ce)\b",
    re.IGNORECASE,
)
CONTACT_RE = re.compile(
    r"\b(\(?\d{2}\)?\s*)?9?\d{4}[-\s]?\d{4}\b|\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b|\b\d{5}-?\d{3}\b",
    re.IGNORECASE,
)
URL_RE = re.compile(r"https?://|www\.", re.IGNORECASE)


def _text(value: object) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    return str(value).strip()


def _norm(value: object) -> str:
    text = _text(value).lower()
    text = text.translate(str.maketrans("áàãâéêíóôõúç", "aaaaeeiooouc"))
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", text)).strip()


def _first_title(row: pd.Series) -> str:
    for col in TITLE_COLUMNS:
        if col in row.index:
            value = _text(row.get(col))
            if value:
                return value
    return ""


def _cut_at_stop_marker(text: str) -> str:
    low_norm = _norm(text)
    best = len(text)
    for marker in STOP_MARKERS:
        marker_norm = _norm(marker)
        pos_norm = low_norm.find(marker_norm)
        if pos_norm >= 0:
            pos_original = text.lower().find(marker.lower())
            if pos_original < 0:
                pos_original = max(0, int(len(text) * (pos_norm / max(len(low_norm), 1))))
            best = min(best, pos_original)
    return text[:best].strip(" -•|:;")


def _is_noise(piece: str, title_norm: str) -> bool:
    part = _text(piece).strip(" -•|:;")
    norm = _norm(part)
    if not part or len(part) < 18:
        return True
    if title_norm and norm == title_norm:
        return True
    if any(term and term in norm for term in (_norm(t) for t in BAD_TERMS)):
        return True
    if ADDRESS_RE.search(part) or CONTACT_RE.search(part) or URL_RE.search(part):
        return True
    if sum(part.count(x) for x in ["|", " / ", " > ", " - "]) >= 4:
        return True
    return False


def clean_product_description(value: object, title: str = "") -> str:
    text = _text(value).replace("\ufeff", " ").replace("\u200b", " ").replace("\xa0", " ")
    text = re.sub(r"[\r\n\t]+", " | ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return ""

    text = _cut_at_stop_marker(text)
    title_norm = _norm(title)
    pieces = re.split(r"\s*\|\s*|(?<=\.)\s+|\s{2,}|[•]+", text)

    cleaned: list[str] = []
    seen: set[str] = set()
    for piece in pieces:
        part = _text(piece).strip(" -•|:;")
        norm = _norm(part)
        if _is_noise(part, title_norm):
            continue
        if norm in seen:
            continue
        seen.add(norm)
        cleaned.append(part)
        if len(" ".join(cleaned)) >= 1800:
            break

    result = re.sub(r"\s+", " ", " ".join(cleaned)).strip()
    return result[:2000]


def clean_product_descriptions_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return df

    out = df.copy().fillna("")
    cols = [col for col in out.columns if _norm(col) in {_norm(c) for c in DESCRIPTION_COLUMNS}]
    if not cols:
        return out

    for idx, row in out.iterrows():
        title = _first_title(row)
        for col in cols:
            original = row.get(col, "")
            cleaned = clean_product_description(original, title=title)
            out.at[idx, col] = cleaned
    return out
