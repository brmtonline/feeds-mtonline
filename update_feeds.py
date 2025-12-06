#!/usr/bin/env python3
from pathlib import Path

# Cidades para as quais vamos gerar arquivos de teste
CITIES = ["colider", "altafloresta", "guaranta", "matupa"]

OUTPUT_DIR = Path("feeds")
OUTPUT_DIR.mkdir(exist_ok=True)

TEMPLATE_LINES = [
    '<?xml version="1.0" encoding="UTF-8"?>',
    '<rss version="2.0">',
    '  <channel>',
    '    <title>Feed de teste - {city}</title>',
    '    <link>https://www.mtonline.com.br/</link>',
    '    <description>Feed de teste automático para {city}</description>',
    '    <language>pt-BR</language>',
    '  </channel>',
    '</rss>',
]


def main() -> None:
    for city in CITIES:
        xml = "\n".join(TEMPLATE_LINES).format(city=city)
        output_file = OUTPUT_DIR / f"{city}.xml"
        output_file.write_text(xml, encoding="utf-8")
        print(f"Gerado {output_file}")


if __name__ == "__main__":
    main()
