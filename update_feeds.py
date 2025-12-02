#!/usr/bin/env python3
import html
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path

# Configuração das cidades
CITIES = {
    "colider": {
        "name": "Prefeitura de Colíder",
        "list_url": "https://www.colider.mt.gov.br/Imprensa/Noticias/",
        "site_url": "https://www.colider.mt.gov.br/",
        "domain": "https://www.colider.mt.gov.br",
        "description": "Últimas notícias da Prefeitura de Colíder (MT).",
    },
    "altafloresta": {
        "name": "Prefeitura de Alta Floresta",
        "list_url": "https://www.altafloresta.mt.gov.br/Noticias/",
        "site_url": "https://www.altafloresta.mt.gov.br/",
        "domain": "https://www.altafloresta.mt.gov.br",
        "description": "Últimas notícias da Prefeitura de Alta Floresta (MT).",
    },
    "guaranta": {
        "name": "Prefeitura de Guarantã do Norte",
        "list_url": "https://www.guarantadonorte.mt.gov.br/Noticias/",
        "site_url": "https://www.guarantadonorte.mt.gov.br/",
        "domain": "https://www.guarantadonorte.mt.gov.br",
        "description": "Últimas notícias da Prefeitura de Guarantã do Norte (MT).",
    },
    "matupa": {
        "name": "Prefeitura de Matupá",
        "list_url": "https://www.matupa.mt.gov.br/Imprensa/Noticias/",
        "site_url": "https://www.matupa.mt.gov.br/",
        "domain": "https://www.matupa.mt.gov.br",
        "description": "Últimas notícias da Prefeitura de Matupá (MT).",
    },
}

MAX_ITEMS = 10  # Número máximo de notícias por feed
OUTPUT_DIR = Path("feeds")
OUTPUT_DIR.mkdir(exist_ok=True)


def log(msg: str):
    print(f"[{datetime.now().isoformat(sep=' ', timespec='seconds')}] {msg}")


def absolute_url(domain: str, href: str) -> str:
    href = href.strip()
    if href.startswith("http://") or href.startswith("https://"):
        return href
    if not href.startswith("/"):
        href = "/" + href
    return domain.rstrip("/") + href


def extract_list_links(city_key: str, cfg: dict):
    """
    Tenta extrair links de notícias a partir da página de listagem.
    Estratégia genérica:
      - pega <a> cujo href contenha '/Noticias/' ou '/Imprensa/Noticias/'
      - filtra textos curtos (menu/rodapé)
    """
    url = cfg["list_url"]
    domain = cfg["domain"]
    log(f"[{city_key}] Buscando lista de notícias em {url}")

    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    links = []
    seen = set()

    for a in soup.find_all("a", href=True):
        href = a["href"]
        full = absolute_url(domain, href)

        if "/Noticias/" not in full and "/Imprensa/Noticias/" not in full:
            continue

        title = a.get_text(strip=True)
        if not title or len(title) < 20:  # evita itens pequenos
            continue

        if full in seen:
            continue

        seen.add(full)
        links.append({"title": title, "url": full})

        if len(links) >= MAX_ITEMS:
            break

    log(f"[{city_key}] Encontrados {len(links)} links de notícias")
    return links


def extract_article_details(article_url: str):
    """
    Tenta extrair:
      - título (H1 ou <title>)
      - primeiro parágrafo
      - data (por enquanto: data atual)
    """
    resp = requests.get(article_url, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    h1 = soup.find("h1")
    if h1:
        title = h1.get_text(strip=True)
    elif soup.title:
        title = soup.title.get_text(strip=True)
    else:
        title = article_url

    description = ""
    for p in soup.find_all("p"):
        text = p.get_text(" ", strip=True)
        if text:
            description = text
            break

    if not description:
        description = title

    pub_date = datetime.now(timezone.utc)

    return {
        "title": title,
        "url": article_url,
        "description": description,
        "pub_date": pub_date,
    }


def escape_xml(text: str) -> str:
    return html.escape(text or "", quote=True)


def build_rss(city_key: str, cfg: dict, items: list) -> str:
    now = datetime.now(timezone.utc)
    channel_title = cfg["name"]
    channel_link = cfg["site_url"]
    channel_desc = cfg["description"]

    rss_items_xml = []
    for item in items:
        title = escape_xml(item["title"])
        link = escape_xml(item["url"])

        desc_cdata = f"<![CDATA[{item['description']}]]>"
        pub_date_str = format_datetime(item["pub_date"])

        rss_items_xml.append(
            f"""    <item>
      <title>{title}</title>
      <link>{link}</link>
      <guid>{link}</guid>
      <description>{desc_cdata}</description>
      <pubDate>{pub_date_str}</pubDate>
    </item>"""
        )

    items_block = "\n".join(rss_items_xml)

    rss = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>{escape_xml(channel_title)}</title>
    <link>{escape_xml(channel_link)}</link>
    <description>{escape_xml(channel_desc)}</description>
    <language>pt-BR</language>
    <lastBuildDate>{format_datetime(now)}</lastBuildDate>

{items_block}
  </channel>
</rss>
"""
    return rss


def update_city_feed(city_key: str, cfg: dict):
    links = extract_list_links(city_key, cfg)

    articles = []
    for link in links:
        try:
            details = extract_article_details(link["ur]()

