import json
import os
import re
import sys
import requests
from bs4 import BeautifulSoup

CONFIG_FILE = "config.json"
STATE_FILE = "state.json"
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0 Safari/537.36"
    ),
    "Accept-Language": "de-DE,de;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def parse_price(raw) -> float:
    """'392,37 €' oder '392.37' -> 392.37 (dt. und US-Format)."""
    if isinstance(raw, (int, float)):
        return float(raw)
    cleaned = re.sub(r"[^\d,.]", "", str(raw))
    if not cleaned:
        raise ValueError(f"Kein Preis erkennbar in: {raw!r}")
    if "," in cleaned and "." in cleaned:
        if cleaned.rfind(",") > cleaned.rfind("."):   # 1.299,99
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:                                          # 1,299.99
            cleaned = cleaned.replace(",", "")
    elif "," in cleaned:
        cleaned = cleaned.replace(",", ".")
    return float(cleaned)


def _iter_nodes(data):
    """Laeuft rekursiv durch JSON-LD (auch @graph / Listen)."""
    if isinstance(data, dict):
        yield data
        for v in data.values():
            yield from _iter_nodes(v)
    elif isinstance(data, list):
        for item in data:
            yield from _iter_nodes(item)


def _offer_price(offers):
    if isinstance(offers, dict):
        for key in ("price", "lowPrice"):
            if offers.get(key) is not None:
                return parse_price(offers[key])
    if isinstance(offers, list):
        prices = [_offer_price(o) for o in offers]
        prices = [p for p in prices if p is not None]
        return min(prices) if prices else None
    return None


def extract_main_price(soup, html):
    """Hauptpreis (Buy-Box)."""
    # 1) JSON-LD Produktdaten
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or tag.get_text())
        except Exception:
            continue
        for node in _iter_nodes(data):
            if isinstance(node, dict) and "offers" in node:
                price = _offer_price(node["offers"])
                if price is not None:
                    return price, "json-ld"
    # 2) Microdata-Meta
    meta = soup.select_one('[itemprop="price"]')
    if meta and meta.get("content"):
        return parse_price(meta["content"]), "itemprop"
    # 3) Fallback: erstes sichtbares Euro-Preisformat
    m = re.search(r"(\d{1,4}(?:\.\d{3})*,\d{2})\s*€", html)
    if m:
        return parse_price(m.group(1)), "regex"
    return None, None


def extract_marketplace_price(html):
    """Guenstigster Drittanbieter-Preis aus 'Andere Anbieter von X€'."""
    m = re.search(r"Andere Anbieter von\s*([\d.]*\d,\d{2}|\d+,\d{2})\s*€", html)
    if m:
        return parse_price(m.group(1))
    return None


def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def send_discord(product, label, price, all_offers):
    detail = "\n".join(f"• {l}: {p:.2f} €" for l, p in all_offers)
    payload = {
        "embeds": [{
            "title": f"💰 Preisalarm: {product['name']}",
            "description": (
                f"Günstigstes Angebot: **{price:.2f} €** ({label})\n"
                f"Zielpreis: {product['target_price']:.2f} €\n\n"
                f"**Alle Angebote:**\n{detail}\n\n"
                f"[Zum Produkt]({product['url']})"
            ),
            "url": product["url"],
            "color": 3066993,
        }]
    }
    r = requests.post(WEBHOOK_URL, json=payload, timeout=30)
    r.raise_for_status()
    print(f"[{product['name']}] Discord-Benachrichtigung gesendet.")


def check_product(product, state):
    name = product["name"]
    entry = state.setdefault(name, {"notified": False})
    try:
        resp = requests.get(product["url"], headers=HEADERS, timeout=30)
        resp.raise_for_status()
        html = resp.text
        soup = BeautifulSoup(html, "html.parser")

        main_price, source = extract_main_price(soup, html)
        market_price = extract_marketplace_price(html)
    except Exception as e:
        print(f"[{name}] Fehler: {e}")
        return

    offers = []
    if main_price is not None:
        offers.append(("Hauptangebot", main_price))
    if market_price is not None:
        offers.append(("Andere Anbieter", market_price))

    if not offers:
        print(f"[{name}] Kein Preis gefunden (evtl. Bot-Schutz aktiv).")
        return

    label, best_price = min(offers, key=lambda o: o[1])
    entry["last_offers"] = {l: p for l, p in offers}

    offers_str = " | ".join(f"{l}: {p:.2f}€" for l, p in offers)
    print(f"[{name}] {offers_str} -> günstigstes {best_price:.2f}€ ({label}) / "
          f"Ziel {product['target_price']:.2f}€")

    if best_price <= product["target_price"]:
        if not entry["notified"]:
            send_discord(product, label, best_price, offers)
            entry["notified"] = True
    else:
        entry["notified"] = False


def main():
    if not WEBHOOK_URL:
        sys.exit("DISCORD_WEBHOOK_URL fehlt (als GitHub-Secret setzen).")
    config = load_json(CONFIG_FILE, {"products": []})
    state = load_json(STATE_FILE, {})
    for product in config["products"]:
        check_product(product, state)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
