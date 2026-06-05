from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable

RESPONSIBLE_FILE = 'bling_app_zero/core/system_inventory.py'

STATUS_ATIVO = 'ATIVO'
STATUS_LEGADO = 'LEGADO'
STATUS_SUBSTITUIDO = 'SUBSTITUIDO'
STATUS_RISCO = 'RISCO'
STATUS_REMOVER_DEPOIS = 'REMOVER_DEPOIS'


@dataclass(frozen=True)
class SystemInventoryItem:
    id: str
    name: str
    status: str
    layer: str
    purpose: str
    owner_spine: str
    main_paths: tuple[str, ...]
    risk: str = ''
    action: str = ''

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data['main_paths'] = list(self.main_paths)
        return data


SYSTEM_INVENTORY: tuple[SystemInventoryItem, ...] = (
    SystemInventoryItem(
        id='app_boot',
        name='App boot / inicialização Streamlit',
        status=STATUS_ATIVO,
        layer='APP',
        purpose='Inicializa página, guarda erros críticos, processa OAuth e renderiza Home/sidebar.',
        owner_spine='app.py',
        main_paths=('app.py', 'bling_app_zero/ui/startup_guard.py', 'bling_app_zero/ui/home.py'),
        action='Manter como porta única de entrada do aplicativo.',
    ),
    SystemInventoryItem(
        id='home_router',
        name='Home / roteador principal',
        status=STATUS_ATIVO,
        layer='UI',
        purpose='Decide se mostra Home, wizard, conexão Bling ou fluxo universal.',
        owner_spine='Flow Spine',
        main_paths=('bling_app_zero/ui/home_router.py', 'bling_app_zero/ui/home.py'),
        action='Manter e evitar novos roteadores paralelos.',
    ),
    SystemInventoryItem(
        id='flow_spine',
        name='Espinha dorsal geral de fluxos',
        status=STATUS_ATIVO,
        layer='CORE',
        purpose='Centraliza contratos, etapas, destino API/CSV, rótulos e próximo passo.',
        owner_spine='Flow Spine',
        main_paths=('bling_app_zero/core/flow_spine.py', 'bling_app_zero/core/flow_spine_output.py', 'bling_app_zero/features_runtime/registry.py', 'bling_app_zero/features_runtime/router.py'),
        action='Transformar em fonte oficial de todo fluxo novo.',
    ),
    SystemInventoryItem(
        id='oauth_bling',
        name='OAuth Bling / token / backend bridge',
        status=STATUS_ATIVO,
        layer='INTEGRACAO',
        purpose='Autoriza Bling, trata callback, sincroniza token local/backend e protege Android/WebView.',
        owner_spine='Flow Spine',
        main_paths=('bling_app_zero/core/bling_oauth.py', 'bling_app_zero/core/bling_token_store.py', 'bling_app_zero/ui/bling_backend_bridge.py', 'bling_app_zero/ui/sidebar_tools.py'),
        action='Manter Android-safe como padrão; remover patches antigos quando diagnóstico estabilizar.',
    ),
    SystemInventoryItem(
        id='site_capture_spine',
        name='Captura por site / BLINGSMARTSCAN',
        status=STATUS_ATIVO,
        layer='ENTRADA',
        purpose='Captura produtos de sites para cadastro, estoque e preço usando interface/progresso unificado.',
        owner_spine='Site Capture Spine',
        main_paths=('bling_app_zero/ui/site_capture_spine.py', 'bling_app_zero/ui/site_panel.py', 'bling_app_zero/ui/site_panel_capture.py', 'bling_app_zero/agents/site_capture_agent.py'),
        action='Manter como única entrada oficial por site.',
    ),
    SystemInventoryItem(
        id='deep_crawler',
        name='Crawler profundo de produtos',
        status=STATUS_ATIVO,
        layer='ENGINE',
        purpose='Descobre URLs de produto, respeita limites, profundidade, orçamento e páginas visitadas.',
        owner_spine='Site Capture Spine',
        main_paths=('bling_app_zero/engines/fast_site_scraper/deep_site_capture.py', 'bling_app_zero/engines/fast_site_scraper/constants.py', 'bling_app_zero/flows/site_operation_router.py'),
        action='Manter acoplado à captura por site, não à UI diretamente.',
    ),
    SystemInventoryItem(
        id='manual_import',
        name='Importação manual / site protegido',
        status=STATUS_ATIVO,
        layer='ENTRADA',
        purpose='Permite colar HTML/tabela ou subir conteúdo quando o site bloqueia a captura automática.',
        owner_spine='Flow Spine',
        main_paths=('bling_app_zero/ui/manual_table_import_panel.py', 'bling_app_zero/core/manual_import_engine.py', 'bling_app_zero/core/manual_import_state.py'),
        risk='Normaliza operações para universal por compatibilidade; precisa ser alinhado futuramente à Flow Spine.',
        action='Revisar depois para preservar operação cadastro/estoque/preço sem cair em universal.',
    ),
    SystemInventoryItem(
        id='file_upload_reader',
        name='Upload e leitura de arquivos',
        status=STATUS_ATIVO,
        layer='ENTRADA',
        purpose='Lê planilhas/modelos/dados enviados e alimenta origem/modelo do fluxo.',
        owner_spine='Flow Spine',
        main_paths=('bling_app_zero/core/files.py', 'bling_app_zero/ui/home_models_upload.py', 'bling_app_zero/ui/universal_entry_step.py'),
        action='Manter; padronizar mensagens e validações pelo contrato ativo.',
    ),
    SystemInventoryItem(
        id='mapping',
        name='Mapeamento de colunas',
        status=STATUS_ATIVO,
        layer='TRANSFORMACAO',
        purpose='Mapeia origem para modelo/API, preserva linhas e prepara dataframe final.',
        owner_spine='Flow Spine Output',
        main_paths=('bling_app_zero/ui/cadastro_mapping_step.py', 'bling_app_zero/ui/universal_mapping_step.py', 'bling_app_zero/ui/shared_mapping.py', 'bling_app_zero/core/mapping_state.py'),
        action='Continuar removendo decisões por contexto antigo.',
    ),
    SystemInventoryItem(
        id='pricing',
        name='Precificação / calculadora',
        status=STATUS_ATIVO,
        layer='TRANSFORMACAO',
        purpose='Calcula preço de venda quando o contrato exige precificação.',
        owner_spine='Flow Spine Output',
        main_paths=('bling_app_zero/ui/home_wizard_pricing_step.py', 'bling_app_zero/ui/cadastro_pricing.py', 'bling_app_zero/ui/home_pricing_config.py'),
        action='Manter ligado a plan.needs_pricing.',
    ),
    SystemInventoryItem(
        id='product_enrichment',
        name='Enriquecimento IA de produto',
        status=STATUS_ATIVO,
        layer='IA',
        purpose='Corrige título/descrição, gera descrição segura por título, escolhe categoria e imagens confiáveis.',
        owner_spine='BLINGSMARTCORE',
        main_paths=('bling_app_zero/core/bling_smart_enrichment.py', 'bling_app_zero/core/bling_text_polisher.py', 'bling_app_zero/core/bling_product_update_intelligence.py'),
        action='Manter sem inventar ficha técnica; evoluir para IA externa apenas com controle de custo.',
    ),
    SystemInventoryItem(
        id='preview_final',
        name='Preview final / validação',
        status=STATUS_ATIVO,
        layer='SAIDA',
        purpose='Mostra base final revisada e aplica blindagem antes do download/envio.',
        owner_spine='Flow Spine Output',
        main_paths=('bling_app_zero/ui/cadastro_preview_step.py', 'bling_app_zero/ui/universal_preview_step.py', 'bling_app_zero/agents/blingsmartcore.py'),
        action='Manter preview como etapa obrigatória para CSV; API pode usar preview curto do payload.',
    ),
    SystemInventoryItem(
        id='download_csv',
        name='Download CSV / exportação por modelo',
        status=STATUS_ATIVO,
        layer='SAIDA',
        purpose='Gera CSV final, backup CSV ou modelo preenchido conforme destino do fluxo.',
        owner_spine='Flow Spine',
        main_paths=('bling_app_zero/ui/cadastro_download_step.py', 'bling_app_zero/ui/home_download.py', 'bling_app_zero/core/exporter.py', 'bling_app_zero/core/template_download_exporter.py'),
        action='Manter destino csv_download centralizado na Flow Spine.',
    ),
    SystemInventoryItem(
        id='bling_api_send',
        name='Envio API Bling',
        status=STATUS_ATIVO,
        layer='SAIDA',
        purpose='Envia cadastro, estoque e preços para o Bling em lotes com pré-varredura e checkpoint.',
        owner_spine='Flow Spine Output',
        main_paths=('bling_app_zero/ui/bling_api_batch_panel.py', 'bling_app_zero/core/bling_direct_sender.py', 'bling_app_zero/core/bling_direct_sender_smart_diff.py', 'bling_app_zero/core/bling_intelligent_update_sender.py'),
        risk='Preço API ainda depende de resolução confiável do produto antes do PATCH quando não houver ID Bling.',
        action='Próximo BLINGFIX recomendado: resolver preço por SKU/GTIN antes do PATCH.',
    ),
    SystemInventoryItem(
        id='send_state_batches',
        name='Estado de envio / lotes / checkpoint',
        status=STATUS_ATIVO,
        layer='CORE',
        purpose='Controla offset, lotes, pausas, erros, pendências e progresso do envio API.',
        owner_spine='Flow Spine Output',
        main_paths=('bling_app_zero/core/bling_send_state.py', 'bling_app_zero/core/bling_send_engine.py', 'bling_app_zero/core/bling_preflight_scan.py'),
        action='Manter operações cadastro/estoque/preço sempre normalizadas pelo mesmo contrato.',
    ),
    SystemInventoryItem(
        id='diagnostics',
        name='Diagnóstico / logs / suporte',
        status=STATUS_ATIVO,
        layer='SUPORTE',
        purpose='Gera pacote BLINGFIX com logs, auditoria, estado da sessão e inventário dos subsistemas.',
        owner_spine='Diagnostics',
        main_paths=('bling_app_zero/ui/maintenance_panel.py', 'bling_app_zero/ui/support_diagnostic_panel.py', 'bling_app_zero/core/audit.py', 'bling_app_zero/core/debug.py'),
        action='Incluir inventário oficial no zip de diagnóstico.',
    ),
    SystemInventoryItem(
        id='legacy_features_runtime_old',
        name='Runtime antigo de features',
        status=STATUS_RISCO,
        layer='LEGADO',
        purpose='Arquivos antigos de features/runtime podem coexistir com features_runtime novo.',
        owner_spine='Sem dono único',
        main_paths=('bling_app_zero/features/runtime.py', 'bling_app_zero/features/registry.py', 'bling_app_zero/features/download_pipeline.py', 'bling_app_zero/features/validator.py'),
        risk='Pode gerar decisões paralelas se algum import antigo ainda chamar esses módulos.',
        action='Auditar imports e marcar como substituído quando ninguém usar.',
    ),
    SystemInventoryItem(
        id='legacy_wizard_engines',
        name='Motores antigos de wizard/workflow',
        status=STATUS_RISCO,
        layer='LEGADO',
        purpose='Motores antigos coexistem com Flow Spine e Home Wizard atual.',
        owner_spine='Sem dono único',
        main_paths=('bling_app_zero/core/wizard_engine.py', 'bling_app_zero/core/workflow_engine.py', 'bling_app_zero/core/navigation_controller.py', 'bling_app_zero/core/wizard_state.py'),
        risk='Pode confundir manutenção se forem usados em paralelo ao home_wizard.py.',
        action='Auditar uso real antes de remover.',
    ),
    SystemInventoryItem(
        id='legacy_stock_site_panel',
        name='Painel antigo de estoque por site',
        status=STATUS_SUBSTITUIDO,
        layer='LEGADO',
        purpose='Fluxo antigo específico de estoque por site; hoje a captura deve passar pelo Site Capture Spine.',
        owner_spine='Substituído por Site Capture Spine',
        main_paths=('bling_app_zero/ui/estoque_site_panel.py',),
        risk='Se ainda for importado, pode reabrir interface diferente da captura central.',
        action='Confirmar se não há imports ativos e remover depois.',
    ),
    SystemInventoryItem(
        id='legacy_oauth_patch',
        name='Patch antigo de mesma aba OAuth',
        status=STATUS_REMOVER_DEPOIS,
        layer='LEGADO',
        purpose='Patch de compatibilidade antiga para OAuth em mesma aba.',
        owner_spine='Substituído por Android-safe OAuth',
        main_paths=('bling_app_zero/ui/bling_same_tab_patch.py',),
        risk='Pode conflitar conceitualmente com o fluxo Android-safe atual.',
        action='Remover depois que o OAuth Android-safe estabilizar nos diagnósticos.',
    ),
)


def inventory_items(statuses: Iterable[str] | None = None) -> tuple[SystemInventoryItem, ...]:
    wanted = {str(status).strip().upper() for status in statuses or () if str(status).strip()}
    if not wanted:
        return SYSTEM_INVENTORY
    return tuple(item for item in SYSTEM_INVENTORY if item.status in wanted)


def inventory_summary() -> dict[str, object]:
    counts: dict[str, int] = {}
    layers: dict[str, int] = {}
    for item in SYSTEM_INVENTORY:
        counts[item.status] = counts.get(item.status, 0) + 1
        layers[item.layer] = layers.get(item.layer, 0) + 1
    return {
        'total_subsystems': len(SYSTEM_INVENTORY),
        'status_counts': counts,
        'layer_counts': layers,
        'active_subsystems': counts.get(STATUS_ATIVO, 0),
        'risk_subsystems': counts.get(STATUS_RISCO, 0),
        'legacy_or_removal_subsystems': counts.get(STATUS_LEGADO, 0) + counts.get(STATUS_SUBSTITUIDO, 0) + counts.get(STATUS_REMOVER_DEPOIS, 0),
        'responsible_file': RESPONSIBLE_FILE,
    }


def inventory_payload() -> dict[str, object]:
    return {
        'summary': inventory_summary(),
        'items': [item.to_dict() for item in SYSTEM_INVENTORY],
    }


def inventory_markdown() -> str:
    lines = ['# Inventário oficial dos subsistemas', '', f'Total: {len(SYSTEM_INVENTORY)} subsistemas', '']
    summary = inventory_summary()
    lines.append('## Resumo por status')
    for status, count in sorted(dict(summary.get('status_counts') or {}).items()):
        lines.append(f'- {status}: {count}')
    lines.append('')
    lines.append('## Itens')
    for item in SYSTEM_INVENTORY:
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
    return '\n'.join(lines).strip() + '\n'


__all__ = [
    'STATUS_ATIVO',
    'STATUS_LEGADO',
    'STATUS_REMOVER_DEPOIS',
    'STATUS_RISCO',
    'STATUS_SUBSTITUIDO',
    'SYSTEM_INVENTORY',
    'SystemInventoryItem',
    'inventory_items',
    'inventory_markdown',
    'inventory_payload',
    'inventory_summary',
]
