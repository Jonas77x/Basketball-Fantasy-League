# Yahoo-API-Zugang beantragen (ca. 20 Minuten)

**Warum jetzt?** Seit Sommer 2026 prüft Yahoo jeden API-Antrag von Hand, und das dauert erfahrungsgemäß 1–2 Wochen, manchmal länger. Nur mit Freigabe kann das System deinen Live-Draft am 19.10. automatisch mitlesen und später deinen Kader und deine Matchups anzeigen. Ohne Freigabe funktioniert der Draft-Assistent trotzdem, dann trägst du die Picks per Schnelleingabe selbst ein.

> Wichtig: Das **Client Secret** (ein geheimer Schlüssel, den du in Schritt 1 bekommst) schickst du mir **nie** im Chat. Es kommt später nur in die Datei `.env` auf deinem Rechner. Die **Client ID** ist nicht geheim.

---

## Schritt 1: Liga-ID herausfinden (1 Minute)
1. Öffne im Browser am PC https://basketball.fantasysports.yahoo.com und melde dich mit deinem Yahoo-Konto an.
2. Klick auf deine Liga.
3. Schau in die Adresszeile. Dort steht etwas wie `basketball.fantasysports.yahoo.com/nba/12345`. Die Zahl hinter `/nba/` ist deine **Liga-ID**. Notier sie dir.

## Schritt 2: Yahoo-Entwickler-App anlegen (5 Minuten)
1. Öffne https://developer.yahoo.com/apps/create/ und melde dich mit **demselben Yahoo-Konto** an, mit dem du in der Liga spielst.
2. Fülle das Formular so aus. Falls ein Feld leicht anders heißt, nimm das passendste:

   | Feld | Was du einträgst |
   |---|---|
   | Application Name | `Fantasy Assistent Jonas` |
   | Description | `Private fantasy basketball assistant for my own league` |
   | Homepage URL | `https://github.com/jonas77x/basketball-fantasy-league` |
   | Redirect URI(s) | `https://localhost:8000/auth/callback` |
   | OAuth Client Type | **Confidential Client** |
   | API Permissions | Wenn **Fantasy Sports** angeboten wird: **Read** anhaken (oder **Read/Write**, falls es das gibt). Wenn es Fantasy Sports **nicht** gibt, ist das seit 2026 normal. Hake dann nur **OpenID Connect Permissions → Profile** an, falls mindestens eine Auswahl nötig ist. |

3. Klick auf **Create App**.
4. Du siehst jetzt **Client ID** und **Client Secret**:
   - Kopier dir beide in eine Notiz auf deinem PC.
   - Die **Client ID** brauchst du gleich in Schritt 3.
   - Das Secret bleibt geheim.

## Schritt 3: Zugang bei Yahoo beantragen (10 Minuten)
1. Öffne https://sports.yahoo.com/developer/access/
2. Fülle das Formular aus. Die englischen Texte kannst du 1:1 kopieren. Ersetze nur die Teile in `[eckigen Klammern]`.

| Feld | Eintrag |
|---|---|
| Name | dein Name |
| Business Title | `Individual hobby developer (no company)` |
| Email Address | deine E-Mail (die, die du regelmäßig liest) |
| Phone Number | deine Handynummer mit `+49` vorne |
| Business Name & Address | `Private individual, no business – [deine Stadt], Germany` |
| Consumer-Facing Product or App Name | `Personal Fantasy Basketball Assistant (private, single league)` |
| Brief Company Description | `No company. Private, non-commercial hobby project by a single Yahoo Fantasy Basketball player.` |
| Website URL or App Store Details | `https://github.com/jonas77x/basketball-fantasy-league` |
| Expected Users | **Small (< 1,000 users)** |
| Client ID | die Client ID aus Schritt 2 |

**Describe Your Intended Use Case** (Text kopieren, Liga-ID ist schon eingesetzt):

```
Private, non-commercial tool used only by me (1 user) for my own Yahoo Fantasy Basketball league (one private league, league ID 60530, 2026-27 season, head-to-head categories). It runs on my own PC and later on a small private server; nobody else has access. Data needed (read only): my league's settings (stat categories, roster positions, transaction limits, playoff weeks, waiver rules), the draft results during our live draft on October 19, 2026 (to show draft recommendations next to the Yahoo draft room), team rosters, weekly matchups and scoreboard, standings, league transactions, and player info, status, ownership and stats. Purpose: draft recommendations, daily lineup suggestions, waiver/streaming suggestions and trade analysis for my own team. No data is resold, published or shared. Expected volume: a few hundred requests per day with caching; during the roughly 2-hour live draft about one request every 5 seconds. Attribution "Fantasy data provided by Yahoo Fantasy" is shown in the app.
```

**Additional Notes** (Text kopieren):

```
Personal single-league use only (1 user). If possible I would like read/write access to set my own daily lineup. Any other write action (add/drop, trades) would only be executed after my explicit manual confirmation, at most a few write calls per day. Read-only access is perfectly fine if write access is not available.
```

3. Klick auf **Submit Application**.

## Schritt 4: Danach
- Schau in den nächsten Tagen in dein E-Mail-Postfach, **auch in den Spam-Ordner**. Yahoo schickt eventuell einen Bestätigungslink oder Rückfragen. Bestätigen und kurz antworten.
- Sag mir Bescheid, wenn:
  1. du den Antrag abgeschickt hast und
  2. Yahoo geantwortet hat (egal ob Ja oder Nein).
- Bis dahin baue ich alles so, dass es mit und ohne Freigabe funktioniert.
