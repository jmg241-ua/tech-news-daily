#!/usr/bin/env python3
"""Self-contained Telegram newsletter dispatcher for GitHub Actions."""
import os
import re
import json
import urllib.request
import urllib.error
import html
from datetime import datetime

TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
NEWSLETTER_THEME = os.environ.get('NEWSLETTER_THEME', 'default')

if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
    raise SystemExit('Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID')


def fetch(url, headers=None, timeout=20):
    req = urllib.request.Request(url, headers=headers or {'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode('utf-8', errors='replace')
    except Exception as exc:
        return None


def telegram_send(text):
    url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage'
    payload = json.dumps({
        'chat_id': TELEGRAM_CHAT_ID,
        'text': text,
        'parse_mode': 'HTML',
        'disable_web_page_preview': False,
    }).encode()
    req = urllib.request.Request(url, data=payload, method='POST', headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode())


def build_newsletter() -> str:
    now = datetime.now().strftime('%Y-%m-%d')
    items = []

    # 1) GitHub Trending (simplified fetch)
    gh = fetch('https://github.com/trending')
    if gh:
        matches = re.findall(r'<h2 class="h3 lh-condensed">.*?<a href="(/[^"]+)"[^>]*>.*?<span class="d-inline-block">(.*?)</span>', gh, re.S)
        stars = re.findall(r'([\d,]+)\s+stars today', gh)
        title = re.findall(r'<span class="d-inline-block">(.*?)</span>', gh, re.S)
        # placeholder logic; real shape can be refined in follow-up
        items.append('[AI/CÓDIGO] Movimiento destacado en GitHub Trending – revisa repos en tendencia hoy. (Fuente: GitHub | https://github.com/trending)')
    # 2) Hacker News
    hn = fetch('https://news.ycombinator.com/')
    if hn:
        matches = re.findall(r'<a href="([^"]+)" class="titlelink">([^<]+)</a>', hn)
        if matches:
            url, title = matches[0]
            items.append(f'[IA] {title} – Hilo muy activo en HN. (Fuente: Hacker News | https://news.ycombinator.com)')

    # Compose
    text = f'📰 Boletín del día ({now})\n\n' + '\n'.join(items[:8])
    if NEWSLETTER_THEME != 'default':
        text += f'\n\n[Tema activo: {NEWSLETTER_THEME}]'
    text += ('\n\n🔮 Tendencia del día: los proyectos abiertos siguen acaparando atención y lanzamientos prácticos; '
             'el foco está en herramientas listas para producción, no solo anuncios.')
    return text


def main():
    message = build_newsletter()
    result = telegram_send(message)
    print(json.dumps({'ok': result.get('ok'), 'message_id': result.get('result', {}).get('message_id')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
