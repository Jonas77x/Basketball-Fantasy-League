# CLAUDE.md – Projektregeln

Persönlicher Fantasy-Basketball-Assistent für Jonas (Yahoo, private H2H-Kategorien-Liga, eine Liga, keine Keeper).
Jonas programmiert nicht. Claude plant, baut, testet und deployt. Der Plan steht in `PLAN.md`.

## Kommunikation
- Mit Jonas Deutsch, locker, ohne Fachjargon. Wenn er etwas selbst tun muss, gibt es eine Schritt-für-Schritt-Anleitung für Einsteiger.
- Oberflächen-Texte, Telegram-Nachrichten und Doku (README, PLAN) auf Deutsch. Code, Bezeichner und Code-Kommentare auf Englisch.
- Nach jeder Phase: Tests grün, Commit, dann 3–5 Sätze an Jonas, was geht und was er ausprobieren soll.
- Geht etwas technisch nicht, direkt sagen und die beste Alternative vorschlagen.

## Sicherheitsregeln (nicht verhandelbar)
1. Waiver-Moves, Drops und Trades **nie** ohne ausdrückliche Bestätigung von Jonas ausführen. Nur die tägliche Aufstellung darf automatisch laufen, und das muss per Einstellung abschaltbar sein (`AUTO_LINEUP`).
2. **Dry-Run ist standardmäßig an** (`DRY_RUN=true`). Im Dry-Run wird nichts an Yahoo gesendet, nur simuliert und protokolliert.
3. Jede Aktion an Yahoo (auch simuliert) wird im Aktionsprotokoll gespeichert: was, wann (UTC), warum, Ergebnis.
4. Alle Yahoo-Aktionen laufen ausschließlich über `fantasy/actions/executor.py`. Kein anderer Code darf schreibende Yahoo-Requests absetzen.
5. Zugangsdaten nur in `.env` (steht in `.gitignore`). Neue Einstellungen immer mit Erklärung in `.env.example` eintragen. Keine Secrets in Logs, Tests, Commits oder KI-Prompts.
6. Rate-Limits respektieren und cachen, siehe unten.

## Yahoo-API (Stand 09/2026)
- Zugang nur nach manueller Freigabe durch Yahoo. **Aktuell nur Lesezugriff.** Schreibzugriff wird nicht vergeben.
- Nur Endpunkte aus der offiziellen Doku verwenden: https://sports.yahoo.com/developer/docs/ . Keine Endpunkte raten. Die Quelle jedes Endpunkts steht als Kommentar am Code.
- Alle Requests laufen über den zentralen Client in `fantasy/yahoo/` (Cache, Rate-Limit, Backoff bei 429/999, Logging).
- Richtwerte: normal ≤ 1 Request/s mit Cache-TTL je Ressource. Live-Draft: adaptiv alle 3–10 s.
- Bei 403 „not authorized“ ist die App nicht freigegeben oder der Token hat alte Scopes. Lösung: neu verbinden (erneute Zustimmung), nicht nur den Token erneuern.
- Pflicht-Hinweis in der Oberfläche: „Fantasy data provided by Yahoo Fantasy“ mit Link zu Yahoo Fantasy.

## Zeitzonen
- Zeitpunkte in der DB immer in UTC speichern.
- Der NBA-Spieltag und der Yahoo-Roster-Tag ist das **Datum in `America/New_York`**.
- Anzeige für Jonas immer in `Europe/Berlin`.
- Nur `zoneinfo` verwenden, **niemals feste Offsets**. Zwischen 25.10. und 01.11. beträgt der Unterschied Berlin–New York nur 5 statt 6 Stunden.

## Datenquellen und Rate-Limits
| Quelle | Wofür | Regel |
|---|---|---|
| Basketball-Reference | Stats, Spielplan, Draft 2026 | max. 1 Request / 4 s, Cache ≥ 12 h, Rohdaten als Snapshot in `data/snapshots/` |
| Hashtag Basketball | Yahoo-ADP, Yahoo-Positionen | max. 1×/Tag |
| nba.com / ESPN | Spielplan, Scores, Verletzungen | nur optional, blockt Server-IPs, immer Fallback haben |
| RSS-Feeds | News | alle 15–30 min, Duplikate zusammenführen |
| Anthropic | Begründungen, News, Recap | Antworten in der DB cachen, Tagesbudget, Modell per `.env` (Standard `claude-sonnet-5`) |

## Entwicklung
- Python 3.12, Paketverwaltung mit `uv`.
- Starten: `uv run fantasy` (Windows: `start.bat`). Server: `docker compose up -d`.
- Tests: `uv run pytest`. Lint: `uv run ruff check .`. Beides muss vor jedem Commit grün sein.
- Tests greifen **nie** aufs Netz zu, sondern nutzen gespeicherte Beispiel-Antworten in `tests/fixtures/`.
- Neue Logik (Projektionen, Draft, Aufstellung, Waiver, Trades) bekommt immer Tests.
- Arbeiten auf dem vorgegebenen Feature-Branch. Commits mit klaren Nachrichten. Nie `.env`, Tokens oder die SQLite-DB committen.
- Die ursprüngliche `Fantasy Draft-Assistent.html` bleibt als Referenz im Repo.
