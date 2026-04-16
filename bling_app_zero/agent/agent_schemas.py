
from __future__ import annotations

from typing import Any, Dict, List


def schema_plano_execucao() -> Dict[str, Any]:
    return {
        "name": "SchemaPlanoExecucao",
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "etapa_atual": {
                    "type": "string",
                    "enum": [
                        "origem",
                        "normalizacao",
                        "mapeamento",
                        "precificacao",
                        "validacao",
                        "final",
                    ],
                },
                "acao": {"type": "string"},
                "ferramenta": {"type": "string"},
                "motivo": {"type": "string"},
                "pode_avancar": {"type": "boolean"},
            },
            "required": [
                "etapa_atual",
                "acao",
                "ferramenta",
                "motivo",
                "pode_avancar",
            ],
        },
    }


def schema_mapeamento_bling() -> Dict[str, Any]:
    return {
        "name": "SchemaMapeamentoBling",
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "operacao": {
                    "type": "string",
                    "enum": ["cadastro", "estoque"],
                },
                "confianca": {
                    "type": "number",
                    "minimum": 0.0,
                    "maximum": 1.0,
                },
                "campos_obrigatorios_ok": {"type": "boolean"},
                "mapeamentos": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "coluna_origem": {"type": "string"},
                            "coluna_bling": {"type": "string"},
                            "transformacao": {"type": "string"},
                            "obrigatorio": {"type": "boolean"},
                        },
                        "required": [
                            "coluna_origem",
                            "coluna_bling",
                            "transformacao",
                            "obrigatorio",
                        ],
                    },
                },
                "pendencias": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
            "required": [
                "operacao",
                "confianca",
                "campos_obrigatorios_ok",
                "mapeamentos",
                "pendencias",
            ],
        },
    }


def schema_validacao_final() -> Dict[str, Any]:
    return {
        "name": "SchemaValidacaoFinal",
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "aprovado": {"type": "boolean"},
                "erros": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "avisos": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "linhas_validas": {
                    "type": "integer",
                    "minimum": 0,
                },
                "linhas_invalidas": {
                    "type": "integer",
                    "minimum": 0,
                },
                "corrigido_automaticamente": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
            "required": [
                "aprovado",
                "erros",
                "avisos",
                "linhas_validas",
                "linhas_invalidas",
                "corrigido_automaticamente",
            ],
        },
    }


def schema_saida_final() -> Dict[str, Any]:
    return {
        "name": "SchemaSaidaFinal",
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["ok", "erro", "revisao"],
                },
                "arquivo_gerado": {"type": "string"},
                "tipo_saida": {
                    "type": "string",
                    "enum": ["csv"],
                },
                "preview_disponivel": {"type": "boolean"},
                "mensagem_usuario": {"type": "string"},
            },
            "required": [
                "status",
                "arquivo_gerado",
                "tipo_saida",
                "preview_disponivel",
                "mensagem_usuario",
            ],
        },
    }


def build_response_format(schema_def: Dict[str, Any]) -> Dict[str, Any]:
    """
    Helper para integrar com Responses API / Structured Outputs.
    """
    return {
        "type": "json_schema",
        "json_schema": {
            "name": schema_def["name"],
            "schema": schema_def["schema"],
            "strict": True,
        },
    }


def get_all_agent_schemas() -> List[Dict[str, Any]]:
    return [
        schema_plano_execucao(),
        schema_mapeamento_bling(),
        schema_validacao_final(),
        schema_saida_final(),
  ]
