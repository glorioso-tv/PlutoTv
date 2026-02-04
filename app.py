from fastapi import FastAPI, Response
from pluto import playlist_pluto
import time
import html
from urllib.parse import urlparse
import re
import requests

app = FastAPI()

# ===== PROTEÇÃO CONTRA BAN / CACHE =====
CACHE_TTL = 1800  # 30 minutos
_CACHE_DATA = None
_CACHE_TIME = 0
# ==============================

# Headers padrões
headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                         "(KHTML, like Gecko) Chrome/51.0.2704.103 Safari/537.36"}


# =============================
# Função DNS resolver para IPTV
# =============================
def dns_resolver_iptv(url, headers):
    url = url.replace('https://', 'http://')
    url_parsed = urlparse(url)

    protocol = url_parsed.scheme
    port = str(url_parsed.port) if url_parsed.port else ('443' if 'https' in url else '')
    net = url_parsed.hostname
    host = f"{protocol}://{net}" + (f":{port}" if port else "")

    ip_pattern = re.compile(r'^(https?://)?(\d{1,3}\.){3}\d{1,3}(:\d+)?(/.*)?$')
    if ip_pattern.match(net):
        return {'url': url, 'headers': headers}

    params = {"name": net, "type": "A"}
    try:
        r = requests.get('https://dns.google/dns-query', headers={"Accept": "application/dns-json"}, params=params).json()
        ip_ = r['Answer'][-1].get('data', '')
    except:
        ip_ = net

    if ip_:
        new_host = f"{protocol}://{ip_}" + (f":{port}" if port else "")
        url_replace = url.replace(host, new_host)
        headers_ = {'Host': net}
        headers_.update(headers)
        return {'url': url_replace, 'headers': headers_}
    return {}


# =============================
# Função de cache
# =============================
def get_cached_playlist():
    """Retorna a lista em cache; atualiza se expirou."""
    global _CACHE_DATA, _CACHE_TIME
    now = time.time()

    if _CACHE_DATA and (now - _CACHE_TIME) < CACHE_TTL:
        return _CACHE_DATA

    # Atualiza cache chamando playlist_pluto()
    _CACHE_DATA = playlist_pluto()
    _CACHE_TIME = now
    return _CACHE_DATA


# =============================
# Rota principal M3U
# =============================
@app.get("/")
def pluto_m3u():
    channels = get_cached_playlist()
    m3u = "\ufeff#EXTM3U\n"

    for name, desc, thumb, stream in channels:
        if not stream:
            continue

        # Resolver DNS do stream
        resolved = dns_resolver_iptv(stream, headers)
        if resolved:
            stream_url = resolved['url']
        else:
            stream_url = stream  # fallback

        m3u += f'#EXTINF:-1 tvg-logo="{thumb}",{name}\n'
        m3u += f'{stream_url}\n'

    return Response(
        content=m3u,
        media_type="application/x-mpegURL; charset=utf-8"
    )


# =============================
# Rota HTML de visualização
# =============================
@app.get("/index")
def pluto_index():
    channels = get_cached_playlist()

    html_content = """
    <html>
    <head>
        <meta charset="utf-8">
        <title>Pluto TV - Lista</title>
        <style>
            body { background: #111; color: #fff; font-family: Arial; padding: 20px; }
            h1 { text-align: center; }
            .channel { display: flex; align-items: center; margin: 10px 0; background: #222; padding: 10px; border-radius: 8px; }
            .channel img { width: 80px; height: auto; margin-right: 15px; }
            .channel a { color: #00bfff; text-decoration: none; }
        </style>
    </head>
    <body>
        <h1>📺 Canais Disponíveis</h1>
    """

    for name, desc, thumb, stream in channels:
        if not stream:
            continue

        resolved = dns_resolver_iptv(stream, headers)
        if resolved:
            stream_url = resolved['url']
        else:
            stream_url = stream

        html_content += f"""
        <div class="channel">
            <img src="{thumb}" alt="{html.escape(name)}">
            <div>
                <b>{html.escape(name)}</b><br>
                <a href="{stream_url}" target="_blank">Abrir stream</a>
            </div>
        </div>
        """

    html_content += "</body></html>"

    return Response(content=html_content, media_type="text/html; charset=utf-8")

