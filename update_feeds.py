
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import textwrap
import re


HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; MTOnlineBot/1.0; +https://www.mtonline.com.br)"
}


def limpar_texto(txt: str) -> str:
    txt = txt.replace("\r", " ").replace("\n", " ")
    txt = re.sub(r"\s+", " ", txt)
    return txt.strip()


def criar_paragrafos(texto: str, max_chars: int = 900) -> str:
    """
    Quebra o texto em 2–3 parágrafos curtos, para ficar leve de ler no MT Online.
    """
    texto = limpar_texto(texto)

    if len(texto) > max_chars:
        texto = texto[:max_chars].rsplit(".", 1)[0] + "."

    # Tentativa de separar por frases
    frases = re.split(r"(?<=[.!?])\s+", texto)
    blocos = []
    bloco_atual = ""

    for f in frases:
        if len(bloco_atual) + len(f) < max_chars // 3:
            bloco_atual += (" " if bloco_atual else "") + f
        else:
            if bloco_atual:
                blocos.append(bloco_atual.strip())
            bloco_atual = f

    if bloco_atual:
        blocos.append(bloco_atual.strip())

    # Garante no mínimo 1 e no máximo 3 parágrafos
    if not blocos:
        blocos = [texto]
    if len(blocos) > 3:
        blocos = blocos[:3]

    return "\n\n".join(f"<p>{b}</p>" for b in blocos if b)


def extrair_conteudo_generico(url: str) -> str:
    """
    Faz o download da notícia e tenta extrair o texto principal.
    É genérico para todos os sites – pode precisar de ajuste fino depois.
    """
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
    except Exception as e:
        return f"<p>Não foi possível carregar o texto completo desta notícia. ({e})</p>"

    soup = BeautifulSoup(resp.text, "lxml")

    # Tenta achar um container de conteúdo mais comum
    possiveis = [
        {"name": "div", "attrs": {"class": re.compile(r"(conteudo|content|noticia|post)", re.I)}},
        {"name": "article", "attrs": {}},
        {"name": "div", "attrs": {"id": re.compile(r"(conteudo|content)", re.I)}},
    ]

    texto = ""
    for cfg in possiveis:
        bloco = soup.find(cfg["name"], cfg["attrs"])
        if bloco:
            ps = bloco.find_all("p")
            if ps:
                texto = " ".join(p.get_text(" ", strip=True) for p in ps)
                break

    if not texto:
        # Fallback: pega todos <p> da página
        ps = soup.find_all("p")
        if ps:
            texto = " ".join(p.get_text(" ", strip=True) for p in ps)

    if not texto:
        return "<p>Texto da notícia não pôde ser extraído automaticamente.</p>"

    return criar_paragrafos(texto)


def gerar_xml(cidade_nome: str, base_link_mtonline: str, itens: list) -> str:
    agora = datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S GMT")

    xml = textwrap.dedent(f"""\
        <?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
          <channel>
            <title>MT Online – Notícias de {cidade_nome}</title>
            <link>{base_link_mtonline}</link>
            <description>Principais notícias recentes de {cidade_nome}, compiladas automaticamente pelo sistema do MT Online.</description>
            <language>pt-BR</language>
            <pubDate>{agora}</pubDate>
            <lastBuildDate>{agora}</lastBuildDate>
            <generator>MT Online + GitHub Actions</generator>
    """)

    for item in itens:
        xml += textwrap.dedent(f"""\
            
            <item>
              <title>{item["titulo"]}</title>
              <link>{item["link"]}</link>
              <guid isPermaLink="true">{item["link"]}</guid>
              <pubDate>{item.get("pubDate", agora)}</pubDate>
              <description><![CDATA[
{item["descricao"]}
              ]]></description>
            </item>
        """)

    xml += textwrap.dedent("""\
          </channel>
        </rss>
    """)

    return xml


def salvar_xml(caminho: str, conteudo: str):
    with open(caminho, "w", encoding="utf-8") as f:
        f.write(conteudo)


# ============================================================
# COLETORES POR CIDADE
# ============================================================

def coletar_colider():
    """
    Colíder – https://www.colider.mt.gov.br/Imprensa/Noticias/
    OBS: Estrutura pode mudar. Se quebrar, é só ajustarmos este coletor.
    """
    url_lista = "https://www.colider.mt.gov.br/Imprensa/Noticias/"
    resp = requests.get(url_lista, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")

    itens = []
    # Pega links que levam para /Imprensa/Noticias/
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/Imprensa/Noticias/" in href and a.get_text(strip=True):
            titulo = limpar_texto(a.get_text())
            link = href if href.startswith("http") else "https://www.colider.mt.gov.br" + href
            descricao = extrair_conteudo_generico(link)

            itens.append({
                "titulo": titulo,
                "link": link,
                "descricao": descricao
            })

    # Remove duplicados mantendo ordem
    vistos = set()
    itens_unicos = []
    for it in itens:
        if it["link"] not in vistos:
            itens_unicos.append(it)
            vistos.add(it["link"])

    return itens_unicos[:5]


def coletar_guaranta():
    """
    Guarantã do Norte – https://www.guarantadonorte.mt.gov.br/Noticias/
    """
    url_lista = "https://www.guarantadonorte.mt.gov.br/Noticias/"
    resp = requests.get(url_lista, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")

    itens = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/Noticias/" in href and a.get_text(strip=True):
            titulo = limpar_texto(a.get_text())
            link = href if href.startswith("http") else "https://www.guarantadonorte.mt.gov.br" + href
            descricao = extrair_conteudo_generico(link)

            itens.append({
                "titulo": titulo,
                "link": link,
                "descricao": descricao
            })

    vistos = set()
    itens_unicos = []
    for it in itens:
        if it["link"] not in vistos:
            itens_unicos.append(it)
            vistos.add(it["link"])

    return itens_unicos[:5]


def coletar_peixoto():
    """
    Peixoto de Azevedo – https://www.peixotodeazevedo.mt.gov.br/noticias/
    """
    url_lista = "https://www.peixotodeazevedo.mt.gov.br/noticias/"
    resp = requests.get(url_lista, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")

    itens = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/noticias/" in href and a.get_text(strip=True):
            titulo = limpar_texto(a.get_text())
            link = href if href.startswith("http") else "https://www.peixotodeazevedo.mt.gov.br" + href
            descricao = extrair_conteudo_generico(link)

            itens.append({
                "titulo": titulo,
                "link": link,
                "descricao": descricao
            })

    vistos = set()
    itens_unicos = []
    for it in itens:
        if it["link"] not in vistos:
            itens_unicos.append(it)
            vistos.add(it["link"])

    return itens_unicos[:5]


def coletar_alta_floresta():
    """
    Alta Floresta – https://www.altafloresta.mt.gov.br/Noticias/
    """
    url_lista = "https://www.altafloresta.mt.gov.br/Noticias/"
    resp = requests.get(url_lista, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")

    itens = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/Noticias/" in href and a.get_text(strip=True):
            titulo = limpar_texto(a.get_text())
            link = href if href.startswith("http") else "https://www.altafloresta.mt.gov.br" + href
            descricao = extrair_conteudo_generico(link)

            itens.append({
                "titulo": titulo,
                "link": link,
                "descricao": descricao
            })

    vistos = set()
    itens_unicos = []
    for it in itens:
        if it["link"] not in vistos:
            itens_unicos.append(it)
            vistos.add(it["link"])

    return itens_unicos[:5]


def main():
    base_mtonline = "https://www.mtonline.com.br"

    # Colíder
    try:
        colider_itens = coletar_colider()
        xml_colider = gerar_xml("Colíder (MT)", base_mtonline, colider_itens)
        salvar_xml("colider.xml", xml_colider)
        print("Atualizado colider.xml")
    except Exception as e:
        print("Erro em Colíder:", e)

    # Guarantã do Norte
    try:
        guaranta_itens = coletar_guaranta()
        xml_guaranta = gerar_xml("Guarantã do Norte (MT)", base_mtonline, guaranta_itens)
        salvar_xml("guaranta.xml", xml_guaranta)
        print("Atualizado guaranta.xml")
    except Exception as e:
        print("Erro em Guarantã:", e)

    # Peixoto de Azevedo
    try:
        peixoto_itens = coletar_peixoto()
        xml_peixoto = gerar_xml("Peixoto de Azevedo (MT)", base_mtonline, peixoto_itens)
        salvar_xml("peixoto.xml", xml_peixoto)
        print("Atualizado peixoto.xml")
    except Exception as e:
        print("Erro em Peixoto:", e)

    # Alta Floresta
    try:
        alta_itens = coletar_alta_floresta()
        xml_alta = gerar_xml("Alta Floresta (MT)", base_mtonline, alta_itens)
        salvar_xml("altafloresta.xml", xml_alta)
        print("Atualizado altafloresta.xml")
    except Exception as e:
        print("Erro em Alta Floresta:", e)


if __name__ == "__main__":
    main()
