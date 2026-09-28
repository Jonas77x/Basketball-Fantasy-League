# Fantasy-Basketball-Assistent

Dein persönlicher Assistent für deine Yahoo-Fantasy-Basketball-Liga (Head-to-Head nach Kategorien).

**Stand: Phase 1 – Draft-Assistent.** Was als Nächstes kommt, steht in [`PLAN.md`](PLAN.md).

| Was geht schon? | Was kommt später? |
|---|---|
| Draft-Assistent mit Empfehlungen, Begründungen, Punt-Vorschlägen und Prognose, wer bis zu deinem Pick weg ist | Live-Mitlesen des Yahoo-Drafts (sobald Yahoo den API-Zugang freigibt) |
| Übungs-Draft gegen simulierte Gegner | Team-Dashboard, Aufstellung, Waiver, Trades, News, Telegram |
| Optional: „KI um Rat fragen“ | Server, damit alles rund um die Uhr läuft |

---

## Inhalt
1. [Installation auf Windows (einmalig, ca. 15 Minuten)](#1-installation-auf-windows)
2. [Starten](#2-starten)
3. [So benutzt du den Draft-Assistenten](#3-so-benutzt-du-den-draft-assistenten)
4. [Checkliste für den Draft-Abend (Mo 19.10., 21:00 Uhr)](#4-checkliste-für-den-draft-abend)
5. [Daten aktualisieren](#5-daten-aktualisieren)
6. [KI einrichten (optional)](#6-ki-einrichten-optional)
7. [Updates holen](#7-updates-holen)
8. [Häufige Probleme](#8-häufige-probleme)
9. [Yahoo-API-Zugang](#9-yahoo-api-zugang)

---

## 1. Installation auf Windows

Du brauchst zwei Programme: **GitHub Desktop** (holt den Code auf deinen PC) und **uv** (kümmert sich um Python, du musst Python nicht selbst installieren).

### Schritt 1: Code herunterladen mit GitHub Desktop
1. Lade GitHub Desktop herunter: https://desktop.github.com und installiere es.
2. Starte GitHub Desktop und melde dich mit deinem GitHub-Konto an (**Sign in to GitHub.com**).
3. Klick auf **File → Clone repository …**.
4. Wähle in der Liste **Jonas77x/Basketball-Fantasy-League** aus.
5. Bei **Local path** kannst du den vorgeschlagenen Ordner lassen (z. B. `C:\Users\<Name>\Documents\GitHub\Basketball-Fantasy-League`). Merk dir den Ordner.
6. Klick auf **Clone**.
7. Oben in der Mitte steht **Current branch**. Klick darauf und wähle den Branch **`claude/busy-cannon-83xyc7`**. Dort liegt der aktuelle Stand.

### Schritt 2: uv installieren
1. Drück die **Windows-Taste**, tipp **PowerShell** und öffne **Windows PowerShell**.
2. Kopier diese Zeile hinein und drück Enter:
   ```
   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
   ```
3. Warte, bis „uv installed“ oder etwas Ähnliches erscheint.
4. **Schließ das PowerShell-Fenster.** Wichtig, damit Windows das neue Programm findet.

Das war's mit der Installation.

## 2. Starten
1. Öffne im Explorer den Projektordner aus Schritt 1.
2. Doppelklick auf **`start.bat`**.
3. Beim allerersten Start lädt uv Python und alle Bausteine herunter. Das dauert 1–2 Minuten. Danach geht es in wenigen Sekunden.
4. Dein Browser öffnet sich automatisch mit **http://localhost:8000**. Falls nicht, tipp die Adresse selbst ein.
5. **Beenden:** das schwarze Fenster schließen oder dort **Strg+C** drücken.

> Windows fragt beim ersten Start eventuell nach der Firewall. „Abbrechen“ ist okay, solange du nur an diesem PC arbeitest.

## 3. So benutzt du den Draft-Assistenten

### Einstellungen
Oben unter **Liga-Einstellungen** trägst du ein:
- Anzahl Teams, deine Draft-Position und die Zahl der Runden. Deine Draft-Position legt Yahoo meist kurz vor dem Draft fest.
- Optional die Team-Namen in Draft-Reihenfolge. Dann steht im Verlauf „Team von Max“ statt „Team 4“.

Mit dem Yahoo-API-Zugang (Phase 2) werden diese Werte später automatisch aus deiner Liga gelesen.

### Picks eintragen (Schnelleingabe)
- Tipp ein paar Buchstaben eines Namens in **Pick eintragen**, zum Beispiel „joki“, und drück **Enter**.
  - Der Pick wird automatisch dem Team zugeordnet, das gerade dran ist. Die Reihenfolge berechnet der Assistent selbst (Snake-Draft).
  - Mit den Pfeiltasten ↑/↓ wählst du einen anderen Treffer aus der Liste.
  - Die wahrscheinlichsten Picks stehen oben.
- **Spieler nicht in der Liste?** Einfach den ganzen Namen tippen und „… als Pick eintragen“ wählen. Dann stimmt die Zählung trotzdem.
- **Vertippt?** Oben rechts auf **Letzten Pick zurücknehmen** klicken.

### Was dir angezeigt wird

**Empfehlungen**
- Wenn du dran bist: die drei besten Optionen mit Begründung.
- Der Assistent rechnet mit, wer bis zu deinem *nächsten* Pick wahrscheinlich weg ist. Beispiel: „Kommt nicht zurück“ oder „ist mit 90 % noch da, kein Zeitdruck“.
- Wenn du nicht dran bist: eine Prognose, wer bei deinem Pick voraussichtlich noch verfügbar ist.

**Dein Team**
- Kader und Kategorien-Profil.
- Deine Chance, eine Woche gegen ein Durchschnittsteam zu gewinnen.

**Punt-Vorschläge**
- Ab Runde 3 schlägt der Assistent vor, eine Kategorie bewusst zu opfern, wenn sich das für dich lohnt.
- Ein Klick auf **Übernehmen** passt alle Empfehlungen daran an.
- Du kannst Kategorien auch selbst antippen, um sie zu opfern oder wieder zu aktivieren.

**Spielerpool**
- Alle verfügbaren Spieler mit Prognose pro Spiel für 2026-27.
- Farbig: grün = stark, rot = schwach.
- Filter nach Position, Suche und Sortierung.

**Was die Zahlen bedeuten**
- **Wert** = Summe der Z-Werte über deine Kategorien. Grob gesagt: wie viel besser als ein durchschnittlicher Draft-Spieler.
- **Fit** = derselbe Wert, aber angepasst an die Baustellen deines Teams.
- **ADP** = durchschnittliche Draft-Position bei Yahoo.

### Übungs-Draft
Oben im Menü auf **Übungs-Draft**. Die anderen Teams picken dort automatisch nach der echten Yahoo-ADP, mit etwas Zufall. So kannst du verschiedene Strategien ausprobieren, zum Beispiel Punt FT% mit Giannis. Dein echter Draft bleibt davon unberührt.

### Handy im selben WLAN (optional)
1. In der Datei `.env` die Zeile `HOST=127.0.0.1` auf `HOST=0.0.0.0` ändern und neu starten.
2. Am Handy `http://<IP-deines-PCs>:8000` öffnen.
3. Die IP findest du so: in PowerShell `ipconfig` eingeben und nach „IPv4-Adresse“ schauen, z. B. 192.168.178.23.
4. Bei der Windows-Firewall-Frage dann **Zulassen** (nur „Private Netzwerke“) wählen.

## 4. Checkliste für den Draft-Abend
Mo 19.10., 21:00 Uhr (in New York 15:00 Uhr).

- [ ] **Am Nachmittag:** Doppelklick auf `daten-aktualisieren.bat` (holt die neueste Yahoo-ADP).
- [ ] **Updates holen:** siehe Abschnitt 7, falls ich noch etwas verbessert habe.
- [ ] **20:45 Uhr:**
  1. `start.bat` starten.
  2. In den Liga-Einstellungen Teams, Draft-Position und Runden prüfen.
  3. Falls im echten Draft schon Test-Picks stehen: **Draft zurücksetzen**.
- [ ] **Fenster nebeneinander:** links der Yahoo-Draftraum, rechts der Assistent (Windows-Taste + ← / →).
- [ ] **Während des Drafts:** jeden Pick der anderen kurz per Schnelleingabe eintragen (2–3 Buchstaben + Enter).
  - Bist du dran, stehen oben deine drei besten Optionen.
  - Ab Phase 2 passiert das Eintragen automatisch, sobald Yahoo den API-Zugang freigibt.
- [ ] **Tipp:** Stell in Yahoo deine Draft-Queue zusätzlich mit ein paar Wunschspielern voll, als Sicherheitsnetz, falls der PC hängt.

## 5. Daten aktualisieren
Doppelklick auf **`daten-aktualisieren.bat`**. Das holt:
- Stats der letzten drei Saisons und die Rookies 2026 von Basketball-Reference
- die aktuelle Yahoo-ADP und Yahoo-Positionen von Hashtag Basketball

Danach den Assistenten neu starten. Die Quellen werden höflich abgefragt (mit Pausen und Zwischenspeicher), also bitte nicht öfter als einmal am Tag.

Verletzungen und Rollen, die in keiner Statistik stehen (z. B. „fällt bis März aus“), pflege ich in der Datei `data/manual/adjustments_2026_27.toml`. Wenn dir eine wichtige News auffällt, sag mir Bescheid.

## 6. KI einrichten (optional)
Der Knopf **KI um Rat fragen** holt eine zweite Meinung von Claude (Modell Sonnet 5). Das kostet pro Frage etwa 1 US-Cent. Ohne Schlüssel funktioniert alles andere genauso.

1. Geh auf https://console.anthropic.com und leg ein Konto an.
2. Unter **Billing** Guthaben aufladen. Das Minimum sind 5 $, das reicht für viele Monate.
3. Unter **API Keys** auf **Create Key** klicken und den Schlüssel kopieren. Er beginnt mit `sk-ant-`.
4. Öffne im Projektordner die Datei **`.env`** mit dem Editor: Rechtsklick → Öffnen mit → Editor.
5. Trag den Schlüssel hinter `ANTHROPIC_API_KEY=` ein, ohne Leerzeichen, und speichere die Datei.
6. Starte den Assistenten neu.

Das Tagesbudget ist auf 0,50 $ begrenzt (`AI_DAILY_BUDGET_USD` in der `.env`). Gleiche Fragen werden aus dem Zwischenspeicher beantwortet und kosten nichts.

## 7. Updates holen
Wenn ich etwas Neues gebaut habe:
1. Schwarzes Fenster schließen, falls der Assistent läuft.
2. In GitHub Desktop auf **Fetch origin** und dann auf **Pull origin** klicken.
3. `start.bat` neu starten.

Deine Einstellungen (`.env`) und deine Draft-Daten (Ordner `var`) bleiben dabei erhalten.

## 8. Häufige Probleme

**„uv ist noch nicht installiert“**
Schritt 2 wiederholen und danach **alle** PowerShell- bzw. Eingabeaufforderungs-Fenster schließen. Hilft das nicht, den PC einmal neu starten.

**Browser zeigt „Seite nicht erreichbar“**
Läuft das schwarze Fenster noch? Steht dort ein Fehler? Beim ersten Start einfach 1–2 Minuten warten und die Seite neu laden (F5).

**„Address already in use“ / Port 8000 belegt**
Der Assistent läuft wahrscheinlich schon in einem anderen Fenster. Alternativ in der `.env` `PORT=8001` eintragen und `http://localhost:8001` öffnen.

**Ein Spieler fehlt in der Liste**
Über die Schnelleingabe den ganzen Namen tippen und „… als Pick eintragen“ wählen. Oder `daten-aktualisieren.bat` ausführen.

**Die KI antwortet nicht**
Die Meldung unter dem Knopf erklärt den Grund: Schlüssel fehlt, Guthaben leer oder Tagesbudget erreicht.

**Ich habe mich im Draft verklickt**
**Letzten Pick zurücknehmen** (oben rechts), so oft wie nötig.

## 9. Yahoo-API-Zugang
Yahoo gibt seine Schnittstelle seit 2026 nur noch nach Antrag frei, und derzeit nur zum Lesen. Die Anleitung mit fertigen Texten steht in [`docs/YAHOO_ANTRAG.md`](docs/YAHOO_ANTRAG.md). Sobald die Freigabe da ist, baue ich das automatische Mitlesen ein (Phase 2).

---

*Datenquellen: Basketball-Reference (Statistiken, Draft 2026), Hashtag Basketball (Yahoo-ADP, Positionen). Nur für den privaten Gebrauch.*
