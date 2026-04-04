from typing import Dict, List, Optional


# =========================================================
# MODOS
# =========================================================
MODO_CADASTRO = "Cadastro de produtos"
MODO_ESTOQUE = "Atualização de estoque"


# =========================================================
# MODELO OFICIAL BLING - CADASTRO
# =========================================================
BLING_CADASTRO_COLUNAS = [
    "ID",
    "Código",
    "Descrição",
    "Unidade",
    "NCM",
    "Origem",
    "Preço",
    "Valor IPI fixo",
    "Observações",
    "Situação",
    "Estoque",
    "Preço de custo",
    "Cód no fornecedor",
    "Fornecedor",
    "Localização",
    "Estoque maximo",
    "Estoque minimo",
    "Peso líquido (Kg)",
    "Peso bruto (Kg)",
    "GTIN/EAN",
    "GTIN/EAN da embalagem",
    "Largura do Produto",
    "Altura do Produto",
    "Profundidade do produto",
    "Data Validade",
    "Descrição do Produto no Fornecedor",
    "Descrição Complementar",
    "Itens p/ caixa",
    "Produto Variação",
    "Tipo Produção",
    "Classe de enquadramento do IPI",
    "Código da lista de serviços",
    "Tipo do item",
    "Grupo de Tags/Tags",
    "Tributos",
    "Código Pai",
    "Código Integração",
    "Grupo de produtos",
    "Marca",
    "CEST",
    "Volumes",
    "Descrição Curta",
    "Cross-Docking",
    "URL Imagens Externas",
    "Link Externo",
    "Meses Garantia no Fornecedor",
    "Clonar dados do pai",
    "Condição do produto",
    "Frete Grátis",
    "Número FCI",
    "Vídeo",
    "Departamento",
    "Unidade de medida",
    "Preço de compra",
    "Valor base ICMS ST para retenção",
    "Valor ICMS ST para retenção",
    "Valor ICMS próprio do substituto",
    "Categoria do produto",
    "Informações Adicionais",
]

BLING_CADASTRO_OBRIGATORIOS = [
    "Código",
    "Descrição",
    "Unidade",
    "Preço",
    "Situação",
]

BLING_CADASTRO_COLUNA_PRECO = "Preço"
BLING_CADASTRO_COLUNA_IMAGENS = "URL Imagens Externas"
BLING_CADASTRO_COLUNA_PRECO_CUSTO = "Preço de custo"
BLING_CADASTRO_COLUNA_PRECO_COMPRA = "Preço de compra"


# =========================================================
# MODELO OFICIAL BLING - ESTOQUE
# =========================================================
BLING_ESTOQUE_COLUNAS = [
    " ID Produto",
    "Codigo produto *",
    "GTIN **",
    "Descrição Produto",
    "Deposito (OBRIGATÓRIO)",
    "Balanço (OBRIGATÓRIO)",
    "Preço unitário (OBRIGATÓRIO)",
    "Preço de Custo",
    "Observação",
    "Data",
]

BLING_ESTOQUE_OBRIGATORIOS = [
    "Codigo produto *",
    "Deposito (OBRIGATÓRIO)",
    "Balanço (OBRIGATÓRIO)",
    "Preço unitário (OBRIGATÓRIO)",
]

BLING_ESTOQUE_COLUNA_PRECO = "Preço unitário (OBRIGATÓRIO)"
BLING_ESTOQUE_COLUNA_PRECO_CUSTO = "Preço de Custo"


# =========================================================
# ALIASES - CADASTRO
# =========================================================
ALIASES_CADASTRO: Dict[str, List[str]] = {
    "ID": ["id", "codigo pai id"],
    "Código": ["codigo", "código", "sku", "ref", "referencia", "referência", "cod", "cod produto", "codigo produto", "part number"],
    "Descrição": ["descricao", "descrição", "nome", "titulo", "título", "produto", "nome produto", "descricao produto", "item", "nome do produto"],
    "Unidade": ["unidade", "und", "un", "u.m", "unid", "medida"],
    "NCM": ["ncm"],
    "Origem": ["origem", "origem mercadoria"],
    "Preço": ["preco", "preço", "valor", "valor venda", "preco venda", "preço venda", "price", "valor unitario", "valor unitário"],
    "Valor IPI fixo": ["ipi", "valor ipi", "ipi fixo"],
    "Observações": ["observacao", "observação", "obs", "observacoes", "observações"],
    "Situação": ["situacao", "situação", "status", "ativo", "inativo", "status produto"],
    "Estoque": ["estoque", "saldo", "quantidade", "qtd", "qtde", "disponivel", "disponível", "saldo estoque"],
    "Preço de custo": ["preco custo", "preço custo", "custo", "valor custo", "cost", "custo unitario", "custo unitário"],
    "Cód no fornecedor": ["cod fornecedor", "codigo fornecedor", "cód no fornecedor", "ref fornecedor", "sku fornecedor", "codigo fornecedor externo"],
    "Fornecedor": ["fornecedor", "distribuidor", "importadora"],
    "Localização": ["localizacao", "localização", "prateleira", "endereco estoque"],
    "Estoque maximo": ["estoque maximo", "estoque máximo", "maximo", "máximo"],
    "Estoque minimo": ["estoque minimo", "estoque mínimo", "minimo", "mínimo"],
    "Peso líquido (Kg)": ["peso liquido", "peso líquido", "peso liq", "peso"],
    "Peso bruto (Kg)": ["peso bruto"],
    "GTIN/EAN": ["gtin", "ean", "codigo barras", "código barras", "cod barras", "barcode"],
    "GTIN/EAN da embalagem": ["gtin embalagem", "ean embalagem", "codigo barras embalagem"],
    "Largura do Produto": ["largura", "width"],
    "Altura do Produto": ["altura", "height"],
    "Profundidade do produto": ["profundidade", "comprimento", "length", "profundidade produto"],
    "Data Validade": ["validade", "data validade", "vencimento"],
    "Descrição do Produto no Fornecedor": ["descricao fornecedor", "descrição fornecedor", "nome fornecedor", "descricao produto fornecedor"],
    "Descrição Complementar": ["descricao complementar", "descrição complementar", "complemento", "detalhes", "descricao longa", "descrição longa"],
    "Itens p/ caixa": ["itens caixa", "item caixa", "cx", "caixa", "quantidade caixa", "qtd caixa"],
    "Produto Variação": ["variacao", "variação", "tipo variacao", "produto variacao", "grade", "cor", "tamanho"],
    "Tipo Produção": ["tipo producao", "tipo produção"],
    "Classe de enquadramento do IPI": ["classe ipi", "enquadramento ipi"],
    "Código da lista de serviços": ["lista servicos", "lista serviços", "codigo servico"],
    "Tipo do item": ["tipo item"],
    "Grupo de Tags/Tags": ["tags", "grupo tags", "grupo de tags", "tag"],
    "Tributos": ["tributos", "impostos", "regra tributaria", "regra tributária"],
    "Código Pai": ["codigo pai", "código pai", "sku pai"],
    "Código Integração": ["codigo integracao", "código integração", "id integracao", "id integração"],
    "Grupo de produtos": ["grupo produtos", "grupo de produtos", "grupo", "colecao", "coleção", "linha"],
    "Marca": ["marca", "fabricante", "brand"],
    "CEST": ["cest"],
    "Volumes": ["volume", "volumes"],
    "Descrição Curta": ["descricao curta", "descrição curta", "resumo", "short description", "subtitulo", "subtítulo"],
    "URL Imagens Externas": ["imagem", "imagens", "url imagem", "url imagens", "fotos", "fotos produto", "imagem externa", "link imagem", "imagem 1", "foto 1"],
    "Link Externo": ["link externo", "url produto", "link produto", "url externa", "site produto", "pagina produto", "página produto"],
    "Meses Garantia no Fornecedor": ["garantia", "meses garantia"],
    "Clonar dados do pai": ["clonar dados pai"],
    "Condição do produto": ["condicao", "condição", "novo usado", "condicao produto"],
    "Frete Grátis": ["frete gratis", "frete grátis"],
    "Número FCI": ["fci", "numero fci", "número fci"],
    "Vídeo": ["video", "vídeo", "youtube"],
    "Departamento": ["departamento", "genero", "gênero", "publico", "público", "setor"],
    "Unidade de medida": ["unidade medida", "medida"],
    "Preço de compra": ["preco compra", "preço compra", "valor compra", "compra"],
    "Valor base ICMS ST para retenção": ["base icms st", "valor base icms st"],
    "Valor ICMS ST para retenção": ["icms st", "valor icms st"],
    "Valor ICMS próprio do substituto": ["icms proprio", "icms próprio substituto"],
    "Categoria do produto": ["categoria", "categoria produto", "grupo categoria", "departamento categoria", "subcategoria", "segmento"],
    "Informações Adicionais": ["informacoes adicionais", "informações adicionais", "info adicionais", "nfe", "nf-e", "observacao fiscal", "observação fiscal"],
}


# =========================================================
# ALIASES - ESTOQUE
# =========================================================
ALIASES_ESTOQUE: Dict[str, List[str]] = {
    " ID Produto": ["id produto", "id", "produto id"],
    "Codigo produto *": ["codigo", "código", "sku", "ref", "referencia", "referência", "cod produto", "codigo produto"],
    "GTIN **": ["gtin", "ean", "codigo barras", "código barras", "barcode"],
    "Descrição Produto": ["descricao", "descrição", "nome", "titulo", "título", "produto", "descricao produto", "nome produto"],
    "Deposito (OBRIGATÓRIO)": ["deposito", "depósito", "armazem", "armazém", "estoque deposito"],
    "Balanço (OBRIGATÓRIO)": ["saldo", "estoque", "quantidade", "qtd", "qtde", "balanco", "balanço", "saldo estoque"],
    "Preço unitário (OBRIGATÓRIO)": ["preco", "preço", "valor", "valor unitario", "valor unitário", "preco venda", "preço venda", "price"],
    "Preço de Custo": ["custo", "preco custo", "preço custo", "valor custo", "cost", "preco compra", "preço compra"],
    "Observação": ["observacao", "observação", "obs", "observacoes", "observações"],
    "Data": ["data", "data saldo", "data estoque", "data movimentacao", "data movimentação"],
}


# =========================================================
# HELPERS DE MODELO
# =========================================================
def get_modelo(modo: str) -> dict:
    if modo == MODO_ESTOQUE:
        return {
            "colunas": BLING_ESTOQUE_COLUNAS,
            "obrigatorios": BLING_ESTOQUE_OBRIGATORIOS,
            "aliases": ALIASES_ESTOQUE,
            "coluna_preco": BLING_ESTOQUE_COLUNA_PRECO,
            "coluna_preco_custo": BLING_ESTOQUE_COLUNA_PRECO_CUSTO,
            "coluna_preco_compra": None,
            "coluna_imagens": None,
        }

    return {
        "colunas": BLING_CADASTRO_COLUNAS,
        "obrigatorios": BLING_CADASTRO_OBRIGATORIOS,
        "aliases": ALIASES_CADASTRO,
        "coluna_preco": BLING_CADASTRO_COLUNA_PRECO,
        "coluna_preco_custo": BLING_CADASTRO_COLUNA_PRECO_CUSTO,
        "coluna_preco_compra": BLING_CADASTRO_COLUNA_PRECO_COMPRA,
        "coluna_imagens": BLING_CADASTRO_COLUNA_IMAGENS,
    }


def slug_modo(modo: str) -> str:
    return "estoque" if modo == MODO_ESTOQUE else "cadastro"


def listar_colunas_modelo(modo: str) -> List[str]:
    return list(get_modelo(modo)["colunas"])


def listar_obrigatorios_modelo(modo: str) -> List[str]:
    return list(get_modelo(modo)["obrigatorios"])


def listar_aliases_modelo(modo: str) -> Dict[str, List[str]]:
    return dict(get_modelo(modo)["aliases"])


def obter_coluna_preco(modo: str) -> Optional[str]:
    return get_modelo(modo)["coluna_preco"]


def obter_coluna_preco_custo(modo: str) -> Optional[str]:
    return get_modelo(modo)["coluna_preco_custo"]


def obter_coluna_preco_compra(modo: str) -> Optional[str]:
    return get_modelo(modo)["coluna_preco_compra"]


def obter_coluna_imagens(modo: str) -> Optional[str]:
    return get_modelo(modo)["coluna_imagens"]
