# -*- coding: utf-8 -*-
"""
Gera o feed RSS da Prefeitura de Colíder (MT) para o MT Online.
Por enquanto, só trata Colíder. Depois adicionamos outras cidades.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "feeds"

COLIDER_LIST_URL = "https://www.colider.mt.gov.br/Imprensa/Noticias/"
COLIDER_DOMAIN = "https://www.colider.mt.gov.br"

# Meses em português para converter a data do card
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


def fetch_html(url: str) -> str:
    """Baixa HTML com requests."""
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    # Garante UTF-8
    if not resp.encoding:
        resp.encoding = "utf-8"
    return resp.text


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def parse_colider_date(text: str) -> datetime:
    """
    O card começa assim:
    '05 de Dezembro de 2025 Prefeitura de Colíder divulga ...'
    Pegamos só a parte da data.
    """
    m = re.match(
        r"^(\d{1,2}) de ([A-Za-zçÇéÉãõáíóúôâÊÔÂÚÍ]+) de (\d{4})",
        text,
    )
    if not m:
        # Se não bater o padrão, usa agora
        return datetime.now(timezone.utc)

    day = int(m.group(1))
    month_name = m.group(2).lower()
    year = int(m.group(3))

    month = MONTHS_PT.get(month_name, 1)
    return datetime(year, month, day, tzinfo=timezone.utc)


def build_colider_items():
    """Monta os itens de feed para a página de notícias de Colíder."""
    base_url = "https://www.colider.mt.gov.br"
    lista_url = base_url + "/Imprensa/Noticias/"

    html = requests.get(lista_url, timeout=20).text
    soup = BeautifulSoup(html, "html.parser")

    items = []
    agora = time.time()

    # Percorre todos os links da página
    for a in soup.find_all("a", href=True):
        href = a["href"]
        texto = " ".join(a.get_text(strip=True).split())

        # Queremos apenas links de notícias (descarta menu, rodapé, etc.)
        if "/Imprensa/Noticias/" not in href:
            continue

        # Descarta links de acessibilidade (#content-main, #content-footer etc.)
        if "#content-" in href or "#input-" in href:
            continue

        # Descarta itens sem texto de notícia (ex.: só "Notícias")
        if " de 20" not in texto:
            # os cards de notícias sempre têm algo como "05 de Dezembro de 2025 ..."
            continue

        # Monta URL absoluta
        if href.startswith("http"):
            link_completo = href
        else:
            link_completo = base_url + href

        # Usa o próprio texto do card como título/descrição
        titulo = texto
        descricao = texto

        item = {
            "title": titulo,
            "link": link_completo,
            "guid": link_completo,
            "description": descricao,
            # por simplicidade, usa a data atual no pubDate
            "pubDate": formatdate(agora, usegmt=True),
        }
        items.append(item)

        # Limita a, por exemplo, 10 notícias mais recentes
        if len(items) >= 10:
            break

    return items



def format_rfc2822(dt: datetime) -> str:
    return dt.strftime("%a, %d %b %Y %H:%M:%S %z")


def escape_xml(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def write_rss(slug: str, title: str, link: str, description: str, items: list) -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    path = OUTPUT_DIR / f"{slug}.xml"

    parts = []
    parts.append('<?xml version="1.0" encoding="UTF-8"?>')
    parts.append('<rss version="2.0">')
    parts.append("<channel>")
    parts.append(f"<title>{escape_xml(title)}</title>")
    parts.append(f"<link>{escape_xml(link)}</link>")
    parts.append(f"<description>{escape_xml(description)}</description>")
    parts.append("<language>pt-BR</language>")
    parts.append(f"<lastBuildDate>{format_rfc2822(datetime.now(timezone.utc))}</lastBuildDate>")

    for item in items:
        parts.append("<item>")
        parts.append(f"<title>{escape_xml(item['title'])}</title>")
        parts.append(f"<link>{escape_xml(item['link'])}</link>")
        parts.append(f"<guid>{escape_xml(item['link'])}</guid>")
        # Descrição em CDATA pra aceitar acentos e quebras sem problema
        parts.append(f"<![CDATA[{item['description']}]]>")
        parts.append(f"<pubDate>{format_rfc2822(item['pubDate'])}</pubDate>")
        parts.append("</item>")

    parts.append("</channel>")
    parts.append("</rss>")

    path.write_text("\n".join(parts), encoding="utf-8")


def main() -> None:
    items = build_colider_items()
    if not items:
        # Se não achar nada, não sobrescreve o arquivo anterior
        print("[colider] Nenhuma notícia encontrada; feed não atualizado.")
        return

    write_rss(
        slug="colider",
        title="Prefeitura de Colíder",
        link=COLIDER_LIST_URL,
        description="Últimas notícias da Prefeitura de Colíder (MT).",
        items=items,
    )
    print(f"[colider] Feed atualizado com {len(items)} itens.")


if __name__ == "__main__":
    main()
