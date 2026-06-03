from __future__ import annotations

from dataclasses import dataclass

RESPONSIBLE_FILE = 'bling_app_zero/core/app_shortcuts.py'

CONTEXT_API = 'api'
CONTEXT_CSV = 'csv'
CONTEXT_AUTO = 'auto'

STEP_MODELO = 'modelo'
STEP_ORIGEM = 'origem'
STEP_ENTRADA = 'entrada'
STEP_PRECIFICACAO = 'precificacao'
STEP_MAPEAMENTO = 'mapeamento'
STEP_REGRAS = 'regras'
STEP_DOWNLOAD = 'download'

OP_CADASTRO = 'cadastro'
OP_ESTOQUE = 'estoque'
OP_PRECO = 'atualizacao_preco'
OP_UNIVERSAL = 'universal'

ORIGIN_SITE = 'site'
ORIGIN_FILE = 'arquivo'


@dataclass(frozen=True)
class AppShortcut:
    key: str
    label: str
    icon: str
    group: str
    context: str
    step: str
    operation: str = ''
    origin: str = ''
    description: str = ''

    @property
    def title(self) -> str:
        return f'{self.icon} {self.label}'.strip()


APP_SHORTCUTS: tuple[AppShortcut, ...] = (
    AppShortcut('cadastro_api', 'Cadastrar produtos', '🛒', 'Enviar direto ao Bling', CONTEXT_API, STEP_ORIGEM, OP_CADASTRO),
    AppShortcut('estoque_api', 'Atualizar estoque', '📦', 'Enviar direto ao Bling', CONTEXT_API, STEP_ORIGEM, OP_ESTOQUE),
    AppShortcut('precos_api', 'Atualizar preços', '💲', 'Enviar direto ao Bling', CONTEXT_API, STEP_ORIGEM, OP_PRECO),
    AppShortcut('site', 'Buscar no site', '🌐', 'Entrada de dados', CONTEXT_AUTO, STEP_ENTRADA, '', ORIGIN_SITE),
    AppShortcut('arquivo', 'Importar planilha', '📎', 'Entrada de dados', CONTEXT_AUTO, STEP_ENTRADA, '', ORIGIN_FILE),
    AppShortcut('cadastro_csv', 'Cadastro CSV', '📄', 'Gerar arquivo', CONTEXT_CSV, STEP_MODELO, OP_CADASTRO),
    AppShortcut('estoque_csv', 'Estoque CSV', '📦', 'Gerar arquivo', CONTEXT_CSV, STEP_MODELO, OP_ESTOQUE),
    AppShortcut('precos_csv', 'Preços CSV', '💲', 'Gerar arquivo', CONTEXT_CSV, STEP_MODELO, OP_PRECO),
    AppShortcut('precificar', 'Precificar', '💰', 'Ferramentas', CONTEXT_CSV, STEP_PRECIFICACAO, OP_UNIVERSAL),
    AppShortcut('mapear', 'Mapear campos', '🗺️', 'Ferramentas', CONTEXT_CSV, STEP_MAPEAMENTO, OP_UNIVERSAL),
    AppShortcut('regras', 'Revisar regras', '✅', 'Ferramentas', CONTEXT_CSV, STEP_REGRAS, OP_UNIVERSAL),
    AppShortcut('download', 'Enviar/Baixar', '⬇️', 'Ferramentas', CONTEXT_AUTO, STEP_DOWNLOAD),
    AppShortcut('modelos', 'Modelos', '📁', 'Ferramentas', CONTEXT_CSV, STEP_MODELO, OP_UNIVERSAL),
    AppShortcut('inicio', 'Início', '🏠', 'Ferramentas', 'home', 'home'),
)


def grouped_shortcuts() -> tuple[tuple[str, tuple[AppShortcut, ...]], ...]:
    groups: list[str] = []
    for shortcut in APP_SHORTCUTS:
        if shortcut.group not in groups:
            groups.append(shortcut.group)
    return tuple((group, tuple(item for item in APP_SHORTCUTS if item.group == group)) for group in groups)


def find_shortcut(key: object) -> AppShortcut | None:
    text = str(key or '').strip()
    for shortcut in APP_SHORTCUTS:
        if shortcut.key == text:
            return shortcut
    return None


__all__ = [
    'APP_SHORTCUTS',
    'AppShortcut',
    'CONTEXT_API',
    'CONTEXT_AUTO',
    'CONTEXT_CSV',
    'OP_CADASTRO',
    'OP_ESTOQUE',
    'OP_PRECO',
    'OP_UNIVERSAL',
    'ORIGIN_FILE',
    'ORIGIN_SITE',
    'STEP_DOWNLOAD',
    'STEP_ENTRADA',
    'STEP_MAPEAMENTO',
    'STEP_MODELO',
    'STEP_ORIGEM',
    'STEP_PRECIFICACAO',
    'STEP_REGRAS',
    'find_shortcut',
    'grouped_shortcuts',
]
