import json
from pathlib import Path
from typing import Dict, Optional


# =========================================================
# CAMINHOS
# =========================================================
BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

MAPEAMENTOS_FILE = DATA_DIR / "mapeamentos_fornecedor.json"


# =========================================================
# LEITURA / ESCRITA SEGURA
# =========================================================
def carregar_mapeamentos_salvos() -> Dict[str, dict]:
    """
    Carrega todos os mapeamentos salvos do disco.
    """
    if not MAPEAMENTOS_FILE.exists():
        return {}

    try:
        conteudo = MAPEAMENTOS_FILE.read_text(encoding="utf-8").strip()
        if not conteudo:
            return {}

        dados = json.loads(conteudo)
        if isinstance(dados, dict):
            return dados

        return {}
    except Exception:
        return {}


def salvar_mapeamentos_salvos(dados: Dict[str, dict]) -> None:
    """
    Salva todos os mapeamentos no disco.
    """
    if not isinstance(dados, dict):
        dados = {}

    MAPEAMENTOS_FILE.write_text(
        json.dumps(dados, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# =========================================================
# OPERAÇÕES POR FORNECEDOR
# =========================================================
def salvar_mapeamento_fornecedor(
    fornecedor_id: str,
    nome_arquivo_origem: str,
    mapeamento_manual: dict,
    precificacao_config: dict,
    modo_operacao: str,
) -> None:
    """
    Salva ou atualiza o mapeamento de um fornecedor.
    """
    if not fornecedor_id:
        return

    banco = carregar_mapeamentos_salvos()

    banco[fornecedor_id] = {
        "fornecedor_id": fornecedor_id,
        "nome_arquivo_origem": nome_arquivo_origem or "",
        "mapeamento_manual": mapeamento_manual or {},
        "precificacao_config": precificacao_config or {},
        "modo_operacao": modo_operacao or "",
    }

    salvar_mapeamentos_salvos(banco)


def carregar_mapeamento_fornecedor(fornecedor_id: str) -> Optional[dict]:
    """
    Retorna o mapeamento salvo de um fornecedor específico.
    """
    if not fornecedor_id:
        return None

    banco = carregar_mapeamentos_salvos()
    return banco.get(fornecedor_id)


def remover_mapeamento_fornecedor(fornecedor_id: str) -> bool:
    """
    Remove o mapeamento salvo de um fornecedor.
    Retorna True se removeu, False se não existia.
    """
    if not fornecedor_id:
        return False

    banco = carregar_mapeamentos_salvos()

    if fornecedor_id not in banco:
        return False

    del banco[fornecedor_id]
    salvar_mapeamentos_salvos(banco)
    return True


def listar_mapeamentos_fornecedor() -> Dict[str, dict]:
    """
    Retorna todos os mapeamentos salvos.
    """
    return carregar_mapeamentos_salvos()
