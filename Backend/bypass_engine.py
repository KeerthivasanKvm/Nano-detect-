"""
Bypass Engine
─────────────
All bypass functions ported from the reference bypasser.py
+ Playwright-backed browser fallback
+ Per-call retry logic
"""

import re
import base64
import time
import asyncio
import logging
from urllib.parse import urlparse, unquote, parse_qs, quote
from typing import Optional

import requests
import cloudscraper
from bs4 import BeautifulSoup
from curl_cffi import requests as Nreq
from curl_cffi.requests import Session as cSession

from config import MAX_RETRIES, RETRY_DELAY
from proxy_manager import proxy_dict, get_proxy
from browser_manager import fetch_page_content, get_final_redirect, run_with_browser

log = logging.getLogger(__name__)

# ─── Retry decorator (sync) ───────────────────────────────────────────────────

def _retry_sync(fn):
    """Wrap a sync function with retry + exponential back-off."""
    def wrapper(*args, **kwargs):
        delay = RETRY_DELAY
        last  = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                result = fn(*args, **kwargs)
                if result and "Something went wrong" not in str(result):
                    return result
                raise ValueError(f"Bad result: {result}")
            except Exception as e:
                last = e
                log.warning(f"[{fn.__name__}] attempt {attempt}/{MAX_RETRIES} failed: {e}")
                if attempt < MAX_RETRIES:
                    time.sleep(delay)
                    delay *= 2
        raise last or RuntimeError(f"{fn.__name__} exhausted all retries")
    return wrapper

def _retry_async(fn):
    """Wrap an async function with retry + exponential back-off."""
    async def wrapper(*args, **kwargs):
        delay = RETRY_DELAY
        last  = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                result = await fn(*args, **kwargs)
                if result and "Something went wrong" not in str(result):
                    return result
                raise ValueError(f"Bad result: {result}")
            except Exception as e:
                last = e
                log.warning(f"[{fn.__name__}] attempt {attempt}/{MAX_RETRIES} failed: {e}")
                if attempt < MAX_RETRIES:
                    await asyncio.sleep(delay)
                    delay *= 2
        raise last or RuntimeError(f"{fn.__name__} exhausted all retries")
    return wrapper


# ═══════════════════════════════════════════════════════════════════════════
# RECAPTCHA v3
# ═══════════════════════════════════════════════════════════════════════════

def recaptcha_v3(anchor_url="https://www.google.com/recaptcha/api2/anchor?ar=1"
                 "&k=6Lcr1ncUAAAAAH3cghg6cOTPGARa8adOf-y9zv2x"
                 "&co=aHR0cHM6Ly9vdW8ucHJlc3M6NDQz"
                 "&hl=en&v=pCoGBhjs9s8EhFOHJFe8cqis&size=invisible&cb=ahgyd1gkfkhe"):
    from requests import Session
    rs = Session()
    rs.headers.update({"content-type": "application/x-www-form-urlencoded"})
    matches = re.findall(r"([api2|enterprise]+)\/anchor\?(.*)", anchor_url)[0]
    url_base = f"https://www.google.com/recaptcha/{matches[0]}/"
    params   = matches[1]
    res      = rs.get(url_base + "anchor", params=params)
    token    = re.findall(r'"recaptcha-token" value="(.*?)"', res.text)[0]
    params_d = dict(pair.split("=") for pair in params.split("&"))
    res      = rs.post(url_base + "reload", params=f'k={params_d["k"]}',
                       data=(f"v={params_d['v']}&reason=q&c={token}"
                             f"&k={params_d['k']}&co={params_d['co']}"))
    return re.findall(r'"rresp","(.*?)"', res.text)[0]


# ═══════════════════════════════════════════════════════════════════════════
# SYNC BYPASSERS
# ═══════════════════════════════════════════════════════════════════════════

@_retry_sync
def bypass_adfly(url: str) -> str:
    def decrypt_url(code):
        a, b = "", ""
        for i, c in enumerate(code):
            (a if i % 2 == 0 else None).__class__  # noop – just index split
            if i % 2 == 0: a += c
            else:           b  = c + b
        key = list(a + b)
        i = 0
        while i < len(key):
            if key[i].isdigit():
                for j in range(i + 1, len(key)):
                    if key[j].isdigit():
                        u = int(key[i]) ^ int(key[j])
                        if u < 10: key[i] = str(u)
                        i = j; break
            i += 1
        key = "".join(key)
        decrypted = base64.b64decode(key)[16:-16]
        return decrypted.decode("utf-8")

    client = cloudscraper.create_scraper(allow_brotli=False)
    res    = client.get(url, proxies=proxy_dict()).text
    ysmm   = re.findall(r"ysmm\s+=\s+['|\"](.*?)['|\"]", res)[0]
    dest   = decrypt_url(ysmm)
    if re.search(r"go\.php\?u\=", dest):
        dest = base64.b64decode(re.sub(r"(.*?)u=", "", dest)).decode()
    elif "&dest=" in dest:
        dest = unquote(re.sub(r"(.*?)dest=", "", dest))
    return dest


@_retry_sync
def bypass_linkvertise(url: str) -> str:
    resp = requests.get("https://bypass.pm/bypass2", params={"url": url},
                        proxies=proxy_dict(), timeout=15).json()
    if resp.get("success"):
        return resp["destination"]
    raise ValueError(resp.get("msg", "linkvertise api failed"))


@_retry_sync
def bypass_ouo(url: str) -> str:
    tempurl = url.replace("ouo.press", "ouo.io")
    p       = urlparse(tempurl)
    uid     = tempurl.split("/")[-1]
    client  = cSession(headers={
        "authority": "ouo.io",
        "accept":    "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "referer":   "http://www.google.com/ig/adde?moduleurl=",
    })
    res      = client.get(tempurl, impersonate="chrome110")
    next_url = f"{p.scheme}://{p.hostname}/go/{uid}"
    for _ in range(2):
        if res.headers.get("Location"): break
        bs4    = BeautifulSoup(res.content, "lxml")
        inputs = bs4.form.findAll("input", {"name": re.compile(r"token$")})
        data   = {inp.get("name"): inp.get("value") for inp in inputs}
        data["x-token"] = recaptcha_v3()
        res    = client.post(next_url, data=data,
                             headers={"content-type": "application/x-www-form-urlencoded"},
                             allow_redirects=False, impersonate="chrome110")
        next_url = f"{p.scheme}://{p.hostname}/xreallcygo/{uid}"
    return res.headers.get("Location", "")


@_retry_sync
def bypass_droplink(url: str) -> str:
    client  = cloudscraper.create_scraper(allow_brotli=False)
    ref     = re.findall(r"action[ ]{0,}=[ ]{0,}['|\"](.*?)['|\"]",
                         client.get(url, timeout=10).text)[0]
    res     = client.get(url, headers={"referer": ref})
    bs4     = BeautifulSoup(res.content, "html.parser")
    inputs  = bs4.find_all("input")
    data    = {i.get("name"): i.get("value") for i in inputs}
    p       = urlparse(url)
    time.sleep(3.1)
    resp    = client.post(f"{p.scheme}://{p.netloc}/links/go", data=data,
                          headers={"content-type": "application/x-www-form-urlencoded",
                                   "x-requested-with": "XMLHttpRequest"}).json()
    if resp.get("status") == "success":
        return resp["url"]
    raise ValueError("droplink failed")


@_retry_sync
def bypass_try2link(url: str) -> str:
    client = cloudscraper.create_scraper(allow_brotli=False)
    url    = url.rstrip("/")
    params = (("d", int(time.time()) + 240),)
    r      = client.get(url, params=params, headers={"Referer": "https://newforex.online/"})
    soup   = BeautifulSoup(r.text, "html.parser")
    inputs = soup.find(id="go-link").find_all(name="input")
    data   = {i.get("name"): i.get("value") for i in inputs}
    time.sleep(7)
    resp   = client.post("https://try2link.com/links/go", data=data,
                         headers={"Host": "try2link.com",
                                  "X-Requested-With": "XMLHttpRequest",
                                  "Origin": "https://try2link.com",
                                  "Referer": url})
    return resp.json()["url"]


@_retry_sync
def bypass_shareus(url: str) -> str:
    DOMAIN  = "https://us-central1-my-apps-server.cloudfunctions.net"
    headers = {"user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}
    sess    = requests.Session()
    code    = url.split("/")[-1]
    sess.get(f"{DOMAIN}/v", params={"shortid": code, "initial": "true",
                                    "referrer": "https://shareus.io/"}, headers=headers)
    for i in range(1, 4):
        sess.post(f"{DOMAIN}/v", json={"current_page": i}, headers=headers)
    return sess.get(f"{DOMAIN}/get_link", headers=headers).json()["link_info"]["destination"]


@_retry_sync
def bypass_bitly_tinyurl(url: str) -> str:
    return requests.get(url, proxies=proxy_dict(), timeout=15,
                        allow_redirects=True).url


@_retry_sync
def bypass_mediafire(url: str) -> str:
    res  = requests.get(url, stream=True, proxies=proxy_dict())
    for line in res.text.splitlines():
        m = re.search(r'href="((http|https)://download[^"]+)', line)
        if m: return m.group(1)
    raise ValueError("mediafire link not found")


@_retry_sync
def bypass_dropbox(url: str) -> str:
    return (url.replace("www.", "")
               .replace("dropbox.com", "dl.dropboxusercontent.com")
               .replace("?dl=0", ""))


@_retry_sync
def bypass_du_link(url: str) -> str:
    client  = cloudscraper.create_scraper(allow_brotli=False)
    url     = url.rstrip("/")
    code    = url.split("/")[-1]
    final   = f"https://du-link.in/{code}"
    resp    = client.get(final, headers={"referer": "https://profitshort.com/"},
                         allow_redirects=False)
    soup    = BeautifulSoup(resp.content, "html.parser")
    inputs  = soup.find_all("input")
    data    = {i.get("name"): i.get("value") for i in inputs}
    r       = client.post("https://du-link.in/links/go", data=data,
                          headers={"x-requested-with": "XMLHttpRequest"})
    return r.json()["url"]


@_retry_sync
def bypass_mdisk(url: str) -> str:
    cid  = url.split("/")[-1]
    resp = requests.get(f"https://diskuploader.entertainvideo.com/v1/file/cdnurl?param={cid}",
                        proxies=proxy_dict(), timeout=15).json()
    return resp.get("download") or resp.get("source") or ""


# ═══════════════════════════════════════════════════════════════════════════
# BROWSER-BASED (playwright)
# ═══════════════════════════════════════════════════════════════════════════

async def bypass_via_browser(url: str) -> str:
    """Generic browser bypass – follow redirects + scrape the final destination."""
    from playwright.async_api import Page

    @_retry_async
    async def _task_wrapper(dummy=None):
        async def task(page: Page) -> str:
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(3)
            return page.url
        return await run_with_browser(task, proxy_url=get_proxy())

    return await _task_wrapper()


async def bypass_publicearn(url: str) -> str:
    """Publicearn requires JS interaction – use browser."""
    from playwright.async_api import Page

    @_retry_async
    async def _do(dummy=None):
        async def task(page: Page) -> str:
            await page.goto(url, wait_until="domcontentloaded")
            await asyncio.sleep(32)   # mandatory wait
            code = url.split("/")[-1]
            ref  = urlparse(page.url).netloc
            cget = cloudscraper.create_scraper(allow_brotli=False).request
            resp = cget("GET", f"https://go.publicearn.com/{code}/?uid=1",
                        headers={"referer": f"https://{ref}/"})
            soup  = BeautifulSoup(resp.content, "html.parser")
            data  = {i.get("name"): i.get("value") for i in soup.find_all("input")}
            resp2 = cget("POST", "https://go.publicearn.com/links/go", data=data,
                         headers={"x-requested-with": "XMLHttpRequest"})
            return resp2.json()["url"]
        return await run_with_browser(task, proxy_url=get_proxy())

    return await _do()


# ═══════════════════════════════════════════════════════════════════════════
# ROUTER
# ═══════════════════════════════════════════════════════════════════════════

async def bypass(url: str) -> str:
    """
    Main entry point.
    Detect URL type → call correct bypass → return result string.
    """
    from url_detector import detect
    info = detect(url)
    cat  = info.category
    log.info(f"Bypassing [{cat}] {url}")

    try:
        loop = asyncio.get_event_loop()

        if cat == "adfly":
            return await loop.run_in_executor(None, bypass_adfly, url)
        elif cat == "linkvertise":
            return await loop.run_in_executor(None, bypass_linkvertise, url)
        elif cat == "ouo":
            return await loop.run_in_executor(None, bypass_ouo, url)
        elif cat == "droplink":
            return await loop.run_in_executor(None, bypass_droplink, url)
        elif cat == "try2link":
            return await loop.run_in_executor(None, bypass_try2link, url)
        elif cat == "shareus":
            return await loop.run_in_executor(None, bypass_shareus, url)
        elif cat in ("bitly", "tinyurl", "cutt_ly", "is_gd"):
            return await loop.run_in_executor(None, bypass_bitly_tinyurl, url)
        elif cat == "mediafire":
            return await loop.run_in_executor(None, bypass_mediafire, url)
        elif cat == "dropbox":
            return await loop.run_in_executor(None, bypass_dropbox, url)
        elif cat == "du_link":
            return await loop.run_in_executor(None, bypass_du_link, url)
        elif cat == "mdisk":
            return await loop.run_in_executor(None, bypass_mdisk, url)
        elif cat == "publicearn":
            return await bypass_publicearn(url)
        else:
            # Generic browser-based fallback for unknown / complex links
            return await bypass_via_browser(url)

    except Exception as e:
        log.error(f"Bypass failed for [{cat}] {url}: {e}")
        raise
