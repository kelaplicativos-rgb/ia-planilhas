import time
import pandas as pd

from core.logger import logs, log
from core.reader import ler_planilha
from core.scraper import coletar_links_site, extrair_site
from core.normalizer import normalizar_planilha_entrada
from core.bling.estoque import preencher_modelo_estoque
from core.bling.cadastro import preencher_modelo_cadastro
from core.merger import merge_dados


def formatar_tempo(segundos: float) -> str:
    segundos = int(max(0, segundos))
    minutos = segundos // 60
    resto = segundos % 60
    if minutos > 0:
        return f"{minutos}m {resto}s"
    return f"{resto}s"


def registrar_etapa(relatorio, etapa, ok, tempo, detalhes="", erro=""):
    relatorio.append({
        "Etapa": etapa,
        "Status": "OK" if ok else "ERRO",
        "Tempo": formatar_tempo(tempo),
        "Detalhes": detalhes,
        "Erro": erro,
    })


def relatorio_para_txt(relatorio):
    linhas = []
    linhas.append("RELATÓRIO DE DIAGNÓSTICO")
    linhas.append("=" * 50)

    for item in relatorio:
        linhas.append(f"Etapa: {item['Etapa']}")
        linhas.append(f"Status: {item['Status']}")
        if item.get("Detalhes"):
            linhas.append(f"Detalhes: {item['Detalhes']}")
        if item.get("Erro"):
            linhas.append(f"Erro: {item['Erro']}")
        linhas.append(f"Tempo: {item['Tempo']}")
        linhas.append("-" * 50)

    return "\n".join(linhas)


def garantir_colunas_finais(df: pd.DataFrame) -> pd.DataFrame:
    colunas_necessarias = [
        "Código",
        "GTIN",
        "Produto",
        "Preço",
        "Preço Custo",
        "Descrição Curta",
        "Descrição Complementar",
        "Imagem",
        "Link",
        "Marca",
        "Estoque",
        "NCM",
        "Origem",
        "Peso Líquido",
        "Peso Bruto",
        "Estoque Mínimo",
        "Estoque Máximo",
        "Unidade",
        "Tipo",
        "Situação",
    ]

    if df is None or df.empty:
        return pd.DataFrame(columns=colunas_necessarias)

    df = df.copy()

    for col in colunas_necessarias:
        if col not in df.columns:
            df[col] = ""

    df = df[colunas_necessarias].fillna("")
    df["Descrição Curta"] = df.apply(
        lambda r: r["Descrição Curta"] if str(r["Descrição Curta"]).strip() else str(r["Produto"]).strip(),
        axis=1,
    )
    df = df[df["Produto"].astype(str).str.strip() != ""].copy()

    return df.reset_index(drop=True)


def executar_diagnostico(
    *,
    modelo_estoque_file,
    modelo_cadastro_file,
    arquivo_dados,
    modo_coleta,
    url_base,
    estoque_padrao,
    depositos,
    diagnostico_amostra_links,
    uploaded_buffer_cls,
    atualizar_progresso_fn,
    progress,
    progresso_info,
    inicio_global,
):
    logs.clear()
    log("🧪 EXECUTANDO DIAGNÓSTICO POR BLOCOS 🧪")

    relatorio = []

    modelo_est = None
    modelo_cad = None
    entrada = None
    df_planilha = pd.DataFrame()
    links = []
    produtos = []
    df_site = pd.DataFrame()
    df_final = pd.DataFrame()
    df_estoque = pd.DataFrame()
    df_cadastro = pd.DataFrame()

    etapas_total = 10
    etapa_atual = 0

    def avanca(etapa_nome):
        nonlocal etapa_atual
        etapa_atual += 1
        atualizar_progresso_fn(
            progress,
            progresso_info,
            etapa_atual / etapas_total,
            etapa_nome,
            inicio_global,
        )

    # 1. modelo estoque
    t0 = time.time()
    try:
        if not modelo_estoque_file:
            raise ValueError("Modelo ESTOQUE não enviado")

        modelo_est = ler_planilha(
            uploaded_buffer_cls(modelo_estoque_file.getvalue(), modelo_estoque_file.name)
        )

        if modelo_est is None or modelo_est.empty:
            raise ValueError("Modelo ESTOQUE vazio ou inválido")

        registrar_etapa(
            relatorio,
            "Leitura modelo estoque",
            True,
            time.time() - t0,
            f"{len(modelo_est)} linhas | {len(modelo_est.columns)} colunas",
        )
    except Exception as e:
        registrar_etapa(relatorio, "Leitura modelo estoque", False, time.time() - t0, erro=str(e))
        avanca("Erro na leitura do modelo estoque")
        return {"relatorio": pd.DataFrame(relatorio), "txt": relatorio_para_txt(relatorio)}
    avanca("Leitura modelo estoque OK")

    # 2. modelo cadastro
    t0 = time.time()
    try:
        if not modelo_cadastro_file:
            raise ValueError("Modelo CADASTRO não enviado")

        modelo_cad = ler_planilha(
            uploaded_buffer_cls(modelo_cadastro_file.getvalue(), modelo_cadastro_file.name)
        )

        if modelo_cad is None or modelo_cad.empty:
            raise ValueError("Modelo CADASTRO vazio ou inválido")

        registrar_etapa(
            relatorio,
            "Leitura modelo cadastro",
            True,
            time.time() - t0,
            f"{len(modelo_cad)} linhas | {len(modelo_cad.columns)} colunas",
        )
    except Exception as e:
        registrar_etapa(relatorio, "Leitura modelo cadastro", False, time.time() - t0, erro=str(e))
        avanca("Erro na leitura do modelo cadastro")
        return {"relatorio": pd.DataFrame(relatorio), "txt": relatorio_para_txt(relatorio)}
    avanca("Leitura modelo cadastro OK")

    # 3. planilha de dados
    t0 = time.time()
    try:
        detalhe = "Etapa ignorada neste modo"

        if modo_coleta in ["Planilha + Site", "Só Planilha"]:
            if not arquivo_dados:
                raise ValueError("Planilha de dados não enviada")

            entrada = ler_planilha(
                uploaded_buffer_cls(arquivo_dados.getvalue(), arquivo_dados.name)
            )

            if entrada is None or entrada.empty:
                raise ValueError("Planilha de dados vazia ou inválida")

            detalhe = f"{len(entrada)} linhas | {len(entrada.columns)} colunas"

        registrar_etapa(relatorio, "Leitura planilha de dados", True, time.time() - t0, detalhe)
    except Exception as e:
        registrar_etapa(relatorio, "Leitura planilha de dados", False, time.time() - t0, erro=str(e))
        avanca("Erro na leitura da planilha")
        return {"relatorio": pd.DataFrame(relatorio), "txt": relatorio_para_txt(relatorio)}
    avanca("Leitura planilha OK")

    # 4. normalização
    t0 = time.time()
    try:
        detalhe = "Etapa ignorada neste modo"

        if entrada is not None and not entrada.empty:
            df_planilha = normalizar_planilha_entrada(
                entrada,
                url_base=url_base,
                estoque_padrao=estoque_padrao,
            )
            detalhe = f"{len(df_planilha)} linhas após normalização"

        registrar_etapa(relatorio, "Normalização da planilha", True, time.time() - t0, detalhe)
    except Exception as e:
        registrar_etapa(relatorio, "Normalização da planilha", False, time.time() - t0, erro=str(e))
        avanca("Erro na normalização")
        return {"relatorio": pd.DataFrame(relatorio), "txt": relatorio_para_txt(relatorio)}
    avanca("Normalização OK")

    # 5. coleta links
    t0 = time.time()
    try:
        detalhe = "Etapa ignorada neste modo"

        if modo_coleta in ["Planilha + Site", "Só Site"]:
            links = coletar_links_site(url_base)
            detalhe = f"{len(links)} links coletados"

        registrar_etapa(relatorio, "Coleta de links", True, time.time() - t0, detalhe)
    except Exception as e:
        registrar_etapa(relatorio, "Coleta de links", False, time.time() - t0, erro=str(e))
        avanca("Erro na coleta de links")
        return {"relatorio": pd.DataFrame(relatorio), "txt": relatorio_para_txt(relatorio)}
    avanca("Coleta de links OK")

    # 6. extração do site
    t0 = time.time()
    try:
        detalhe = "Etapa ignorada neste modo"

        if modo_coleta in ["Planilha + Site", "Só Site"] and links:
            amostra = links[:diagnostico_amostra_links]

            for link in amostra:
                try:
                    r = extrair_site(link, "", estoque_padrao)
                    if r:
                        produtos.append(r)
                except Exception as ex:
                    log(f"Falha extração diagnóstico: {ex}")

            df_site = pd.DataFrame(produtos)
            detalhe = f"{len(produtos)} produtos extraídos em {len(amostra)} links testados"

        registrar_etapa(relatorio, "Extração de produtos do site", True, time.time() - t0, detalhe)
    except Exception as e:
        registrar_etapa(relatorio, "Extração de produtos do site", False, time.time() - t0, erro=str(e))
        avanca("Erro na extração do site")
        return {"relatorio": pd.DataFrame(relatorio), "txt": relatorio_para_txt(relatorio)}
    avanca("Extração do site OK")

    # 7. merge
    t0 = time.time()
    try:
        df_final = merge_dados(df_planilha, df_site, url_base, estoque_padrao)
        df_final = garantir_colunas_finais(df_final)

        if df_final is None or df_final.empty:
            raise ValueError("Merge não gerou dados válidos")

        registrar_etapa(
            relatorio,
            "Merge final",
            True,
            time.time() - t0,
            f"{len(df_final)} linhas após merge",
        )
    except Exception as e:
        registrar_etapa(relatorio, "Merge final", False, time.time() - t0, erro=str(e))
        avanca("Erro no merge")
        return {"relatorio": pd.DataFrame(relatorio), "txt": relatorio_para_txt(relatorio)}
    avanca("Merge OK")

    # 8. estoque
    t0 = time.time()
    try:
        df_estoque = preencher_modelo_estoque(modelo_est, df_final, depositos)

        if df_estoque is None or df_estoque.empty:
            raise ValueError("Planilha de estoque não gerada")

        registrar_etapa(
            relatorio,
            "Geração planilha estoque",
            True,
            time.time() - t0,
            f"{len(df_estoque)} linhas geradas",
        )
    except Exception as e:
        registrar_etapa(relatorio, "Geração planilha estoque", False, time.time() - t0, erro=str(e))
        avanca("Erro no estoque")
        return {"relatorio": pd.DataFrame(relatorio), "txt": relatorio_para_txt(relatorio)}
    avanca("Estoque OK")

    # 9. cadastro
    t0 = time.time()
    try:
        df_cadastro = preencher_modelo_cadastro(modelo_cad, df_final)

        if df_cadastro is None or df_cadastro.empty:
            raise ValueError("Planilha de cadastro não gerada")

        registrar_etapa(
            relatorio,
            "Geração planilha cadastro",
            True,
            time.time() - t0,
            f"{len(df_cadastro)} linhas geradas",
        )
    except Exception as e:
        registrar_etapa(relatorio, "Geração planilha cadastro", False, time.time() - t0, erro=str(e))
        avanca("Erro no cadastro")
        return {"relatorio": pd.DataFrame(relatorio), "txt": relatorio_para_txt(relatorio)}
    avanca("Cadastro OK")

    # 10. zip
    t0 = time.time()
    try:
        csv_estoque = df_estoque.to_csv(index=False, sep=";", encoding="utf-8-sig")
        csv_cadastro = df_cadastro.to_csv(index=False, sep=";", encoding="utf-8-sig")
        log_texto = "\n".join(logs)

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr("estoque.csv", csv_estoque)
            z.writestr("cadastro.csv", csv_cadastro)
            z.writestr("debug_log.txt", log_texto or "")
        zip_bytes = zip_buffer.getvalue()

        if not zip_bytes:
            raise ValueError("ZIP não gerado")

        registrar_etapa(
            relatorio,
            "Geração do ZIP",
            True,
            time.time() - t0,
            f"{len(zip_bytes)} bytes",
        )
    except Exception as e:
        registrar_etapa(relatorio, "Geração do ZIP", False, time.time() - t0, erro=str(e))
        avanca("Erro no ZIP")
        return {"relatorio": pd.DataFrame(relatorio), "txt": relatorio_para_txt(relatorio)}
    avanca("ZIP OK")

    return {
        "relatorio": pd.DataFrame(relatorio),
        "txt": relatorio_para_txt(relatorio),
        "df_final": df_final,
        "df_estoque": df_estoque,
        "df_cadastro": df_cadastro,
  }
