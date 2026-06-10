"""BLINGFIX 90 - unified site API capture runtime guard.

Imported automatically by Python when the repository root is on sys.path.
It patches the Streamlit site capture modules after import so the same
site-search engine is used for cadastro, estoque and atualizacao_preco.

BLINGFIX 90 adds a hard stop for the 42% hang: direct API site operations use a
small first batch during extraction. This prevents the SmartScan extraction step
from staying indefinitely on the "Produtos localizados / Extraindo dados" phase.
"""
from __future__ import annotations

import importlib.abc
import importlib.machinery
import sys
from types import ModuleType
from typing import Any

TARGET_MODULES = {
    "bling_app_zero.ui.site_panel",
    "bling_app_zero.ui.site_panel_capture",
}
DIRECT_API_SITE_OPERATIONS = {"cadastro", "estoque", "atualizacao_preco"}
SITE_API_CAPTURE_POLICIES: dict[str, dict[str, Any]] = {
    "cadastro": {
        "max_pages": 12,
        "max_products": 40,
        "max_depth": 1,
        "send_mode": "produto",
    },
    "estoque": {
        "max_pages": 12,
        "max_products": 80,
        "max_depth": 1,
        "send_mode": "estoque",
    },
    "atualizacao_preco": {
        "max_pages": 12,
        "max_products": 60,
        "max_depth": 1,
        "send_mode": "preco",
    },
}


def _policy(operation: object) -> dict[str, Any]:
    op = str(operation or "").strip().lower()
    return dict(SITE_API_CAPTURE_POLICIES.get(op) or SITE_API_CAPTURE_POLICIES["cadastro"])


def _is_direct_api_operation(module: ModuleType, operation: object) -> bool:
    op = str(operation or "").strip().lower()
    try:
        contract = module.active_contract()
        return bool(contract.is_api and contract.operation == op and op in DIRECT_API_SITE_OPERATIONS)
    except Exception:
        return False


def _audit(module: ModuleType, event: str, *, status: str = "OK", details: dict[str, Any] | None = None) -> None:
    try:
        module.add_audit_event(
            event,
            area="SITE",
            step="entrada",
            status=status,
            details={**(details or {}), "responsible_file": "sitecustomize.py", "blingfix": "90_stop_42_percent_extraction"},
        )
    except Exception:
        pass


def _patch_site_panel(module: ModuleType) -> None:
    if getattr(module, "_blingfix_90_site_api_extraction_guard_patched", False):
        return

    module.SITE_API_CAPTURE_POLICIES = SITE_API_CAPTURE_POLICIES
    module.DIRECT_API_SITE_OPERATIONS = DIRECT_API_SITE_OPERATIONS
    module.SUPPORTED_SITE_OPERATIONS = {module.UNIVERSAL_OPERATION, *DIRECT_API_SITE_OPERATIONS}

    def _is_direct_api_site_mode(operation: str) -> bool:
        return _is_direct_api_operation(module, operation)

    def _api_site_max_pages(operation: str) -> int:
        return int(_policy(operation)["max_pages"])

    def _api_site_max_products(operation: str) -> int:
        return int(_policy(operation)["max_products"])

    def _api_site_max_depth(operation: str) -> int:
        return int(_policy(operation)["max_depth"])

    def _api_site_send_mode(operation: str) -> str:
        return str(_policy(operation)["send_mode"])

    def _scan_total_options(operation: str) -> dict[str, Any]:
        if _is_direct_api_site_mode(operation):
            op = str(operation or "").strip().lower()
            return {
                "enabled": True,
                "max_pages": _api_site_max_pages(op),
                "max_products": _api_site_max_products(op),
                "max_depth": _api_site_max_depth(op),
                "scan_total_ui": True,
                "stock_balance_only": op == "estoque",
                "stock_full_site_scan": False,
                "stock_api_fast_batch": op == "estoque",
                "stock_api_skip_predeep_discovery": op == "estoque",
                "cadastro_api_fast_batch": op == "cadastro",
                "cadastro_api_skip_predeep_discovery": op == "cadastro",
                "price_api_fast_batch": op == "atualizacao_preco",
                "price_api_skip_predeep_discovery": op == "atualizacao_preco",
                "skip_predeep_discovery": True,
                "unified_api_site_engine": True,
                "api_site_batch_contract": op,
                "api_site_send_mode": _api_site_send_mode(op),
                "site_api_capture_policy": "unified_site_api_capture_v2_stop_42_percent",
                "api_direct_first_batch_only": True,
                "disable_deep_extraction_after_discovery": True,
                "budget_seconds": min(int(getattr(module, "SITE_PANEL_DISCOVERY_BUDGET_SECONDS", 45)), 20),
            }
        return {
            "enabled": True,
            "max_pages": getattr(module, "SCAN_TOTAL_MAX_PAGES", 120),
            "max_products": getattr(module, "SCAN_TOTAL_MAX_PRODUCTS", 500),
            "max_depth": getattr(module, "SCAN_TOTAL_MAX_DEPTH", 2),
            "scan_total_ui": True,
            "stock_balance_only": False,
            "stock_full_site_scan": False,
            "stock_api_fast_batch": False,
            "stock_api_skip_predeep_discovery": False,
            "cadastro_api_fast_batch": False,
            "cadastro_api_skip_predeep_discovery": False,
            "price_api_fast_batch": False,
            "price_api_skip_predeep_discovery": False,
            "skip_predeep_discovery": False,
            "unified_api_site_engine": False,
            "api_site_batch_contract": "",
            "api_site_send_mode": "",
            "site_api_capture_policy": "public_full_scan",
            "budget_seconds": getattr(module, "SITE_PANEL_DISCOVERY_BUDGET_SECONDS", 45),
        }

    def _render_scan_total_notice(operation: str) -> None:
        if _is_direct_api_site_mode(operation):
            op = str(operation or "").strip().lower()
            if op == "cadastro":
                module.orange_warning("Cadastro/API usa busca única em lote curto: captura rápida para liberar envio ao Bling sem travar nos 42%.")
            elif op == "estoque":
                module.orange_warning("Estoque/API usa busca única em lote curto: captura rápida de saldo/identificação sem travar nos 42%.")
            elif op == "atualizacao_preco":
                module.orange_warning("Preço/API usa busca única em lote curto: captura rápida de preço sem travar nos 42%.")
            else:
                module.orange_warning("API usa busca única em lote curto sem travar nos 42%.")
            return
        module.orange_warning("Busca completa ativa: o sistema procura produtos no site e captura os dados conforme o contrato ativo.")

    module._is_direct_api_site_mode = _is_direct_api_site_mode
    module._api_site_max_pages = _api_site_max_pages
    module._api_site_max_products = _api_site_max_products
    module._api_site_max_depth = _api_site_max_depth
    module._api_site_send_mode = _api_site_send_mode
    module._scan_total_options = _scan_total_options
    module._render_scan_total_notice = _render_scan_total_notice
    module._blingfix_90_site_api_extraction_guard_patched = True

    _audit(module, "site_api_unified_panel_patch_installed", details={"operations": sorted(DIRECT_API_SITE_OPERATIONS), "policy": "v2_stop_42_percent"})


def _force_options(module: ModuleType, operation: object, options: dict[str, Any] | None) -> dict[str, Any]:
    forced = dict(options or {})
    op = str(operation or "").strip().lower()
    if not _is_direct_api_operation(module, op):
        return forced

    policy = _policy(op)
    forced.update(
        {
            "enabled": True,
            "max_pages": int(policy["max_pages"]),
            "max_products": int(policy["max_products"]),
            "max_depth": int(policy["max_depth"]),
            "scan_total_ui": True,
            "stock_balance_only": op == "estoque",
            "stock_full_site_scan": False,
            "stock_api_fast_batch": op == "estoque",
            "stock_api_skip_predeep_discovery": op == "estoque",
            "cadastro_api_fast_batch": op == "cadastro",
            "cadastro_api_skip_predeep_discovery": op == "cadastro",
            "price_api_fast_batch": op == "atualizacao_preco",
            "price_api_skip_predeep_discovery": op == "atualizacao_preco",
            "skip_predeep_discovery": True,
            "unified_api_site_engine": True,
            "api_site_batch_contract": op,
            "api_site_send_mode": str(policy["send_mode"]),
            "site_api_capture_policy": "unified_site_api_capture_v2_stop_42_percent_hard_guard",
            "api_direct_first_batch_only": True,
            "disable_deep_extraction_after_discovery": True,
            "budget_seconds": 20,
        }
    )
    return forced


def _patch_site_panel_capture(module: ModuleType) -> None:
    if getattr(module, "_blingfix_90_site_api_extraction_guard_patched", False):
        return

    module.DIRECT_API_SITE_OPERATIONS = DIRECT_API_SITE_OPERATIONS
    module.DIRECT_API_SITE_LIMITS = {
        op: {"max_pages": int(policy["max_pages"]), "max_products": int(policy["max_products"])}
        for op, policy in SITE_API_CAPTURE_POLICIES.items()
    }

    original_run_site_capture = module.run_site_capture
    original_run_current_site_engine = module._run_current_site_engine

    def _skip_predeep_discovery(operation: str, options: dict[str, Any]) -> bool:
        if bool(options.get("skip_predeep_discovery") or options.get("price_api_skip_predeep_discovery")):
            return True
        return _is_direct_api_operation(module, operation)

    def capture_limits_for_operation(operation: str, deep_options: dict[str, Any] | None) -> tuple[int, int, bool]:
        options = _force_options(module, operation, deep_options)
        op = str(operation or "").strip().lower()
        if _is_direct_api_operation(module, op):
            policy = _policy(op)
            return int(policy["max_pages"]), int(policy["max_products"]), True

        if module._is_stock_balance_only(operation, options):
            return (
                min(max(int(options.get("max_pages") or 0), module.STOCK_BALANCE_PAGES_LIMIT), module.STOCK_BALANCE_PAGES_LIMIT),
                min(max(int(options.get("max_products") or 0), module.STOCK_BALANCE_PRODUCTS_LIMIT), module.STOCK_BALANCE_PRODUCTS_LIMIT),
                True,
            )
        if bool(options.get("enabled")):
            return (
                min(max(int(options.get("max_pages") or 0), module.ALL_PAGES_LIMIT), module.ALL_PAGES_LIMIT),
                min(max(int(options.get("max_products") or 0), module.ALL_PRODUCTS_LIMIT), module.ALL_PRODUCTS_LIMIT),
                True,
            )
        return module.ALL_PAGES_LIMIT, module.ALL_PRODUCTS_LIMIT, True

    def guarded_engine_runner(**kwargs):
        operation = str(kwargs.get("operation") or "").strip().lower()
        if _is_direct_api_operation(module, operation):
            policy = _policy(operation)
            kwargs["all_products"] = True
            kwargs["max_pages"] = min(int(kwargs.get("max_pages") or policy["max_pages"]), int(policy["max_pages"]))
            kwargs["max_products"] = min(int(kwargs.get("max_products") or policy["max_products"]), int(policy["max_products"]))
            kwargs["max_depth"] = min(int(kwargs.get("max_depth") or policy["max_depth"]), int(policy["max_depth"]))
            _audit(
                module,
                "site_api_42_percent_extraction_guard_applied",
                details={
                    "operation": operation,
                    "max_pages": kwargs["max_pages"],
                    "max_products": kwargs["max_products"],
                    "max_depth": kwargs["max_depth"],
                    "policy": "v2_stop_42_percent",
                },
            )
        return original_run_current_site_engine(**kwargs)

    def run_site_capture(*, operation: str, raw_urls: str, requested_columns, df_modelo_cadastro, df_modelo_estoque, df_modelo, deep_options=None) -> None:
        options = _force_options(module, operation, deep_options)
        if _is_direct_api_operation(module, operation):
            _audit(
                module,
                "site_api_unified_capture_options_forced",
                details={
                    "operation": operation,
                    "feature_contract": getattr(module.active_contract(), "key", ""),
                    "max_pages": int(options.get("max_pages") or 0),
                    "max_products": int(options.get("max_products") or 0),
                    "max_depth": int(options.get("max_depth") or 0),
                    "skip_predeep_discovery": bool(options.get("skip_predeep_discovery")),
                    "unified_api_site_engine": bool(options.get("unified_api_site_engine")),
                    "api_site_batch_contract": options.get("api_site_batch_contract", ""),
                    "api_site_send_mode": options.get("api_site_send_mode", ""),
                    "site_api_capture_policy": options.get("site_api_capture_policy", ""),
                    "api_direct_first_batch_only": bool(options.get("api_direct_first_batch_only")),
                    "fix_reason": "evitar_travamento_42_porcento_na_extracao",
                },
            )
        return original_run_site_capture(
            operation=operation,
            raw_urls=raw_urls,
            requested_columns=requested_columns,
            df_modelo_cadastro=df_modelo_cadastro,
            df_modelo_estoque=df_modelo_estoque,
            df_modelo=df_modelo,
            deep_options=options,
        )

    module._skip_predeep_discovery = _skip_predeep_discovery
    module.capture_limits_for_operation = capture_limits_for_operation
    module._run_current_site_engine = guarded_engine_runner
    module.run_site_capture = run_site_capture
    module._blingfix_90_site_api_extraction_guard_patched = True

    _audit(module, "site_api_unified_capture_patch_installed", details={"operations": sorted(DIRECT_API_SITE_OPERATIONS), "policy": "v2_stop_42_percent"})


def _patch_module(module: ModuleType) -> None:
    name = getattr(module, "__name__", "")
    if name == "bling_app_zero.ui.site_panel":
        _patch_site_panel(module)
    elif name == "bling_app_zero.ui.site_panel_capture":
        _patch_site_panel_capture(module)


class _BlingfixLoader(importlib.abc.Loader):
    def __init__(self, wrapped: importlib.abc.Loader) -> None:
        self._wrapped = wrapped

    def create_module(self, spec):
        create_module = getattr(self._wrapped, "create_module", None)
        if create_module is None:
            return None
        return create_module(spec)

    def exec_module(self, module: ModuleType) -> None:
        self._wrapped.exec_module(module)
        _patch_module(module)


class _BlingfixFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname: str, path=None, target=None):
        if fullname not in TARGET_MODULES:
            return None
        spec = importlib.machinery.PathFinder.find_spec(fullname, path)
        if spec is None or spec.loader is None:
            return None
        if isinstance(spec.loader, _BlingfixLoader):
            return spec
        spec.loader = _BlingfixLoader(spec.loader)
        return spec


for _module_name in list(TARGET_MODULES):
    loaded = sys.modules.get(_module_name)
    if loaded is not None:
        _patch_module(loaded)

if not any(isinstance(finder, _BlingfixFinder) for finder in sys.meta_path):
    sys.meta_path.insert(0, _BlingfixFinder())
