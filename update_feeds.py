#!/usr/bin/env python3
import html
import re
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# Apenas Colíder por enquanto (podemos depois adicionar as outras cidades aqui)
CITIES = {
    "colider": {
        "name": "Prefeitura de Colíder",
        "list_url": "https://www.colider.mt.gov.br/Imprensa/Noticias/",
        "site_url": "https://www.colider.mt.gov.br/Imprensa/Noticias/",
        "domain": "https://www.colider.mt.gov.br",
        "description": "Últimas notícias da Prefeitura de Colíder (MT).",
    },
}

MAX_ITEMS = 10
OUTPUT_DIR = Path("feeds")
OUTPUT_DIR.mkdir(exist_ok=True)

# Meses em português para tentar ler a data "04 de Dezembro de 2025"
MONTHS_PT = {
    "janeiro": 1,
    "fevereiro": 2,
    "março": 3,
    "marco": 3,
    "abril": 4,
    "maio": 5,
    "junho": 6,
    "julho": 7,
    "agosto": 8,
    "setembro": 9,
    "outubro": 10,
    "novembro": 11,
    "dezembro": 12,
}


def log(msg: str) -> None:
    print(f"[{datetime.now().isoformat(sep=' ', timespec='seconds')}] {msg}")


def absolute_url(domain: str, href: str) -> str:
    href = href.strip()
    if href.startswith("http://") or href.startswith("https://"):
        return href
    if not href.startswith("/"):
        href = "/" + href
    return domain.rstrip("/") + href


def parse_pt_br_date(text: str) -> datetime:
    """Tenta encontrar uma data no formato '04 de Dezembro de 2025'."""
    now = datetime.now(timezone.utc)
    if not text:
        return now

    text_norm = (
        text.lower()
        .replace("ç", "c")
        .replace("ã", "a")
        .replace("â", "a")
        .replace("á", "a")
        .replace("é", "e")
        .replace("ê", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ô", "o")
        .replace("ú", "u")
    )

    m = re.search(r"(\d{1,2})\s+de\s+([a-z]+)\s+de\s+(\d{4})", text_norm)
    if not m:
        return now

    day = int(m.group(1))
    month_name = m.group(2)
    year = int(m.group(3))
    month = MONTHS_PT.get(month_name)
    if not month:
        return now

    try:
        return datetime(year, month, day, tzinfo=timezone.utc)
    except ValueError:
        return now


def extract_colider_list(cfg: dict):
    """Busca na página de notícias os links das últimas matérias."""
    url = cfg["list_url"]
    domain = cfg["domain"]
    log(f"[colider] Buscando lista de notícias em {url}")

    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    links = []
    seen = set()

    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/Imprensa/Noticias/" not in href:
            continue

        full = absolute_url(domain, href)
        if full in seen:
            continue

        # evita links de imagens, documentos etc
        if any(ext in full.lower() for ext in [".jpg", ".jpeg", ".png", ".pdf"]):
            continue

        title = a.get_text(strip=True)
        if not title or len(title) < 20:
            continue

        seen.add(full)
        links.append({"title": title, "url": full})
        if len(links) >= MAX_ITEMS:
            break

    log(f"[colider] Encontrados {len(links)} links de notícias")
    return links


def extract_colider_article(article_url: str):
    """Abre a notícia individual e extrai título, resumo e data."""
    resp = requests.get(article_url, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # Título
    h1 = soup.find("h1")
    if h1:
        title = h1.get_text(strip=True)
    elif soup.title:
        title = soup.title.get_text(strip=True)
    else:
        title = article_url

    # Descrição: junta alguns parágrafos relevantes
    paragraphs = []
    for p in soup.find_all("p"):
        text = p.get_text(" ", strip=True)
        if not text:
            continue
        # ignora parágrafos curtos ou de crédito
        if text.lower().startswith(("foto por", "legenda foto", "autor:", "fonte:")):
            continue
        paragraphs.append(text)
        if len(" ".join(paragraphs)) > 500:
            break

    description = " ".join(paragraphs) if paragraphs else title

    # tenta achar linha com "Data:"
    date_text = ""
    for element in soup.find_all(text=True):
        if isinstance(element, str) and "Data:" in element:
            date_text = element
            break

    pub_date = parse_pt_br_date(date_text)

    return {
        "title": title,
        "url": article_url,
        "description": description,
        "pub_date": pub_date,
    }


def escape_xml(text: str) -> str:
    return html.escape(text or "", quote=True)


def build_rss_colider(cfg: dict, items: list) -> str:
    """Monta o XML RSS com base nas notícias coletadas."""
    now = datetime.now(timezone.utc)
    channel_title = cfg["name"]
    channel_link = cfg["site_url"]
    channel_desc = cfg["description"]

    rss_items = []
    for item in items:
        title = escape_xml(item["title"])
        link = escape_xml(item["url"])
        description = item["description"]
        desc_cdata = "<![CDATA[" + description + "]]>"
        pub_date_str = format_datetime(item["pub_date"])

        item_xml_lines = [
            "    <item>",
            f"      <title>{title}</title>",
            f"      <link>{link}</link>",
            f"      <guid>{link}</guid>",
            f"      <description>{desc_cdata}</description>",
            f"      <pubDate>{pub_date_str}</pubDate>",
            "    </item>",
        ]
        rss_items.append("\n".join(item_xml_lines))

    items_block = "\n".join(rss_items)

    header_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0">',
        "  <channel>",
        f"    <title>{escape_xml(channel_title)}</title>",
        f"    <link>{escape_xml(channel_link)}</link>",
        f"    <description>{escape_xml(channel_desc)}</description>",
        "    <language>pt-BR</language>",
        f"    <lastBuildDate>{format_datetime(now)}</lastBuildDate>",
        "",
    ]
    footer_lines = [
        "  </channel>",
        "</rss>",
    ]

    xml_parts = header_lines + [items_block] + footer_lines
    return "\n".join(xml_parts)


def update_colider(cfg: dict) -> None:
    links = extract_colider_list(cfg)

    articles = []
    for link in links:
        try:
            details = extract_colider_article(link["url"])
            articles.append(details)
        except Exception as e:
            log(f"[colider] Erro ao abrir notícia {link['url']}: {e}")

    if not articles:
        log("[colider] Nenhuma notícia processada, feed não será atualizado.")
        return

    rss_xml = build_rss_colider(cfg, articles)
    output_file = OUTPUT_DIR / "colider.xml"
    output_file.write_text(rss_xml, encoding="utf-8")
    log(f"[colider] Feed atualizado em {output_file}")


def main() -> None:
    cfg = CITIES["colider"]
    update_colider(cfg)


if __name__ == "__main__":
    main()
