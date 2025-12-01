name: Atualizar Feeds MT Online

on:
  workflow_dispatch:
  schedule:
    - cron: "0 */4 * * *"   # executa a cada 4 horas

jobs:
  atualizar:
    runs-on: ubuntu-latest

    steps:
      - name: Finalizar compra do código
        uses: actions/checkout@v3

      - name: Configurar Python
        uses: actions/setup-python@v4
        with:
          python-version: "3.10"

      - name: Instalar dependências
        run: |
          pip install requests beautifulsoup4 lxml feedparser

      - name: Rodar script de atualização
        run: |
          python3 update_feeds.py

      - name: Commit se houver mudanças
        run: |
          git config --global user.name "GitHub Actions"
          git config --global user.email "actions@github.com"
          git add .
          git commit -m "Atualização automática dos feeds" || echo "Nenhuma alteração para commitar"
          git push
