#!/usr/bin/env python3
import html
import re
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# Apenas Colíder por enquanto
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

# regex para datas em português, ex: "05 de Dezembro de 2025"
DATE_REGEX = re.compile(
    r"(\d{1,2})\s+de\s+([A-Za-zçãéêíóú]+)\s+de\s+(\d{4})",
    re.IGNORECASE,
)

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
    """Tenta encontrar uma data no formato '04 de Dezembro de 2025' dentro de 'text'."""
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

    m = DATE_REGEX.search(text_norm)
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
    """
    Busca na página de notícias os blocos principais de notícias.

    Estrutura (em texto plano) dos links:
    '05 de Dezembro de 2025 Título da notícia Um trechinho da notícia…'
    """
    url = cfg["list_url"]
    domain = cfg["domain"]
    log(f"[colider] Buscando lista de notícias em {url}")

    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    items = []
    seen_urls = set()

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        text = a.get_text(" ", strip=True)

        if not text:
            continue

        # só links dentro de /Imprensa/Noticias/
        if "/Imprensa/Noticias/" not in href:
            continue

        # ignorar âncoras internas tipo #content-main, #content-menu, etc.
        if "#" in href:
            continue

        # precisa ter uma data (é assim que a lista de notícias aparece)
        if not DATE_REGEX.search(text):
            continue

        full_url = absolute_url(domain, href)
        if full_url in seen_urls:
            continue

        seen_urls.add(full_url)

        pub_date = parse_pt_br_date(text)
        m = DATE_REGEX.search(text)
        title_part = text[m.end() :].strip() if m else text

        # a primeira frase após a data normalmente já traz título + lead
        title_hint = title_part
        description_hint = title_part

        items.append(
            {
                "url": full_url,
                "list_text": text,
                "pub_date": pub_date,
                "title_hint": title_hint,
                "description_hint": description_hint,
            }
        )

        if len(items) >= MAX_ITEMS:
            break

    log(f"[colider] Encontrados {len(items)} itens de notícias na lista")
    return items


def extract_colider_article(article_url: str, fallback: dict):
    """
    Abre a notícia individual e extrai título e resumo.
    Se algo falhar, usa o que veio da lista (fallback).
    """
    title = fallback.get("title_hint") or article_url
    description = fallback.get("description_hint") or title
    pub_date = fallback.get("pub_date") or datetime.now(timezone.utc)

    try:
        resp = requests.get(article_url, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Título mais preciso
        h1 = soup.find("h1")
        if h1:
            t = h1.get_text(strip=True)
            if t:
                title = t
        elif soup.title:
            t = soup.title.get_text(strip=True)
            if t:
                title = t

        # Descrição: pega parágrafos relevantes
        paragraphs = []
        for p in soup.find_all("p"):
            text = p.get_text(" ", strip=True)
            if not text:
                continue

            text_norm = text.lower()

            # ignora textos de rodapé / cabeçalho
            if "unidade fiscal do municipio de colider" in text_norm:
                continue
            if "todos os direitos reservados" in text_norm:
                continue
            if "este site utiliza cookies" in text_norm:
                continue

            paragraphs.append(text)
            if len(" ".join(paragraphs)) > 500:
                break

        if paragraphs:
            description = " ".join(paragraphs)

    except Exception as e:
        log(f"[colider] Erro ao abrir notícia {article_url}: {e}")

    return {
        "title": title,
        "url": article_url,
        "description": description,
        "pub_date": pub_date,
    }


def escape_xml(text: str) -> str:
    return html.escape(text or "", quote=True)


def build_rss_colider(cfg: dict, items: list) -> str:
    now = datetime.now(timezone.utc)
    channel_title = cfg["name"]
    channel_link = cfg["site_url"]
    channel_desc = cfg["description"]

    rss_items = []
    for item in items:
        title = escape_xml(item["title"])
        link = escape_xml(item["url"])
        desc_cdata = "<![CDATA[" + (item["description"] or "") + "]]>"
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
    entries = extract_colider_list(cfg)
    articles = []

    for entry in entries:
        details = extract_colider_article(entry["url"], entry)
        articles.append(details)

    if
