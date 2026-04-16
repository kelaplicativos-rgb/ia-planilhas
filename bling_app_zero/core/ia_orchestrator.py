
from __future__ import annotations

"""
Shim de compatibilidade.

Mantém o caminho antigo bling_app_zero.core.ia_orchestrator funcionando,
mas delega toda a execução para o novo pacote bling_app_zero.agent.
"""

from bling_app_zero.agent.agent_orchestrator import (
    IAPlanoExecucao,
    executar_fluxo_real_com_ia,
    interpretar_comando_usuario,
    marcar_etapa_manual,
    plano_para_json,
    pode_ir_para_final,
    pode_ir_para_mapeamento,
    resumo_execucao_atual,
)

__all__ = [
    "IAPlanoExecucao",
    "executar_fluxo_real_com_ia",
    "interpretar_comando_usuario",
    "marcar_etapa_manual",
    "plano_para_json",
    "pode_ir_para_final",
    "pode_ir_para_mapeamento",
    "resumo_execucao_atual",
]
