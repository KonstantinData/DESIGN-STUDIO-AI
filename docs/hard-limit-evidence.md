# Nachweis des Anbieterlimits

Am 18. Oktober 2026 hat der Auftraggeber im Chat einen Screenshot aus „Project Settings → Limits“ übermittelt. Sichtbar sind:

- „Project spend limit“ mit „Limit enforced“;
- ein Verbrauch von 0,00 USD bei einem Limit von 25,00 USD;
- „Requests will start to fail when limit is reached“;
- ein davon getrennt konfigurierter Spend Alert.

Dies belegt anhand des vom Auftraggeber bereitgestellten Screenshots die aktive Erzwingung eines 25-USD-Limits für das gezeigte Projekt. Es ist keine unabhängig ausgeführte Anbieterabfrage. Der Projektname und die Bindung eines API-Schlüssels sind im Screenshot nicht sichtbar. Vor dem ersten kostenpflichtigen Aufruf muss der sicher hinterlegte Schlüssel dem vorgesehenen Projekt „Design-Studio-AI“ zugeordnet sein.

Unabhängig davon hat der Auftraggeber für den Abnahmelauf ausdrücklich höchstens **5 USD** freigegeben. Das 25-USD-Projektlimit erweitert diese Freigabe nicht. Anwendungsseitig gelten höchstens 500 US-Cent einschließlich laufender Reservierungen. Ein vollständiger 15-Bilder-Lauf ist mit den gegenwärtigen konservativen Reservierungsobergrenzen ohne belegten Abrechnungsabgleich oder sicher verifizierte niedrigere Obergrenzen nicht innerhalb dieses Rahmens nachgewiesen.

Es wurde aufgrund des Screenshots kein kostenpflichtiger Aufruf ausgelöst und kein Anbieter aktiviert. Der Nachweis enthält keine Geheimnisse. Die spätere Betreiberprüfung von Projektbindung und Gültigkeit ist gesondert zu dokumentieren; ein frei gesetzter Zeitstempel ersetzt diese Prüfung nicht.

## Ergänzung am 19. Oktober 2026

Der Auftraggeber hat ausdrücklich bestätigt, dass sowohl der hinterlegte API-Schlüssel als auch der Screenshot mit dem erzwingenden 25-USD-Limit aus dem Projekt „Design-Studio-AI“ stammen. Dies ist eine zugeordnete Betreiberbestätigung; die normale Modell-API liefert selbst keinen Projektnamen. Der Schlüssel ist inzwischen über die veröffentlichte Umgebung sicher verfügbar. Ein authentifizierter Abruf von `/v1/models` aus dem Anwendungscontainer ergab HTTP 200 und listete die vorgesehenen Modelle.

Die Projektzuordnung ist damit auf Grundlage der Betreiberbestätigung dokumentiert. Weiterhin unverändert gelten die separate 5-USD-Lauffreigabe, Reservierung laufender Kosten, Prüfung sicherer Modellkostenobergrenzen und die übrigen Produktgates. Die Bestätigung allein hat keine kostenpflichtige Generierung gestartet.
