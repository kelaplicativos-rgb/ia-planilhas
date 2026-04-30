from __future__ import annotations

ETAPAS_ORDEM = ["origem", "precificacao", "mapeamento", "preview_final"]

ETAPAS_LABELS = {
    "origem": "1. Origem",
    "precificacao": "2. Precificação",
    "mapeamento": "3. Mapeamento",
    "preview_final": "4. Preview final",
}

APP_DEFAULTS = {
    "_boot_log_registrado": False,
    "site_auto_loop_ativo": False,
    "site_auto_intervalo_segundos": 60,
    "site_auto_status": "inativo",
    "site_auto_ultima_execucao": "",
    "site_auto_modo": "manual",
    "site_auto_ultima_url": "",
    "site_auto_ultimo_total_produtos": 0,
    "wizard_etapa_atual": "origem",
    "wizard_etapa_maxima": "origem",
    "ultima_etapa_renderizada": "",
    "_troca_etapa_em_andamento": False,
    "mostrar_log_debug_ui": False,
    "_ultima_etapa_logada_render": "",
    "_flow_lock_preview_final": False,
    "_flow_lock_origem": "",
}
