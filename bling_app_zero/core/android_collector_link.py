from __future__ import annotations

import os

DEFAULT_ANDROID_COLLECTOR_APK_URL = 'https://github.com/kelaplicativos-rgb/ia-planilhas/releases/latest/download/mapeiaai-coletor-android.apk'
ANDROID_COLLECTOR_SECRETS = (
    'MAPEIAAI_ANDROID_COLLECTOR_APK_URL',
    'MAPEIAAI_COLETOR_ANDROID_APK_URL',
    'ANDROID_COLLECTOR_APK_URL',
)
RESPONSIBLE_FILE = 'bling_app_zero/core/android_collector_link.py'


def _secret_value(name: str) -> str:
    value = str(os.environ.get(name) or '').strip()
    if value:
        return value
    try:
        import streamlit as st
        return str(st.secrets.get(name, '') or '').strip()
    except Exception:
        return ''


def android_collector_apk_url() -> str:
    for name in ANDROID_COLLECTOR_SECRETS:
        value = _secret_value(name)
        if value:
            return value
    return DEFAULT_ANDROID_COLLECTOR_APK_URL


def android_collector_apk_source() -> str:
    for name in ANDROID_COLLECTOR_SECRETS:
        if _secret_value(name):
            return name
    return 'default_github_release_latest'


__all__ = [
    'ANDROID_COLLECTOR_SECRETS',
    'DEFAULT_ANDROID_COLLECTOR_APK_URL',
    'RESPONSIBLE_FILE',
    'android_collector_apk_source',
    'android_collector_apk_url',
]
