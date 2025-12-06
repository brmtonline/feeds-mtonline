#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gera o feed RSS da Prefeitura de Colíder (MT) para o MT Online.
Por enquanto, só trata Colíder.
"""

from pathlib import Path
from datetime import datetime, timezone
from email.utils import formatdate
import re

import requests
from bs4 import BeautifulSoup

# Diretório onde o feed será salvo
OUTPUT_DIR = Path("feeds")
OUTPUT_DIR.mkdir(exist_ok=True)

BASE_URL = "https://www.colider.mt.gov.br"
LIST_URL = BASE_URL + "/Imprensa/Noticias/"


def log(msg: str) -> None:
    now = datetime.now().isoformat(sep=" ", timespec="seconds")
    print(f"[colider] {now} - {msg}")


def escape_xml(text: str) -> str:
    """Escapa caracteres especiais para XML."""
    return (
        (text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def fetch_colider_items(max_items: int = 10):
    """
    Lê a página de notícias de Colíder e monta uma lista de itens de feed.

    Usa somente a página de listagem (cards), sem abrir cada notícia,
    para evitar pegar rodapé/cookies etc.
    """
    log(f"Buscando lista em {LIST_URL}")
    resp = requests.get(LIST_URL, timeout=30)
    resp.raise_for_status()

    # Garante decodificação correta
    if not resp.encoding:
        resp.encoding = "utf-8"

    soup = BeautifulSoup(resp.text, "html.parser")

    items = []
    seen_links = set()

    for a in soup.find_all("a", href=True):
        href = a["href"]
        text = " ".join(a.get_text(strip=True).split())

        if not text:
            continue

        # Queremos apenas links de notícias
        if "/Imprensa/Noticias/" not in href:
            continue

        # Evita âncoras internas e áreas de layout
        if "#content-" in href or "#input-" in href or "#contentmenu" in href:
            continue

        # Ignora rodapé e UFCL
        text_up = text.upper()
        if "TODOS OS DIREITOS RESERVADOS" in text_up:
            continue
        if "UNIDADE FISCAL DO MUNICIPIO DE COLIDER" in text_up:
            continue

        # Os cards de notícia sempre têm algo como "05 de Dezembro de 2025 ..."
        if " DE " not in text:
            continue
        if not re.search(r"\d{1,2}\s+de\s+[A-Za-zçÇéÉãõáíóúôâÊÔÂÚÍ]+\s+de\s+\d{4}", text):
            # Se não tiver cara de data em português, pula
            continue

        # URL absoluta
        if href.startswith("http"):
            full_url = href
        else:
            full_url = BASE_URL + href

        if full_url in seen_links:
            continue
        seen_links.add(full_url)

        # Título: pega o restante do texto depois da data, se conseguir separar
        m = re.match(
            r"^(\d{1,2}\s+de\s+[A-Za-zçÇéÉãõáíóúôâÊÔÂÚÍ]+\s+de\s+\d{4})\s+(.*)$",
            text,
        )
        if m:
            title = m.group(2).strip()
        else:
            title = text

        # Se o título ficar muito grande, corta um pouco
        if len(title) > 150:
            title = title[:150].rsplit(" ", 1)[0] + "..."

        # Descrição: usa o texto inteiro do card (sem cortar demais)
        description = text
        if len(description) > 350:
            description = description[:350].rsplit(" ", 1)[0] + "..."

        pub_date = formatdate(usegmt=True)  # usa data/hora atual

        items.append(
            {
                "title": title,
                "link": full_url,
                "guid": full_url,
                "description": description,
                "pubDate": pub_date,
            }
        )

        if len(items) >= max_items:
            break

    log(f"Encontrados {len(items)} itens de notícias")
    return items


def build_rss(items):
    """Monta o XML RSS em texto."""
    now_rfc = formatdate(usegmt=True)

    lines = []
    lines.append('<?xml version="1.0" encoding="UTF-8"?>')
    lines.append('<rss version="2.0">')
    lines.append("<channel>")
    lines.append(f"<title>{escape_xml('Prefeitura de Colíder')}</title>")
    lines.append(f"<link>{escape_xml(LIST_URL)}</link>")
    lines.append(
        f"<description>{escape_xml('Últimas notícias da Prefeitura de Colíder (MT).')}</description>"
    )
    lines.append("<language>pt-BR</language>")
    lines.append(f"<lastBuildDate>{now_rfc}</lastBuildDate>")

    for item in items:
        lines.append("<item>")
        lines.append(f"<title>{escape_xml(item['title'])}</title>")
        lines.append(f"<link>{escape_xml(item['link'])}</link>")
        lines.append(f"<guid>{escape_xml(item['guid'])}</guid>")
        # descrição em CDATA para não ter problema com acentos e símbolos
        lines.append(f"<![CDATA[{item['description']}]]>")
        lines.append(f"<pubDate>{item['pubDate']}</pubDate>")
        lines.append("</item>")

    lines.append("</channel>")
    lines.append("</rss>")

    return "\n".join(lines)


def main():
    items = fetch_colider_items()
    if not items:
        log("Nenhuma notícia encontrada; feed não será atualizado.")
        return

    rss_text = build_rss(items)
    output_file = OUTPUT_DIR / "colider.xml"
    output_file.write_text(rss_text, encoding="utf-8")
    log(f"Feed atualizado em {output_file}")


if __name__ == "__main__":
    main()
