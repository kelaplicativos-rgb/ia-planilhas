import re


def sugestao_automatica(nome_coluna: str) -> str:
    nome = (nome_coluna or "").strip().lower()

    regras = [
        (r"codigo|código|sku|ref|referencia|referência", "codigo"),
        (r"nome|titulo|título|produto|descricao|descrição", "nome"),
        (r"descri.*curta|desc.*curta", "descricao_curta"),
        (r"preco.*custo|custo|compra", "preco_custo"),
        (r"preco|preço|valor", "preco"),
        (r"estoque|saldo|qtd|quantidade", "estoque"),
        (r"gtin|ean|barcode|cbarra|codigobarras", "gtin"),
        (r"marca|fabricante", "marca"),
        (r"categoria|departamento|secao|seção", "categoria"),
        (r"ncm", "ncm"),
        (r"cest", "cest"),
        (r"cfop", "cfop"),
        (r"unidade|und|un", "unidade"),
        (r"fornecedor", "fornecedor"),
        (r"cnpj", "cnpj_fornecedor"),
        (r"numero.*nfe|nfe|nf-e|nota", "numero_nfe"),
        (r"data.*emissao|emissao|emissão", "data_emissao"),
        (r"imagem|foto", "imagens"),
        (r"deposito|depósito", "deposito_id"),
        (r"origem", "origem"),
    ]

    for padrao, destino in regras:
        if re.search(padrao, nome):
            return destino

    return ""
