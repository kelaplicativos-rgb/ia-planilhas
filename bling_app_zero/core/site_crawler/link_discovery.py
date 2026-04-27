from bs4 import BeautifulSoup
from urllib.parse import urljoin


def extract_product_links(html, base):
    soup = BeautifulSoup(html, "lxml")

    links = []

    for a in soup.find_all("a", href=True):
        href = urljoin(base, a["href"])

        if "/produto" in href or "/p/" in href:
            links.append(href)

    return links


def extract_category_links(html, base):
    return []


def extract_pagination_links(html, base):
    return []
