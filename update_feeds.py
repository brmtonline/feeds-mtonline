#!/usr/bin/env python3
"""
Gera o feed RSS de notícias da Prefeitura de Colíder (MT).

- Lê a página de notícias: https://www.colider.mt.gov.br/Imprensa/Noticias/
- Coleta links de notícias reais (ignorando menu, rodapé, etc.)
- Abre cada notícia para extrair título e descrição
- Gera feeds/colider.xml com até MAX_ITEMS itens
"""

from pathlib import Path
from datetime import datetime, timezone
from email.utils import format_datetime
import html

import requests
from bs4 import BeautifulSoup

# Configuração da cidade (por enquanto só Colíder)
CITY_NAME = "Prefeitura de Colíder"
LIST_URL = "https://www.colider.mt.gov.br/Imprensa/Noticias/"
SITE_URL = "https://www.colider.mt.gov.br/Imprensa/Noticias/"
DOMAIN = "https://www.colider.mt.gov.br"

MAX_ITEMS = 10
OUTPUT_DIR = Path("feeds")
OUTPUT_DIR.mkdir(exist_ok=True)


def log(msg: str) -> None:
    now = datetime.now().isoformat(sep=" ", timespec="seconds")
    print(f"[{now}] {msg}")


def absolute_url(href: str) -> str:
    href = href.strip()
    if href.startswith("http://") or href.startswith("https://"):
        return href
    if not href.startswith("/"):
        href = "/" + href
    return DOMAIN.rstrip("/") + href


def extract_list_links() -> list[str]:
    """
    Lê a página de notícias e retorna uma lista de URLs de notícias.
    Critérios:
    - href contém '/Imprensa/Noticias/'
    - não contém '#'
    - texto não é de rodapé/cabeçalho
    """
    log(f"[colider] Buscando lista em {LIST_URL}")
    resp = requests.get(LIST_URL, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    links: list[str] = []
    seen: set[str] = set()

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        text = a.get_text(" ", strip=True)

        if not text:
            continue

        # Apenas links de notícias
        if "/Imprensa/Noticias/" not in href:
            continue

        # Ignora âncoras internas
        if "#" in href:
            continue

        text_low = text.lower()

        # Ignorar textos típicos de rodapé/cabeçalho
        if "todos os direitos reservados" in text_low:
            continue
        if "unidade fiscal do municipio de colider" in text_low:
            continue
        if "portal da transparencia" in text_low:
            continue

        full = absolute_url(href)
        if full in seen:
            continue

        seen.add(full)
        links.append(full)

        if len(links) >= MAX_ITEMS:
            break

    log(f"[colider] Encontrados {len(links)} links de notícias")
    return links


def extract_article(url: str) -> dict:
    """
    Abre uma notícia individual e extrai:
    - title: <h1> ou <title>
    - description: primeiros parágrafos relevantes
    - pub_date: agora (por enquanto, sem parse da data)
    """
    log(f"[colider] Abrindo notícia: {url}")
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # Título
    title = url
    h1 = soup.find("h1")
    if h1:
        t = h1.get_text(strip=True)
        if t:
            title = t
    elif soup.title:
        t = soup.title.get_text(strip=True)
        if t:
            title = t

    # Descrição
    paragraphs: list[str] = []
    for p in soup.find_all("p"):
        text = p.get_text(" ", strip=True)
        if not text:
            continue

        text_low = text.lower()

        # Ignorar rodapé, cookies, UFCL etc.
        if "unidade fiscal do municipio de colider" in text_low:
            continue
        if "todos os direitos reservados" in text_low:
            continue
        if "este site utiliza cookies" in text_low:
            continue

        paragraphs.append(text)
        if len(" ".join(paragraphs)) > 500:
            break

    description = " ".join(paragraphs) if paragraphs else title

    return {
        "title": title,
        "url": url,
        "description": description,
        "pub_date": datetime.now(timezone.utc),
    }


def escape_xml(text: str) -> str:
    return html.escape(text or "", quote=True)


def build_rss(items: list[dict]) -> str:
    """
    Monta o XML RSS com os itens coletados.
    """
    now = datetime.now(timezone.utc)

    header = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0">',
        "  <channel>",
        f"    <title>{escape_xml(CITY_NAME)}</title>",
        f"    <link>{escape_xml(SITE_URL)}</link>",
        "    <description>Últimas notícias da Prefeitura de Colíder (MT).</description>",
        "    <language>pt-BR</language>",
        f"    <lastBuildDate>{format_datetime(now)}</lastBuildDate>",
        "",
    ]

    item_blocks: list[str] = []
    for item in items:
        title = escape_xml(item["title"])
        link = escape_xml(item["url"])
        desc_cdata = "<![CDATA[" + (item["description"] or "") + "]]>"
        pub_date_str = format_datetime(item["pub_date"])

        block_lines = [
            "    <item>",
            f"      <title>{title}</title>",
            f"      <link>{link}</link>",
            f"      <guid>{link}</guid>",
            f"      <description>{desc_cdata}</description>",
            f"      <pubDate>{pub_date_str}</pubDate>",
            "    </item>",
        ]
        item_blocks.append("\n".join(block_lines))

    footer = [
        "  </channel>",
        "</rss>",
    ]

    xml_lines = header + item_blocks + footer
    return "\n".join(xml_lines)


def main() -> None:
    links = extract_list_links()
    articles: list[dict] = []

    for url in links:
        try:
            article = extract_article(url)
            articles.append(article)
        except Exception as e:
            log(f"[colider] Erro ao processar {url}: {e}")

    if not articles:
        log("[colider] Nenhuma notícia processada; feed não será atualizado.")
        return

    rss_xml = build_rss(articles)
    output_file = OUTPUT_DIR / "colider.xml"
    output_file.write_text(rss_xml, encoding="utf-8")
    log(f"[colider] Feed atualizado em {output_file}")


if __name__ == "__main__":
    main()
