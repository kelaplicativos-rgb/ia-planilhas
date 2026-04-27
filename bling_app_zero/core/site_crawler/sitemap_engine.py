def discover_links_from_sitemap(session, base_url):
    urls = []

    try:
        sitemap = base_url.rstrip("/") + "/sitemap.xml"
        r = session.get(sitemap, timeout=20, verify=False)

        if r.status_code == 200:
            for line in r.text.split():
                if "<loc>" in line:
                    urls.append(line.replace("<loc>", "").replace("</loc>", ""))

    except Exception:
        pass

    return urls
