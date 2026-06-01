from flask import Flask, Response, send_from_directory
from update_feeds import FONTES, buscar_noticias, gerar_rss
import threading
import time
import os

app = Flask(__name__)

CACHE = {}
LOCK = threading.Lock()

def atualizar_todos():
    print("Atualizando feeds...")
    for fonte in FONTES:
        try:
            itens = buscar_noticias(fonte)
            if itens:
                xml = gerar_rss(fonte, itens)
                with LOCK:
                    CACHE[fonte["id"]] = xml
                print(f"OK: {fonte['municipio']} ({len(itens)} notícias)")
        except Exception as e:
            print(f"ERRO {fonte['municipio']}: {e}")
        time.sleep(2)

def loop_atualizacao():
    while True:
        atualizar_todos()
        time.sleep(3600)

threading.Thread(target=loop_atualizacao, daemon=True).start()

@app.route("/")
def index():
    links = ""
    for f in FONTES:
        links += f'<li><a href="/rss/{f["id"]}">{f["municipio"]}</a></li>'
    return f"<h1>MT Online RSS</h1><ul>{links}</ul>"

@app.route("/rss/<fonte_id>")
def feed(fonte_id):
    with LOCK:
        xml = CACHE.get(fonte_id)
    if not xml:
        fonte = next((f for f in FONTES if f["id"] == fonte_id), None)
        if not fonte:
            return Response("Feed não encontrado", status=404)
        itens = buscar_noticias(fonte)
        xml = gerar_rss(fonte, itens) if itens else "<rss/>"
        with LOCK:
            CACHE[fonte_id] = xml
    return Response(xml, mimetype="application/rss+xml")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
