import random
import time
import requests
import urllib3

from core.logger import log

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

session = requests.Session()


def get_headers():
    return {
        "User-Agent": random.choice([
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Mobile Safari/537.36",
        ]),
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Connection": "keep-alive",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }


def fetch(url, timeout=12):
    for tentativa in range(2):
        try:
            time.sleep(random.uniform(0.15, 0.45))
            r = session.get(
                url,
                headers=get_headers(),
                timeout=timeout,
                allow_redirects=True,
                verify=False,
            )

            if r.status_code == 200:
                r.encoding = r.apparent_encoding or "utf-8"
                return r.text

            log(f"fetch status={r.status_code} url={url}")

        except Exception as e:
            log(f"ERRO fetch tentativa={tentativa + 1} url={url} detalhe={e}")

    return None
