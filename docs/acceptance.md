# Abnahmeprotokoll DESIGN STUDIO AI

## Aktueller Prüfstand der vorbereiteten Hetzner-Aktivierung

Für die aktuelle Live-Aktivierung und vom Betreiber beziehungsweise Nutzer ausgelöste Generierungen gilt ein Projektgesamtrahmen von **25 USD**. Davon getrennt bleibt die ursprüngliche Freigabe von **höchstens 5 USD für den autonomen Abnahmelauf** bestehen; sie wurde nicht auf 25 USD erweitert. Die Live-Aktivierung autorisiert keinen unbeaufsichtigten 25-USD-PoC. Für die vorbereitete Hetzner-Aktivierung wird der serverseitige Höchstbetrag auf **2480 US-Cent** begrenzt; die **20 Cent konservative unbekannte Cloud-Exposition** bleiben gesondert erhalten. Sie werden weder gelöscht noch als tatsächliche Rechnung ausgegeben oder zusätzlich auf den neuen Server-Spend gebucht. Der kombinierte konservative Rahmen beträgt damit höchstens 2500 Cent.

Laut Betreiberstatus ist die geschützte HTTPS-Anwendung bereitgestellt; die Generierung ist noch geschlossen. Das Aktivierungsartefakt wird unabhängig ausschließlich lokal/lesend geprüft, ohne Remotezugriff oder Anbieteraufruf durch QA. Ein nicht bildgenerierender Authentifizierungstest ersetzt keinen echten Bildnachweis. **Weiterhin 0/15 reale Produktbilder; keine Produktionsabnahme.** Details und endgültige Artefaktnachweise folgen unten. Die folgenden Abschnitte zum ersten Cloudlauf bleiben historische Evidenz.

## Aktualisierung nach Veröffentlichung am 19. Oktober 2026

Die veröffentlichte Umgebung meldet für `STUDIO_OPENAI_API_KEY` und `TURNSTILE_SECRET` jeweils eine gespeicherte Bindung ohne Konfigurationsfehler. Beide Variablen sind in der Cloud vorhanden; ihre Werte wurden nicht ausgegeben. Die Anwendungscontainer wurden mit den bereitgestellten Bindungen neu erstellt. Ein authentifizierter, nicht bildgenerierender Abruf von OpenAI `/v1/models` ergab HTTP 200 und listete `gpt-4.1-mini` sowie `gpt-image-1.5`. Die bisherige OpenAI-Proxy-Sperre ist damit für diesen Abruf aufgehoben. Turnstile `/siteverify` antwortete auf einen bewusst ungültigen Testtoken mit HTTP 200 und `invalid-input-response`; dies ist kein Nachweis einer erfolgreich gelösten realen Browser-Challenge.

Die nachstehenden Aussagen über fehlende Schlüssel oder CONNECT 403 beschreiben den früheren Prüfstand. Aktuell bleiben echte Bildgenerierung, die Budgetfeasibilität des vollständigen 15-Bilder-Laufs, eine reale Turnstile-Challenge auf erlaubter Domain und die übrigen Produkt-/Betriebsgates ungeprüft. Der Generierungs-Kill-Switch bleibt aktiv. Zwei tatsächliche Briefingaufrufe sind inzwischen fehlgeschlagen: zuerst Transportfehler, danach HTTP401 invalid_api_key. Gesamt 20 US-Cent konservativ verbuchte Obergrenze, tatsächliche Kosten unbekannt, 0 Bilder. Der unten protokollierte Fehlversuch ersetzt die früheren Null-Aufruf-Aussagen als aktuellen Stand.

Stand: 18. Oktober 2026. Grundlage: `docs/ausfuehrungsregeln.md`.

**Öffentliche Produktionsfreigabe: BLOCKED.** Dieses Dokument ist eine prüfbare Gate-Matrix, keine Zusicherung der Produktionsreife. Ein lokaler Start, erfolgreiche Tests oder Implementierungsumfang ersetzen keine realen Bildresultate und keine fachliche Abnahme. PASS wird nur mit konkreter Evidenz vergeben. BLOCKED umfasst fehlende Nachweise; es behauptet keinen nachgewiesenen Defekt.

## Reale Produktabnahme

| Gate | Erforderlicher Nachweis | Status / Evidenz |
| --- | --- | --- |
| Textpfad | Ein Satz ohne Pflichtfragen; drei echte, sichtbar unterschiedliche Küchenbilder im selben Beispielraum; gemeinsames versioniertes Briefing vor Anbieteraufrufen | BLOCKED – initialer Textlauf freigegeben; erstes echtes Briefing transportseitig fehlgeschlagen, noch keine Bildresultate |
| Progressive Resultate | Einzelne fertige Bilder erscheinen sofort; ein fehlgeschlagenes Konzept blockiert andere nicht | BLOCKED – echte Browserprüfung mit realen Bildjobs fehlt |
| Konzepte | A Ergonomie/Laufwege, B Licht/Raumwirkung, C Stauraum/Ordnung; keine bloßen Farbvarianten | BLOCKED – menschliche Prüfung echter Bilder erforderlich |
| Kuratierung | Genau drei bildgeprüfte Zeilen je Konzept: Architektur, Highlight, Materialharmonie | BLOCKED – reale Bild-/Textprüfung fehlt |
| Materialänderung | Aus ursprünglichem A; Raum und Möbelanordnung bleiben Zielvorgabe | BLOCKED – echte Änderung und Sichtprüfung fehlen |
| Aufbauänderung | Unabhängig aus ursprünglichem A; nur gewähltes Konzeptprofil ändert sich | BLOCKED – echte Änderung und Sichtprüfung fehlen |
| Revisionen | Unveränderliche Historie, Auswahl und Rollback ohne neuen Bildauftrag; globale Raumkorrektur versioniert und ältere Basis gekennzeichnet | TEILNACHWEIS – lokale Prüfungen unten; reale Produktabnahme bleibt BLOCKED |
| Foto | Geeignetes Foto: Qualitätsprüfung, getrennte Provenienz, gemeinsame Raumversion, drei echte Resultate | BLOCKED – geeignete Testvorlage, echte Bilder und fachliche Prüfung fehlen |
| Grundriss | Geeigneter Grundriss: eigene Analyse, Qualitätsprüfung, gemeinsame Raumversion, drei echte Resultate | BLOCKED – geeignete Testvorlage, echte Bilder und fachliche Prüfung fehlen |
| Ungeeignete Medien | Unleserliche/nicht geeignete Medien stoppen vor Bildkosten; neue Eingabe oder Beispielraum möglich | TEILNACHWEIS – fehlgeschlagener Start erlaubt begrenzte Neueingabe; echte semantische Qualitätsprüfung BLOCKED |
| Raumtreue | Fenster, Türen, Wände, Proportionen, Durchgänge und Blickrichtung manuell zur Vorlage prüfen; kritische Fehler einzeln dokumentieren | BLOCKED – menschliche Fachabnahme echter Vorlagen/Ergebnisse fehlt |
| Ehrlichkeit | Beispielraum bzw. sichtbare Raummerkmale kenntlich; keine garantierte Maß-/Technik-/Hersteller-/Bildtreue, erfundenen Scores oder heruntergespielten Raumfehler | TEILNACHWEIS – ehrliche Sperr- und Quellenhinweise lokal geprüft; echte Bild-/Inhaltsabnahme BLOCKED |
| 15-Bilder-PoC | Text, Foto und Grundriss jeweils A/B/C + Material- + Aufbauänderung aus ursprünglichem A; tatsächliche Kosten und Laufzeit je Versuch samt Fehlversuchen | BLOCKED – 0 von 15 realen Bildern; Live-Projektgesamtrahmen 25 USD, geplantes Serverlimit 2480 Cent plus erhaltene 20 Cent externe Cloud-Exposition; separates autonomes Abnahmelaufbudget weiterhin höchstens 5 USD; Zugangsdaten vorhanden; Screenshot belegt aktives 25-USD-Limit im gezeigten Projekt; Zuordnung zum Projekt Design-Studio-AI inzwischen durch Auftraggeber bestätigt; sichere Preisobergrenzen und echte Challenge auf erlaubter Domain vor kostenpflichtigem Lauf prüfen; zwei tatsächliche Briefingversuche fehlgeschlagen: 20 Cent konservative Gesamtobergrenze, tatsächliche Kosten unbekannt; noch keine Bildgenerierung |

Automatische Bildbewertung darf ausschließlich im Shadow-Modus laufen. Die fachliche Raumprüfung bleibt menschlich. Ein technischer Simulator kann Sicherheits- und Zustandslogik prüfen, erfüllt aber kein Bild- oder Produktgate.

## Sicherheit, Betrieb und Datenschutz

| Gate | Erforderlicher Nachweis | Status / Evidenz |
| --- | --- | --- |
| Keine Kundenschranke | Drei Startbilder, fünf erfolgreiche Änderungen, Ansicht, Rollback und unbegrenzte Downloads ohne Registrierung/Kontaktdaten/Kosten | TEILNACHWEIS – lokale Quoten-/Browserprüfung vorhanden; echter Nutzermehrwert bleibt BLOCKED |
| Änderungsguthaben | Nur erfolgreiche Änderungen verbrauchen Guthaben; nach Ausschöpfung bleiben vorhandene Resultate verfügbar | TEILNACHWEIS – lokale Prüfungen unten; reale Produktabnahme bleibt BLOCKED |
| Bot-Schutz | Serverseitig validierte Challenge, Session-/Quotenlimits ohne invasives Fingerprinting oder Kontaktzwang | TEILNACHWEIS – Missing-Secret-Failclosed im isolierten Test bestätigt; Secret inzwischen vorhanden; 20 parallele Admissionrequests geprüft; echte Challenge/Produktionslast BLOCKED |
| Idempotenz und Parallelität | Wiederholte Requests erzeugen keine doppelten kostenpflichtigen Aufrufe; serverseitig begrenzte Parallelität | TEILNACHWEIS – unabhängige Handoff-Idempotenz und parallele Sessionadmission PASS; bezahlte Jobs nur kontrollierte Fachagententests |
| Budgetreservierung | Konservative atomare Reservierung vor jedem Anbieteraufruf; Tenant- und Globalstopp berücksichtigen laufende Jobs | TEILNACHWEIS – Fachagent: 10 parallele Reservierungen lassen bei 500 Cent exakt fünf zu; unabhängige Crashreservierung PASS; echte Preisobergrenzen BLOCKED |
| Kostenrechnung und Retry | Tatsächliche Kosten inkl. Fehler dokumentiert; höchstens ein technischer Retry je Bild innerhalb reservierter Mittel | TEILNACHWEIS – unabhängiger Rechnungsausgleich PASS mit synthetischen Belegen; echte Abrechnung BLOCKED |
| Anbieterfreigabe | Projektspezifischer Schlüssel serverseitig; aktiviertes echtes 25-USD-Hard-Limit im richtigen Projekt geprüft, separat kleinerer Laufrahmen freigegeben | AKTIVIERUNG IN PRÜFUNG – Live-Projektrahmen 25 USD; separates autonomes Abnahmelaufbudget höchstens 5 USD; Serverlimit 2480 Cent plus 20 Cent konservative externe Exposition; Zugangsdaten vorhanden; Projektbindung durch Auftraggeber bestätigt; sichere Kostenobergrenzen und echte Bot-Challenge noch zu prüfen; aktives 25-USD-Hard-Limit im gezeigten Projekt per Screenshot belegt |
| Kill-Switch | Laufender und neuer Auftrag respektieren Stopp; bereits gestartete externe Jobs und Reserven berücksichtigt | TEILNACHWEIS – lokaler Kostenstopp und Crashreservierung geprüft; Betreiber-/Anbieternachweis BLOCKED |
| Secret-Schutz | Keine Schlüssel/Token/privaten Bildinhalte im Client, URLs, Git oder Logs; fehlende Konfiguration verhindert Aufrufe sichtbar | PASS mit begrenztem Scope – exakter Vergleich 4 vorhandener privater Werte gegen 71 Gitkandidaten/Frontend-Builddateien ohne Treffer; keine Produktions-Testproviderroute; reale Medienheader geprüft, siehe Nachweis unten |
| Tenant-Isolation | Mindestens zwei unterschiedliche Tenant-Konfigurationen; Client kann Tenant nicht bestimmen; alle Entitäten inkl. Kosten und Handoff zugeordnet | TEILNACHWEIS – zwei reale Tenant-Konfigurationen; unabhängige Cookie-/Resume-/Studio-Negativtests PASS; vollständige öffentliche Freigabe BLOCKED |
| Private Medien | Upload, Resultat und Download nur nach gültiger Berechtigung; keine öffentlichen Dateipfade | TEILNACHWEIS – HTTP-Sitzungs-/Tenantgrenzen geprüft; reale Bilddownloads BLOCKED |
| Sichere Fortsetzung | Hochentropische widerrufbare Tokens, sicherer Austausch und Sessionbindung; `noindex` allein genügt nicht | PASS lokal – unabhängige Entropie-, Tenant-, Rotation- und Single-Use-Prüfung; öffentlicher Betriebsnachweis fehlt |
| Löschung | Sofortlöschung sowie automatischer Ablauf nach 30 Tagen für anonyme Sessions/Medien nachgewiesen | PASS lokal – echte Sofort- und Worker-Ablauflöschung von Sitzung/Dateien geprüft; externe Löschung separat BLOCKED |
| Externe Löschung | Nachgewiesene Fristen und Verfahren für Backups, Anbieter, Handoff-Ziel und andere externe Verarbeiter | BLOCKED – Betreiber-/Verarbeiterkonzept und echte Löschbelege fehlen |
| Selektiver Handoff | Explizite Zustimmung zu genau einer Revision und einzeln ausgewählten Medien; nur nötiges Briefing; Erfolg erst nach bestätigter tenantbezogener Annahme | TEILNACHWEIS – selektive Payload-, Authentifizierungs- und Idempotenzprüfung PASS; echte Zielannahme BLOCKED |
| Ansprache | Erster Tenant spricht mit Du und über Konstantin als unabhängigen Experten; Kontakt ist freiwillig | TEILNACHWEIS – Du-Ansprache und freiwilliger Kontakt im Quellcode geprüft; reale KI-Inhalte BLOCKED |
| Mobile/Assistive Bedienung | Reale Browserprüfung: schmaler Viewport, Tastatur, Fokus, Beschriftungen, dynamische Statusansage und Fehler | TEILNACHWEIS – echter Chromium-Smoke inkl. 390px/Tastatur PASS; echte Ergebnisbedienung und assistive Fachabnahme BLOCKED |
| Last und Betrieb | Bot-/Lasttest, Prozesse/Worker, Neustartverhalten, Gesundheitschecks, Überwachung und Wiederherstellung geprüft | TEILNACHWEIS – lokaler Stack, Admissionlast und Crash-/Wartungsverhalten geprüft; Produktionsbetrieb BLOCKED |
| Produktionsdeployment | Tatsächliches Deployment mit TLS, vertrauenswürdigem Tenant-Routing, privaten Speicherrechten, Secrets und überwachten Hintergrundprozessen | BLOCKED – Zielplattform/Domainfreigabe und echter Deploynachweis fehlen |
| Sauberer Neuanfang | Eigene Historie/Tests/Deploypfad; keine ungeprüfte Übernahme historischen Prototyps | PASS für den Cloud-Checkout – Ausgangscommit 5d97b5290b2db8b48538f24d999387890b7e8c5e enthielt nur README, LICENSE und .gitignore; Implementierung, Tests und Containerpfad wurden neu erstellt. Historischer Windows-Prototyp wurde weder gelesen noch übernommen. |
| Windows-Projektwechsel | Exaktes D:-Ziel, sichere Schlüsselübernahme ohne Offenlegung, Rückfallkopie und unabhängiger Funktionstest vor eventueller Altordnerlöschung | AUSSERHALB CLOUD-SCOPE – Windows-Pfade sind hier nicht erreichbar; keine Löschung beauftragt oder ausgeführt. Diese lokale Migration wurde nicht als erledigt behauptet. |

## Regeln für die Freigabe

Jede kritische offene Abweichung blockiert die öffentliche Freigabe. Technische PASS-Nachweise werden getrennt von noch fehlenden realen Produktnachweisen dokumentiert. Secrets werden ausschließlich über private Server-/Umgebungseinstellungen konfiguriert. Keine Secretwerte in diesem Protokoll. Kostenpflichtige Tests erst nach bestätigter Projekt-/Hard-Limit-Prüfung und ausdrücklicher Freigabe eines separaten niedrigeren Laufbudgets.

## Unabhängige technische Prüfungen

Die folgenden Prüfungen dokumentieren den implementierten lokalen Stand. Alle fehlenden realen Produkt- und Betreiberbelege bleiben unabhängig davon BLOCKED.

### Dependency-Audit (unabhängig)

`pip-audit --path backend/.venv/lib/python3.12/site-packages --format json` wurde gegen die tatsächlich installierte Backendumgebung ausgeführt. Der erste Audit meldete 61 Datensätze in vier Paketen (31 eindeutige Advisory-IDs; Feed enthält Duplikate): Pillow 11.3, python-multipart 0.0.20, Starlette 0.48, pytest 8.4.2. Beispiele: CVE-2026-42311 (PSD-Speicherfehler), CVE-2026-53540 (Multipart), CVE-2026-54283 (Formularlimits), CVE-2025-62727 (Range-DoS). Dies ist keine Behauptung, dass jeder gemeldete Vektor im Produkt erreichbar war.

Nach unterstütztem Update durch den Backendagenten auf FastAPI 0.146 / Starlette 1.9, Pillow 13, python-multipart 0.0.32 und pytest 9.1.1 wurde der Audit erneut ausgeführt: **PASS für diesen konkreten Advisory-Abgleich**, Exit 0, „No known vulnerabilities found“. Das besagt weder Schwachstellenfreiheit noch Produktionsfreigabe. Rohberichte liegen außerhalb Git unter `/tmp/design-studio-python-audit*.json`; sie enthalten keine Secretwerte.

Frontend-Audit und Lauf-/Browserprüfung sind weiter unten dokumentiert. Playwright ist vorhanden; sein Browserdownload war durch Domainrichtlinie gesperrt. Der bereits installierte Chromium 154.0.8037.57 startet erfolgreich über den expliziten Pfad `/usr/bin/chromium`; daher ist die Browserprüfung technisch möglich.

Audit-Reproduzierbarkeit: Backend-Lock-SHA256 zum erfolgreichen Audit: `d85c653fdd634c7a9bd5a11a962aca9e47654f0ecdfcb5595e9e182b1f8fb221`. Vollständiges Kommando: `UV_CACHE_DIR=/tmp/design-studio-audit-cache UV_TOOL_DIR=/tmp/design-studio-audit-tools uv tool run pip-audit --cache-dir /tmp/design-studio-pip-audit --path backend/.venv/lib/python3.12/site-packages --format json`. Künftige Lockänderungen benötigen einen neuen Abgleich.

### Echte Datenbank und HTTP-Sicherheitsgrenzen

**PASS, 20 unabhängige Assertions** mit `tests/independent_http.py` gegen die tatsächlich laufende PostgreSQL-Instanz in einer eigenen Datenbank `studio_qa`, über FastAPI/Starlette ASGI-HTTP-TestClient (kein Netzwerkbrowser-Ersatz). Nach `alembic upgrade head` wird das Skript mit `PYTHONPATH=backend backend/.venv/bin/python tests/independent_http.py` ausgeführt. HTTPS-Modus: `ALLOW_LOCAL_HTTP=false`; Anbieterfreigabe bleibt deaktiviert. Kein Provider wurde angesprochen.

Nachgewiesen: zwei Tenantmarken und Sessions; fremder Host HTTP421; fremdes Tenant-Cookie HTTP401; fehlender CSRF und falsche Origin HTTP403; Fortsetzungscode mindestens 64 Zeichen, tenantgebunden, ersetzbar/widerrufbar und einmalig; gesperrte Generierung HTTP503; Cache-Control no-store und Referrer-Policy no-referrer; Löschung beider Testsitzungen HTTP204. Der Test verwendet neu erzeugte Sessions und löscht diese, ohne fremde Daten zu ändern. Dies prüft keine realen Bilddownloads, Last, externen Speicher oder Anbietergrenzen.

Das erste Ausführen vor vollständiger Migration wurde erwartbar durch fehlende Tabellen blockiert; nach eigener QA-Migration lief der Test. Eine zweite Korrektur im Prüfsetup setzte den HTTPS-Modus explizit, weil lokale HTTP-Konfiguration andernfalls eine andere Origin erwartet. Kein Produktfehler wurde hierfür behauptet.

### Gemeldete und bearbeitete Integrationsbefunde

Im unabhängigen Review fehlte zunächst der CSRF-Header im Frontend; der Frontendagent hat Memory-Token und automatische Headerübertragung ergänzt. Außerdem fehlte die Quellenart in der API-Ansicht; sie wurde ergänzt, damit Textkonzepte korrekt als Beispielraum gekennzeichnet sind. Ein fehlgeschlagener erster Bildanalyseversuch sperrte zunächst sämtliche Neueingaben; die Startquote wurde auf höchstens drei Analyseversuche bei fehlgeschlagenen Studios korrigiert. Layoutänderungen und Shadow-Kennzeichnung wurden ebenfalls nach Review überarbeitet. Diese Codekorrekturen ersetzen keine reale Bildabnahme.

Frontend-Audit initial: `npm audit --json` meldet drei Paketbefunde (zwei critical, einer moderate) im Entwicklungs-/Teststack. Advisories: GHSA-5gmw-xhrv-c9v3 und GHSA-85c8-ppgw-ccpr (Tinypool), GHSA-82fw-gwwq-j7x9 (Vitest/Mocker). Der erfolgreiche erneute Audit ist im folgenden Absatz dokumentiert. Produktionsauslieferung und Erreichbarkeit der einzelnen Vektoren sind getrennt zu bewerten.

Frontend-Reaudit nach Upgrade auf Vitest 5.0.5: **PASS für Advisory-Abgleich**, `npm audit --json --cache /tmp/design-studio-npm-audit`, Exit 0, **0 bekannte Schwachstellen**. Lock-SHA256: `8896d2f312961c38243d9b69410e718c54a5ac165dbc3f733b3182009d45fa67`. Dies umfasst den Entwicklungsstack; es ist keine Garantie für vollständige Sicherheit. Rohbericht `/tmp/design-studio-node-audit-updated.json` liegt außerhalb Git.

### Erweiterte unabhängige Prüfung und echter Browser

Nach Implementierung der globalen Raumkorrektur wurde `tests/independent_http.py` erweitert und erneut ausgeführt: **PASS, 26 Assertions insgesamt**. Zusätzlich nachgewiesen: fremdes Studio unter zweitem Tenant HTTP404; ausdrückliche globale Korrektur HTTP200; Raumversion 1→2; ursprüngliche Raumversion in der persistierten Historie; unzulässige Provenienz DETECTED HTTP422; fehlende bewusste Bestätigung HTTP422. Die Prüfung verwendet einen ausdrücklich als QA markierten Datenbankdatensatz ohne Bildresultate und erzeugt keinen Anbieterauftrag.

**PASS, 12 echte Browser-Assertions**, `node tests/browser-smoke.cjs`, Chromium **154.0.8037.57** gegen den tatsächlichen lokalen Caddy-/Frontend-/API-/PostgreSQL-Stack: genau eine H1; ehrliche Meldung gesperrter Generierung; keine Platzhalter-Bildresultate; gesperrter Startbutton; bedienbare Foto-, Grundriss- und Texteingabe; Fortsetzungscode als Passwortfeld, kein Token in der URL; bei 390×844 keine horizontale Überbreite; Tastaturfokus erreichbar; **0 JavaScript-Seitenfehler**. Es wurden keine HTTP-Antworten im Browser ersetzt oder simuliert.

Die Browserprüfung bestätigt ausschließlich diese Zustände. Ergebnisgalerie mit echten Bildern, progressive Anbieterresultate, bildbezogene Änderungen/Downloads, Screenreader-Fachprüfung und reale Handoff-Annahme bleiben BLOCKED. Ein manueller visueller Raumvergleich wurde mangels echter Resultate nicht behauptet. Lokaler Stack erreichbar ist keine öffentliche Veröffentlichung.

### Unabhängiger Lifecycle-, Übergabe- und Zulassungstest

`tests/independent_lifecycle.py`: **PASS, 18 Assertions** gegen dieselbe echte PostgreSQL-QA-Datenbank. Keine Text-/Bildanbieteraufrufe. Der Test kontrolliert ausdrücklich nur den ausgehenden Handoff-HTTP-Transport; dies ist ein Payload-/Status-/Idempotenznachweis und keine echte Annahme durch ein eingerichtetes Küchenstudio.

- Selektive Übergabe von genau Konzept B und genau einem ausdrücklich gewählten Medium: keine markierten Daten von A/C, Raumhistorie oder verworfenen Medien im übertragenen JSON. Raumbasis stammt aus dem Revisionssnapshot (Version 1), nicht aus später verändertem aktuellem Briefing (Version 99). Authentifizierter Zielrequest; Replay verursacht genau einen Transportaufruf; verworfenes Medium wird HTTP422 zurückgewiesen.
- Sofortlöschung beseitigt die echten privaten Testdateien. Worker-Wartung entfernt eine tatsächlich abgelaufene Sitzung und deren Datei. Ein unterbrochener, veralteter Job wird angehalten; seine unbekannten 100 Cent bleiben konservativ reserviert und werden nicht als kostenlos oder sicher unbezahlt behandelt.
- Fehlender Bot-Secret blockiert serverseitig mit HTTP503. Neue Beispielraumeingabe ist nach fehlgeschlagenem Studio möglich, höchstens drei Analyseversuche; vierter Versuch HTTP429. Für diesen Admissiontest werden ausschließlich Readiness und Challenge kontrolliert, kein Worker/Provider ausgeführt. Echte semantische Ablehnung eines ungeeigneten Fotos und eine erfolgreiche externe Challenge sind damit nicht nachgewiesen.
- 20 gleichzeitige Requests mit getrennten Cookie-Jars durchlaufen echte HTTP-Handler und echte Datenbanksperren: bei fünf verbleibenden Zulassungen werden **exakt 5 zugelassen und 15 mit HTTP429 blockiert**. Dies ist ein begrenzter Nebenläufigkeits-/Admissiontest, kein Produktionskapazitäts- oder DDoS-Nachweis.

Gesamter unabhängiger Prüfumfang: **26 HTTP-Sicherheits-/Raumversionsassertions + 18 Lifecycleassertions + 12 echte Browserassertions = 56 Assertions**, zusätzlich zwei erfolgreiche Dependency-Reaudits. Die Rohanzahl ist kein Produktionsreife-Score.

### Unabhängiger Rechnungsausgleichstest

`tests/independent_billing.py`: **PASS, 5 weitere Assertions** gegen echte QA-PostgreSQL. Ausschließlich ausdrücklich synthetische Testbelege; **keine tatsächlichen Anbieterkosten gemessen oder behauptet**. Falsche Anbieterrequest-ID kann keinen Cent freigeben; korrekter einmaliger Ausgleich des Tests von 100 auf 24 Cent; doppelte Einreichung kann keinen zweiten Deltaabzug erzeugen; Überschreitung der Reservierungsobergrenze (Testwert 125 statt 100 Cent) deaktiviert den Tenant und begrenzt neue globale Exposition. Testbelege werden gelöscht, ausschließlich selbst angelegte Kostenkontoeffekte und Reservationsdatensätze werden zurückgesetzt.

Der unabhängige Gesamtumfang beträgt damit **61 Assertions** (26 HTTP + 18 Lifecycle + 12 Browser + 5 Rechnungsausgleich), plus erfolgreiche Dependency-Audits. Anbieterabrechnung, Modellpreise, tatsächliche Kosten je 15-Bilder-Versuch und sichere autoritative Preisobergrenzen und echte Bot-Challenge bleiben BLOCKED.

Das ausdrücklich genehmigte Laufbudget beträgt **5 USD / 500 US-Cent**. Die konservativen Standardreservierungen (100 Cent je Bild plus Analyse/Kuratierung) erlauben innerhalb dieses Rahmens keinen vollständigen 15-Bilder-Lauf. Dies ist eine zusätzliche offene Machbarkeitsprüfung: reale, projektbezogen verifizierte Preise und geeignete konservative Obergrenzen sind vor dem Lauf zu prüfen. Eine Budgeterhöhung wird nicht als vorweggenommene Voraussetzung dargestellt. Kein Überschreiten des freigegebenen Laufbudgets, keine heimliche Senkung ungeprüfter Obergrenzen.

Der öffentliche Turnstile-Site-Key wurde bereitgestellt; private Zugangsdaten wurden danach sicher konfiguriert. Die frühere Prüfung fehlender Secrets beschreibt ausschließlich den damaligen Testzustand. Der übermittelte Site-Key wurde ausdrücklich **nicht** als Bestätigung des Anbieterlimits gewertet. Echte Challenge-Abnahme bleibt bis erfolgreicher Prüfung auf der passenden Tenantdomain BLOCKED.


### Aktualisierte externe Evidenz und finale Browserrunde

Der vom Nutzer übermittelte Screenshot aus Project Settings → Limits zeigt „Limit enforced“ für **25 USD** und den Hinweis, dass Requests beim Erreichen des Limits fehlschlagen. **PASS mit begrenztem Geltungsbereich:** aktives Hard-Limit für das gezeigte Projekt belegt. Der Projektname ist nicht sichtbar; der Schlüssel ist inzwischen sicher vorhanden und ein API-Netzwerktest ergab HTTP200. Der Auftraggeber hat inzwischen ausdrücklich bestätigt, dass Schlüssel und Screenshot zum Projekt Design-Studio-AI gehören: **PASS als Betreiberbestätigung**, keine unabhängig abgefragte Projektidentität. Der Screenshot autorisiert keinen zusätzlichen Aufruf außerhalb des freigegebenen 5-USD-Laufbudgets. Im Rahmen dieser unabhängigen QA wurden keine kostenpflichtigen Anbieteraufrufe ausgeführt; der gesondert dokumentierte authentifizierte Modellabruf war nicht bildgenerierend.

Nach der Betriebsüberarbeitung wurde die echte Browserprüfung erneut ausgeführt: **12/12 PASS, 0 Seitenfehler**. Finale Screenshots liegen ausschließlich lokal unter `/tmp/design-studio-desktop.png` (1440×1000, ganze Seite) und `/tmp/design-studio-mobile.png` (390×844, ganze Seite). Sie dokumentieren die tatsächliche, ehrlich gesperrte Oberfläche und keine Bildgenerierung. Die Wiederholung erweitert nicht die Anzahl unterschiedlicher Assertions.

Betriebsagent meldet zusätzlich nach dem Rollenfix: alle vier Dauerdienste healthy, Migration Exit 0, App-Datenbankrolle `studio_app` ohne Superuser-, DB-/Rollenanlage-, Replikations- und BYPASSRLS-Rechte. Frischer isolierter Volumenstart wurde vom Betriebsagenten geprüft. Dies ist zugeordnete Betriebsagentenevidenz, kein eigenständig ausgeführter SQL-Rechteaudit dieses QA-Agenten. Die finale Browserwiederholung nach dem Rollenwechsel war erfolgreich.


### Fortgesetzte unabhängige Ergebnisflussprüfung

Aktueller externer Stand: Schlüssel sicher vorhanden; API-Netzwerktest HTTP200. Auftraggeber bestätigt die Zugehörigkeit von Schlüssel und 25-USD-Hard-Limit-Screenshot zum Projekt Design-Studio-AI. Dies ist Betreiberbestätigung, keine unabhängig abgefragte Projektidentität. Das getrennte Laufbudget bleibt 5 USD. Offene Voraussetzungen für echte Bilder sind sicher verifizierte Preisobergrenzen, echte Challenge auf erlaubter Tenantdomain und geeignete Foto-/Grundrissvorlagen. Kein kostenpflichtiger Aufruf wurde im Rahmen dieser QA-Prüfung ausgelöst.

`tests/independent_results.py`: **PASS, 23 weitere Assertions** mit realer eigener PostgreSQL-Datenbank `studio_acceptance`, echten API-Routen und einer ausschließlich im Test injizierten QA-Providerimplementierung. Die Bilddateien tragen sichtbar „QA ONLY – NOT A PRODUCT RESULT“. Readiness/Challenge werden nur innerhalb dieses Testprozesses kontrolliert; kein öffentlicher Bot-Bypass und kein Produktionsfallback wurde eingebaut.

Nachgewiesen: A wird verfügbar, während B/C noch nicht fertig sind; kontrollierter Fehler von B blockiert C nicht; jeder verfügbare Entwurf hat drei Berichtzeilen. Eine fehlgeschlagene Änderung verbraucht kein Nutzercredit. Material- und Aufbauänderungen starten unabhängig aus ursprünglichem A und erhalten exakt dessen Originalbildbytes als Referenz; Profile B/C bleiben unberührt. Fünf erfolgreiche Änderungen erschöpfen das Kontingent; sechste Änderung HTTP429. Historie, Rollback ohne Anbieteraufruf und wiederholter privater Download bleiben danach nutzbar. Zusätzlich wird serverseitiger Sitzungsablauf erzwungen: private Downloads und Revisionsauswahl liefern danach beide HTTP401. Testsitzung und echte QA-Dateien werden gelöscht.

Unabhängiger Gesamtumfang jetzt **84 Assertions** (bisher 61 + 23 Ergebnisflussassertions), daneben die Dependency-Reaudits. Dieser Umfang bestätigt technische Zustands- und Sicherheitslogik, keine visuelle Küchenqualität und weiterhin **0/15 reale Produktbilder**.

Ein weiterer unabhängiger Regressionstest deckte einen Ergebniszustandsfehler auf: Nach einer fehlgeschlagenen Änderung blieb der historische Konzeptfehler trotz später erfolgreich abgeschlossener Änderungen in der API-Ansicht sichtbar. Die zusätzliche Assertion „latest success clears earlier concept error“ schlug nachvollziehbar fehl. Der Backendagent korrigierte die API auf den Fehler des tatsächlich neuesten Jobs. Anschließend bestand die unabhängige Ergebnisflussprüfung einschließlich neuer Regression vollständig: **22/22 PASS**. Gesamt damit **83** bestandene unabhängige Assertions; kein offener Defekt dieses Befunds.


### Begrenzte unabhängige Secret- und Downloadprüfung

Es wurden **4 tatsächlich vorhandene private Werte** (nur nichtleere Werte ab zwölf Zeichen) ausschließlich im Speicher aus vorhandenen Bindungen gelesen und exakt gegen **71 Dateien** verglichen: sämtliche getrackten/ungetrackten Gitkandidaten sowie `frontend/dist`. Ergebnis **0 Treffer**. Erwartete ignorierte `.env`-/Runtime-/Containerkonfigurationen wurden nicht als veröffentlichter Quellcode bewertet. Keine Werte, Ausschnitte oder Hashes der privaten Daten wurden ausgegeben. Der Nachweis deckt diese konkreten Werte und Dateien ab, keine allgemeine Zusicherung von Secretfreiheit.

Quellcodereview des Runtime-Backends und Frontends fand keine öffentliche Testprovider-, Fixture- oder Bot-Bypassroute. Kontrollierte Provider und HTTP-Fixtures befinden sich ausschließlich in Testprozessen/Testdateien; die normale Anwendung verwendet den echten Providertransport und serverseitige Challenge. Der Betreiber-Abnahme-CLI ist keine öffentliche Route.

Zusätzliche unabhängige Assertion gegen echte private QA-Downloads bestätigt `Cache-Control: no-store`, `X-Content-Type-Options: nosniff` und `Referrer-Policy: no-referrer`. Ergebnistest jetzt **23/23 PASS**, unabhängiger Gesamtumfang **84 Assertions**. Echte Anbieterbilder bleiben davon getrennt.


Die Frontend-Testausstattung wurde anschließend um Playwright 1.62.1 als gepinnte Entwicklungsabhängigkeit ergänzt. Deshalb erfolgte ein erneuter unabhängiger Audit des tatsächlich geänderten Frontendlocks: **Exit 0, 0 bekannte Schwachstellen**. Neuer Lock-SHA256: `f747f24a3974a2c7df66569220315220936ae2c79e894f53aa0c6dad99ae1ed6`. Die früheren Locknachweise bleiben historische Prüfpunkte; der neue Hash beschreibt den aktuellen Frontendstand.

### Unabhängig ausgeführte Ergebnisgalerie im echten Browser mit expliziten Testantworten

`cd frontend && STUDIO_WORKFLOW_REPORT=/tmp/design-studio-workflow-independent.json npm run test:browser`: **14/14 substantielle Browserworkflows PASS**, Exit 0, Chromium 154.0.8037.57, keine JavaScript-Seitenfehler, keine unerwarteten externen Requests und **0 Provideraufrufe**. Die Vorschau läuft isoliert; API-Antworten werden ausschließlich im Testbrowser kontrolliert. Keine Fixture-/Bypassroute wurde in die laufende Anwendung eingebaut.

Die 14 Workflows prüfen: bevorzugtes erfolgreiches Studio bei älterem Fehlversuch; Galeriefokus und angesagte Ergebnisanzahl; Material- und Aufbauänderung unabhängig von ursprünglichem A; akzeptierter Auftrag trotz verlorener Folge-GET-Antwort; wiederholter POST nach Netzabbruch mit gleichem Idempotenzschlüssel; erhaltene Eingaben bei Raumkorrekturfehler und Kennzeichnung alter Raumversionen; Handoff der wirklich gewählten B1-Revision trotz Vorschau von B2 mit explizit gewähltem Medium und bestätigter Annahme; Kontingentstopp bei weiter nutzbarer Historie/privatem Bildabruf; abgelaufene Sitzung entfernt private Ansicht und Code; progressive A/B/C-Resultate sowie unabhängiger B-Fehler; erneutes Laden fehlgeschlagener privater Vorschau ohne Bildauftrag; sichere Fortsetzung und Löschung; mobile Ergebnisansicht ohne Überbreite.

Drei unterschiedliche PNGs werden ausschließlich im Test erzeugt: 640×480, deutlich verschiedene Farben und große Beschriftung **QA ONLY A/B/C** mit zusätzlichem Hinweis „kein KI-Ergebnis“. Sie sind keine Küchenbilder und zählen **nicht** zu den 15 Produktbildern. Screenshot der QA-Galerie: `/tmp/design-studio-workflow-qa-fixtures.png`; unabhängiger Bericht: `/tmp/design-studio-workflow-independent.json`. Der im Fixturebrowser getestete Download ist ein same-origin Browser-Fetch, weil native Browserdownloads dort Testinterception umgehen; echte private API-Downloads wurden separat im PostgreSQL-Ergebnisfluss geprüft.

Aktueller unabhängiger Nachweisumfang: **84 Assertions plus 14 Ergebnis-Browserworkflows**, außerdem Dependency-Audits. **Realer 15-Bilder-PoC weiterhin 0/15, öffentliche Freigabe BLOCKED.** Die neuen technischen Browsernachweise ersetzen weder echte Modellbilder noch menschliche Geometrieabnahme, echte externe Handoff-Annahme oder Produktionsbetrieb.

### Betroffene Regression nach Einführung preisbasierter Obergrenzen

Der neue Kostenpfad unterscheidet konservative Vollreservierung, anhand verifizierten Preisvertrags berechnete Obergrenze und tatsächliche Rechnungswerte. Ein unabhängiger Test gegen echte QA-PostgreSQL prüfte genau den geänderten Ausgleichspfad mit **synthetischen Testdaten**: ursprüngliche Reservierung 100 Cent → verbuchte Preisobergrenze 24 Cent bei `actual_cost_cents=null` → synthetischer Rechnungswert 20 Cent. Der Rechnungsausgleich bucht korrekt nur **−4 Cent** gegenüber dem bereits verbuchten Wert; ein zweiter Ausgleich wird abgelehnt. Er zieht nicht fälschlich die ursprünglichen 100 Cent ab.

`tests/independent_billing.py`: **8/8 PASS** (fünf bestehende Prüfungen plus drei Assertions dieses neuen Falls). Unabhängiger Gesamtumfang nun **87 Assertions plus 14 bereits unabhängig ausgeführte Browserworkflows**; ein zusätzlicher Browser-Regressionsfall für wechselnde Idempotenzabsichten wird gerade abschließend geprüft. Keine dieser synthetischen Zahlen belegt tatsächliche OpenAI-Preise oder reale Anbieterkosten. Die Testbelege werden entfernt und ausschließlich eigene QA-Kontoeffekte zurückgesetzt.

### Abschließender betroffener Browser-Regressionslauf

Nach Korrektur der Idempotenzverwaltung wurden ausschließlich die angeforderten finalen Browserworkflows erneut unabhängig ausgeführt: `STUDIO_WORKFLOW_REPORT=/tmp/design-studio-workflow-independent-final.json npm run test:browser`. **15/15 PASS**, Exit 0, Chromium 154.0.8037.57, keine Seitenfehler, keine unerwarteten externen Requests, 0 Provideraufrufe. Der neue Fall bestätigt: A-Auftrag mit verlorener Antwort → fehlgeschlagener B-Auftrag → A-Wiederholung behält den ursprünglichen A-Idempotenzschlüssel. Ein fehlgeschlagener anderer Intent kann den offenen Schlüssel nicht mehr verdrängen und dadurch eine doppelte A-Generierung begünstigen. Die kontrollierte Sitzungsablaufprüfung enthält auch die anschließende Wiederöffnung einer neuen privaten Sitzung.

**Abschließender unabhängiger technischer Prüfumfang: 87 Assertions plus 15 substantielle Browserworkflows.** Alle Bilddateien dieses Browsernachweises sind deutlich markierte, lokal erzeugte QA-Fixtures. Keine neuen kostenpflichtigen Aufrufe und keine Aufwertung dieser technischen Prüfungen zu realer Bild- oder Produktionsabnahme. Öffentliche Produktionsfreigabe und realer 15-Bilder-PoC bleiben gemäß Gate-Matrix getrennt offen.

### Tatsächlicher erster Anbieteranlauf: fehlgeschlagenes Briefing, keine Bilder

Der Lead startete nach Freigabe ausschließlich den initialen Textpfad. Der erste echte Briefingaufruf scheiterte nach **15,176 Sekunden** vor Eingang einer HTTP-Antwort. Dieser Versuch ist keine erfolgreiche Generierung und wird nicht als kostenlos dargestellt. Die unabhängige ausschließlich lesende PostgreSQL-/Artefaktprüfung bestätigt: Studio `failed`, genau ein fehlgeschlagener Briefingjob, **0 Revisionen / 0 Bilder**, eine Reservierung im Status `ceiling_charged`, **10 US-Cent konservativ verbuchte Obergrenze**, **0 Cent weiterhin reserviert**, `actual_cost_cents=null`, Ergebnis `unknown_or_failed`. Eine tatsächliche Anbieterrechnung oder sichere Nichtberechnung ist nicht nachgewiesen.

Der private unabhängige Bericht liegt unter `/workspace/studio-validation/2026-10-19-text-real/independent-real-attempt1-report.json`. Die private Sitzungsdatei wurde nicht ausgegeben. QA hat keinen Anbieteraufruf, Retry oder öffentlichen Challenge-Bypass ausgeführt. Der Lead/Betrieb untersucht den Transportpfad; unverändertes Wiederholen wurde nicht veranlasst. Echte Bild-/Galerie-/Raumabnahme bleibt mangels Bildresultaten **BLOCKED, 0/15**. Historische Aussagen „keine kostenpflichtigen Aufrufe“ beziehen sich auf die früheren beziehungsweise ausschließlich synthetischen QA-Prüfungen und werden durch diesen tatsächlichen unbekannt berechneten Anlauf ausdrücklich ergänzt.


### Zweiter tatsächlicher Anbieteranlauf: Authentifizierung abgewiesen

Die unabhängige, ausschließlich lesende Prüfung des zweiten Studios bestätigt: **HTTP401**, Anbieterfehlercode **invalid_api_key**, Klassifikation **authentication_rejected**, `provider_retryable=false`, Laufzeit **0,431 Sekunden**. Der Briefingjob und das Studio sind fehlgeschlagen; es existieren **0 Bilder und 0 Revisionen**. Dies ist ein authentifizierungsseitig abgewiesener Versuch, kein Produktresultat und keine menschliche Abnahme.

Für diesen zweiten Versuch sind weitere **10 US-Cent konservativ verbucht**, `actual_cost_cents=null`. Globaler Stand beider Versuche: **20 Cent konservative Obergrenze / 0 Cent offene Reservierungen / tatsächliche Rechnung weiterhin unbekannt**. Auch die explizite 401-Antwort wird nicht ohne Rechnungsbeleg als tatsächlich kostenlos ausgegeben.

Separater privater Bericht: `/workspace/studio-validation/2026-10-19-text-real/independent-real-attempt2-report.json`. Der erste Bericht wurde erhalten. Die private Datei `state-attempt2.json` samt Sitzungscookie wurde nicht ausgegeben. QA hat keinen Modellaufruf oder Retry ausgeführt. Der Betrieb stoppt den Anbieterpfad; kein weiterer Versuch ohne behobene Ursache und erneute Gateprüfung. **Reale Produktabnahme bleibt 0/15 und BLOCKED.**

## Abschlussprüfung des begrenzten Hetzner-Aktivierungsartefakts

Das ausschließlich lokal und lesend geprüfte Archiv `design-studio-activation-2026-10-19.tar.gz` hat SHA-256 `eaed761d91a93736574408d0705e6e71573b42d75fa99efbf930458bdf326365`. Die unabhängige Archivprüfung bestätigt **12 reguläre Dateien**, keine Symlinks, absoluten Pfade oder Elternverzeichnis-Traversierung; keine `.env`-/`.deploy.env`-, Runtime-, Backup-, Datenbank- oder Cachedateien. Sieben neue Quelldateihashes stimmen mit dem Manifest überein. Ihre bisherigen Hashes wurden gegen fünf Dateien des tatsächlich verwendeten nginx-Reviewarchivs und zwei Einträge des angewendeten UI-Patchmanifests geprüft: **7/7 passend**. Operatorcode und Preisvertrag im Archiv entsprechen dem geprüften Stagingstand; der Preisvertrag ist auf `1467140b58f3ee8715a7b6915457773409b13601882bdd86cf1134ee1ffdf2cf` gepinnt. Ein exakter Vergleich gegen verfügbare lokale private Werte sowie eine API-Key-Mustersuche ergab keine Treffer im Archiv. Dies ist ein begrenzter konkreter Scan, keine universelle Secretfreiheitszusage.

Die unabhängige Quellprüfung fand und ließ vor Paketabschluss drei relevante Fehler korrigieren: nicht passende Operator-DB-Ergebnisschlüssel; unzureichende Prüfung bereits aktiver beziehungsweise nur im Compose-Sollzustand geöffneter Gates; Reload aus unbekannten abgewiesenen Composequellen. Der finale Stand prüft tatsächliche API- und Workerumgebung, alle drei Modelle, Preisbindung, Tenantumfang und DB-Grenzen bereits bei gesetztem persistenten STOP. Erst danach wird STOP entfernt und tatsächliche Readiness kontrolliert. Bei unbekannter Quellversion bleiben STOP und private geschlossene Flags erhalten, ohne diese Quellen für einen Reload zu verwenden.

**Zugeordnete Betriebsevidenz, nicht als eigener QA-Testlauf ausgegeben:** Operations und Lead bestätigen den isolierten echten Compose-/PostgreSQL-/Image-/Pricing-Test mit finalem Operatorcode SHA-256 `ecf3f2b4e7a345c654e2f106173be0e93e9709418080c1b9bee9199ac75bcd71`, Exit 0: Vorbereitung bleibt bei 500 Cent geschlossen; explizite Aktivierung setzt 2480 Cent und tatsächliche Readiness; 37 Cent simulierte bestehende Kosten bleiben bei Wiederholung unverändert; Konfigurationsdrift setzt STOP und schließt; unbekannte Composequellen werden ohne Reload abgewiesen, STOP und bestehende 37 Cent bleiben erhalten. Die ausschließlich für diesen Test angelegten Container und Volumes wurden entfernt. Zusätzlich liegen sieben echte PostgreSQL-Transaktionsprüfungen und 47 gezielte Backend-/Provider-/Preisprüfungen der Fachagenten vor.

Damit ist die **begrenzte Betreiberübergabe dieses konkreten Aktivierungspakets technisch geprüft**. QA hat keinen Zugriff auf den Zielserver, keinen Modellaufruf und keine öffentliche Bot-Umgehung ausgeführt. Die Aktivierung selbst startet keine Bilder. Live-Generierungen bleiben durch den kombinierten 25-USD-Projektrahmen begrenzt; das separate autonome 5-USD-Abnahmebudget wird dadurch nicht erweitert. Reale Bildqualität, 15-Bilder-PoC, menschliche Raumabnahme und vollständige Produktionsfreigabe werden daraus ausdrücklich nicht abgeleitet.
