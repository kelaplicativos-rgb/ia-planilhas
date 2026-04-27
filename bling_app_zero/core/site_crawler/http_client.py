import requests


def build_session(auth_context=None):
    session = requests.Session()

    session.headers.update({
        "User-Agent": "Mozilla/5.0",
        "Accept": "*/*",
    })

    session.verify = False

    return session
