from bling_app_zero.core.site_crawler.crawler_engine import run_crawler

def buscar_dataframe(self, *, base_url: str, **kwargs):
    return run_crawler(base_url)
