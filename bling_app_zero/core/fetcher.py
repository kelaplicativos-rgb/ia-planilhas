from __future__ import annotations

import time
import random
import requests


# ==========================================================
# CONFIG
# ==========================================================
TIMEOUT = 15
RETRIES = 3

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Mozilla/5.0 (Linux; Android 10)",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
]


# ==========================================================
# HEADERS DINÂMICOS
# ==========================================================
def _get_headers():
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
    }


# ==========================================================
# FETCH PRINCIPAL
# ==========================================================
def fetch_url(url: str) -> str | None:

    for tentativa in range(RETRIES):

        try:
            response = requests.get(
                url,
                headers=_get_headers(),
                timeout=TIMEOUT,
            )

            if response.status_code == 200:
                return response.text

        except requests.exceptions.SSLError:
            # 🔥 fallback SSL
            try:
                response = requests.get(
                    url,
                    headers=_get_headers(),
                    timeout=TIMEOUT,
                    verify=False,
                )

                if response.status_code == 200:
                    return response.text

            except Exception:
                pass

        except Exception:
            pass

        # 🔥 pequeno delay anti-bloqueio
        time.sleep(random.uniform(0.5, 1.5))

    return None
