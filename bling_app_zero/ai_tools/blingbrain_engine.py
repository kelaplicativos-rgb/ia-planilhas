from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BlingBrainResponse:
    title: str
    safety: str
    steps: list[str]
    action_type: str


def _normalize(text: str) -> str:
    return str(text or '').strip().lower()


def build_blingbrain_response(prompt: str, etapa: str = '', operacao: str = '') -> BlingBrainResponse:
    """Gera uma orientação segura para o assistente IA do sistema.

    Esta primeira versão não altera DataFrames automaticamente. Ela classifica
    o pedido e orienta o usuário sobre o caminho seguro para aplicar revisão.
    """
    text = _normalize(prompt)
    etapa_atual = str(etapa or 'etapa atual').strip() or 'etapa atual'
    operacao_atual = str(operacao or 'fluxo atual').strip() or 'fluxo atual'

    if not text:
        return BlingBrainResponse(
            title='Como posso ajudar neste fluxo?',
            safety='A IA é opcional e não altera o CSV sem confirmação.',
            action_type='orientacao',
            steps=[
                'Descreva o que você quer revisar, procurar ou melhorar.',
                'Exemplo: reformular descrições antes do download final.',
                'Exemplo: procurar a palavra bluetooth nas descrições.',
            ],
        )

    if any(term in text for term in ['gtin fake', 'ean fake', 'gerar gtin', 'gerar ean']):
        return BlingBrainResponse(
            title='GTIN/EAN artificial exige cuidado',
            safety='GTIN/EAN é código oficial. O caminho seguro é limpar inválidos, deixar vazio ou gerar código interno/SKU, não usar GTIN fake como padrão.',
            action_type='gtin',
            steps=[
                'Validar GTIN/EAN existente.',
                'Limpar GTIN inválido antes do CSV final.',
                'Gerar código interno/SKU apenas para controle, quando não houver código.',
                'Mostrar prévia e exigir confirmação antes de aplicar.',
            ],
        )

    if 'ncm' in text:
        return BlingBrainResponse(
            title='Sugestão de NCM para revisão manual',
            safety='NCM é classificação fiscal. A IA deve sugerir, justificar e deixar o usuário confirmar manualmente.',
            action_type='ncm',
            steps=[
                'Ler descrição, categoria e marca do produto.',
                'Gerar uma sugestão de NCM com justificativa.',
                'Salvar em coluna separada, como NCM sugerido.',
                'Aplicar no campo NCM oficial somente após confirmação do usuário.',
            ],
        )

    if any(term in text for term in ['descrição', 'descricao', 'descricoes', 'descrições', 'texto']):
        return BlingBrainResponse(
            title='Revisão de descrições com IA',
            safety='A IA deve reescrever apenas com base nos dados capturados, sem inventar especificações, garantia, medidas ou compatibilidades.',
            action_type='descricao',
            steps=[
                f'Usar o DataFrame final do {operacao_atual} na {etapa_atual}.',
                'Criar uma cópia revisada, sem apagar o original.',
                'Mostrar antes/depois para conferência.',
                'Aplicar no CSV final somente se o usuário confirmar.',
            ],
        )

    if any(term in text for term in ['titulo', 'título', 'nome do produto', 'reformular titulo', 'reformular título']):
        return BlingBrainResponse(
            title='Reformulação de títulos com IA',
            safety='A IA pode melhorar clareza e padrão, mas não deve inventar marca, modelo, voltagem, cor ou compatibilidade.',
            action_type='titulo',
            steps=[
                'Localizar coluna de título/nome/descrição curta.',
                'Gerar título revisado em coluna temporária.',
                'Comparar original x revisado.',
                'Aplicar somente após confirmação.',
            ],
        )

    if any(term in text for term in ['palavra', 'buscar', 'procurar', 'contem', 'contém']):
        return BlingBrainResponse(
            title='Busca inteligente em descrições',
            safety='Esta ação pode começar sem IA usando filtro textual; a IA entra apenas para busca semântica ou termos parecidos.',
            action_type='busca',
            steps=[
                'Selecionar a coluna onde procurar.',
                'Filtrar produtos que contêm a palavra ou termo informado.',
                'Opcionalmente usar IA para achar termos parecidos.',
                'Mostrar lista filtrada sem alterar o CSV automaticamente.',
            ],
        )

    return BlingBrainResponse(
        title='Plano seguro para usar IA neste fluxo',
        safety='Nenhuma alteração deve ser aplicada automaticamente. A IA gera sugestão, o usuário compara e confirma.',
        action_type='geral',
        steps=[
            f'Identificar a etapa atual: {etapa_atual}.',
            f'Identificar a operação atual: {operacao_atual}.',
            'Ler somente os dados já disponíveis no sistema.',
            'Gerar uma versão revisada separada do original.',
            'Exibir prévia antes/depois e pedir confirmação.',
        ],
    )
