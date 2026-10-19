# Betriebsprüfung vom 18. Oktober 2026

Lokale Infrastrukturprüfung, keine öffentliche Produktionsfreigabe und keine Bildabnahme.

| Prüfung | Ergebnis |
| --- | --- |
| Docker Engine 28.4 / Compose 2.40.3 | verfügbar |
| Python-/Node-/Caddy-/PostgreSQL-Images | TLS-geprüft geladen, Digests in Dockerfiles/Compose gebunden |
| `docker compose config --quiet` | PASS |
| `./scripts/start-local.sh` inklusive Build/Migration/Wiederanlauf | PASS, private bestehende `.env` bleibt erhalten |
| API `/healthz` und `/api/config` | HTTP 200, Generierung durch Kostenstopp gesperrt |
| Zweiter Host `tenant-two.localhost` | eigene Marke/Konfiguration, kein Client-Tenant-Feld |
| Unbekannter Proxyhost | HTTP 421 |
| Anwendungsmedienvolume | Schreibprobe mit unprivilegiertem Anwendungsbenutzer erfolgreich, Probe entfernt |
| Worker-Lebendigkeit | Heartbeat nach DB-Zugriff vorhanden, Healthcheck integriert |
| App-Datenbankrolle `studio_app` | NOSUPERUSER, NOCREATEDB, NOCREATEROLE, NOREPLICATION, NOBYPASSRLS geprüft |
| Frische PostgreSQL-Initialisierung | separater temporärer tmpfs-Container, getrennte erzeugte Admin-/App-Passwörter, Rechte und Schemaoperationen erfolgreich; Testcontainer entfernt |
| Lokaler DB-Dump/Restore | separater Restore in `studio_restore_smoke`, Alembic `0002`, 10 öffentliche Tabellen; Testdatenbank und privater Dump entfernt |
| Cloudproxy-/CA-Route aus Container | kostenloser PyPI-HTTPS-Abruf HTTP 200, TLS-Prüfung aktiv |
| OpenAI aus Container ohne Auth (historischer Erstversuch) | Damals CONNECT vom Plattformproxy HTTP 403; später prüfte der Lead authentifizierten Modellzugriff HTTP 200. Beides ist keine Bildabnahme. |

Die Rolle `studio` war auf dem ersten lokalen Volume der PostgreSQL-Bootstrap-Superuser. PostgreSQL verbietet dessen Umwandlung in einen Nicht-Superuser. Deshalb wurde ein neuer Nicht-Superuser für die Anwendung angelegt, ausschließlich öffentliche Anwendungsobjekte und Anwendungsdatenbank übertragen, ein separater Administrator provisioniert und der alte Bootstrap-Login deaktiviert sowie sein Passwort rotiert und verworfen. Neue Volumes beginnen direkt mit dem getrennten Rollenmodell. Keine Geheimniswerte wurden protokolliert.

Der lokale Dump/Restore bestätigt PostgreSQL-Werkzeuge und Schemawiederherstellung. Er enthält keine nachgewiesenen realen Nutzerbilder und belegt weder einen vollständigen Medienrestore noch verschlüsselte Produktionsbackups, Wiederherstellungsziele, externe Löschung oder deren 30-Tage-Einhaltung. TLS für eine tatsächliche öffentliche Domain, Container-Schwachstellenscan, produktive Alarmierung und Lastabnahme sind ebenfalls nicht nachgewiesen. Diese offenen Betriebsnachweise bleiben Freigabegates.


# Erweiterte Betriebsprüfung vom 19. Oktober 2026 (Europe/Berlin)

| Prüfung | Ergebnis |
| --- | --- |
| Wiederholbare Operatorstrecke | `scripts/backup.py` und `scripts/verify-recovery.py` implementiert und tatsächlich ausgeführt |
| Verschlüsselung | GnuPG/AES-256, unabhängig erzeugter Testkey, nichtleere verschlüsselte Datei und erfolgreiche authentifizierte Entschlüsselung |
| Kryptografische Negativtests | Veränderte Ciphertextdatei abgewiesen; falscher privater Key abgewiesen; fehlende/fehlerhafte Integrität niemals ignoriert |
| Archivgrenzen | Eingabe-/Klartext-/Member-/Gesamtgröße begrenzt, nur unkomprimiertes äußeres TAR; Traversal, Links, Geräte und Sparse-Einträge abgewiesen |
| Vollständiger isolierter Restore | Eigene Quell-/Ziel-PostgreSQL-Datenbanken und private Volumes, echter Dump plus tatsächliche private PNG-Testdateien, kein Anbieterzugriff |
| Aktive Sitzung nach Restore | Sitzungsdatensatz und zugeordnetes privates Medium vorhanden, Anwendungs-UID 10001 und Dateimodus 0600 bestätigt |
| Löschung nach Snapshot | Separater aktueller, verschlüsselter Löschledger reimportiert; entsprechende Sitzung und Mediendatei nach Restore nicht vorhanden |
| Bereits abgelaufene Sitzung im Snapshot | Vor Veröffentlichung entfernt, einschließlich Datei; neue Löschmarkierung geschrieben |
| Aktuelle Kontrollmetadaten | Neuer Ziel-HMAC-Key bleibt erhalten; alter Snapshot-Key wird nicht kopiert; persistenter Generierungsstopp zwingend gesetzt |
| Vorhandenes Restoreziel | Zweiter Restore verweigert das Überschreiben der bestehenden Datenbank |
| Isolation und Aufräumen | Nur eigens erzeugte Testprojekte/-volumes entfernt; bestehende Anwendungsdatenbank und Medienvolumes erhalten |
| Datenschutzarme Betriebsprüfung | `scripts/readiness.py`: vier Dienstzustände, überfällige Sitzungen/alte Jobs, Quotenreservierungen und Schreibberechtigung aggregiert geprüft |
| Generierungsbereitschaft | `scripts/readiness.py --require-generation` beendet sich bei gesperrter Generierung ausdrücklich mit Exit 1 |

Die PNG-Dateien sind ausschließlich erzeugte technische Recovery-Testdaten und niemals behauptete echte Küchenkonzepte oder Produktresultate. Es wurden keine bezahlten Anbieteraufrufe durchgeführt. Produktions-Backupziel, Verschlüsselung der Hostdatenträger, Offsite-/Ledger-Replikation, reale maximale Wiederherstellungszeit und externe 30-Tage-Löschung bleiben ohne Betreiberinfrastruktur unbelegt. Vor Freigabe eines wiederhergestellten Systems sind aktuelle seit Snapshot angefallene Anbieterkosten abzugleichen; der wiederhergestellte Kostenstand darf den Generierungsstopp nicht automatisch aufheben.

Abschließender tatsächlicher Containerstand am 19. Oktober: alle vier Dienste gesund, Migration `0004`, API-Rolle `studio_app` ohne erhöhte Rechte, installierte Paketgrenze `/app` korrekt erkannt. Aus genau diesem API-Container war der authentifizierte, ausschließlich lesende Abruf `/v1/models` mit HTTP 200 erfolgreich. Ausgeliefertes Browserbundle: `index-DhSVCuru.js`, HTTP 200. Generierung bleibt bewusst gesperrt; konservativ belastete und reservierte Kostenkonten stehen jeweils auf 0 Cent.

Der reale Proxytest bestätigte das ausschließlich gemeinsam genutzte Proxy-Netz mit Caddy-Peer `172.30.74.2`. Zwei abweichende gefälschte Weiterleitungsheader wurden auf denselben tatsächlichen Client/HMAC-Bucket begrenzt; nicht autorisierte Mutationen blieben 401/403. Eine Anfrage über 13 MiB wurde mit 413 abgewiesen. Uvicorns tatsächlicher Containerbefehl enthält 32 als Parallelitätsgrenze. Die dynamische IPAM-Vergabe ist von der festen Proxyadresse getrennt; ein beim Erststart beobachteter Adresskonflikt wurde behoben und der anschließende Start tatsächlich geprüft.

Die separate Prüfung des fertig gebauten Backendcontainers bestätigte, dass externe private Preisverträge außerhalb `/app` lesbar sind und ein nicht ausführender Operator-Smoke seine privaten Auditdateien außerhalb `/app` mit Modus 0600 erzeugen kann. Diese Prüfung nutzte ausdrücklich synthetische Vertragstestdaten und führte keine Anbieteraufrufe aus. Verifizierte echte Modellpreise werden daraus nicht abgeleitet.

## Kontrollierter Anbieterstart: tatsächlicher Netzfehler und Behebung

Der erste echte, ausschließlich vom Lead eingereichte Text-Briefingversuch scheiterte nach ungefähr 15,18 Sekunden mit einer endlichen `transport_error`-Klassifikation, ohne HTTP-Status oder Anbieter-Request-ID. Der Worker belastete den konservativen 10-Cent-Rahmen; keine Reservierung und kein aktiver Auftrag blieben bestehen. Diese 10 Cent wurden weder zurückgesetzt noch als tatsächliche Rechnung behauptet. Der Lauf wurde terminal geschlossen, persistenter STOP gesetzt und der Worker auf false/false/true zurückgesetzt; alle privaten Zustände blieben erhalten.

Ursache wurde mit kostenlosen Prüfungen isoliert: API und Worker hatten jeweils `ConnectTimeout` für synchrone und asynchrone Modelllistenabrufe nach rund 15,2 Sekunden. Der Host lieferte asynchron HTTP 200 in rund 0,91 Sekunden. Beide Container verwendeten denselben Proxynamen wie der Host, aber dessen konfigurierte Adresse entsprach nicht mehr der aktuellen Host-DNS-Auflösung. Nach erneuter Generierung des privaten Cloud-Overlays und Neuerstellung ausschließlich der geschlossenen API/Worker lieferten beide synchron und asynchron HTTP 200 in rund 0,95–1,08 Sekunden. TLS-Prüfung blieb aktiv; Datenbank und Volumes wurden nicht zurückgesetzt.

Der wiederholbare kostenlose Operatorcheck `scripts/provider-preflight.py` wurde anschließend tatsächlich ausgeführt: API und Worker HTTP 200, Proxy-DNS-Vergleich jeweils wahr. Für einen durch den Lead separat genehmigten einmaligen technischen Wiederholungsversuch blieb die Gesamtobergrenze 500 Cent bei bereits 10 Cent konservativer Belastung unverändert. Ops reichte selbst keinen bezahlten Auftrag ein.


## Zweiter Initialversuch und Authentifizierungsgrenze

Nach der belegten Proxykorrektur reichte der Lead genau einen neuen Initialversuch ein. Dieser scheiterte bereits beim Briefing in ungefähr 0,431 Sekunden mit HTTP 401 `invalid_api_key` und einer sicheren `authentication_rejected`-Klassifikation. Nach terminalem Zustand und global 0 aktiven Jobs setzte Ops wieder persistent STOP und stellte den Worker auf false/false/true zurück. Gesamtobergrenze weiterhin 500 Cent, konservativ belastet 20 Cent, reserviert 0; keine Rücksetzung oder fingierte Rückerstattung.

Kostenlose Gegenproben belegten: Modelllisten-GET ohne Authentifizierung und mit absichtlich ungültigem Bearer jeweils HTTP 200; die Modellliste ist somit kein Schlüsselgültigkeitsnachweis. Ein ausdrücklich freigegebener, nicht generierender POST auf Responses mit leerem JSON ohne Modell/Eingabe antwortete sowohl beim Host als auch im Worker HTTP 401 `invalid_api_key`. Sichere Ausgabe enthielt ausschließlich Status, endliche Codes und validierte Request-IDs, niemals Rohantworten oder Schlüssel.

Ein interner Vergleich bestätigte identische, vorhandene STUDIO-Bindungen auf Host, API und Worker; keine alternative namensgleiche OpenAI-Schlüsselbindung war vorhanden. Die vom Lead geprüfte gespeicherte Domain-/Variablenzuordnung ist korrekt deklariert. Die Gültigkeit des bestehenden sicheren Wertes beziehungsweise seine korrekte Weitergabe durch die Plattform bleibt der konkrete externe Blocker. Es wurden keine zusätzlichen Schlüssel-/Domainanforderungen angelegt.
