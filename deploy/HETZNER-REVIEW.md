# Geschützter Testbetrieb auf 46.225.221.42

Bestätigt: Ubuntu/x86_64, Docker/Compose und certbot vorhanden, Host-nginx betreibt 80/443 und sechs bestehende Sites. Die neue Site heißt `studio.mein-kuechenexperte.de`. Bestehende Sites, Container, Netzwerke und Daten werden nicht ersetzt. Es wurde aus dieser Cloud keine SSH-Verbindung hergestellt und nichts auf dem Server installiert.

Das Archiv enthält den aktuellen Quellcode, keine lokalen Schlüssel, `.env`, Cloud-Proxybindungen, Datenbank, Sitzungen oder Bilder. Der neue Testbetrieb bleibt durch BasicAuth geschützt und kann keine kostenpflichtigen Generierungen starten. Bestehende konservative Kostenexposition **20 Cent von 500 Cent** wird durch eine neue Datenbank nicht aufgehoben; vor jeder späteren Aktivierung ist der maßgebliche Kostenstand separat zu übertragen/abzugleichen. Die bestehende Responses-401-Störung und Produktabnahme bleiben offen.

Jeder Codeblock ist EIN einzelner Terminalbefehl. Zuerst Archiv und zugehörige HETZNER-NGINX-SHA256SUMS vom eigenen Computer in ein neues Verzeichnis auf den Server kopieren (SSH-Zugang und geprüften Hostfingerprint verwenden). Danach dort prüfen:

```sh
sha256sum -c HETZNER-NGINX-SHA256SUMS
```

Ein neues, leeres Ziel verwenden; bei bestehendem Ziel abbrechen:

```sh
test ! -e /srv/design-studio-review && install -d -m 700 /srv/design-studio-review && tar -xzf design-studio-ai-hetzner-nginx-2026-10-19.tar.gz -C /srv/design-studio-review
```

```sh
cd /srv/design-studio-review
```

```sh
python3 scripts/hetzner-preflight.py
```

Die Prüfung ist lesend. Sie blockiert bei Konflikten mit **beiden** Netzen 172.30.74.0/28 und 172.30.75.0/28, belegtem Loopback-Port8788, weniger als12GiB freiem Ziel-Datenträger oder3GiB verfügbarem RAM. Nicht vorhandene Ressourcen werden nicht durch Pruning, Stoppen anderer Projekte oder automatische Paketinstallation freigemacht. Momentaufnahme des Benutzers:22GB frei,5.6GiB RAM verfügbar, keine der beiden Netzkollisionen; vor dem tatsächlichen Start erneut prüfen.

Review-Passwort interaktiv hashen; kein Passwort als Kommandoargument verwenden:

```sh
docker run --rm -it --entrypoint caddy caddy:2.10.2-alpine@sha256:4c6e91c6ed0e2fa03efd5b44747b625fec79bc9cd06ac5235a779726618e530d hash-password
```

Den ausgegebenen bcrypt-Hash privat bereithalten. Der nächste Befehl fragt Benutzernamen und Hash ab, erzeugt unterschiedliche zufällige DB-/Admin-Passwörter und eine private `.deploy.env` mit Modus0600. Kein vorhandener Wert wird überschrieben:

```sh
python3 scripts/hetzner-install.py prepare
```

```sh
python3 scripts/hetzner-install.py start
```

Der Installer baut seriell nur dieses Projekt und startet `design-studio-review`. Er ändert nginx/Firewall nicht, bindet nur127.0.0.1:8788 und erzwingt provider=false, budget=false, kill=true. Er ist für die erste Installation; bestehende Review-Projekte werden durch `prepare` abgewiesen. Wiederholtes `start` wird wegen vorhandener Netze blockiert: danach keinen Installationslauf erzwingen, sondern das vorhandene Projekt gezielt warten.

Ohne Authentifizierung muss folgende lokale Prüfung401 ergeben:

```sh
curl --noproxy '*' -s -o /dev/null -w '%{http_code}\n' -H 'Host: studio.mein-kuechenexperte.de' http://127.0.0.1:8788/
```

## Nur die neue nginx-Site ergänzen

DNS-A `studio` muss auf46.225.221.42 zeigen, zunächst **DNS only**, nicht Cloudflare-proxied. Globale nginx-Real-IP-Einstellungen unverändert lassen. Kandidat HTTP erlaubt zunächst nur lokale App-Anfragen; öffentlich ist lediglich ACME erreichbar. Keine Review-Zugangsdaten über öffentliches HTTP senden.

```sh
test ! -e /etc/nginx/sites-available/design-studio-review && test ! -e /etc/nginx/sites-enabled/design-studio-review && install -d -m 755 /var/www/design-studio-acme && install -m 644 deploy/nginx.studio-http.conf /etc/nginx/sites-available/design-studio-review && ln -s /etc/nginx/sites-available/design-studio-review /etc/nginx/sites-enabled/design-studio-review
```

```sh
nginx -t && systemctl reload nginx
```

Bei einem Validierungsfehler nicht neu laden; nur den neu angelegten Symlink entfernen und Ursache prüfen. Keine anderen Sites löschen. Bestehende Port80/443-Regeln und nginx-Service bleiben bestehen. Der Hostname ist eigenständig, kein Catch-all/default_server.

Zertifikat mit vorhandenem certbot interaktiv beziehen; echte E-Mail/Einwilligung durch Betreiber, keine erfundenen Angaben:

```sh
certbot certonly --webroot -w /var/www/design-studio-acme -d studio.mein-kuechenexperte.de --cert-name design-studio-review
```

Nur nach erfolgreicher Ausstellung: Kandidat sichert zunächst die eigene HTTP-Konfiguration, bindet die tatsächlich ausgegebenen Zertifikatspfade ein, prüft nginx und lädt bei Erfolg neu. Andere Sites bleiben unverändert. Bei Prüfungsfehler wird die eigene HTTP-Datei zurückkopiert und NICHT neu geladen:

```sh
test -r /etc/letsencrypt/live/design-studio-review/fullchain.pem && test -r /etc/letsencrypt/live/design-studio-review/privkey.pem && cp -n /etc/nginx/sites-available/design-studio-review /etc/nginx/sites-available/design-studio-review.http-backup && install -m 644 deploy/nginx.studio-tls.conf /etc/nginx/sites-available/design-studio-review && (nginx -t && systemctl reload nginx || { cp /etc/nginx/sites-available/design-studio-review.http-backup /etc/nginx/sites-available/design-studio-review; false; })
```

```sh
curl -s -o /dev/null -w '%{http_code}\n' https://studio.mein-kuechenexperte.de/
```

Erwartet401 mit gültigem öffentlichen TLS-Zertifikat. Danach im Browser anmelden; Authentifizierung schützt auch API, Downloads und App-Health. Worker-/DB-Health laufen intern. Nach erfolgreicher TLS-Abnahme den auf dieses Zertifikat beschränkten Hook installieren, sofern der Zielname noch frei ist:

```sh
test ! -e /etc/letsencrypt/renewal-hooks/deploy/design-studio-review && install -m 755 deploy/certbot-design-studio-hook.sh /etc/letsencrypt/renewal-hooks/deploy/design-studio-review
```

```sh
certbot renew --cert-name design-studio-review --dry-run --run-deploy-hooks
```

Vorhandenen Renewal-Timer und andere Hooks erhalten. Bei Fehlschlag keine TLS-Prüfung deaktivieren.

## Proxyvertrauen, Grenzen und Rückbau

Host-nginx überschreibt X-Forwarded-For mit `$remote_addr` und entfernt Forwarded/X-Real-IP. Caddy vertraut ausschließlich dem kontrollierten Docker-Gateway172.30.75.1/32, benutzt `{client_ip}` und übergibt an die API. Die API vertraut ausschließlich Caddy172.30.74.2/32. Ein späterer Cloudflare-Proxybetrieb erfordert separat überprüfte echte Client-IP-Konfiguration; nicht einfach DNS auf proxied umschalten. Die isolierte reale nginx→Caddy-Prüfung ist über `scripts/test-hetzner-proxy.py` reproduzierbar; nicht auf dem laufenden Server ausführen, falls Testnetze/Testports kollidieren.

Rückbau: nur die neue Site deaktivieren, `nginx -t` und reload; anschließend nur dieses Projekt stoppen. Datenvolumes erhalten, niemals `down --volumes`, niemals Docker-Prune. Produktionsfreigabe, externe Backups/Löschbelege und reale Bildabnahme sind mit diesem geschützten Testbetrieb nicht erklärt. Keine API-Schlüssel oder Cloud-Proxy-Overlays aus dieser Umgebung auf den Server übertragen.

## Hier ausgeführte Prüfungen

Compose-Konfiguration inklusive harter Kostenabschaltung, gemeinsamem Backend-Image und ausschließlichem Loopback-Port8788 geprüft. Reale isolierte nginx1.28→Caddy2.10.2→Echo-Kette:401 ohne/200 mit Auth, echte Client-IP erhalten, gespoofte Weiterleitungsheader verworfen, untrusted Docker-Peer abgewiesen. HTTPS-nginx-Syntax mit temporärem isoliertem Testzertifikat geprüft; kein öffentliches Zertifikat damit behauptet. Preflight verweigert auf dieser Cloud erwartungsgemäß die bereits belegte Proxy-IPAM. Alle Testcontainer/-netze entfernt, bestehende Anwendung unverändert. Archiv anhand expliziter Quelldateiliste auf Schlüsselmaterial und private Laufzeitdaten geprüft. Serverstart, echte TLS-Ausstellung und öffentliche Browserabnahme müssen auf dem Zielserver erfolgen.
