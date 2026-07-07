# Starlink Price Monitor

Prüft alle 30 Minuten per GitHub Actions den Preis einer pccomponentes-Produktseite
und schickt eine Discord-Benachrichtigung, sobald der Zielpreis (oder günstiger)
erreicht ist. Läuft komplett in der Cloud – kein eigener Rechner nötig.

## Einrichtung (5 Schritte)

1. **Repo anlegen** (öffentlich = kostenlos & unbegrenzte Actions-Minuten) und alle
   Dateien dieses Ordners hochladen – inkl. `.github/workflows/monitor.yml`.

2. **Discord-Webhook erstellen:** Server-Einstellungen → Integrationen → Webhooks →
   *Neuer Webhook* → Kanal wählen → **Webhook-URL kopieren**.

3. **Secret setzen:** Repo → Settings → Secrets and variables → Actions →
   *New repository secret*
   - Name: `DISCORD_WEBHOOK_URL`
   - Wert: die kopierte Webhook-URL

4. **Zielpreis anpassen** in `config.json` (`target_price`). Aktuell: `250.00`.

5. **Testlauf:** Reiter *Actions* → Workflow „Price Monitor" → *Run workflow*.
   Im Log siehst du den erkannten Preis. Danach läuft alles automatisch alle 30 Min.

## Wie es funktioniert

- `monitor.py` liest den Preis robust über drei Wege: JSON-LD Produktdaten →
  `itemprop="price"`-Meta → Regex auf das sichtbare Euro-Format.
- `state.json` (wird automatisch erzeugt und committet) merkt sich, ob bereits
  benachrichtigt wurde → **keine Wiederholungs-Pings** alle 30 Min, solange der Preis
  niedrig bleibt. Steigt der Preis wieder über das Ziel, wird der Alarm neu scharf.

## Weitere Produkte

Einfach in `config.json` weitere Einträge im `products`-Array ergänzen (funktioniert
für beliebige pccomponentes-Produktseiten):

```json
{ "name": "Anderes Produkt", "url": "https://www.pccomponentes.de/...", "target_price": 199.00 }
```

## Hinweise

- **GitHub-Cron ist best effort**, nicht sekundengenau – für „alle halbe Stunde" völlig ok.
- **Bot-Schutz:** Aktuell geht der einfache Request durch. Falls pccomponentes irgendwann
  blockt (Log zeigt „Kein Preis gefunden"), ist ein Umstieg auf Playwright nötig.
- Es werden **beide** Preise verglichen: der Hauptpreis (Buy-Box) **und** der
  günstigste Drittanbieter-Preis aus der Zeile „Andere Anbieter von …". Der Alarm
  feuert, sobald eines von beiden den Zielpreis erreicht. Die Discord-Nachricht
  zeigt an, welches Angebot ausgelöst hat und listet alle gefundenen Preise auf.
