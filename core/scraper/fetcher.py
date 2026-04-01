import random
import time

import requests

from core.logger import log

session = requests.Session()


def get_headers():
    return {
        "User-Agent": random.choice(
            [
                "Mozilla/5.0",
                "Mozilla/5.0 (Windows NT 10.0)",
                "Mozilla/5.0 (Android)",
                "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)",
            ]
        ),
        "Accept-Language": "pt-BR,pt;q=0.9",
        "Accept": "text/html,application/xhtml+xml",
        "Connection": "keep-alive",
    }


def fetch(url):
    for tentativa in range(3):
        try:
            time.sleep(random.uniform(0.4, 1.0))
            r = session.get(url, headers=get_headers(), timeout=20, verify=False)
            if r.status_code == 200:
                r.encoding = "utf-8"
                return r.text
            log(f"WARN fetch status={r.status_code} url={url}")
        except Exception as e:
            log(f"ERRO fetch tentativa={tentativa + 1} url={url} detalhe={e}")
    return None
