👉 isso quebra o `json.loads`

---

## ❌ 2. Falta normalização de preço
Pode vir:
- `"1.299,90"`
- `"R$ 1.299"`

👉 precisa limpar

---

## ❌ 3. Estoque pode vir string
👉 precisa garantir int seguro

---

# 🚀 CORREÇÃO (NÍVEL PRODUÇÃO)

## 📁 Arquivo:
`bling_app_zero/core/ia_extractor.py`

---

# ✅ CÓDIGO COMPLETO CORRIGIDO

```python
from __future__ import annotations

import json
import re
import streamlit as st

# ==========================================================
# IA (OPENAI)
# ==========================================================
try:
    from openai import OpenAI
except Exception:
    OpenAI = None


# ==========================================================
# HELPERS
# ==========================================================
def _safe_json(texto: str) -> dict:
    try:
        texto = texto.strip()

        # remove ```json ```
        texto = re.sub(r"```json|```", "", texto, flags=re.IGNORECASE).strip()

        return json.loads(texto)
    except Exception:
        return {}


def _numero(valor: str) -> str:
    valor = str(valor or "")
    valor = valor.replace("R$", "").replace(" ", "")
    match = re.search(r"(\d[\d\.,]*)", valor)
    return match.group(1) if match else ""


def _to_int(valor) -> int:
    try:
        return int(float(str(valor).replace(",", ".")))
    except Exception:
        return 0


# ==========================================================
# MAIN
# ==========================================================
def extrair_com_ia(html: str, url: str) -> dict:

    if not OpenAI:
        return {}

    try:
        client = OpenAI(api_key=st.secrets.get("OPENAI_API_KEY"))

        prompt = f"""
Extraia dados de produto do HTML abaixo.

Responda SOMENTE JSON válido.

Campos obrigatórios:
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

        texto = resp.choices[0].message.content or ""

        data = _safe_json(texto)

        if not data:
            return {}

        return {
            "Nome": data.get("Nome", ""),
            "Preço": _numero(data.get("Preco", "")),
            "Descrição": data.get("Descricao", ""),
            "Marca": data.get("Marca", ""),
            "Categoria": data.get("Categoria", ""),
            "URL Imagens Externas": " | ".join(data.get("Imagens", [])),
            "Link Externo": url,
            "Estoque": _to_int(data.get("Estoque", 0)),
        }

    except Exception:
        return {}
