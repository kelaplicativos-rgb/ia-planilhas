from bs4 import BeautifulSoup


def extract_product_from_page(html, url):
    soup = BeautifulSoup(html, "lxml")

    nome = ""
    preco = ""

    if soup.find("h1"):
        nome = soup.find("h1").get_text(strip=True)

    if soup.find(attrs={"class": lambda x: x and "price" in x.lower()}):
        preco = soup.find(attrs={"class": lambda x: x and "price" in x.lower()}).get_text(strip=True)

    imagens = []
    for img in soup.find_all("img"):
        src = img.get("src")
        if src and "http" in src:
            imagens.append(src)

    return {
        "nome": nome,
        "preco": preco,
        "url": url,
        "imagens": imagens[:5],
    }
