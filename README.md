# DESIGN STUDIO AI

Mandantenfähiges Küchenstudio: Ein Textimpuls, Raumfoto oder Grundriss soll drei eigenständige, tatsächlich gerenderte Konzepte auf gemeinsamer Raumgrundlage ergeben. Die Nutzung bleibt ohne Registrierung und Kontaktdaten möglich; Beratung ist freiwillig.

## Verbindliche Grundlage

Die [Ausführungsregeln](docs/ausfuehrungsregeln.md) bestimmen Produktverhalten, Datenschutz, Kostenkontrolle und Abnahme. Die Cloud arbeitet im vorhandenen Checkout; die im Dokument genannten Windows-Verzeichnisse sind historische lokale Pfade und werden hier nicht angelegt oder gelöscht.

## Umsetzungsstand und Freigabe

Dies ist eine laufende Implementierung. Eine Produktionsfreigabe setzt echte Bilder, den dokumentierten 15-Bilder-Lauf, menschliche Raumprüfung und sämtliche Sicherheits- und Betriebsgates voraus. Technische Tests mit kontrollierten Anbieterantworten ersetzen diese Abnahme nicht. Fehlende Schlüssel oder Budgetnachweise müssen Anbieteraufrufe sperren.

Schlüssel gehören ausschließlich in die private Serverumgebung, niemals in Git oder den Browser. Kostenpflichtige Prüfungen erfordern eine gesonderte Freigabe des Laufrahmens und den Nachweis des richtigen Anbieterprojekts samt verbindlichem Kostenstopp.

## Dokumentation

- [API-Vertrag](docs/api.md)
- [Betrieb und Einrichtung](docs/operations.md)
- [Sicherheit und Datenschutz](docs/security.md)
- [Abnahmematrix und Nachweise](docs/acceptance.md)

Die Abnahmematrix unterscheidet bestandene technische Prüfungen von noch blockierten Produkt- und Produktionsnachweisen.

Der lokale Containerstart wurde mit `./scripts/start-local.sh` geprüft (Docker/Compose, Python3; vorhandene private Einstellungen bleiben erhalten). API, Worker, PostgreSQL und Same-Origin-Proxy werden gestartet. Anbieteraufrufe bleiben ohne die dokumentierten Freigaben gesperrt. Betriebsanleitung: [docs/operations.md](docs/operations.md).
