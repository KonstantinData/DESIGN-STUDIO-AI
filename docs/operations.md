# Betrieb und Wiederanlauf

Dieses Repository ist ein Implementierungsstand. Lokaler Betrieb mit deaktiviertem Anbieter ist keine Produktabnahme. Fehlende echte Bilder, nutzbare Generierungsauthentifizierung, externe Übergabe und Datenschutzbelege blockieren Veröffentlichung; siehe `docs/acceptance.md`, soweit vorhanden.

## Reproduzierbarer lokaler Start

Voraussetzungen: Docker Engine, Compose v2.24.4+ (geprüft: 2.40.3), Python 3.12+ und Netzwerkzugriff auf Docker Hub, PyPI und npm. Im vorhandenen Checkout arbeiten; keine zusätzlichen Worktrees anlegen.

```sh
cd /workspace/DESIGN-STUDIO-AI
./scripts/start-local.sh
```

Das Skript erzeugt `.env` exklusiv mit Dateimodus 0600 und zufälligem PostgreSQL-Passwort; vorhandene Einstellungen bleiben erhalten. Die beiden lokalen Hosts `localhost` und `tenant-two.localhost` sind serverseitig verschiedene Tenants. API, Worker und Datenbank bleiben ohne Host-Port. Nur Caddy bindet standardmäßig an Loopback 8080/8443. Caddy erhält den tatsächlichen Host einschließlich Port für Origin-Prüfungen; der Server normalisiert den Hostnamen für das Tenant-Routing. Vom Client gesetzte Tenant-IDs sind kein Routingmechanismus.

`docker compose config --quiet` prüft Struktur ohne Geheimnisse auszugeben. Niemals unredigiertes `docker compose config`, `docker inspect`, Environment-Dumps oder `.env` in Logs/Chat veröffentlichen. Das Skript setzt das Docker-Konfigurationsverzeichnis unter die ignorierte `.runtime`, weil `/home/agent` in der Cloud schreibgeschützt ist. Direkte Build-Befehle benötigen entsprechend `DOCKER_CONFIG="$PWD/.runtime/docker"`.

```sh
docker compose ps
docker compose exec -T db pg_isready -U studio_app -d studio
docker compose logs --tail=100 backend worker
docker compose stop
# Neustart mit vorhandenen Volumes und Migrationen:
./scripts/start-local.sh
```

Kein `docker compose down --volumes` verwenden, wenn Daten erhalten bleiben sollen. Migrationen laufen als eigener einmaliger Dienst vor API/Worker. Images sind mit Digest gebunden, Python-Abhängigkeiten über `uv.lock` eingefroren und npm verwendet `npm ci`. Sicherheitsupdates müssen bewusst aktualisiert, gebaut und getestet werden.

## Produktion: externe Voraussetzungen

Ein gehärteter Linux-Host mit persistenten verschlüsselten Datenträgern, Docker, gesichertem SSH-Zugang, Firewall und Überwachung ist erforderlich. Dieser Cloud-Checkout provisioniert kein öffentliches Hosting. Der Betreiber muss DNS, TLS-Erreichbarkeit, Backups, Überwachung, Auftragsverarbeitung und Zuständigkeiten nachweisen.

1. `.env` sicher provisionieren, `POSTGRES_PASSWORD` und ein davon unabhängiges `POSTGRES_ADMIN_PASSWORD` kryptografisch erzeugen. Die Anwendung nutzt ausschließlich `studio_app` ohne Superuser-/Rollen-/Datenbankerstellungsrechte; der Bootstrap-Administrator gehört nicht in die Anwendungs-Verbindungszeichenfolge. `TENANTS_JSON` enthält ausschließlich freigegebene reale Hostnamen und je Tenant `slug`, `brand`, `expert_name`, öffentliches `turnstile_site_key`, `handoff_url`, `budget_cents` und `enabled`. Geheimnisse gehören ausschließlich in die private Serverumgebung, niemals in Clientbuilds oder Git. Tenant-spezifische Turnstile-Secrets können im privaten JSON konfiguriert werden, ein gemeinsames Konto über `TURNSTILE_SECRET`.
2. `SITE_ADDRESSES` auf dieselben echten DNS-Namen setzen. `HTTP_BIND=0.0.0.0`, `HTTPS_BIND=0.0.0.0`, `HTTP_PORT=80`, `HTTPS_PORT=443` nur auf dem dafür bestimmten Server. Firewall öffnet ausschließlich 80/443 öffentlich. Caddy ACME-TLS benötigt korrektes DNS und eingehend 80/443. Produktions-TLS ist hier ohne Domain und Hosting nicht nachgewiesen. HSTS erst nach erfolgreicher Domain-/TLS-Prüfung betrieblich aktivieren.
3. OpenAI-Projektbindung des serverseitigen `STUDIO_OPENAI_API_KEY`, tatsächliches aktiviertes Hard-Limit, Preise, reservierte Kosten laufender Jobs und den separat freigegebenen 5-USD-Abnahmerahmen prüfen. Dieser ist auf höchstens 500 US-Cent global und je Testtenant begrenzt; das 25-USD-Projektlimit ist kein Laufbudget. `PROVIDER_ENABLED=false`, `BUDGET_APPROVED=false`, `GLOBAL_KILL_SWITCH=true` bleiben bis dahin bestehen. Das 25-USD-Projektlimit autorisiert keinen Aufruf. Ein Spend Alert ersetzt keinen Hard-Stop.
4. Turnstile für die echten Hosts einrichten. `TURNSTILE_SECRET` und site key müssen zusammenpassen. Die Herausforderung darf keine Registrierung verlangen. Ausgehende HTTPS-Verbindungen zu `api.openai.com`, `challenges.cloudflare.com`, freigegebenen tenantbezogenen Handoff-Zielen sowie ACME-Zielen des gewählten CA sind erforderlich. Installation benötigt außerdem `registry-1.docker.io`, `auth.docker.io` und zugehörige Docker-CDN-Domains, `pypi.org`, `files.pythonhosted.org`, `registry.npmjs.org`. Eine unbekannte Plattform-Allowlist nicht überschreiben; benötigte Ziele additiv freigeben.
5. Zwei tatsächlich konfigurierte Tenants, private Downloads, Quoten, Kostenstopps, Recovery, gültiges TLS, Retention, selektive Übergabe und Browser-/Lastprüfungen abnehmen. Eine API-Health-Antwort bestätigt keine generierten Konzepte.

## Persistenz, Backup und Wiederherstellung

`postgres` enthält Sitzungen, Jobs, Kostenkonten und Revisionen; `private_media` die privaten Dateien. `deletion_ledger` enthält unabhängig vom rücksetzbaren Snapshot die dauerhaften Löschmarkierungen. Caddy-Daten enthalten private TLS-Schlüssel und müssen gesondert gesichert werden. Anwendung und Medien sind nicht über Caddy file_server erreichbar.

Die ausführbare Betriebsstrecke ist `scripts/backup.py`; sie benötigt das vorhandene GnuPG und einen unabhängig geprüften, vertrauenswürdigen vollständigen Empfängerfingerprint im privaten GPG-Keyring. Schlüsselwerte werden weder als Argument noch in Skripten hinterlegt. Die private Entschlüsselung muss vor Restore über den kontrollierten GPG-Agenten möglich sein; es gibt keinen Passwort-/Klartext-Fallback. Temporäre Klartextdateien gehören auf privaten RAM- oder verschlüsselten Speicher, nicht auf beliebigen Shared-Storage. Keyring, Scratch- und Backupziel müssen dem Betreiber gehören, Modus 0700 haben und außerhalb des Checkouts liegen. Diese Prüfungen beweisen keine Verschlüsselung des darunterliegenden Datenträgers; dafür bleibt der Betreiber verantwortlich.

```sh
python3 scripts/backup.py --gpg-home "$BACKUP_GPG_HOME" --scratch-dir "$BACKUP_PRIVATE_SCRATCH" backup --recipient "$BACKUP_RECIPIENT_FINGERPRINT" --output "$BACKUP_PRIVATE_DESTINATION/snapshot.gpg"
```

Backup stoppt die tatsächlich laufenden Schreibdienste Web/API/Worker, erstellt einen konsistenten PostgreSQL-Dump und ein privates Medienarchiv und startet ausschließlich die vorher laufenden Dienste wieder. Das Bundle enthält Version, Snapshotzeit und SHA-256 je Komponente und wird als GPG/AES-256-Datei ausgegeben. Vorhandene Ausgabe wird nie überschrieben. Planmäßige Wartung muss laufende kostenpflichtige Jobs berücksichtigen: Stoppen kann deren externen Ausgang unklar lassen; reservierte Kosten dürfen dabei nicht freigegeben oder Aufträge blind erneut gestartet werden. `.rate-limit-key` und `STOP_GENERATION` sind keine Medien und werden nicht aus alten Snapshots übernommen.

Sofortlöschungen nach dem Snapshot dürfen bei Restore nicht wieder erscheinen. Deshalb ist zusätzlich ein **frischer Export des autoritativen aktuellen Löschledgers** erforderlich, unabhängig von alten Snapshots. Für einen kontrollierten Disaster-Cutover:

```sh
python3 scripts/backup.py --gpg-home "$BACKUP_GPG_HOME" --scratch-dir "$BACKUP_PRIVATE_SCRATCH" export-deletions --quiesce-source --recipient "$BACKUP_RECIPIENT_FINGERPRINT" --output "$BACKUP_PRIVATE_DESTINATION/current-deletions.gpg"
```

Dieser Befehl lässt Schreibdienste der Quelle ausdrücklich **gestoppt**, damit danach keine jüngere Löschung am Export vorbeigeht. Bei Fehlern/Abbruch bleibt der Dienststatus zu prüfen; die Quelle erst nach bewusster Entscheidung wieder starten. Ein zerstörter oder veralteter aktueller Ledger ist ein Restore-Blocker, keine Erlaubnis, nur einen alten Ledger aus dem Snapshot zu verwenden. Replikation/Verfügbarkeit des getrennten Ledgers braucht einen vom Betreiber nachgewiesenen Schutzplan.

Restore verlangt ein ausdrücklich separates `COMPOSE_PROJECT_NAME`, eigene private `COMPOSE_ENV_FILES`, leere Datenbank, keine laufenden Schreibdienste und leere Medien-/Ledger-Datenvolumes. Ein bereits provisionierter aktueller HMAC-Key bleibt erhalten. Snapshot und aktueller Ledger werden authentifiziert entschlüsselt; fehlender MDC, falscher Schlüssel, Prüfsummenfehler, fremde Dateinamen, Links, Pfadtraversal, Geräte, Sparse-Dateien und Größenüberschreitungen werden abgewiesen. Der Ledger muss mindestens so neu wie der Snapshot und höchstens 30 Minuten alt sein. Das Alter ersetzt keine organisatorische Vollständigkeitsgarantie.

```sh
# COMPOSE_PROJECT_NAME und COMPOSE_ENV_FILES vorher sicher auf isolierte Zielkonfiguration setzen.
docker compose up -d --wait db
python3 scripts/backup.py --gpg-home "$BACKUP_GPG_HOME" --scratch-dir "$BACKUP_PRIVATE_SCRATCH" restore --confirm-isolated --input "$BACKUP_PRIVATE_DESTINATION/snapshot.gpg" --current-deletion-ledger "$BACKUP_PRIVATE_DESTINATION/current-deletions.gpg"
```

Restore überschreibt keine bestehenden Nutzdaten. Es stellt Schema und Medien gemeinsam wieder her, führt Migrationen, aktuelle Löschmarkierungen und Ablaufbereinigung aus und setzt zwingend den persistenten `STOP_GENERATION`. Keine öffentlichen Dienste werden gestartet. Vor Freigabe **Kostenkonten gegen aktuelle Anbieterabrechnung und seit Snapshot angefallene Kosten abgleichen**: Ein alter Kostenstand darf keine erneuten Ausgaben erlauben. Erst anschließend Autorisierung, aktive/gelöschte/abgelaufene Sitzungen, private Medienrechte und Quoten prüfen. Im Fehlerfall das isolierte Ziel untersuchen oder ausdrücklich ein neues Ziel erstellen; niemals eine teilweise erfolgte Wiederherstellung durch automatisches Überschreiben verdecken.

`scripts/verify-recovery.py` führt die komplette Strecke auf eigenen temporären Datenbanken/Volumes mit generierten privaten Testmedien durch. Es nutzt keine Produktionszugangsdaten, keinen öffentlichen API-Port und keinen Anbieter. Das ist eine lokale technische Wiederherstellungsprüfung, kein Nachweis für verschlüsselte Produktionsspeicher, Offsite-Ziele, garantierte Wiederherstellungszeiten oder externe Löschung.

## 30 Tage, Sofortlöschung und externe Verarbeiter

Worker führt die lokale Retention aus; der Betrieb muss Worker-Lebendigkeit, letzte erfolgreiche Bereinigung, älteste Sitzung/Datei, verwaiste Medien und Datenvolumen überwachen. Ausgefallene Bereinigung blockiert das Datenschutzgate. 30 Tage gelten auch für Backups und externe Verarbeiter, nicht nur für aktive Daten. Eine Wiederherstellung darf bereits gelöschte Daten nicht öffentlich reaktivieren: vor Wiederfreigabe aktuelle Löschereignisse nachziehen und abgelaufene Daten entfernen. Löschprotokolle selbst dürfen keine Prompts, Bilder oder Klartexttokens enthalten.

Es gibt aktuell keinen Nachweis über externe Anbieter-Retention, Auftragsverarbeitungsverträge, zuständige Übergabeempfänger, deren Löschfristen, Backupzyklen oder durchgeführte Restore-/Löschtests. Diese Nachweise sind Veröffentlichungsvoraussetzungen. Automatisches lokales Entfernen beweist keine Löschung bei OpenAI oder einem Studio. Nur ausdrücklich ausgewählte Medien dürfen an das bestätigte tenantbezogene Handoff-Ziel gehen.

## Cloud-Proxy und Zertifikatsvertrauen

`scripts/configure-cloud.py` erkennt vorhandenes HTTPS-Proxying und erzeugt ausschließlich lokal eine private `.runtime/compose.cloud.json`. Builds verwenden die bestehende Proxyauflösung und den konfigurierten CA-Bundle als BuildKit-Secret; API/Worker erhalten dieselbe Proxyroute und einen schreibgeschützten CA-Mount. TLS-Prüfung bleibt aktiv. Das Startskript bindet dieses Overlay automatisch ein. In regulärer direkter Produktionsvernetzung wird ohne Proxy kein Overlay angelegt. Beim Wechsel der Umgebung die generierte Datei prüfen und nur die eigene veraltete Overlay-Datei entfernen, falls kein Proxy mehr verwendet wird.

Beim historischen Erstversuch war ein kostenloser HTTPS-Abruf von PyPI im Container erfolgreich; die damalige anonyme OpenAI-Modellabfrage scheiterte am Plattformproxy mit `403 Forbidden` bei CONNECT. Später bestätigte der Lead authentifizierten Modellzugriff HTTP 200. Ein Modelllistenabruf belegt keine funktionierende Bildgenerierung oder fachliche Abnahme; Schlüsselwerte nicht ausgeben. Projektzuordnung und Projektlimit wurden durch Betreiberbestätigung belegt. Die Modelllistenroute liefert jedoch sogar ohne Authentifizierung HTTP 200 und bestätigt keine nutzbare Generierungsauthentifizierung. Ein nicht generierender POST mit leerem JSON wurde mit 401 invalid_api_key abgewiesen; echte Bildresultate und Produktabnahme fehlen.

## Sofortiger Generierungsstopp

Der persistente lokale Kill-Switch wird vor der nächsten Kostenreservierung geprüft, ohne API-/Worker-Neustart:

```sh
docker compose exec -T backend touch /var/lib/studio/private/STOP_GENERATION
```

Bereits laufende externe Aufrufe können trotzdem Kosten verursachen; Reserven dafür dürfen nicht freigegeben werden. Die Datei stoppt neue Reservierungen auch im Worker. Nur nach dokumentierter Freigabe wieder entfernen; `GLOBAL_KILL_SWITCH=true` sperrt unabhängig davon weiter. Budgetänderungen in `.env` benötigen einen kontrollierten API-/Worker-Neustart und eine erneute Prüfung der Datenbankkonten, nicht nur eine Editoränderung.

Externe Übergaben benötigen zusätzlich ein serverseitiges Bearer-Credential `HANDOFF_AUTH_<SLUG_IN_GROSSBUCHSTABEN_MIT_UNTERSTRICHEN>` und ein ausdrücklich erlaubtes HTTPS-Ziel. Für die beiden lokalen Slugs sind `HANDOFF_AUTH_MEIN_KUECHENEXPERTE` und `HANDOFF_AUTH_ISOLATION_CHECK` im Compose-Vertrag enthalten. Weitere Tenants benötigen die entsprechende gezielte Secret-Injektion in API/Worker, ohne Schlüsselwerte in Git zu schreiben. `HARD_LIMIT_VERIFIED_AT` darf erst nach Zuordnung des tatsächlichen serverseitigen Keys zu dem belegten Projektlimit gesetzt werden; ein erfundenes Datum ist keine Verifikation.

Der Worker-Healthcheck verlangt eine höchstens 120 Sekunden alte `/tmp/worker-heartbeat`, geschrieben nach erfolgreichem Claim-/Wartungsdatenbankzugriff. Das bestätigt den laufenden Workerloop, ersetzt aber keine Überwachung tatsächlich ausgeführter Retention oder erfolgreicher Anbieterjobs. Docker markiert ungesunde Prozesse; ein bloßes `restart: unless-stopped` startet einen weiterlaufenden ungesunden Container nicht automatisch neu. Der Betreiber benötigt Alarmierung und einen kontrollierten Wiederanlauf.

Der öffentliche Turnstile Site-Key des Auftraggebers ist im deaktivierten Produktionsprofil `deploy/tenants.production.json` für `mein-kuechenexperte.de` gespeichert. Zur Produktion den JSON-Inhalt ausdrücklich als privates `TENANTS_JSON` übernehmen, reale zweite Tenantkonfiguration und zulässige Übergabe ergänzen und erst nach vollständiger Abnahme aktivieren. Das lokale Hostrouting bleibt separat; ein Site-Key allein schaltet weder Botprüfung noch Anbieter frei.

Für das globale Budget ist ein Screenshot mit aktivem Limit-Enforcement und 25 USD dokumentiert (`docs/hard-limit-evidence.md`). Der Schlüssel ist serverseitig gebunden; der Auftraggeber bestätigte ausdrücklich Schlüssel und aktiviertes Enforcement im Projekt Design-Studio-AI. Der Modelllistenabruf mit Auth-Header war erfolgreich, beweist aber nach Vergleich mit fehlender und absichtlich ungültiger Authentifizierung keine Schlüsselgültigkeit. Das lokale Abnahmelaufbudget bleibt 5 USD, Anbieteraufrufe gesperrt.

## Vertrauenswürdiger Proxy und begrenzte API-Last

Caddy und API teilen ein eigenes internes Netz `172.30.74.0/28`; Caddy hat fest `172.30.74.2`; dynamische Containeradressen werden ausschließlich aus `172.30.74.8/29` vergeben, damit kein Startreihenfolge-Konflikt die feste Proxyadresse belegt. Nur dieser unmittelbare Peer wird über `TRUSTED_PROXY_CIDRS=172.30.74.2/32` für die Interpretation von `X-Forwarded-For` akzeptiert. Caddy überschreibt diesen Header mit dem tatsächlichen Remote-Peer und entfernt fremde `Forwarded`/`X-Real-IP`. Host bleibt für Tenant-/Origin-Prüfungen erhalten. API und Datenbank haben weiterhin keine öffentlichen Ports. Bei anderer Infrastruktur muss die tatsächlich beobachtete Peeradresse gezielt angepasst und Spoofing negativ getestet werden; pauschales Vertrauen in sämtliche Proxies ist unzulässig. Das statische Netz bei Installation auf Überschneidungen mit vorhandenen Netzen/VPN prüfen.

Caddy begrenzt eingehende API-Bodies auf 13 MiB und setzt Header-/Body-Lesezeitlimits. Uvicorn lässt maximal 32 gleichzeitige Verbindungen/Aufträge mit Backlog 128 zu. Das begrenzt insbesondere den Speicher für gepufferte unautorisierte Requests; 32 mal 13 MiB sind höchstens 416 MiB reine Requestbytes, zusätzlich fallen Parser-, Python- und Anwendungsdaten an. JSON hat serverseitig das engere Limit. Anbieter-Deadlines und HMAC-basierte Tages-IP-Limits kommen zusätzlich hinzu; sie ersetzen keinen globalen API-Ressourcenrahmen.

## Datenschutzarme Bereitschaft und Alarmierung

`python3 scripts/readiness.py` liefert ausschließlich aggregierte Betriebswerte: vier Dienstzustände, überfällige Sitzungen, alte laufende Jobs, Warteschlange, private Schreibberechtigung, konservativ belastete und reservierte Cent. Keine IPs, Prompts, Tokens, Sitzungs-IDs oder Medienpfade werden ausgegeben. Exit 1 zeigt kaputte Infrastruktur/Bereinigung an. Mit `--require-generation` scheitert die Prüfung außerdem, solange tatsächliche Generierungsvoraussetzungen fehlen. Die öffentliche `/healthz` zeigt nur DB-Lebendigkeit; Betreiberbereitschaft ist eine separate Prüfung. Konservative Kostenwerte sind keine behaupteten tatsächlichen Anbieterrechnungsbeträge. Alarmierung/On-Call außerhalb dieses Skripts ist auf echtem Hosting einzurichten.

## Kostenpflichtige Abnahme: kostenlose Netzprüfung vorher

Vor jeder ausdrücklich freigegebenen bezahlten Abnahme `python3 scripts/provider-preflight.py` ausführen. Der Operator prüft dabei API und Worker über einen kostenlosen, authentifizierten asynchronen `GET /v1/models`. Zusätzlich müssen deren Proxyauflösungen mit der aktuellen Hostauflösung übereinstimmen. Ausgabe enthält nur Status, Dauer und Vergleichsbooleans, keine Proxyadressen oder Schlüssel. Exit 1 blockiert die Freigabe; es wird kein Generierungsauftrag angelegt und kein Schalter verändert.

Eine Veröffentlichung/Wiederherstellung kann bereits laufende Docker-Container mit veralteten `extra_hosts` wiederbringen. Beim realen ersten Textversuch zeigte sich genau das: gültiges CA-Bundle und auflösbarer Proxyname, aber eine alte Proxyadresse, dadurch 15-Sekunden-ConnectTimeouts in API und Worker, während derselbe kostenlose Hostabruf HTTP 200 lieferte. `configure-cloud.py` neu ausführen und ausschließlich gesperrte API/Worker ohne Build und ohne Datenvolumenänderungen neu erstellen. Danach kostenlose Prüfungen wiederholen. Den Versuch niemals blind kostenpflichtig wiederholen; bereits konservativ belastete Kosten bleiben bis belastbarer Abrechnungsevidenz erhalten.

`scripts/provision-pricing.py --source "$PRIVATE_VERIFIED_PRICE_SOURCE" --sha256 "$INDEPENDENT_PRICE_SHA256" --operator-verified` installiert einen freigegebenen Vertrag unveränderlich im vorhandenen Preisvolume. Die normale Anwendung behält ihren Read-only-Mount. Der Installationscontainer hat kein Netzwerk, läuft als UID 10001 und erhält ausschließlich das Preisvolume beschreibbar. Ein vorhandener identischer Vertrag wird beibehalten; ein abweichender Hash oder ungeeignete/abgelaufene Metadaten führen zum Abbruch. Das Skript aktiviert und startet keinen Dienst neu. `--operator-verified` ersetzt keine tatsächliche Prüfung der offiziellen Preise und Anfrageobergrenzen.

Für einen kontrollierten privaten Betreiberlauf bleibt die öffentliche API vollständig gesperrt. Nur der Worker erhält nach Freigabe einen aktuellen fest gebundenen Preisvertrag und die erforderlichen Laufzeitflags; die private Operator-CLI reicht genau den freigegebenen Auftrag über die normale Datenbankwarteschlange ein. Private Eingaben, Zustand und Audit liegen mit UID 10001 und Modus 0700/0600 unter einem getrennten Betreiberverzeichnis. Keine Tokens oder Cookiewerte protokollieren. Nach terminalen Jobs und leerer Warteschlange zuerst persistenten `STOP_GENERATION` setzen, dann Worker ohne Build auf `PROVIDER_ENABLED=false`, `BUDGET_APPROVED=false`, `GLOBAL_KILL_SWITCH=true` zurücksetzen. Medien, Sitzungen und Kostenkonten dabei erhalten. Solche Operatorartefakte unterliegen einem gesondert kontrollierten Aufbewahrungs-/Löschplan und sind keine öffentliche Freigabe.

## Aktueller Authentifizierungsblocker

Ein zweiter ausschließlich vom Lead eingereichter Initialversuch scheiterte am Responses-Aufruf mit HTTP 401 und dem endlichen Fehlercode `invalid_api_key`. Die konservative Gesamtbelastung beträgt danach 20 Cent, Reservierungen und laufende Aufträge jeweils 0; beide fehlgeschlagenen Zustände blieben erhalten. Dieser Stand ist keine behauptete tatsächliche Anbieterrechnung. Es erfolgte keine weitere kostenpflichtige Wiederholung.

Die kostenlose Diagnose ist konkret: GET `/v1/models` liefert HTTP 200 auch ohne Authorization und mit absichtlich ungültigem Bearer. Dagegen liefert POST `/v1/responses` mit leerem JSON ohne Modell/Eingabe HTTP 401 `invalid_api_key`, sowohl auf dem Host als auch im Worker. Dieser ungültige Diagnoseaufruf konnte keine Generierung anfordern. Die API-/Worker-Bindung entspricht per internem konstantzeitlichem Vergleich dem aktuellen Hostwert; weder Werte noch Hashes wurden ausgegeben. Es gibt keinen abweichenden Anwendungspfad oder Authorization-Header.

Die bestehende Vault-Anforderung ist bereits auf `STUDIO_OPENAI_API_KEY` und `api.openai.com` gebunden. Der sichere Wert dieser **bestehenden** Bindung muss auf Vollständigkeit/Gültigkeit geprüft werden. Ist der Vault-Wert nachweislich richtig, muss die Weitergabe durch die Plattform repariert werden. Diese Beobachtungen erlauben keine unbelegte Entscheidung zwischen falschem gespeicherten Wert und fehlerhafter Weitergabe; sie rechtfertigen weder einen zusätzlichen Schlüssel noch eine weitere Domainanforderung. Keine Schlüsselwerte in Chat oder Logs übertragen. Öffentliche API und Worker bleiben false/false/true und der persistente STOP bleibt gesetzt.
