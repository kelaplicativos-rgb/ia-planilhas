from __future__ import annotations

import json
import streamlit as st

# ==========================================================
# IA (OPENAI)
# ==========================================================
try:
    from openai import OpenAI
except Exception:
    OpenAI = None


def extrair_com_ia(html: str, url: str) -> dict:

    if not OpenAI:
        return {}

    try:
        client = OpenAI(api_key=st.secrets.get("OPENAI_API_KEY"))

        prompt = f"""
Extraia dados de produto do HTML abaixo.

Retorne JSON com:
- Nome
- Preco
- Descricao
- Marca
- Categoria
- Imagens (lista)
- Estoque (0 ou número)

HTML:
{html[:15000]}
"""

        resp = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )

        texto = resp.choices[0].message.content

        data = json.loads(texto)

        return {
            "Nome": data.get("Nome", ""),
            "Preço": data.get("Preco", ""),
            "Descrição": data.get("Descricao", ""),
            "Marca": data.get("Marca", ""),
            "Categoria": data.get("Categoria", ""),
            "URL Imagens Externas": " | ".join(data.get("Imagens", [])),
            "Link Externo": url,
            "Estoque": int(data.get("Estoque", 0)),
        }

    except Exception:
        return {}
