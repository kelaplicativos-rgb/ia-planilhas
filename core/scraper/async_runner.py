import asyncio

from core.logger import log
from core.scraper.parser import extrair_site


async def _worker(name, queue, resultados, filtro, estoque_padrao):
    while True:
        link = await queue.get()

        if link is None:
            queue.task_done()
            break

        try:
            resultado = await asyncio.to_thread(
                extrair_site,
                link,
                filtro,
                estoque_padrao,
            )

            if resultado:
                resultados.append(resultado)

        except Exception as e:
            log(f"ERRO worker={name} link={link} detalhe={e}")

        finally:
            queue.task_done()


async def processar_links_em_fila_async(links, filtro="", estoque_padrao=0, concorrencia=2):
    queue = asyncio.Queue()
    resultados = []

    for link in links:
        await queue.put(link)

    workers = [
        asyncio.create_task(_worker(i + 1, queue, resultados, filtro, estoque_padrao))
        for i in range(max(1, concorrencia))
    ]

    await queue.join()

    for _ in workers:
        await queue.put(None)

    await asyncio.gather(*workers)

    return resultados


def rodar_fila_async(links, filtro="", estoque_padrao=0, concorrencia=2):
    try:
        return asyncio.run(
            processar_links_em_fila_async(
                links=links,
                filtro=filtro,
                estoque_padrao=estoque_padrao,
                concorrencia=concorrencia,
            )
        )
    except RuntimeError:
        log("Fallback async acionado")
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(
                processar_links_em_fila_async(
                    links=links,
                    filtro=filtro,
                    estoque_padrao=estoque_padrao,
                    concorrencia=concorrencia,
                )
            )
        finally:
            loop.close()
