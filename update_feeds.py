#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gera feeds RSS para prefeituras do Norte de Mato Grosso - Portal MT Online
Atualiza automaticamente via GitHub Actions.
"""

from pathlib import Path
from email.utils import formatdate
from datetime import datetime
import re
import time
import requests
from bs4 import BeautifulSoup

OUTPUT_DIR = Path("feeds")
OUTPUT_DIR.mkdir(exist_ok=True)

# Headers completos simulando navegador real — necessário para sites com proteção
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Cache-Control": "max-age=0",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
}

FONTES = [
    {
        "id": "colider",
        "municipio": "Colíder",
        "base_url": "https://www.colider.mt.gov.br",
        "url_noticias": "https://www.colider.mt.gov.br/Imprensa/Noticias/",
        "padrao_href": "/Imprensa/Noticias/",
    },
    {
        "id": "altafloresta",
        "municipio": "Alta Floresta",
        "base_url": "https://www.altafloresta.mt.gov.br",
        "url_noticias": "https://www.altafloresta.mt.gov.br/Noticias/",
        "padrao_href": "/Noticias/",
    },
    {
        "id": "vera",
        "municipio": "Vera",
        "base_url": "https://www.vera.mt.gov.br",
        "url_noticias": "https://www.vera.mt.gov.br/Imprensa/Noticias/",
        "padrao_href": "/Imprensa/Noticias/",
    },
    {
        "id": "guaranta",
        "municipio": "Guarantã do Norte",
        "base_url": "https://www.guarantadonorte.mt.gov.br",
        "url_noticias": "https://www.guarantadonorte.mt.gov.br/Noticias/",
        "padrao_href": "/Noticias/",
    },
    {
        "id": "claudia",
        "municipio": "Cláudia",
        "base_url": "https://www.claudia.mt.gov.br",
        "url_noticias": "https://www.claudia.mt.gov.br/Noticias/",
        "padrao_href": "/Noticias/",
    },
    {
        "id": "santacarmem",
        "municipio": "Santa Carmem",
        "base_url": "https://www.santacarmem.mt.gov.br",
        "url_noticias": "https://www.santacarmem.mt.gov.br/Noticias/",
        "padrao_href": "/Noticias/",
    },
    {
        "id": "matupa",
        "municipio": "Matupá",
        "base_url": "https://www.matupa.mt.gov.br",
        "url_noticias": "https://www.matupa.mt.gov.br/Noticias/",
        "padrao_href": "/Noticias/",
    },
    {
        "id": "camara-colider",
        "municipio": "Câmara de Colíder",
        "base_url": "https://www.camaracolider.mt.gov.br",
        "url_noticias": "https://www.camaracolider.mt.gov.br/Noticias/",
        "padrao_href": "/Noticias/",
    },
]


def log(municipio, msg):
    now = datetime.now().strftime("%H:%M:%S")
    print(f"[{now}] [{municipio}] {msg}")


def escape_xml(text):
    return (
        (text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def buscar_noticias(fonte, max_items=10):
    municipio = fonte["municipio"]
    url = fonte["url_noticias"]
    base = fonte["base_url"]
    padrao = fonte["padrao_href"]

    log(municipio, f"Buscando em {url}")

    try:
        # Primeira requisição à página principal para pegar cookies
        session = requests.Session()
        session.headers.update(HEADERS)
        
        # Visita a página inicial primeiro (simula comportamento de navegador)
        try:
            session.get(base, timeout=15)
            time.sleep(1)
        except Exception:
            pass

        resp = session.get(url, timeout=30)
        resp.raise_for_status()
        resp.encoding = "utf-8"

    except Exception as e:
        log(municipio, f"ERRO ao acessar: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    items = []
    seen = set()

    for a in soup.find_all("a", href=True):
        href = a["href"]
        text = " ".join(a.get_text(strip=True).split())

        if not text or len(text) < 20:
            continue
        if padrao not in href:
            continue
        if "#" in href:
            continue

        text_upper = text.upper()
        if "TODOS OS DIREITOS" in text_upper:
            continue
        if "UNIDADE FISCAL" in text_upper:
            continue

        # Verifica se tem data no formato brasileiro
        tem_data = re.search(
            r"\d{1,2}\s+de\s+[A-Za-zçÇéÉãõáíóúôâÊÔÂÚÍ]+\s+de\s+\d{4}",
            text,
        )
        if not tem_data:
            continue

        # URL absoluta
        url_completa = href if href.startswith("http") else base + href
        if url_completa in seen:
            continue
        seen.add(url_completa)

        # Separa título do restante
        data_match = tem_data
        pos = data_match.start()
        pos_fim = data_match.end()
        titulo = text[pos_fim:].strip()

        if len(titulo) > 160:
            titulo = titulo[:160].rsplit(" ", 1)[0] + "..."
        if not titulo:
            titulo = text[:160]

        descricao = text
        if len(descricao) > 400:
            descricao = descricao[:400].rsplit(" ", 1)[0] + "..."

        items.append({
            "title": titulo,
            "link": url_completa,
            "guid": url_completa,
            "description": descricao,
            "pubDate": formatdate(usegmt=True),
        })

        if len(items) >= max_items:
            break

    log(municipio, f"Encontradas {len(items)} notícias")
    return items


def gerar_rss(fonte, items):
    municipio = fonte["municipio"]
    url_noticias = fonte["url_noticias"]
    now_rfc = formatdate(usegmt=True)

    linhas = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0">',
        "<channel>",
        f"<title>{escape_xml('Prefeitura de ' + municipio + ' | MT Online')}</title>",
        f"<link>{escape_xml(url_noticias)}</link>",
        f"<description>{escape_xml('Últimas notícias de ' + municipio + ' - MT')}</description>",
        "<language>pt-BR</language>",
        f"<lastBuildDate>{now_rfc}</lastBuildDate>",
    ]

    for item in items:
        linhas += [
            "<item>",
            f"<title>{escape_xml(item['title'])}</title>",
            f"<link>{escape_xml(item['link'])}</link>",
            f"<guid>{escape_xml(item['guid'])}</guid>",
            f"<description><![CDATA[{item['description']}]]></description>",
            f"<pubDate>{item['pubDate']}</pubDate>",
            "</item>",
        ]

    linhas += ["</channel>", "</rss>"]
    return "\n".join(linhas)


def main():
    total_ok = 0
    for fonte in FONTES:
        items = buscar_noticias(fonte)
        if items:
            xml = gerar_rss(fonte, items)
            arquivo = OUTPUT_DIR / f"{fonte['id']}.xml"
            arquivo.write_text(xml, encoding="utf-8")
            log(fonte["municipio"], f"Feed salvo em {arquivo}")
            total_ok += 1
        else:
            log(fonte["municipio"], "Nenhuma notícia — feed não atualizado")
        time.sleep(2)  # pausa entre requisições

    print(f"\n✅ Concluído: {total_ok}/{len(FONTES)} feeds atualizados")


if __name__ == "__main__":
    main()
