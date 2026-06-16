#!/usr/bin/env python3
"""Self-contained Telegram newsletter dispatcher for GitHub Actions."""
import json
import os
import re
from datetime import datetime
from urllib.request import Request, urlopen
from urllib.parse import urlparse


def get_env():
    token = os.environ.get('TELEGRAM_BOT_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    if not token or not chat_id:
        raise SystemExit('Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID')
    return token, chat_id


def get_text(url, headers=None, timeout=20):
    req = Request(url, headers=headers or {'User-Agent': 'Mozilla/5.0'})
    try:
        with urlopen(req, timeout=timeout) as resp:
            return resp.read().decode('utf-8', errors='replace')
    except Exception:
        return None


def telegram_send(text, token, chat_id):
    url = f'https://api.telegram.org/bot{token}/sendMessage'
    payload = json.dumps({
        'chat_id': chat_id,
        'text': text,
        'parse_mode': 'HTML',
        'disable_web_page_preview': False,
    }).encode()
    req = Request(url, data=payload, method='POST', headers={'Content-Type': 'application/json'})
    with urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode())


def is_tool_or_ai_text(text):
    t = text.lower()
    keywords = [
        'ai', 'ia', 'artificial intelligence', 'machine learning', 'ml',
        'llm', 'agent', 'tools', 'tool', 'bot', 'automation', 'open source',
        'devtools', 'developer', 'code', 'api', 'github', 'model', 'gpt',
        'transformer', 'deep learning', 'dataset', 'framework', 'library'
    ]
    title_part = re.split(r'[-–|]', t)[0]
    title_part = title_part.strip()
    return any(k in title_part for k in keywords)


def classify(text):
    if is_tool_or_ai_text(text):
        return 'IA'
    return 'NEWS'


def find_hrefs(html_text, hostname_filter=None):
    results = []
    seen = set()
    for m in re.finditer(r'href="(https?://[^"]+)"', html_text):
        url = m.group(1).strip()
        if not url:
            continue
        parsed = urlparse(url)
        if parsed.scheme not in {'http', 'https'}:
            continue
        hostname = parsed.netloc
        if hostname_filter and hostname_filter not in hostname:
            continue
        if url in seen:
            continue
        seen.add(url)
        results.append(url)
    return results


def clean_a1a2(raw):
    t = raw.strip()
    prefix = re.compile(r'^[A-Za-z]\.\s*[A-Za-z]\.\s*(?:[A-Za-z]\.\s*)?', re.UNICODE)
    t = prefix.sub('', t)
    t = t.strip()
    return re.sub(r'^(?:[-–•]\s*)+', '', t)


def rest_is_authoritative(raw):
    t = raw.strip()
    forbid = [
        'guests',
        'guest',
        'reactions',
        'comments',
        'comentarios',
        'respuestas',
        'compartir',
        'share'
    ]
    parts = re.split(r'[-–|/]', t)
    first = clean_a1a2(parts[0].strip()).lower()
    return first != '' and not any(f in first for f in forbid)


def extract_hacker_news():
    text = get_text('https://news.ycombinator.com/')
    if not text:
        return []
    results = []
    seen = set()
    # titleline > a anchor
    for m in re.finditer(r'<span[^>]+class="titleline"[^>]*>\s*<a[^>]+href="(https?://[^"]+)"[^>]*>\s*([^<]+)\s*</a>', text):
        url = m.group(1).strip()
        if not urlparse(url).scheme:
            continue
        title = clean_a1a2(m.group(2))
        if not title or url in seen:
            continue
        seen.add(url)
        results.append({
            'url': url,
            'title': title,
            'source': 'https://news.ycombinator.com/'
        })
    # normalized relative links
    for m in re.finditer(r'<a[^>]+href="(/item\?id=[^"]+)"', text):
        candidate = 'https://news.ycombinator.com' + m.group(1)
        if candidate in seen:
            continue
        seen.add(candidate)
        results.append({
            'url': candidate,
            'title': 'Hilo destacado en HN',
            'source': 'https://news.ycombinator.com/'
        })
    return results


def extract_the_verge(limit=6):
    text = get_text('https://www.theverge.com/tech')
    if not text:
        return []
    links = find_hrefs(text, hostname_filter='theverge.com')
    out, seen = [], set()
    for url in links:
        if url in seen:
            continue
        seen.add(url)
        out.append({
            'url': url,
            'title': 'Noticia en The Verge',
            'source': 'https://www.theverge.com/tech'
        })
        if len(out) >= limit:
            break
    return out


def extract_ars_technica(limit=6):
    text = get_text('https://arstechnica.com/')
    if not text:
        return []
    links = find_hrefs(text, hostname_filter='arstechnica.com')
    out, seen = [], set()
    for url in links:
        if url in seen:
            continue
        seen.add(url)
        out.append({
            'url': url,
            'title': 'Noticia en Ars Technica',
            'source': 'https://arstechnica.com/'
        })
        if len(out) >= limit:
            break
    return out


def extract_reddit_technology(limit=6):
    text = get_text(
        'https://www.reddit.com/r/technology/.json',
        headers={'User-Agent': 'Mozilla/5.0'},
    )
    if not text:
        return []
    try:
        data = json.loads(text)
        children = data.get('data', {}).get('children', [])
    except Exception:
        return []
    out, seen = [], set()
    for child in children:
        post = child.get('data', {})
        url = post.get('url')
        key = url or post.get('permalink')
        title = (post.get('title') or '').strip()
        if not key or not title or key in seen:
            continue
        try:
            score = int(post.get('score', 0) or 0)
        except Exception:
            score = 0
        if score < 200:
            continue
        href = url if url else f'https://reddit.com{post.get("permalink", "")}'
        seen.add(key)
        out.append({
            'url': href,
            'title': title,
            'source': 'https://reddit.com/r/technology/'
        })
        if len(out) >= limit:
            break
    return out


def normalize_repo_url(raw):
    raw = raw.strip().strip('"').strip("'")
    if raw.startswith('/'):
        raw = 'https://github.com' + raw
    elif '/' in raw and not raw.startswith('http'):
        raw = 'https://github.com/' + raw
    return raw


def fetch_repo_description(repo_url):
    text = get_text(repo_url)
    if not text:
        return ''
    m = re.search(r'<meta[^>]+name="description"[^>]+content="([^"]+)"', text)
    if not m:
        return ''
    desc = m.group(1)
    # Strip the " - repo/owner" suffix GitHub appends
    idx = desc.rfind(' - ')
    if idx != -1:
        desc = desc[:idx]
    return desc.strip()


def extract_github_trending(limit=8):
    text = get_text('https://github.com/trending')
    if not text:
        return []
    out = []
    seen = set()
    for art in re.finditer(r'<article[^>]*>(.*?)</article>', text, re.S):
        block = art.group(1)
        hm = re.search(r'<h2[^>]*>\s*<a[^>]+href="/([^"]+)"', block)
        if not hm:
            continue
        repo_path = hm.group(1)
        if '/' not in repo_path:
            continue
        url = normalize_repo_url(repo_path)
        if url in seen:
            continue
        seen.add(url)
        pm = re.search(r'<p[^>]*>\s*([^<]+)\s*</p>', block)
        desc = pm.group(1).strip() if pm else ''
        if not desc:
            desc = fetch_repo_description(url)
        out.append({
            'url': url,
            'title': url.split('/')[-1],
            'description': desc,
            'source': 'https://github.com/trending',
        })
        if len(out) >= limit:
            break
    return out


def build_newsletter(limit=4):
    now = datetime.now().strftime('%Y-%m-%d')
    github = extract_github_trending(limit=limit)
    lines = [f'📰 Boletín del día ({now})\n']
    for item in github:
        url = item.get('url') or ''
        desc = (item.get('description') or '').strip()
        if desc:
            lines.append(f'[gh] <a href="{url}">{url}</a> - {desc}')
        else:
            lines.append(f'[gh] <a href="{url}">{url}</a>')
    lines.append('\n🔎 Enlaces útiles: https://github.com/trending')
    return '\n'.join(lines)


def main():
    token, chat_id = get_env()
    message = build_newsletter()
    result = telegram_send(message, token, chat_id)
    print(json.dumps({'ok': result.get('ok'), 'message_id': result.get('result', {}).get('message_id')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
