from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from bling_app_zero.core.system_inventory import (
    SYSTEM_INVENTORY,
    STATUS_ATIVO,
    SystemInventoryItem,
    inventory_markdown as official_inventory_markdown,
    inventory_payload as official_inventory_payload,
    inventory_summary as official_inventory_summary,
    registered_paths as official_registered_paths,
)

RESPONSIBLE_FILE = 'bling_app_zero/core/system_inventory_runtime.py'
IGNORED_DIR_NAMES = {
    '.git',
    '.github',
    '.idea',
    '.mypy_cache',
    '.pytest_cache',
    '.ruff_cache',
    '.streamlit',
    '.venv',
    '__pycache__',
    'node_modules',
    'venv',
}

RUNTIME_EXTRA_INVENTORY: tuple[SystemInventoryItem, ...] = (
    SystemInventoryItem(
        id='mirror_planner',
        name='Planejador seguro de espelhamento site → Bling',
        status=STATUS_ATIVO,
        layer='ORQUESTRACAO',
        purpose='Classifica, em modo simulação, quais linhas do site estão prontas para atualização de estoque e quais parecem produtos novos para cadastro.',
        owner_spine='Flow Spine / Site Capture Spine',
        main_paths=('bling_app_zero/core/bling_mirror_planner.py', 'bling_app_zero/ui/mirror_planner_panel.py'),
        risk='Não executa rotina em segundo plano; apenas planeja e separa decisões. A execução recorrente deve ser ligada depois com confirmação e logs.',
        action='Manter como simulação/revisão até os diagnósticos confirmarem estabilidade.',
    ),
    SystemInventoryItem(
        id='mirror_apply_bundle',
        name='Preparador assistido de itens revisados do espelhamento',
        status=STATUS_ATIVO,
        layer='ORQUESTRACAO',
        purpose='Separa as decisões revisadas em duas bases: estoque revisado e produtos novos revisados, sem enviar nada automaticamente.',
        owner_spine='Mirror Planner / Flow Spine',
        main_paths=('bling_app_zero/core/bling_mirror_apply.py',),
        risk='Deve continuar apenas preparando/exportando dados até ser conectado ao fluxo oficial com confirmação explícita.',
        action='Próximo passo: criar ponte para enviar as bases revisadas ao preview/download/envio oficial, sem pular conferência.',
    ),
    SystemInventoryItem(
        id='mirror_official_bridge',
        name='Ponte segura do espelhamento para o fluxo oficial',
        status=STATUS_ATIVO,
        layer='ORQUESTRACAO',
        purpose='Coloca a base revisada do espelhamento no fluxo oficial, preservando preview, validação e confirmação antes de qualquer saída.',
        owner_spine='Mirror Planner / Flow Spine',
        main_paths=('bling_app_zero/core/bling_mirror_bridge.py',),
        risk='Não deve ser usada para pular revisão. A ponte apenas prepara a origem e redireciona para as etapas oficiais.',
        action='Manter logs e diagnóstico para confirmar que preview/download/envio oficial continuam obrigatórios.',
    ),
    SystemInventoryItem(
        id='mirror_monitor_config',
        name='Configuração persistente do espelhamento monitorado',
        status=STATUS_ATIVO,
        layer='ORQUESTRACAO',
        purpose='Guarda toggle, site, depósito, modo, intervalo e status de monitoramento sem iniciar loop dentro do Streamlit.',
        owner_spine='Mirror Planner / Diagnóstico',
        main_paths=('bling_app_zero/core/bling_mirror_config.py', 'bling_app_zero/ui/mirror_monitor_panel.py'),
        risk='É apenas configuração e status. Executor recorrente real deve ser criado separado da tela Streamlit.',
        action='Próximo passo: criar executor agendado externo/seguro que leia esta configuração.',
    ),
    SystemInventoryItem(
        id='mirror_persistent_store',
        name='Store persistente do espelhamento',
        status=STATUS_ATIVO,
        layer='ORQUESTRACAO',
        purpose='Salva configuração, status e histórico curto de execuções fora do session_state, permitindo uso por executor externo.',
        owner_spine='Mirror Monitor / Executor',
        main_paths=('bling_app_zero/core/bling_mirror_store.py',),
        risk='Store local em arquivo pode ser efêmero em alguns provedores; para produção robusta, migrar para banco externo.',
        action='Usar variável de ambiente BLING_MIRROR_STORE_PATH no deploy ou migrar para banco persistente.',
    ),
    SystemInventoryItem(
        id='mirror_discovery_cycle',
        name='Ciclo seguro de descoberta do espelhamento',
        status=STATUS_ATIVO,
        layer='JOB',
        purpose='Executa a primeira etapa real do agendador: varredura controlada do site configurado, com orçamento, limites e log persistente.',
        owner_spine='Mirror Store / Executor',
        main_paths=('bling_app_zero/core/bling_mirror_cycle.py',),
        risk='Ainda não compara contra o Bling e não aplica alterações; apenas descobre URLs prováveis de produto.',
        action='Próximo passo: conectar extração completa, comparação com Bling e envio somente de diferenças.',
    ),
    SystemInventoryItem(
        id='mirror_scheduled_executor',
        name='Executor agendável do espelhamento',
        status=STATUS_ATIVO,
        layer='JOB',
        purpose='Permite execução por Cron/Worker fora da tela, lendo a configuração persistente, rodando descoberta controlada e registrando status sem loop no Streamlit.',
        owner_spine='Mirror Store / Render Cron',
        main_paths=('bling_app_zero/jobs/mirror_executor.py',),
        risk='Aplicação real por API ainda está bloqueada até ligar extração, comparação com Bling e logs transacionais.',
        action='Próximo passo: ligar o executor ao motor de captura + comparação + envio somente de diferenças.',
    ),
)


def inventory_items(statuses: Iterable[str] | None = None) -> tuple[SystemInventoryItem, ...]:
    items = tuple(SYSTEM_INVENTORY) + tuple(RUNTIME_EXTRA_INVENTORY)
    wanted = {str(status).strip().upper() for status in statuses or () if str(status).strip()}
    if not wanted:
        return items
    return tuple(item for item in items if item.status in wanted)


def registered_paths() -> set[str]:
    paths = set(official_registered_paths())
    for item in RUNTIME_EXTRA_INVENTORY:
        for path in item.main_paths:
            normalized = str(path or '').replace('\\', '/').strip()
            if normalized:
                paths.add(normalized)
    return paths


def _project_root() -> Path:
    # .../bling_app_zero/core/system_inventory_runtime.py -> raiz do projeto
    return Path(__file__).resolve().parents[2]


def _relative_path(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except Exception:
        return path.as_posix()


def _should_ignore(path: Path) -> bool:
    return any(part in IGNORED_DIR_NAMES for part in path.parts)


def runtime_repository_python_files() -> tuple[str, ...]:
    """Varre os arquivos Python reais disponíveis no runtime do deploy.

    Diferente da varredura inicial do inventário oficial, esta cobre a raiz do
    repositório também. Assim `app.py` e qualquer novo `.py` criado pouco antes
    do diagnóstico aparecem no ZIP, mesmo quando ainda não foram cadastrados
    manualmente no inventário oficial.
    """
    root = _project_root()
    if not root.exists():
        return tuple()
    files: list[str] = []
    for path in root.rglob('*.py'):
        if _should_ignore(path):
            continue
        files.append(_relative_path(path, root))
    return tuple(sorted(set(files)))


def unregistered_repository_python_files() -> tuple[str, ...]:
    registered = registered_paths()
    files = runtime_repository_python_files()
    return tuple(path for path in files if path not in registered and not path.endswith('/__init__.py'))


def runtime_repository_snapshot() -> dict[str, Any]:
    files = runtime_repository_python_files()
    unregistered = unregistered_repository_python_files()
    return {
        'scope': 'repository_root_and_bling_app_zero',
        'python_files_total': len(files),
        'registered_paths_total': len(registered_paths()),
        'unregistered_files_total': len(unregistered),
        'unregistered_files': list(unregistered),
        'all_python_files': list(files),
        'responsible_file': RESPONSIBLE_FILE,
    }


def inventory_summary() -> dict[str, Any]:
    summary = dict(official_inventory_summary())
    snapshot = runtime_repository_snapshot()
    extra_count = len(RUNTIME_EXTRA_INVENTORY)
    status_counts = dict(summary.get('status_counts') or {})
    layer_counts = dict(summary.get('layer_counts') or {})
    for item in RUNTIME_EXTRA_INVENTORY:
        status_counts[item.status] = int(status_counts.get(item.status, 0)) + 1
        layer_counts[item.layer] = int(layer_counts.get(item.layer, 0)) + 1
    summary['status_counts'] = status_counts
    summary['layer_counts'] = layer_counts
    summary['total_subsystems'] = int(summary.get('total_subsystems') or 0) + extra_count
    summary['active_subsystems'] = int(summary.get('active_subsystems') or 0) + sum(1 for item in RUNTIME_EXTRA_INVENTORY if item.status == STATUS_ATIVO)
    summary['runtime_extra_inventory_total'] = extra_count
    summary['runtime_repository_python_files_total'] = snapshot.get('python_files_total', 0)
    summary['runtime_repository_unregistered_files_total'] = snapshot.get('unregistered_files_total', 0)
    summary['runtime_repository_scan_scope'] = snapshot.get('scope')
    summary['runtime_repository_responsible_file'] = RESPONSIBLE_FILE
    return summary


def inventory_payload() -> dict[str, Any]:
    payload = dict(official_inventory_payload())
    official_items = list(payload.get('items') or [])
    official_items.extend(item.to_dict() for item in RUNTIME_EXTRA_INVENTORY)
    repository_snapshot = runtime_repository_snapshot()
    payload['items'] = official_items
    payload['runtime_extra_inventory'] = [item.to_dict() for item in RUNTIME_EXTRA_INVENTORY]
    payload['runtime_repository_file_snapshot'] = repository_snapshot
    payload['summary'] = inventory_summary()
    return payload


def inventory_markdown() -> str:
    base = official_inventory_markdown().rstrip()
    snapshot = runtime_repository_snapshot()
    lines = [base, '', '## Inventário runtime extra', '']
    for item in RUNTIME_EXTRA_INVENTORY:
        lines.append(f'### {item.id} · {item.status}')
        lines.append(f'**Nome:** {item.name}')
        lines.append(f'**Camada:** {item.layer}')
        lines.append(f'**Dono/Espinha:** {item.owner_spine}')
        lines.append(f'**Função:** {item.purpose}')
        if item.risk:
            lines.append(f'**Risco:** {item.risk}')
        if item.action:
            lines.append(f'**Ação:** {item.action}')
        lines.append('**Arquivos principais:**')
        for path in item.main_paths:
            lines.append(f'- `{path}`')
        lines.append('')
    lines.extend(['', '## Varredura automática ampliada do repositório', ''])
    lines.append(f'- Escopo: `{snapshot.get("scope")}`')
    lines.append(f'- Arquivos Python detectados no repositório/runtime: {snapshot.get("python_files_total", 0)}')
    lines.append(f'- Arquivos cadastrados no inventário oficial/runtime: {snapshot.get("registered_paths_total", 0)}')
    lines.append(f'- Arquivos ainda não cadastrados diretamente: {snapshot.get("unregistered_files_total", 0)}')
    unregistered = list(snapshot.get('unregistered_files') or [])
    if unregistered:
        lines.append('')
        lines.append('### Arquivos Python não cadastrados diretamente na varredura ampliada')
        for path in unregistered[:500]:
            lines.append(f'- `{path}`')
    lines.append('')
    lines.append('### Observação')
    lines.append('Esta seção cobre também `app.py` e novos arquivos `.py` fora de `bling_app_zero`, desde que já estejam presentes no deploy/runtime no momento em que o diagnóstico for gerado.')
    return '\n'.join(lines).strip() + '\n'


__all__ = [
    'RUNTIME_EXTRA_INVENTORY',
    'SYSTEM_INVENTORY',
    'inventory_items',
    'inventory_markdown',
    'inventory_payload',
    'inventory_summary',
    'registered_paths',
    'runtime_repository_python_files',
    'runtime_repository_snapshot',
    'unregistered_repository_python_files',
]
