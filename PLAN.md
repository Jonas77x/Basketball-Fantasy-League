# Plan: Persönlicher Fantasy-Basketball-Assistent

Stand: 28.09.2026 · Draft: **Mo 19.10.2026, 21:00 Uhr** (15:00 Uhr New York) · Saisonstart NBA: **Di 20.10.2026**

---

## 1. Was ich bei der Recherche herausgefunden habe (wichtig!)

### Yahoo hat seine API 2026 stark eingeschränkt
- **Freigabe nur noch auf Antrag.** Seit dem 22.07.2026 antwortet die Yahoo-Fantasy-API bei nicht freigegebenen Apps nur noch mit „nicht autorisiert“. Jede App muss unter [sports.yahoo.com/developer/access](https://sports.yahoo.com/developer/access/) beantragt und von Menschen geprüft werden. Es gibt keine feste Bearbeitungszeit. Berichte anderer Entwickler sprechen von etwa 1–2 Wochen.
- **Nur Lesezugriff.** Auf der Antragsseite steht wörtlich: *„The Yahoo Fantasy Sports API currently provides read access only. Write access is not available at this time.“* Die Doku beschreibt zwar noch Schreib-Endpunkte (Aufstellung per `PUT /team/{key}/roster`, Wechsel/Trades per `POST /league/{key}/transactions`), aber Yahoo vergibt dafür aktuell keine Rechte.

**Was das für dich bedeutet:**

| Wunsch | Geht das? | Beste Alternative |
|---|---|---|
| Live-Draft automatisch mitlesen | Ja, **sobald Yahoo den Antrag freigibt** (Lesezugriff reicht) | Manueller Modus mit Schnelleingabe. Der wird so gebaut, dass er auch allein gut funktioniert. |
| Aufstellung automatisch setzen | **Nein**, solange Yahoo keinen Schreibzugriff vergibt | Das System berechnet täglich die beste Aufstellung und schickt dir per Telegram, was zu tun ist, mit Direktlink in die Yahoo-App. Oft reicht dort ein Tipp auf „Start Active Players“. |
| Waiver-Moves, Trades ausführen | **Nein** (siehe oben) | Vorschlag mit Begründung plus Button, der die richtige Yahoo-Seite öffnet. Du bestätigst in Yahoo, und das System protokolliert es. |
| Kader, Matchups, Transaktionen lesen | Ja, mit Freigabe | Ohne Freigabe: Kader aus dem Draft-Protokoll, Änderungen trägst du von Hand nach. |

Den Code für Schreibaktionen bereite ich trotzdem so vor, dass er sofort funktioniert, falls Yahoo später Schreibrechte vergibt. Standardmäßig bleibt er aus (Dry-Run).

**Was ich bewusst nicht baue:** eine Fernsteuerung des Browsers, die sich als du bei Yahoo einloggt und klickt. Das wäre technisch möglich, verstößt aber gegen die Yahoo-Nutzungsbedingungen und kann deinen Account gefährden.

### NBA-Datenquellen
- **nba.com und ESPN** blockieren Anfragen aus Rechenzentren. Das betrifft auch einen späteren Server. Von deinem PC zu Hause funktionieren sie meistens.
- **Basketball-Reference** funktioniert überall. Dort gibt es die Stats aller Spieler, den Spielplan 2026-27 und den Draft 2026 für die Rookies.
- **Hashtag Basketball** hat die aktuellen Yahoo-ADP (durchschnittliche Draft-Position) und die Yahoo-Positionen (Stand 25.09.2026). Damit geht die Vorhersage „wer ist bis zu meinem Pick weg“ auch ganz ohne Yahoo-API.
- **News:** Die RSS-Feeds von Yahoo Sports, CBS Sports und RotoWire sind erreichbar, außerdem die offizielle Seite zum NBA-Injury-Report.

Alle Quellen werden höflich und selten abgefragt: gecacht und höchstens so oft wie nötig.

---

## 2. Technik (und wo ich vom Vorschlag abweiche)

| Bereich | Wahl | Begründung |
|---|---|---|
| Backend | Python 3.12, FastAPI, SQLite, APScheduler | wie vorgeschlagen |
| Oberfläche | Jinja2 + HTMX, handyfreundlich, Design wie deine HTML-Datei (Hell/Dunkel) | wie vorgeschlagen; die Draft-Seite ist zusätzlich für die PC-Tastatur optimiert |
| Yahoo | Eigener schlanker Client (httpx), nur Endpunkte aus der offiziellen Doku | Die verbreiteten Libraries (yfpy, yahoo_fantasy_api) melden sich über die Kommandozeile an und haben keine zentrale Stelle für Cache, Rate-Limit, Protokoll und Dry-Run. Wir brauchen nur etwa 10 Endpunkte, und yfpy nutze ich als Referenz beim Auslesen der Antworten. |
| NBA-Daten | Basketball-Reference + Hashtag Basketball als Hauptquellen, `nba_api`/ESPN nur als Zusatz, wenn erreichbar | nba.com blockt Server-IPs (selbst getestet) |
| KI | Anthropic API, Modell `claude-sonnet-5` (per `.env` änderbar) | wie gewünscht; überall optional, ohne Key laufen feste Textvorlagen |
| Telegram | `python-telegram-bot` mit Long-Polling | braucht keine öffentliche Adresse, funktioniert zu Hause und auf dem Server |
| **Start auf Windows** | **Doppelklick auf `start.bat`** (nutzt das Tool `uv`, das Python selbst mitbringt) | **Abweichung:** Docker Desktop auf Windows ist schwer (WSL2, Virtualisierung im BIOS) und fehleranfällig für Einsteiger. Docker nutze ich nur auf dem Server. |
| Server | Docker Compose, **ein Befehl**: `docker compose up -d` | wie vorgeschlagen |
| Zugriff vom Handy auf den Server | Tailscale (kostenlos, privates Netz) | Das Dashboard ist nicht offen im Internet, und du brauchst keine Domain |

---

## 3. Kosten (so niedrig wie möglich)

| Posten | Kosten | Wann |
|---|---|---|
| Lokal auf deinem PC (Draft + Tests) | **0 €** | ab Phase 1 |
| Telegram, Tailscale, GitHub | **0 €** | |
| Server rund um die Uhr | **0 €** (Oracle Cloud „Always Free“, Einrichtung fummeliger) **oder ca. 4–6 €/Monat** (Hetzner, einfacher und zuverlässiger) | erst ab Phase 4, du entscheidest dann |
| KI (Sonnet 5: $2 pro 1 Mio. Eingabe-Tokens, $10 pro 1 Mio. Ausgabe-Tokens) | **ca. 1–2 $/Monat** (Schätzung: 1 News-Zusammenfassung/Tag, 1 Recap/Woche, KI-Rat nur auf Knopfdruck; Draft-Abend ca. 0,25 $). Prepaid ab 5 $, das reicht für mehrere Monate. Ein Ausgabenlimit wird eingestellt. | optional, ab Phase 1 |

Spar-Optionen:
- Die KI komplett weglassen. Alles funktioniert dann mit Textvorlagen.
- Für die News-Zusammenfassungen das günstigere Haiku 4.5 nehmen (ca. halber Preis). Das entscheidest du.

---

## 4. Phasen und Meilensteine

### Phase 0: Sofort (du, ca. 20 Min.)
- [ ] **Yahoo-API-Zugang beantragen.** Anleitung mit fertigen Texten: [`docs/YAHOO_ANTRAG.md`](docs/YAHOO_ANTRAG.md). Je früher, desto größer die Chance, dass die Freigabe vor dem Draft da ist.

### Phase 1: Draft-Assistent (Kern) · Ziel: So 04.10.
- Projekt-Grundgerüst, Datenbank, Start per Doppelklick (`start.bat`)
- **Datenimport:**
  - Stats der letzten 3 Saisons von Basketball-Reference, als Datei im Projekt gespeichert
  - Yahoo-ADP + Yahoo-Positionen von Hashtag Basketball
  - Rookies aus dem Draft 2026
- **Projektionen 2026-27:**
  - Basis sind die Werte pro Minute aus den letzten Saisons, die letzte am stärksten gewichtet
  - Korrektur nach Alter (junge Spieler steigen, ab ca. 30 geht es bergab, STL/BLK früher)
  - Minuten-Prognose (Rolle, Teamwechsel)
  - Erwartete Spiele aus der Verletzungshistorie (3 Jahre) plus bekannte aktuelle Verletzungen
  - Rookies als grobe Schätzung nach Draftplatz, klar markiert
  - Deine Werte aus der HTML-Datei (Transfers, Hinweise) werden übernommen
- **Bewertung (Verbesserungen gegenüber der HTML-Datei):**
  - Z-Scores werden gegen den *draftbaren* Pool berechnet, also Teams × Kaderplätze, nicht gegen alle Spieler
  - FG% und FT% bleiben nach Wurfvolumen gewichtet
  - Positions-Knappheit fließt ein (du brauchst z. B. Center für die C-Plätze)
- **Neue Prognose „Wer ist bis zu meinem Pick weg?“:**
  - Simulation der gegnerischen Picks anhand der Yahoo-ADP mit Zufallsstreuung, einige tausend Durchläufe
  - Ergebnis pro Spieler, z. B. „noch da bei deinem Pick: 35 %“
  - Die Empfehlung berücksichtigt, wer *nicht zurückkommt*
- **Empfehlung pro Pick:**
  - Top 3 mit kurzer Begründung auf Deutsch
  - Kategorien-Balance deines Teams
  - Ab Runde 3–4 Punt-Vorschläge mit Rechnung („Wenn du FT% opferst, steigen deine Siegchancen in den anderen 8 Kategorien auf …“)
- **Manueller Modus:**
  - Schnelleingabe: 2–3 Buchstaben tippen, Enter. Die wahrscheinlichsten Picks stehen oben.
  - Rückgängig-Funktion
  - Rookies und fehlende Spieler lassen sich nachtragen
- **Übungsmodus:** kompletter Probe-Draft gegen simulierte Gegner, damit du den Ablauf vor dem 19.10. kennst
- Optional „KI um Rat fragen“ (Sonnet 5), falls du einen Anthropic-Key hast
- Tests: Rechenlogik, Snake-Reihenfolge, komplette simulierte Drafts

**Du probierst aus:** Starten und einen Übungs-Draft machen.

### Phase 2: Yahoo-Anbindung (nur lesen) + Live-Draft · Code fertig: Fr 09.10.
- „Mit Yahoo verbinden“-Button (OAuth2), Token-Erneuerung, Rate-Limit, Cache
- **Liga-Einstellungen aus der API:**
  - Kategorien, Kaderpositionen, Teams, Draft-Reihenfolge
  - Wechsel-Limits (`max_weekly_adds`)
  - Waiver-Regeln (`waiver_type`, `waiver_time`, FAAB)
  - Playoff-Start und Anzahl der Playoff-Teams
- Live-Draft: `league/{key}/draftresults` alle 3–10 Sekunden. Ist dein Pick nah, wird öfter abgefragt. Bei Problemen weicht das System aus und schaltet automatisch auf den manuellen Modus.
- **Prüfen, ob `draftresults` während eines Live-Drafts aktualisiert wird:** Test in einer öffentlichen Yahoo-Liga mit Live-Draft vor dem 19.10. (Lesezugriff auf öffentliche Ligen ist laut Doku erlaubt).
- Zuordnung Yahoo-Spieler ↔ Stats-Datenbank (auch Namen mit Sonderzeichen wie Dončić)
- Tests mit gespeicherten Beispiel-Antworten (die Tests rufen nie echte Server auf)

**Meilenstein Sa 10.10.: Entscheidung.**
- Freigabe da → Generalprobe mit Live-Sync.
- Keine Freigabe → Draft im manuellen Modus. Optional kann ich dann ein kleines Browser-Skript bauen, das den Yahoo-Draftraum auf deinem PC mitliest. Das ist eine Grauzone (es schickt aber keine zusätzlichen Anfragen an Yahoo), und du müsstest mir beim Testen in einem Yahoo-Mock-Draft helfen. Das entscheidest du.

**Generalprobe (bis Sa 17.10.):** ein Yahoo-Mock-Draft am PC mit dem Assistenten daneben.

**Mo 19.10., 21:00 Uhr: Draft.** Eine Checkliste für den Abend kommt ins README.

### Phase 3: Dashboard, Spielplan, Aufstellung, Waiver · Ziel: So 25.10. (erste Matchup-Woche)
- **Team-Dashboard:**
  - Kader mit Verletzungsstatus
  - Aktuelles Matchup mit Prognose pro Kategorie (gewinnt / verliert / knapp), per Simulation aus Projektionen und restlichen Spielen
  - Restliche Spiele diese Woche: deine Spieler vs. Gegner
- **Spielplan-Übersicht:** Spiele pro NBA-Team und Fantasy-Woche
- **Tägliche Aufstellung:**
  - Optimale Aufstellung pro Tag: wer spielt, wer ist verletzt oder fraglich, maximale Einsätze
  - Nachprüfung vor dem ersten Spiel des Tages (späte Absagen)
  - Weil Yahoo keinen Schreibzugriff gibt: Empfehlung mit Direktlink. Automatisch setzen nur, falls Yahoo das je erlaubt. Dann abschaltbar und im Dry-Run standardmäßig an.
- **Waiver und Streaming:**
  - Free Agents nach Kategorien-Bedarf und Spielen in der Restwoche bewertet
  - Wechsel-Limits der Liga werden beachtet
  - Konkrete Vorschläge „Nimm X, entlass Y“
- **Aktionsprotokoll:** jeder Vorschlag und jede Aktion mit was, wann und warum

### Phase 4: Telegram + Server (24/7) · Ziel: So 01.11.
**Abweichung von deiner Reihenfolge:** Telegram und Server ziehe ich vor die Trades. Aufstellungs-Hinweise und Verletzungs-Alarme bringen nur etwas, wenn das System rund um die Uhr läuft und dich erreicht. In den ersten Wochen sind sie wichtiger als Trade-Analysen.

- **Telegram-Bot:**
  - Tägliches Briefing morgens (deutsche Zeit): Matchup-Stand, heutige Aufstellung, wichtige News
  - Verletzungs-Alarm mit Ersatzvorschlag
  - Buttons „In Yahoo öffnen“ / „Erledigt“ / „Ablehnen“
  - Ruhezeiten (nachts keine Pings außer bei echten Alarmen, einstellbar)
- Server: Entscheidung Hetzner vs. kostenlos, Einrichtung per Docker Compose, Tailscale fürs Handy, automatische Datensicherung

### Phase 5: Trades + Liga-Beobachtung · Ziel: So 08.11.
- **Trade-Analyse:**
  - Eingehende Angebote bewerten, nach Auswirkung auf deine Kategorien und deine Siegchancen pro Woche
  - Trade-Finder: Teams, deren Stärken deine Schwächen ergänzen und umgekehrt, damit Vorschläge für beide Seiten realistisch sind
- **Liga-Beobachtung:** Transaktionen und Trades der anderen Teams, Meldung per Telegram, wenn es dich betrifft (z. B. dein Gegner diese Woche streamt massiv)

### Phase 6: Schwarzes Brett, KI-Texte, Extras · Ziel: So 15.11.
- **News:**
  - Mehrere RSS-Quellen und der Injury Report, Duplikate zusammengefasst
  - Sortiert: deine Spieler > Gegner der Woche > interessante Free Agents > Top-News
  - Kurze KI-Zusammenfassung, alle Meldungen gebündelt in einer Anfrage
- **Playoff-Planer:** welche Spieler in den Playoff-Wochen viele Spiele haben
- **Wöchentlicher Liga-Recap mit Humor** zum Posten in eurer Gruppe
- README vervollständigen: Installation, Yahoo, Telegram, Start, häufige Probleme

**Nach jeder Phase:** Tests laufen lassen, Git-Commit, und du bekommst 3–5 Sätze: was jetzt geht und was du ausprobieren sollst.

---

## 5. Sicherheitsregeln (umgesetzt in der Architektur)
- Alle Aktionen an Yahoo laufen durch **eine einzige Stelle im Code** (`actions/executor.py`). Die prüft:
  - Dry-Run an? Dann wird nur simuliert.
  - Liegt deine Bestätigung vor? Gilt für Waiver, Drop und Trade immer.
  - Ist die automatische Aufstellung eingeschaltet?
- Die Stelle protokolliert jede Aktion.
- **Dry-Run ist standardmäßig AN** (`DRY_RUN=true` in `.env`).
- Zugangsdaten nur in `.env`. Die Datei ist per `.gitignore` ausgeschlossen, und `.env.example` erklärt jeden Eintrag.
- Rate-Limits und Cache pro Datenquelle, bei Fehlern automatisch langsamer.

## 6. Grober Aufbau
```
fantasy/            Python-Paket
  config.py         Einstellungen aus .env
  timeutil.py       Zeitzonen (intern US-Eastern, Anzeige Europe/Berlin)
  db.py             SQLite
  sources/          Datenquellen (Basketball-Reference, Hashtag, nba.com, RSS …), je mit Cache + Rate-Limit
  yahoo/            OAuth, lesender Client, Auswertung der Antworten
  engine/           Projektionen, Z-Scores, Draft, Aufstellung, Waiver, Matchup, Trades
  actions/          Executor (Dry-Run, Bestätigung, Protokoll)
  notify/           Telegram
  ai/               KI-Texte (mit Cache und Budget)
  jobs/             Zeitgesteuerte Jobs (APScheduler)
  web/              Oberfläche (FastAPI, Jinja2, HTMX)
data/snapshots/     gespeicherte Rohdaten (Stats, ADP, Rookies)
tests/
```
