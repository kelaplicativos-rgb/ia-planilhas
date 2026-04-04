import json
import os
import hashlib

PASTA_PERFIS = "perfis_colunas"


def garantir_pasta():
    if not os.path.exists(PASTA_PERFIS):
        os.makedirs(PASTA_PERFIS)


def gerar_hash_colunas(colunas):
    colunas_str = "|".join(sorted([str(c).strip().lower() for c in colunas]))
    return hashlib.md5(colunas_str.encode()).hexdigest()


def salvar_perfil(colunas, mapeamento):
    garantir_pasta()

    hash_id = gerar_hash_colunas(colunas)
    caminho = os.path.join(PASTA_PERFIS, f"{hash_id}.json")

    dados = {
        "colunas": colunas,
        "mapeamento": mapeamento
    }

    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=4, ensure_ascii=False)

    return hash_id


def carregar_perfil(colunas):
    garantir_pasta()

    hash_id = gerar_hash_colunas(colunas)
    caminho = os.path.join(PASTA_PERFIS, f"{hash_id}.json")

    if not os.path.exists(caminho):
        return None

    with open(caminho, "r", encoding="utf-8") as f:
        dados = json.load(f)

    return dados.get("mapeamento")


def deletar_perfil(colunas):
    garantir_pasta()

    hash_id = gerar_hash_colunas(colunas)
    caminho = os.path.join(PASTA_PERFIS, f"{hash_id}.json")

    if os.path.exists(caminho):
        os.remove(caminho)
        return True

    return False
