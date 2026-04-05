import json
import os
from typing import Dict


def _api_key() -> str:
    return (os.getenv("OPENAI_API_KEY") or "").strip()


def _compactar_html(html: str, limite: int = 12000) -> str:
    texto = " ".join((html or "").split())
    return texto[:limite]


def _limpar_texto(valor) -> str:
    if valor is None:
        return ""
    return str(valor).strip()


def enriquecer_produto_com_ia(dados: Dict, html: str, url: str) -> Dict:
    base = dict(dados or {})

    if not _api_key():
        base["ia_enriquecida"] = "nao"
        return base

    try:
        from openai import OpenAI

        client = OpenAI(api_key=_api_key())
        prompt_sistema = (
            "Você extrai dados de páginas de produto de e-commerce em português do Brasil. "
            "Receba um JSON pré-extraído e um trecho do HTML. "
            "Corrija apenas quando houver evidência clara no HTML. "
            "Retorne somente JSON válido com as chaves: "
            "nome, descricao_curta, codigo, gtin, preco, preco_custo, marca, categoria, ncm, cest, unidade, imagens, disponibilidade_site. "
            "Para imagens, retorne uma string com URLs separadas por ' | '. "
            "Não invente dados ausentes. "
            "GTIN deve conter só números com 8 a 14 dígitos. "
            "Preço deve usar ponto decimal, exemplo 149.90."
        )
        prompt_usuario = {
            "url": url,
            "dados_extraidos": base,
            "html_resumido": _compactar_html(html),
        }

        resposta = client.responses.create(
            model="gpt-4.1-mini",
            temperature=0,
            input=[
                {"role": "system", "content": prompt_sistema},
                {"role": "user", "content": json.dumps(prompt_usuario, ensure_ascii=False)},
            ],
        )

        texto = getattr(resposta, "output_text", "") or ""
        texto = texto.strip()
        if not texto:
            base["ia_enriquecida"] = "nao"
            return base

        corrigido = json.loads(texto)
        if not isinstance(corrigido, dict):
            base["ia_enriquecida"] = "nao"
            return base

        for chave in [
            "nome",
            "descricao_curta",
            "codigo",
            "gtin",
            "preco",
            "preco_custo",
            "marca",
            "categoria",
            "ncm",
            "cest",
            "unidade",
            "imagens",
            "disponibilidade_site",
        ]:
            valor = _limpar_texto(corrigido.get(chave, ""))
            if valor:
                base[chave] = valor

        if _limpar_texto(base.get("preco")) and not _limpar_texto(base.get("preco_custo")):
            base["preco_custo"] = _limpar_texto(base.get("preco"))

        base["ia_enriquecida"] = "sim"
        return base
    except Exception:
        base["ia_enriquecida"] = "nao"
        return base
