import json
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st

from bling_app_zero.core.leitor import carregar_planilha
from bling_app_zero.utils.excel import salvar_excel_bytes

try:
    from openai import OpenAI
except Exception:
    OpenAI = None


st.set_page_config(page_title="Bling Manual PRO", layout="wide")


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
# CAMINHOS
# =========================================================
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "bling_app_zero" / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
MAPEAMENTOS_FILE = DATA_DIR / "mapeamentos_fornecedor.json"


# =========================================================
# ESTADO
# =========================================================
def init_state() -> None:
    defaults = {
        "modo_operacao": MODO_CADASTRO,
        "df_origem": None,
        "df_saida": None,
        "nome_arquivo_origem": "",
        "ultima_chave_origem": "",
        "fornecedor_id": "",
        "mapeamento_manual": {},
        "campos_sem_vinculo": [],
        "campos_obrigatorios_sem_vinculo": [],
        "precificacao_config": {},
        "logs": [],
        "sugestao_confianca": {},
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def log(msg: str) -> None:
    st.session_state["logs"].append(str(msg))


def limpar_tudo() -> None:
    st.session_state["df_origem"] = None
    st.session_state["df_saida"] = None
    st.session_state["nome_arquivo_origem"] = ""
    st.session_state["ultima_chave_origem"] = ""
    st.session_state["fornecedor_id"] = ""
    st.session_state["mapeamento_manual"] = {}
    st.session_state["campos_sem_vinculo"] = []
    st.session_state["campos_obrigatorios_sem_vinculo"] = []
    st.session_state["precificacao_config"] = {}
    st.session_state["logs"] = []
    st.session_state["sugestao_confianca"] = {}

    for chave in list(st.session_state.keys()):
        if chave.startswith("map_") or chave.startswith("cfg_"):
            del st.session_state[chave]


def zerar_mapeamento_visual() -> None:
    st.session_state["mapeamento_manual"] = {}
    st.session_state["df_saida"] = None
    st.session_state["sugestao_confianca"] = {}
    for chave in list(st.session_state.keys()):
        if chave.startswith("map_"):
            del st.session_state[chave]


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


# =========================================================
# HELPERS TEXTO / NUMÉRICO
# =========================================================
def limpar_texto(valor) -> str:
    if valor is None:
        return ""
    try:
        if pd.isna(valor):
            return ""
    except Exception:
        pass
    texto = str(valor)
    texto = texto.replace("\n", " ").replace("\r", " ").replace("\t", " ")
    texto = re.sub(r"\s+", " ", texto)
    return texto.strip()


def remover_acentos(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", str(texto))
        if not unicodedata.combining(c)
    )


def slug_coluna(nome: str) -> str:
    nome = limpar_texto(nome)
    nome = remover_acentos(nome).lower()
    nome = nome.replace("/", " ").replace("\\", " ").replace("-", " ").replace("_", " ")
    nome = re.sub(r"[^a-z0-9 ]+", "", nome)
    nome = re.sub(r"\s+", " ", nome).strip()
    return nome


def formatar_preview_valor(valor) -> str:
    txt = limpar_texto(valor)
    if len(txt) > 90:
        return txt[:87] + "..."
    return txt


def fornecedor_id_por_nome(nome_arquivo: str, modo: str) -> str:
    base = Path(nome_arquivo).stem
    base_slug = slug_coluna(base) or "fornecedor_sem_nome"
    return f"{base_slug}__{slug_modo(modo)}"


def normalizar_valor_numerico(valor) -> float:
    if valor is None:
        return 0.0

    if isinstance(valor, (int, float)) and not pd.isna(valor):
        return float(valor)

    texto = limpar_texto(valor)
    if not texto:
        return 0.0

    texto = texto.replace("R$", "").replace("%", "").strip()

    if "," in texto and "." in texto:
        if texto.rfind(",") > texto.rfind("."):
            texto = texto.replace(".", "").replace(",", ".")
        else:
            texto = texto.replace(",", "")
    else:
        if "," in texto:
            texto = texto.replace(".", "").replace(",", ".")

    texto = re.sub(r"[^0-9.\-]", "", texto)

    try:
        return float(texto)
    except Exception:
        return 0.0


def formatar_numero_brasileiro(valor: float) -> str:
    return f"{float(valor):.2f}".replace(".", ",")


def parece_numero(valor: str) -> bool:
    texto = limpar_texto(valor)
    if not texto:
        return False
    texto_limpo = re.sub(r"[^0-9,\.\-]", "", texto)
    if not texto_limpo:
        return False
    try:
        _ = normalizar_valor_numerico(texto)
        return True
    except Exception:
        return False


def parece_url(valor: str) -> bool:
    texto = limpar_texto(valor).lower()
    return texto.startswith("http://") or texto.startswith("https://") or "www." in texto


def parece_data(valor: str) -> bool:
    texto = limpar_texto(valor)
    if not texto:
        return False
    padroes = [
        r"^\d{2}/\d{2}/\d{4}$",
        r"^\d{4}-\d{2}-\d{2}$",
        r"^\d{2}-\d{2}-\d{4}$",
    ]
    return any(re.match(p, texto) for p in padroes)


def somente_digitos(valor: str) -> str:
    return re.sub(r"\D+", "", limpar_texto(valor))


def parece_gtin(valor: str) -> bool:
    dig = somente_digitos(valor)
    return len(dig) in {8, 12, 13, 14}


def parece_ncm(valor: str) -> bool:
    dig = somente_digitos(valor)
    return len(dig) == 8


def parece_cest(valor: str) -> bool:
    dig = somente_digitos(valor)
    return len(dig) == 7


def normalizar_lista_urls_imagem(valor) -> str:
    texto = limpar_texto(valor)
    if not texto:
        return ""

    partes = re.split(r"[|,;\n\r\t]+", texto)
    urls = []
    vistos = set()

    for parte in partes:
        url = limpar_texto(parte)
        if not url:
            continue

        chave = url.lower()
        if chave in vistos:
            continue

        vistos.add(chave)
        urls.append(url)

    return "|".join(urls)


# =========================================================
# GTIN / EAN
# =========================================================
def limpar_gtin(valor) -> str:
    return somente_digitos(valor)


def validar_gtin_checksum(gtin: str) -> bool:
    if not gtin or not gtin.isdigit():
        return False

    if len(gtin) not in {8, 12, 13, 14}:
        return False

    digitos = [int(d) for d in gtin]
    check_digit = digitos[-1]
    corpo = digitos[:-1]

    soma = 0
    peso = 3
    for n in reversed(corpo):
        soma += n * peso
        peso = 1 if peso == 3 else 3

    calculado = (10 - (soma % 10)) % 10
    return calculado == check_digit


def tratar_gtin(valor) -> Tuple[str, bool]:
    gtin = limpar_gtin(valor)
    if not gtin:
        return "", False
    if validar_gtin_checksum(gtin):
        return gtin, True
    return "", False


def aplicar_validacao_gtin_df(df: pd.DataFrame, coluna: str) -> Tuple[pd.DataFrame, List[str]]:
    logs = []

    if coluna not in df.columns:
        return df, logs

    novos = []
    total_invalidos = 0
    total_validos = 0

    for idx, valor in enumerate(df[coluna].tolist(), start=1):
        txt_original = limpar_texto(valor)

        if not txt_original:
            novos.append("")
            continue

        gtin_corrigido, valido = tratar_gtin(txt_original)
        if valido:
            novos.append(gtin_corrigido)
            total_validos += 1
        else:
            novos.append("")
            total_invalidos += 1
            logs.append(f"Linha {idx}: GTIN inválido zerado ({txt_original})")

    df[coluna] = novos
    logs.append(f"GTIN válido: {total_validos}")
    logs.append(f"GTIN inválido zerado: {total_invalidos}")
    return df, logs


# =========================================================
# PERSISTÊNCIA
# =========================================================
def carregar_mapeamentos_salvos() -> Dict[str, dict]:
    if not MAPEAMENTOS_FILE.exists():
        return {}
    try:
        return json.loads(MAPEAMENTOS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def salvar_mapeamentos_salvos(dados: Dict[str, dict]) -> None:
    MAPEAMENTOS_FILE.write_text(
        json.dumps(dados, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def salvar_mapeamento_fornecedor(
    fornecedor_id: str,
    nome_arquivo_origem: str,
    mapeamento_manual: dict,
    precificacao_config: dict,
    modo_operacao: str,
) -> None:
    banco = carregar_mapeamentos_salvos()
    banco[fornecedor_id] = {
        "fornecedor_id": fornecedor_id,
        "nome_arquivo_origem": nome_arquivo_origem,
        "mapeamento_manual": mapeamento_manual,
        "precificacao_config": precificacao_config,
        "modo_operacao": modo_operacao,
    }
    salvar_mapeamentos_salvos(banco)


def carregar_mapeamento_fornecedor(fornecedor_id: str) -> Optional[dict]:
    banco = carregar_mapeamentos_salvos()
    return banco.get(fornecedor_id)


# =========================================================
# OPENAI OPCIONAL
# =========================================================
def obter_cliente_openai():
    if OpenAI is None:
        return None

    try:
        api_key = st.secrets.get("OPENAI_API_KEY")
        if not api_key:
            return None
        return OpenAI(api_key=api_key)
    except Exception as e:
        log(f"OpenAI indisponível: {e}")
        return None


def extrair_texto_resposta_openai(resp) -> str:
    try:
        texto = getattr(resp, "output_text", None)
        if texto:
            return str(texto).strip()
    except Exception:
        pass

    try:
        if hasattr(resp, "choices") and resp.choices:
            mensagem = resp.choices[0].message
            conteudo = getattr(mensagem, "content", "")
            if isinstance(conteudo, str):
                return conteudo.strip()
            if isinstance(conteudo, list):
                partes = []
                for item in conteudo:
                    if isinstance(item, dict):
                        if item.get("type") == "text" and item.get("text"):
                            partes.append(str(item["text"]))
                    else:
                        txt = getattr(item, "text", None)
                        if txt:
                            partes.append(str(txt))
                return "\n".join(partes).strip()
    except Exception:
        pass

    try:
        output = getattr(resp, "output", None)
        if output:
            partes = []
            for bloco in output:
                content = getattr(bloco, "content", None) or []
                for item in content:
                    txt = getattr(item, "text", None)
                    if txt:
                        partes.append(str(txt))
            if partes:
                return "\n".join(partes).strip()
    except Exception:
        pass

    try:
        if isinstance(resp, dict):
            choices = resp.get("choices", [])
            if choices:
                message = choices[0].get("message", {})
                content = message.get("content", "")
                if isinstance(content, str):
                    return content.strip()
    except Exception:
        pass

    return ""


def chamar_openai_texto(client, prompt: str) -> str:
    ultimo_erro = None

    try:
        if hasattr(client, "chat") and hasattr(client.chat, "completions"):
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Você é um especialista em mapeamento de planilhas para importação no Bling. "
                            "Responda somente em JSON válido."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0,
            )
            texto = extrair_texto_resposta_openai(resp)
            if texto:
                return texto
    except Exception as e:
        ultimo_erro = e

    try:
        if hasattr(client, "responses"):
            resp = client.responses.create(
                model="gpt-4o-mini",
                input=prompt,
            )
            texto = extrair_texto_resposta_openai(resp)
            if texto:
                return texto
    except Exception as e:
        ultimo_erro = e

    if ultimo_erro:
        raise ultimo_erro

    raise RuntimeError("Nenhum método compatível da OpenAI foi encontrado.")


# =========================================================
# PERFIL REAL DAS COLUNAS DO FORNECEDOR
# =========================================================
def extrair_amostra_coluna(serie: pd.Series, limite: int = 30) -> List[str]:
    valores = []
    for v in serie.fillna("").astype(str).tolist():
        txt = limpar_texto(v)
        if txt:
            valores.append(txt)
        if len(valores) >= limite:
            break
    return valores


def perfil_coluna_fornecedor(serie: pd.Series) -> dict:
    amostra = extrair_amostra_coluna(serie, limite=40)
    total = len(amostra)

    if total == 0:
        return {
            "total": 0,
            "pct_numerico": 0.0,
            "pct_url": 0.0,
            "pct_gtin": 0.0,
            "pct_ncm": 0.0,
            "pct_cest": 0.0,
            "pct_data": 0.0,
            "pct_curto": 0.0,
            "pct_longo": 0.0,
            "pct_sim_nao": 0.0,
            "valores_unicos": 0,
            "media_tamanho": 0.0,
        }

    numerico = sum(1 for v in amostra if parece_numero(v))
    url = sum(1 for v in amostra if parece_url(v))
    gtin = sum(1 for v in amostra if parece_gtin(v))
    ncm = sum(1 for v in amostra if parece_ncm(v))
    cest = sum(1 for v in amostra if parece_cest(v))
    data = sum(1 for v in amostra if parece_data(v))
    curto = sum(1 for v in amostra if len(v) <= 20)
    longo = sum(1 for v in amostra if len(v) >= 60)

    sim_nao_vals = {"sim", "nao", "não", "s", "n", "true", "false", "ativo", "inativo", "1", "0"}
    sim_nao = sum(1 for v in amostra if slug_coluna(v) in sim_nao_vals)

    return {
        "total": total,
        "pct_numerico": numerico / total,
        "pct_url": url / total,
        "pct_gtin": gtin / total,
        "pct_ncm": ncm / total,
        "pct_cest": cest / total,
        "pct_data": data / total,
        "pct_curto": curto / total,
        "pct_longo": longo / total,
        "pct_sim_nao": sim_nao / total,
        "valores_unicos": len(set(amostra)),
        "media_tamanho": sum(len(v) for v in amostra) / total,
    }


def construir_perfis_fornecedor(df_origem: pd.DataFrame) -> Dict[str, dict]:
    perfis = {}
    for coluna in df_origem.columns:
        perfis[coluna] = perfil_coluna_fornecedor(df_origem[coluna])
    return perfis


# =========================================================
# APRENDIZADO DOS MAPEAMENTOS SALVOS
# =========================================================
def memoria_mapeamentos_por_coluna(modo: str) -> Dict[str, Counter]:
    banco = carregar_mapeamentos_salvos()
    memoria: Dict[str, Counter] = defaultdict(Counter)

    for _, payload in banco.items():
        if payload.get("modo_operacao") != modo:
            continue

        mapeamento = payload.get("mapeamento_manual", {}) or {}
        for col_bling, col_origem in mapeamento.items():
            if not col_origem:
                continue
            memoria[slug_coluna(col_origem)][col_bling] += 1

    return memoria


# =========================================================
# SCORE DE SUGESTÃO REFINADO
# =========================================================
def score_nome_coluna(coluna_bling: str, coluna_fornecedor: str, aliases_map: Dict[str, List[str]]) -> float:
    slug_bling = slug_coluna(coluna_bling)
    slug_forn = slug_coluna(coluna_fornecedor)

    if not slug_forn:
        return 0.0

    score = 0.0

    if slug_bling == slug_forn:
        score += 100.0

    aliases = aliases_map.get(coluna_bling, [])
    for alias in aliases:
        alias_slug = slug_coluna(alias)
        if not alias_slug:
            continue
        if alias_slug == slug_forn:
            score += 95.0
        elif alias_slug in slug_forn:
            score += min(75.0, 32.0 + len(alias_slug))
        elif slug_forn in alias_slug and len(slug_forn) >= 4:
            score += 24.0

    palavras_bling = set(slug_bling.split())
    palavras_forn = set(slug_forn.split())
    score += len(palavras_bling.intersection(palavras_forn)) * 8.0

    return score


def score_tipo_valor(coluna_bling: str, perfil: dict, modo: str) -> float:
    score = 0.0

    if modo == MODO_ESTOQUE:
        if coluna_bling == "GTIN **":
            score += perfil["pct_gtin"] * 120
            score += perfil["pct_numerico"] * 15
        elif coluna_bling in {"Balanço (OBRIGATÓRIO)", "Preço unitário (OBRIGATÓRIO)", "Preço de Custo"}:
            score += perfil["pct_numerico"] * 65
        elif coluna_bling == "Data":
            score += perfil["pct_data"] * 120
        elif coluna_bling == "Descrição Produto":
            score += perfil["pct_longo"] * 18
            score += max(0.0, 1 - perfil["pct_numerico"]) * 20
        elif coluna_bling == "Observação":
            score += perfil["pct_longo"] * 12
        elif coluna_bling == "Deposito (OBRIGATÓRIO)":
            score += max(0.0, 1 - perfil["pct_numerico"]) * 14
            score += perfil["pct_curto"] * 12
        elif coluna_bling == "Codigo produto *":
            score += perfil["pct_curto"] * 18
        return score

    if coluna_bling == "URL Imagens Externas":
        score += perfil["pct_url"] * 120
        score += perfil["pct_longo"] * 10

    elif coluna_bling in {
        "Preço", "Preço de custo", "Preço de compra", "Valor IPI fixo",
        "Valor base ICMS ST para retenção", "Valor ICMS ST para retenção",
        "Valor ICMS próprio do substituto"
    }:
        score += perfil["pct_numerico"] * 60

    elif coluna_bling in {"Estoque", "Estoque maximo", "Estoque minimo", "Itens p/ caixa", "Volumes", "Cross-Docking"}:
        score += perfil["pct_numerico"] * 50
        score += perfil["pct_curto"] * 8

    elif coluna_bling == "GTIN/EAN":
        score += perfil["pct_gtin"] * 120
        score += perfil["pct_numerico"] * 15

    elif coluna_bling == "GTIN/EAN da embalagem":
        score += perfil["pct_gtin"] * 115
        score += perfil["pct_numerico"] * 12

    elif coluna_bling == "NCM":
        score += perfil["pct_ncm"] * 120

    elif coluna_bling == "CEST":
        score += perfil["pct_cest"] * 120

    elif coluna_bling == "Data Validade":
        score += perfil["pct_data"] * 120

    elif coluna_bling in {"Descrição", "Descrição Curta", "Descrição Complementar", "Descrição do Produto no Fornecedor", "Informações Adicionais"}:
        score += perfil["pct_longo"] * 25
        score += max(0.0, 1 - perfil["pct_numerico"]) * 20

    elif coluna_bling in {"Situação", "Frete Grátis", "Clonar dados do pai"}:
        score += perfil["pct_sim_nao"] * 100
        score += perfil["pct_curto"] * 12

    elif coluna_bling in {"Marca", "Fornecedor", "Categoria do produto", "Grupo de produtos", "Departamento"}:
        score += max(0.0, 1 - perfil["pct_numerico"]) * 18
        score += perfil["pct_curto"] * 15

    elif coluna_bling in {"Largura do Produto", "Altura do Produto", "Profundidade do produto", "Peso líquido (Kg)", "Peso bruto (Kg)"}:
        score += perfil["pct_numerico"] * 55

    elif coluna_bling == "Link Externo":
        score += perfil["pct_url"] * 100

    elif coluna_bling == "Vídeo":
        score += perfil["pct_url"] * 90

    return score


def score_memoria_mapeada(coluna_bling: str, coluna_fornecedor: str, memoria: Dict[str, Counter]) -> float:
    slug_forn = slug_coluna(coluna_fornecedor)
    if slug_forn not in memoria:
        return 0.0

    contador = memoria[slug_forn]
    total = sum(contador.values())
    if total <= 0:
        return 0.0

    hits = contador.get(coluna_bling, 0)
    return (hits / total) * 90.0


def score_coluna_fornecedor_para_bling(
    coluna_bling: str,
    coluna_fornecedor: str,
    perfil: dict,
    memoria: Dict[str, Counter],
    aliases_map: Dict[str, List[str]],
    modo: str,
) -> float:
    score = 0.0
    score += score_nome_coluna(coluna_bling, coluna_fornecedor, aliases_map)
    score += score_tipo_valor(coluna_bling, perfil, modo)
    score += score_memoria_mapeada(coluna_bling, coluna_fornecedor, memoria)

    slug_forn = slug_coluna(coluna_fornecedor)

    if modo == MODO_ESTOQUE:
        if coluna_bling == "Preço unitário (OBRIGATÓRIO)" and "custo" in slug_forn:
            score -= 20
        if coluna_bling == "Preço de Custo" and ("venda" in slug_forn or "preco venda" in slug_forn):
            score -= 20
        if coluna_bling == "Descrição Produto" and ("curta" in slug_forn or "resumo" in slug_forn):
            score -= 8
        return score

    if coluna_bling == "URL Imagens Externas" and "video" in slug_forn:
        score -= 35
    if coluna_bling == "Vídeo" and "imagem" in slug_forn:
        score -= 35
    if coluna_bling == "Preço" and "custo" in slug_forn:
        score -= 25
    if coluna_bling in {"Preço de custo", "Preço de compra"} and ("venda" in slug_forn or "preco venda" in slug_forn):
        score -= 25
    if coluna_bling == "Descrição" and ("curta" in slug_forn or "resumo" in slug_forn):
        score -= 12
    if coluna_bling == "Descrição Curta" and ("nome" in slug_forn or "titulo" in slug_forn):
        score -= 8

    return score


def limiar_por_campo(coluna_bling: str, modo: str, obrigatorios: List[str]) -> float:
    if modo == MODO_ESTOQUE:
        if coluna_bling in {"Codigo produto *", "Descrição Produto", "Balanço (OBRIGATÓRIO)", "Preço unitário (OBRIGATÓRIO)", "Preço de Custo", "GTIN **"}:
            return 46.0
        if coluna_bling in obrigatorios:
            return 42.0
        return 56.0

    if coluna_bling in {
        "Código", "Descrição", "Preço", "Estoque", "Preço de custo", "Preço de compra",
        "Marca", "Descrição Curta", "Categoria do produto", "URL Imagens Externas",
        "GTIN/EAN", "NCM", "CEST"
    }:
        return 48.0
    if coluna_bling in obrigatorios:
        return 44.0
    return 58.0


def nivel_confianca(score: float) -> str:
    if score >= 150:
        return "alta"
    if score >= 90:
        return "média"
    return "baixa"


def sugerir_mapeamento_local_refinado(df_origem: pd.DataFrame, modo: str) -> Tuple[dict, dict]:
    modelo = get_modelo(modo)
    colunas_bling = modelo["colunas"]
    obrigatorios = modelo["obrigatorios"]
    aliases_map = modelo["aliases"]

    mapeamento = {}
    confianca = {}
    disponiveis = list(df_origem.columns)
    perfis = construir_perfis_fornecedor(df_origem)
    memoria = memoria_mapeamentos_por_coluna(modo)

    for coluna_bling in colunas_bling:
        ranking = []

        for coluna_origem in disponiveis:
            score = score_coluna_fornecedor_para_bling(
                coluna_bling=coluna_bling,
                coluna_fornecedor=coluna_origem,
                perfil=perfis[coluna_origem],
                memoria=memoria,
                aliases_map=aliases_map,
                modo=modo,
            )
            ranking.append((coluna_origem, score))

        ranking.sort(key=lambda x: x[1], reverse=True)

        melhor_coluna = None
        melhor_score = 0.0
        segunda_score = 0.0

        if ranking:
            melhor_coluna, melhor_score = ranking[0]
            if len(ranking) > 1:
                segunda_score = ranking[1][1]

        limiar = limiar_por_campo(coluna_bling, modo, obrigatorios)
        vantagem = melhor_score - segunda_score

        if melhor_score >= limiar and vantagem >= 8:
            mapeamento[coluna_bling] = melhor_coluna
            confianca[coluna_bling] = {
                "coluna": melhor_coluna,
                "score": round(melhor_score, 1),
                "nivel": nivel_confianca(melhor_score),
                "vantagem": round(vantagem, 1),
            }
        else:
            mapeamento[coluna_bling] = None
            confianca[coluna_bling] = {
                "coluna": melhor_coluna if melhor_score > 0 else None,
                "score": round(melhor_score, 1),
                "nivel": "baixa",
                "vantagem": round(vantagem, 1),
            }

    if modo == MODO_ESTOQUE:
        principais = [
            "Codigo produto *",
            "GTIN **",
            "Descrição Produto",
            "Balanço (OBRIGATÓRIO)",
            "Preço unitário (OBRIGATÓRIO)",
            "Preço de Custo",
        ]
    else:
        principais = [
            "Código",
            "Descrição",
            "Preço",
            "Estoque",
            "Preço de custo",
            "Preço de compra",
            "Descrição Curta",
            "Marca",
            "Categoria do produto",
            "URL Imagens Externas",
            "GTIN/EAN",
        ]

    usados = {}
    for campo in principais:
        col = mapeamento.get(campo)
        if not col:
            continue

        if col not in usados:
            usados[col] = campo
        else:
            atual = confianca.get(campo, {}).get("score", 0.0)
            anterior_campo = usados[col]
            anterior = confianca.get(anterior_campo, {}).get("score", 0.0)

            if atual > anterior:
                mapeamento[anterior_campo] = None
                usados[col] = campo
            else:
                mapeamento[campo] = None

    return mapeamento, confianca


# =========================================================
# OPENAI REFINO OPCIONAL
# =========================================================
def sugerir_mapeamento_openai(df_origem: pd.DataFrame, modo: str) -> Optional[dict]:
    client = obter_cliente_openai()
    if client is None:
        log("IA indisponível: OPENAI_API_KEY ausente ou biblioteca OpenAI não carregada.")
        return None

    modelo = get_modelo(modo)
    colunas_bling = modelo["colunas"]
    colunas_fornecedor = list(df_origem.columns)
    exemplo = {}

    if not df_origem.empty:
        primeira = df_origem.head(1).fillna("").astype(str).to_dict(orient="records")[0]
        for k, v in primeira.items():
            exemplo[k] = formatar_preview_valor(v)

    prompt = f"""
Você deve sugerir um mapeamento entre colunas do fornecedor e colunas fixas do modelo Bling.
Responda SOMENTE em JSON válido no formato:
{{"mapeamento": {{"COLUNA BLING": "COLUNA FORNECEDOR ou null"}}}}

Regras:
- Use apenas estas colunas Bling: {colunas_bling}
- Use apenas estas colunas do fornecedor: {colunas_fornecedor}
- Se houver dúvida, coloque null
- Não invente colunas
- Se o modo for estoque:
  - "Codigo produto *" = SKU / código / referência
  - "Descrição Produto" = nome / título / descrição principal
  - "Balanço (OBRIGATÓRIO)" = saldo / estoque / quantidade
  - "Preço unitário (OBRIGATÓRIO)" = preço unitário / venda / valor
  - "Preço de Custo" = custo / compra
  - "GTIN **" = gtin / ean
- Se o modo for cadastro:
  - "Preço" = preço de venda
  - "Preço de custo" / "Preço de compra" = custo/compra quando existir
  - "Código" = SKU/referência/código quando existir
  - "URL Imagens Externas" = campo com URLs/imagens
  - "Descrição" = nome/título principal do produto
  - "Descrição Curta" = resumo/descrição curta quando existir

Exemplo de valores da primeira linha:
{json.dumps(exemplo, ensure_ascii=False)}

Modo atual:
{modo}
"""

    try:
        texto = chamar_openai_texto(client, prompt)
        if not texto:
            log("IA não retornou texto utilizável.")
            return None

        inicio = texto.find("{")
        fim = texto.rfind("}")
        if inicio == -1 or fim == -1:
            log("IA retornou conteúdo fora do formato JSON esperado.")
            return None

        dados = json.loads(texto[inicio:fim + 1])
        bruto = dados.get("mapeamento", {})

        final = {}
        for col_bling in colunas_bling:
            valor = bruto.get(col_bling)
            final[col_bling] = valor if valor in colunas_fornecedor else None

        return final
    except Exception as e:
        log(f"Falha ao sugerir via IA: {e}")
        return None


# =========================================================
# APLICAÇÃO DAS SUGESTÕES
# =========================================================
def aplicar_sugestao_no_estado(mapeamento: dict, confianca: Optional[dict] = None) -> None:
    st.session_state["mapeamento_manual"] = dict(mapeamento)
    if confianca is not None:
        st.session_state["sugestao_confianca"] = confianca

    for col_bling, col_origem in mapeamento.items():
        st.session_state[f"map_{slug_coluna(col_bling)}"] = col_origem or ""


# =========================================================
# MAPEAMENTO VISUAL
# =========================================================
def construir_mapeamento_visual(df_origem: pd.DataFrame, modo: str) -> dict:
    modelo = get_modelo(modo)
    colunas_bling = modelo["colunas"]
    obrigatorios = modelo["obrigatorios"]

    todas_opcoes = list(df_origem.columns)
    mapeamento = {}
    confiancas = st.session_state.get("sugestao_confianca", {}) or {}

    st.markdown("## Vinculação manual das colunas")

    header = st.columns([2.2, 0.9, 2.3, 2.5, 1.2])
    header[0].markdown("**Campo Bling oficial**")
    header[1].markdown("**Obrigatório**")
    header[2].markdown("**Coluna do fornecedor**")
    header[3].markdown("**Prévia**")
    header[4].markdown("**Confiança**")

    st.markdown("---")

    valores_atuais = {}
    for col_bling in colunas_bling:
        estado_key = f"map_{slug_coluna(col_bling)}"
        valor_inicial = st.session_state.get("mapeamento_manual", {}).get(col_bling, "")

        if estado_key in st.session_state:
            valor_inicial = st.session_state.get(estado_key, valor_inicial)

        if valor_inicial not in todas_opcoes:
            valor_inicial = ""

        valores_atuais[col_bling] = valor_inicial

    for col_bling in colunas_bling:
        obrigatorio = col_bling in obrigatorios
        estado_key = f"map_{slug_coluna(col_bling)}"
        valor_atual = valores_atuais.get(col_bling, "")

        usadas_por_outros = {
            valores_atuais.get(outro_campo, "")
            for outro_campo in colunas_bling
            if outro_campo != col_bling and valores_atuais.get(outro_campo, "")
        }

        opcoes = [""]
        for col in todas_opcoes:
            if col == valor_atual or col not in usadas_por_outros:
                opcoes.append(col)

        if valor_atual not in opcoes:
            valor_atual = ""

        if estado_key not in st.session_state or st.session_state.get(estado_key) not in opcoes:
            st.session_state[estado_key] = valor_atual

        c1, c2, c3, c4, c5 = st.columns([2.2, 0.9, 2.3, 2.5, 1.2])

        with c1:
            st.markdown(f"**🔴 {col_bling}**" if obrigatorio else col_bling)

        with c2:
            st.markdown("**SIM**" if obrigatorio else "não")

        with c3:
            escolha = st.selectbox(
                f"Mapear {col_bling}",
                options=opcoes,
                key=estado_key,
                label_visibility="collapsed",
            )

        valores_atuais[col_bling] = escolha or ""

        with c4:
            preview = ""
            if escolha and escolha in df_origem.columns and not df_origem.empty:
                valores_validos = df_origem[escolha].fillna("").astype(str).tolist()
                for valor in valores_validos:
                    valor_limpo = formatar_preview_valor(valor)
                    if valor_limpo:
                        preview = valor_limpo
                        break
            st.caption(preview or "-")

        with c5:
            info = confiancas.get(col_bling, {})
            nivel = info.get("nivel", "")
            if escolha:
                if nivel == "alta":
                    st.success("alta")
                elif nivel == "média":
                    st.warning("média")
                elif nivel == "baixa":
                    st.caption("baixa")
                else:
                    st.caption("-")
            else:
                st.caption("-")

        mapeamento[col_bling] = escolha or None

    return mapeamento


def analisar_vinculos(mapeamento_manual: dict, obrigatorios: List[str]) -> Tuple[List[str], List[str]]:
    sem_vinculo = [campo for campo, origem in mapeamento_manual.items() if not origem]
    obrigatorios_sem_vinculo = [campo for campo in obrigatorios if not mapeamento_manual.get(campo)]
    return sem_vinculo, obrigatorios_sem_vinculo


# =========================================================
# PRECIFICAÇÃO
# =========================================================
def calcular_preco_venda(
    custo: float,
    lucro_percentual: float,
    imposto_percentual: float,
    taxa_percentual: float,
    valor_fixo: float,
) -> float:
    custo = max(custo, 0.0)
    lucro_percentual = max(lucro_percentual, 0.0)
    imposto_percentual = max(imposto_percentual, 0.0)
    taxa_percentual = max(taxa_percentual, 0.0)
    valor_fixo = max(valor_fixo, 0.0)

    preco = custo
    preco += custo * (lucro_percentual / 100.0)
    preco += custo * (imposto_percentual / 100.0)
    preco += custo * (taxa_percentual / 100.0)
    preco += valor_fixo

    return round(preco, 2)


# =========================================================
# GERAÇÃO DA SAÍDA
# =========================================================
def gerar_planilha_saida(
    df_origem: pd.DataFrame,
    mapeamento_manual: dict,
    config_precificacao: dict,
    modo: str,
    deposito_manual: str = "",
) -> pd.DataFrame:
    modelo = get_modelo(modo)
    colunas_bling = modelo["colunas"]
    coluna_imagens = modelo["coluna_imagens"]
    coluna_preco = modelo["coluna_preco"]
    coluna_preco_custo = modelo["coluna_preco_custo"]
    coluna_preco_compra = modelo["coluna_preco_compra"]

    saida = pd.DataFrame("", index=range(len(df_origem)), columns=colunas_bling)

    for col_bling in colunas_bling:
        col_origem = mapeamento_manual.get(col_bling)

        if not col_origem:
            continue
        if col_origem not in df_origem.columns:
            continue

        serie = df_origem[col_origem].fillna("").astype(str).reset_index(drop=True)

        if coluna_imagens and col_bling == coluna_imagens:
            serie = serie.apply(normalizar_lista_urls_imagem)

        saida[col_bling] = serie.values

    if modo == MODO_ESTOQUE:
        hoje = datetime.now().strftime("%d/%m/%Y")

        saida[" ID Produto"] = ""

        if deposito_manual:
            saida["Deposito (OBRIGATÓRIO)"] = str(deposito_manual).strip()

        if "Data" in saida.columns:
            if "Data" not in mapeamento_manual or not mapeamento_manual.get("Data"):
                saida["Data"] = hoje
            else:
                saida["Data"] = saida["Data"].apply(lambda x: limpar_texto(x) or hoje)

        for col_num in ["Balanço (OBRIGATÓRIO)", "Preço unitário (OBRIGATÓRIO)", "Preço de Custo"]:
            if col_num in saida.columns:
                saida[col_num] = [
                    formatar_numero_brasileiro(normalizar_valor_numerico(v)) if limpar_texto(v) else ""
                    for v in saida[col_num].tolist()
                ]

        saida, logs_gtin = aplicar_validacao_gtin_df(saida, "GTIN **")
        for item in logs_gtin:
            log(item)

        return saida[colunas_bling]

    if config_precificacao.get("habilitada"):
        col_custo = config_precificacao.get("coluna_custo_origem")
        if col_custo and col_custo in df_origem.columns:
            lucro = normalizar_valor_numerico(config_precificacao.get("lucro_percentual"))
            impostos = normalizar_valor_numerico(config_precificacao.get("imposto_percentual"))
            taxas = normalizar_valor_numerico(config_precificacao.get("taxa_percentual"))
            fixo = normalizar_valor_numerico(config_precificacao.get("valor_fixo"))

            precos = []
            for valor in df_origem[col_custo].tolist():
                custo = normalizar_valor_numerico(valor)
                precos.append(calcular_preco_venda(custo, lucro, impostos, taxas, fixo))

            saida[coluna_preco] = precos

            if coluna_preco_custo and config_precificacao.get("preencher_preco_custo"):
                saida[coluna_preco_custo] = [
                    normalizar_valor_numerico(v) for v in df_origem[col_custo].tolist()
                ]

            if coluna_preco_compra and config_precificacao.get("preencher_preco_compra"):
                saida[coluna_preco_compra] = [
                    normalizar_valor_numerico(v) for v in df_origem[col_custo].tolist()
                ]

    if "GTIN/EAN" in saida.columns:
        saida, logs_gtin = aplicar_validacao_gtin_df(saida, "GTIN/EAN")
        for item in logs_gtin:
            log(item)

    if "Link Externo" in saida.columns:
        saida["Link Externo"] = ""

    if "Vídeo" in saida.columns:
        saida["Vídeo"] = ""

    if "Descrição Curta" in saida.columns and "Descrição" in saida.columns:
        descricao_curta_vazia = saida["Descrição Curta"].astype(str).str.strip().eq("")
        saida.loc[descricao_curta_vazia, "Descrição Curta"] = saida.loc[descricao_curta_vazia, "Descrição"]

    return saida[colunas_bling]


def gerar_excel_download(df_saida: pd.DataFrame) -> bytes:
    try:
        return salvar_excel_bytes(df_saida)
    except Exception:
        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df_saida.to_excel(writer, index=False)
        output.seek(0)
        return output.getvalue()


def carregar_arquivo_origem(arquivo_origem) -> Optional[pd.DataFrame]:
    try:
        df_origem = carregar_planilha(arquivo_origem)
        if df_origem is None or df_origem.empty:
            return None

        df_origem = df_origem.copy()
        df_origem.columns = [str(c).strip() for c in df_origem.columns]
        df_origem = df_origem.dropna(axis=0, how="all").reset_index(drop=True)
        return df_origem
    except Exception as e:
        log(f"Erro ao ler planilha do fornecedor: {e}")
        return None


# =========================================================
# APP
# =========================================================
def main() -> None:
    init_state()

    st.title("Bling Manual PRO")
    st.caption("Cadastro + Estoque no modelo oficial do Bling → sugestão inteligente → conferência → download")

    with st.sidebar:
        st.header("Ações")

        modo_operacao = st.radio(
            "Modo de operação",
            [MODO_CADASTRO, MODO_ESTOQUE],
            index=0 if st.session_state.get("modo_operacao", MODO_CADASTRO) == MODO_CADASTRO else 1,
        )
        st.session_state["modo_operacao"] = modo_operacao

        if st.button("🧹 Limpar tudo", use_container_width=True):
            limpar_tudo()
            st.session_state["modo_operacao"] = modo_operacao
            st.rerun()

        if st.button("♻️ Zerar mapeamento", use_container_width=True):
            zerar_mapeamento_visual()
            st.rerun()

        st.divider()

        if modo_operacao == MODO_ESTOQUE:
            st.markdown("**Modelo oficial travado: Estoque**")
            st.caption("10 colunas fixas do modelo de saldo de estoque")
            st.caption("Depósito manual obrigatório")
        else:
            st.markdown("**Modelo oficial travado: Cadastro**")
            st.caption("59 colunas fixas do Bling")

        st.caption("A sugestão usa nome da coluna + amostra real + histórico salvo")
        st.caption("Na dúvida, deixa em branco")

    modelo = get_modelo(modo_operacao)
    colunas_bling = modelo["colunas"]
    obrigatorios = modelo["obrigatorios"]

    st.markdown("## 1) Suba a planilha do fornecedor")

    arquivo_origem = st.file_uploader(
        "Planilha do fornecedor",
        type=["xlsx", "xls", "csv", "zip"],
        key=f"upload_origem_{slug_modo(modo_operacao)}",
    )

    if arquivo_origem is not None:
        chave_atual = f"{modo_operacao}-{arquivo_origem.name}-{getattr(arquivo_origem, 'size', 0)}"

        if st.session_state["ultima_chave_origem"] != chave_atual:
            df_origem = carregar_arquivo_origem(arquivo_origem)

            if df_origem is None or df_origem.empty:
                st.error("Erro ao ler a planilha do fornecedor.")
                return

            st.session_state["df_origem"] = df_origem
            st.session_state["nome_arquivo_origem"] = arquivo_origem.name
            st.session_state["ultima_chave_origem"] = chave_atual
            st.session_state["df_saida"] = None

            fornecedor_id = fornecedor_id_por_nome(arquivo_origem.name, modo_operacao)
            st.session_state["fornecedor_id"] = fornecedor_id

            mapeamento_auto, confianca = sugerir_mapeamento_local_refinado(df_origem, modo_operacao)
            aplicar_sugestao_no_estado(mapeamento_auto, confianca)

            salvo = carregar_mapeamento_fornecedor(fornecedor_id)
            if salvo:
                aplicar_sugestao_no_estado(
                    salvo.get("mapeamento_manual", {}),
                    st.session_state.get("sugestao_confianca", {}),
                )
                st.session_state["precificacao_config"] = salvo.get("precificacao_config", {})
                log(f"Mapeamento reaproveitado automaticamente para: {fornecedor_id}")

            log(f"Planilha do fornecedor carregada: {arquivo_origem.name}")

    df_origem = st.session_state["df_origem"]

    if df_origem is None:
        st.info("Anexe a planilha do fornecedor para começar.")
        return

    st.success(f"✅ Arquivo carregado: {st.session_state['nome_arquivo_origem']}")

    c1, c2, c3 = st.columns(3)
    c1.metric("Linhas", len(df_origem))
    c2.metric("Colunas do fornecedor", len(df_origem.columns))
    c3.metric("Fornecedor ID", st.session_state["fornecedor_id"] or "-")

    with st.expander("👀 Ver planilha do fornecedor", expanded=False):
        try:
            df_origem_preview = df_origem.astype(str)
        except Exception:
            df_origem_preview = df_origem.copy()

        st.markdown("### 📊 Prévia da planilha (dados reais)")
        st.dataframe(df_origem_preview.head(20), use_container_width=True)

        st.markdown("### 🧠 Colunas detectadas")
        df_colunas = pd.DataFrame({
            "Nº": list(range(1, len(df_origem.columns) + 1)),
            "Nome da coluna": list(df_origem.columns),
        })
        st.dataframe(df_colunas, use_container_width=True, hide_index=True)

    st.markdown("## 2) Sugestão inteligente refinada")

    s1, s2, s3 = st.columns([1.5, 1.3, 3.2])

    with s1:
        if st.button("🧠 Recalcular sugestões", use_container_width=True):
            mapeamento_auto, confianca = sugerir_mapeamento_local_refinado(df_origem, modo_operacao)
            atual = st.session_state.get("mapeamento_manual", {}) or {}
            combinado = {}

            for campo in colunas_bling:
                combinado[campo] = atual.get(campo) or mapeamento_auto.get(campo)

            aplicar_sugestao_no_estado(combinado, confianca)
            st.success("Sugestões refinadas aplicadas.")
            st.rerun()

    with s2:
        usar_openai = st.checkbox("Usar IA se disponível", value=False, key=f"usar_openai_checkbox_{slug_modo(modo_operacao)}")
        if st.button("✨ Refinar com IA", use_container_width=True, disabled=not usar_openai):
            mapeamento_ia = sugerir_mapeamento_openai(df_origem, modo_operacao)
            if mapeamento_ia:
                atual = st.session_state.get("mapeamento_manual", {}) or {}
                combinado = {}
                for campo in colunas_bling:
                    combinado[campo] = atual.get(campo) or mapeamento_ia.get(campo)
                aplicar_sugestao_no_estado(combinado, st.session_state.get("sugestao_confianca", {}))
                st.success("Sugestão por IA aplicada. Onde houve dúvida, o campo permaneceu em branco ou foi mantido.")
                st.rerun()
            else:
                st.warning("IA não disponível ou sem resposta válida. Mantive o mapeamento atual.")

    with s3:
        st.caption(
            "A sugestão usa o nome da coluna, uma amostra real dos valores e o histórico dos mapeamentos salvos. "
            "Quando a confiança não passa do limite ou fica muito próxima da segunda melhor opção, o campo fica em branco."
        )

    if modo_operacao == MODO_ESTOQUE:
        st.markdown("## 3) Configuração fixa do estoque")
        deposito_manual = st.text_input(
            "Depósito que será lançado na planilha final",
            value="GERAL",
            key="deposito_manual_estoque",
        ).strip()
    else:
        deposito_manual = ""

    mapeamento_manual = construir_mapeamento_visual(df_origem, modo_operacao)
    st.session_state["mapeamento_manual"] = mapeamento_manual

    if modo_operacao == MODO_ESTOQUE and deposito_manual:
        mapeamento_manual["Deposito (OBRIGATÓRIO)"] = None
        st.caption("O campo depósito será preenchido pelo valor digitado acima na geração final.")

    campos_sem_vinculo, obrigatorios_sem_vinculo = analisar_vinculos(mapeamento_manual, obrigatorios)

    if modo_operacao == MODO_ESTOQUE and deposito_manual:
        obrigatorios_sem_vinculo = [c for c in obrigatorios_sem_vinculo if c != "Deposito (OBRIGATÓRIO)"]
        campos_sem_vinculo = [c for c in campos_sem_vinculo if c != "Deposito (OBRIGATÓRIO)"]

    st.session_state["campos_sem_vinculo"] = campos_sem_vinculo
    st.session_state["campos_obrigatorios_sem_vinculo"] = obrigatorios_sem_vinculo

    st.markdown("## 4) Status da conferência")

    if obrigatorios_sem_vinculo:
        st.error("Campos obrigatórios sem vínculo: " + ", ".join(obrigatorios_sem_vinculo))
    else:
        st.success("Todos os campos obrigatórios estão vinculados.")

    opcionais_sem_vinculo = [c for c in campos_sem_vinculo if c not in obrigatorios_sem_vinculo]
    if opcionais_sem_vinculo:
        st.warning("Campos opcionais sem vínculo: " + ", ".join(opcionais_sem_vinculo))

    precificacao_config = st.session_state.get("precificacao_config", {}) or {}

    if modo_operacao == MODO_CADASTRO:
        st.markdown("## 5) Precificação inteligente")

        opcoes_origem = [""] + list(df_origem.columns)
        config_salva = st.session_state.get("precificacao_config", {}) or {}

        p1, p2, p3, p4, p5 = st.columns(5)

        with p1:
            habilitada = st.checkbox(
                "Ativar precificação",
                value=bool(config_salva.get("habilitada", False)),
                key="cfg_habilitada",
            )

        with p2:
            coluna_custo_origem = st.selectbox(
                "Coluna de custo",
                options=opcoes_origem,
                index=opcoes_origem.index(config_salva.get("coluna_custo_origem", "")) if config_salva.get("coluna_custo_origem", "") in opcoes_origem else 0,
                key="cfg_coluna_custo_origem",
                disabled=not habilitada,
            )

        with p3:
            lucro = st.number_input(
                "Lucro %",
                min_value=0.0,
                value=float(config_salva.get("lucro_percentual", 0.0)),
                step=0.1,
                key="cfg_lucro_percentual",
                disabled=not habilitada,
            )

        with p4:
            impostos = st.number_input(
                "Impostos %",
                min_value=0.0,
                value=float(config_salva.get("imposto_percentual", 0.0)),
                step=0.1,
                key="cfg_imposto_percentual",
                disabled=not habilitada,
            )

        with p5:
            taxas = st.number_input(
                "Taxas %",
                min_value=0.0,
                value=float(config_salva.get("taxa_percentual", 0.0)),
                step=0.1,
                key="cfg_taxa_percentual",
                disabled=not habilitada,
            )

        p6, p7, p8 = st.columns([1.2, 1.2, 2.6])

        with p6:
            valor_fixo = st.number_input(
                "Valor fixo",
                min_value=0.0,
                value=float(config_salva.get("valor_fixo", 0.0)),
                step=0.01,
                key="cfg_valor_fixo",
                disabled=not habilitada,
            )

        with p7:
            preencher_preco_custo = st.checkbox(
                "Preencher Preço de custo",
                value=bool(config_salva.get("preencher_preco_custo", True)),
                key="cfg_preencher_preco_custo",
                disabled=not habilitada,
            )
            preencher_preco_compra = st.checkbox(
                "Preencher Preço de compra",
                value=bool(config_salva.get("preencher_preco_compra", False)),
                key="cfg_preencher_preco_compra",
                disabled=not habilitada,
            )

        with p8:
            if habilitada and coluna_custo_origem:
                exemplo_custo = 100.0
                exemplo_preco = calcular_preco_venda(exemplo_custo, lucro, impostos, taxas, valor_fixo)
                st.success(
                    f"Exemplo: custo 100,00 → venda {exemplo_preco:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                )
            else:
                st.caption("Ative a precificação e escolha a coluna de custo para recalcular o preço de venda.")

        precificacao_config = {
            "habilitada": bool(habilitada),
            "coluna_custo_origem": coluna_custo_origem,
            "lucro_percentual": float(lucro),
            "imposto_percentual": float(impostos),
            "taxa_percentual": float(taxas),
            "valor_fixo": float(valor_fixo),
            "preencher_preco_custo": bool(preencher_preco_custo),
            "preencher_preco_compra": bool(preencher_preco_compra),
        }
        st.session_state["precificacao_config"] = precificacao_config
    else:
        st.markdown("## 5) Precificação no estoque")
        st.caption("No modo estoque, o preço unitário vai direto para a coluna oficial do modelo fixo. A precificação de IA fica desligada neste modo.")
        precificacao_config = {
            "habilitada": False,
            "coluna_custo_origem": "",
            "lucro_percentual": 0.0,
            "imposto_percentual": 0.0,
            "taxa_percentual": 0.0,
            "valor_fixo": 0.0,
            "preencher_preco_custo": True,
            "preencher_preco_compra": False,
        }
        st.session_state["precificacao_config"] = precificacao_config

    st.markdown("## 6) Reaproveitamento do fornecedor")

    sv1, sv2 = st.columns([1.5, 3.5])

    with sv1:
        if st.button("💾 Salvar mapeamento deste fornecedor", use_container_width=True):
            fornecedor_id = st.session_state["fornecedor_id"] or fornecedor_id_por_nome(
                st.session_state["nome_arquivo_origem"],
                modo_operacao,
            )
            salvar_mapeamento_fornecedor(
                fornecedor_id=fornecedor_id,
                nome_arquivo_origem=st.session_state["nome_arquivo_origem"],
                mapeamento_manual=mapeamento_manual,
                precificacao_config=precificacao_config,
                modo_operacao=modo_operacao,
            )
            st.success("Mapeamento salvo com sucesso.")
            log(f"Mapeamento salvo para fornecedor: {fornecedor_id}")

    with sv2:
        st.caption("Quando subir novamente uma planilha do mesmo fornecedor no mesmo modo, o sistema tenta reaproveitar o vínculo salvo automaticamente.")

    st.markdown("## 7) Gerar planilha final")

    if st.button("📦 Gerar planilha para conferência", use_container_width=True):
        try:
            df_saida = gerar_planilha_saida(
                df_origem=df_origem,
                mapeamento_manual=mapeamento_manual,
                config_precificacao=precificacao_config,
                modo=modo_operacao,
                deposito_manual=deposito_manual,
            )
            st.session_state["df_saida"] = df_saida
            log(f"Planilha final gerada com {len(df_saida)} linhas no modo {modo_operacao}.")
            st.success("Planilha gerada. Revise a prévia abaixo antes de baixar.")
        except Exception as e:
            st.error(f"Erro ao gerar planilha final: {e}")
            log(f"Erro ao gerar planilha final: {e}")

    df_saida = st.session_state.get("df_saida")

    if df_saida is not None and not df_saida.empty:
        st.markdown("## 8) Prévia final para conferência")
        st.dataframe(df_saida.head(20), use_container_width=True)

        st.markdown("### Resumo rápido")
        r1, r2, r3 = st.columns(3)
        r1.metric("Linhas na saída", len(df_saida))
        r2.metric("Colunas fixas Bling", len(df_saida.columns))
        preenchidas = sum(1 for c in df_saida.columns if df_saida[c].astype(str).str.strip().ne("").any())
        r3.metric("Colunas com algum valor", preenchidas)

        arquivo_excel = gerar_excel_download(df_saida)

        nome_download = (
            "bling_estoque_modelo_oficial.xlsx"
            if modo_operacao == MODO_ESTOQUE
            else "bling_cadastro_travado_modelo_oficial.xlsx"
        )

        st.download_button(
            "📥 Baixar planilha final",
            data=arquivo_excel,
            file_name=nome_download,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

    if st.session_state["logs"]:
        with st.expander("Logs"):
            st.text_area(
                "Log",
                value="\n".join(st.session_state["logs"]),
                height=220,
            )


if __name__ == "__main__":
    main()
