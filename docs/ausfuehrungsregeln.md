# DESIGN STUDIO AI – verbindliche Ausführungsregeln

**Zielrepository:** `D:\Git-GitHub\Repositories\DESIGN-STUDIO-AI`

**Produkt:** eigenständige, mandantenfähige Anwendung; `mein-kuechenexperte.de` ist der erste Tenant.
**Status:** Umsetzungsvorgabe, keine Freigabe oder Behauptung einer bereits funktionierenden Anwendung.

## 1. Nicht verhandelbares Produktziel

Ein Mensch gibt **einen einzigen Impuls** ein: einen Satz, ein Raumfoto oder einen Grundriss. Ohne Pflichtfragebogen erzeugt das System **drei tatsächlich gerenderte, räumlich zusammenhängende und sichtbar unterschiedliche Küchenkonzepte**. Jedes enthält ein Bild, einen zum Bild passenden dreizeiligen Kuratierungsbericht und eine ehrliche Einordnung der Annahmen. Die Konzepte treffen einzeln ein, sobald sie fertig sind. Der Mensch kann eines auswählen, gezielt verändern, frühere Versionen ansehen und Bilder herunterladen. Der komplette Studio-Nutzen ist für Kunden kostenlos und ohne Registrierung oder Kontaktdaten verfügbar. Nur eine ausdrücklich gewünschte Beratung führt zu einem freiwilligen Kontaktformular.

**Eine Demo, SVG-Illustrationen, Platzhalterbilder, drei `queued`-Jobs, ein API-Gerüst oder bestandene Unit-Tests sind kein Produktergebnis.** Diese Dinge dürfen niemals als „live testbare Anwendung“, fertige Galerie oder Erfüllung der vier Grundsätze bezeichnet werden.

## 2. Die harten Sam-Altman-Regeln – Wortlaut des Auftraggebers

Die Grundsätze von Sam Altman lassen sich auf **vier fundamentale Säulen** zusammenfassen, die den Übergang vom klassischen Software-Zeitalter in das *Intelligence Age* beschreiben:

1. **Agentische Autonomie („Compute over Chat“)**

   - **Prinzip:** KI ist kein passives Formular und kein sequenzieller Frage-Antwort-Chatbot, sondern eine **autonome kognitive Infrastruktur**.

   - **Anwendung:** Der Mensch gibt nur noch den initialen kognitiven Impuls (einen Satz, eine Idee oder ein Foto). Die KI übernimmt die komplette Schwerarbeit im Hintergrund, trifft fundierte Annahmen und liefert fertige, komplexe Arbeitsergebnisse, anstatt den Nutzer mit Rückfragen zu belasten.

2. **Skalierung durch Rechenleistung („Massive Parallelität“)**

   - **Prinzip:** Wenn kognitive Leistung im Überfluss vorhanden ist, nutzt man Rechenleistung (Compute), um **Optionenraum und Qualität radikal zu vergrößern**.

   - **Anwendung:** Statt in der gleichen Zeit *einen* Kompromiss-Entwurf über mühsame Dialoge abzufragen, berechnet das System parallel mehrere vollständige, konkurrierende Konzepte gleichzeitig.

3. **Mensch-KI-Synergie („Superintelligenz als Hebel“)**

   - **Prinzip:** KI ersetzt nicht den Wert menschlicher Expertise, sondern befreit den Menschen von der kognitiven Routine und Vorbereitung.

   - **Anwendung:** Die KI übernimmt 100 % der visuellen und strukturellen Ideengenerierung. Der menschliche Experte kommt an der Schnittstelle ins Spiel, wo echter Mehrwert entsteht: **Vertrauen, individuelle Anpassung, persönliche Führung und reale Umsetzung.**

4. **Hürdenfreie Intelligenz („Value First“)**

   - **Prinzip:** Der Zugang zu Intelligenz muss so reibungsarm und unmittelbar wie möglich gestaltet sein.

   - **Anwendung:** Ergebnisse entstehen sofort, bedingungslos und ohne Barrieren (keine Registrierungspflicht, keine Kontaktdaten-Schranken für den ersten Mehrwert). Der Nutzer erlebt die Leistungsfähigkeit des Systems, bevor eine Gegenleistung gefordert wird.

**Operative Konsequenz:** Der Auftrag startet unmittelbar nach dem Impuls; fertige Bilder erscheinen progressiv. „Sofort“ ist kein erfundenes Sekundenversprechen. Fehlende Informationen werden als überprüfbare Annahmen verarbeitet, ungeeignete Uploads ehrlich abgewiesen. Bot-Schutz und Kostenkontrolle dürfen keinen Registrierungs- oder Kontaktzwang erzeugen.

## 3. Harte Architekturgrenzen

1. **Neuanfang ohne Altcode:** Der bisherige lokale Prototyp `C:\Users\konst\Documents\Codex\2026-10-18\new-chat\Design-Studio-AI` ist ausschließlich historische Evidenz. Keine Dateien, Mock-Logik, SVG-Galerie, Datenbank oder Architekturentscheidung daraus automatisch übernehmen. Übernahmen bedürfen einer neuen fachlichen Begründung und Prüfung gegen diese Datei. Das neue Repository bekommt eine eigene Git-Historie, eigene Tests und einen eigenen Deploy-Pfad.
2. **Zwei Eingabepfade:** Text/Inspiration erzeugt einen plausiblen **gemeinsamen Beispielraum**. Foto und Grundriss werden als unterschiedliche Quellen analysiert; sichtbare Konturen, Fenster, Türen und Blickrichtung dürfen nicht stillschweigend umgebaut werden. Unleserliche Eingaben stoppen vor kostenpflichtiger Bildgenerierung und bieten neues Bild oder Beispielraum an.
3. **Briefing vor Bildern:** Ein versioniertes Master-Briefing entsteht vor den drei Bildaufträgen. Es trennt (1) globales Raumprofil mit Provenienz `USER_GIVEN`, `DETECTED`, `ASSUMED`, `UNKNOWN`, (2) globales Nutzerbriefing, (3) je ein Konzeptprofil A/B/C und (4) unveränderliche Revisionen pro Konzept. Keine bestätigten Maße, Anschlüsse oder Himmelsrichtungen erfinden. Alle drei Initialbilder referenzieren dieselbe Raumversion.
4. **Drei konkurrierende Konzepte:** A betont Ergonomie und Laufwege, B Licht und Raumwirkung, C Stauraum und Ordnung. **Alle drei** müssen funktional, ästhetisch und plausibel sein. Sie dürfen nicht nur verschiedene Farben desselben Entwurfs zeigen.
5. **Gezielte Änderungen:** Oberflächenänderungen erhalten Raum- und Möbelanordnung als Zielvorgabe; Aufbauänderungen aktualisieren ausschließlich das gewählte Konzeptprofil. Beide Varianten starten bei der Abnahme unabhängig vom ursprünglichen Konzept A. Eine bewusste globale Raumkorrektur erzeugt eine neue Raumversion und kennzeichnet ältere Entwürfe als auf vorheriger Grundlage erstellt. Zurückspringen in vorhandene Revisionen erzeugt keinen Bildauftrag.
6. **Ehrliche Ergebnisse:** Jeder Entwurf trägt den passenden Hinweis: Beispielraum zur Inspiration oder Designvisualisierung auf Basis sichtbarer Raummerkmale. Keine Aussage über exaktes Aufmaß, technische Freigabe, Herstellerverfügbarkeit oder garantierte Bildtreue. Keine erfundenen Prozent-Scores. Ein kritischer Raumfehler wird als Fehler behandelt, nicht als leichte Abweichung.
7. **Kuratierung:** Je fertigem Konzept genau drei inhaltliche Zeilen: architektonischer Ansatz, Design-Highlight und Material-Harmonie. Die Aussagen werden gegen das sichtbare Bild geprüft.

## 4. Kostenfreiheit, Bot-Schutz und Budget

- Beim ersten Tenant kosten **Start mit drei Bildern, fünf erfolgreiche gezielte Änderungen, Ansicht, Rollback und unbegrenzte Downloads** den Kunden 0 €. Registrierung, E-Mail und Telefonnummer sind dafür nie Voraussetzung. Nach Verbrauch des Änderungskontingents bleiben bestehende Ergebnisse nutzbar; nur neue kostenverursachende Generierungen stoppen.
- Serverseitige Bot-Challenge, Session- und Quotenlimits, Idempotenz, Parallelitätsgrenze, konservative Reservierung **vor** jedem Anbieteraufruf, Tenant- und globaler Kostenstopp sind Pflicht. Kein invasives Fingerprinting. Ein technischer Fehler verbraucht kein Nutzer-Änderungsguthaben, seine tatsächlichen API-Kosten werden erfasst. Maximal ein automatischer technischer Wiederholungsversuch je Bild, soweit der Kostenrahmen reicht.
- Das vom Auftraggeber genannte OpenAI-Projektlimit von **25 USD** ist keine implizite Freigabe für einen Testlauf. Vor einem kostenpflichtigen PoC: das aktivierte **Enforce a hard limit** im richtigen Projekt prüfen, einen separaten niedrigeren Laufrahmen festlegen, Reserven für laufende Jobs berücksichtigen und den Kill-Switch testen. Ein bloßer Spend Alert ist kein Kostenstopp. Die Kundenkosten bleiben unabhängig davon 0 €.
- API-Schlüssel ausschließlich serverseitig und außerhalb von Git. Keine Schlüssel, Bearer-Tokens oder privaten Bildinhalte in Client, URL, Repository oder Logs. Ein fehlender Schlüssel oder fehlende Budgetfreigabe verhindert Anbieteraufrufe sichtbar und fehlerehrlich.

## 5. Datenschutz, Mandanten und Übergabe

- Jede Sitzung, jedes Profil, Bild, Job, Revision, Token, Kostenkonto und Handoff wird serverseitig einem Tenant zugeordnet. Der Client kann seinen Tenant nicht durch ein Feld wählen. Mindestens zwei unterschiedlich konfigurierte Tenants und Cross-Tenant-Negativtests sind vor Freigabe Pflicht.
- Uploads und Ergebnisse sind privat. Fortsetzungslinks benötigen hochentropische, widerrufbare Tokens; `noindex` allein schützt keine Daten. Downloads erfordern eine gültige Berechtigung. Anonyme Sessions und temporäre Medien werden nach der festgelegten Frist von 30 Tagen automatisch entfernt; sofortiges Löschen ist möglich. Backups und externe Verarbeiter benötigen ein nachgewiesenes Löschkonzept.
- Die KI spricht im ersten Tenant konsequent mit „Du“ und **über** Konstantin als unabhängigen menschlichen Experten, niemals als Konstantin. Kontaktaufnahme ist freiwillig. Der Handoff überträgt nach ausdrücklicher Auswahl nur **eine konkrete Revision samt erforderlichem Briefing und ausdrücklich gewählten Medien**; keine verworfenen Konzepte oder ganze Historie. Erfolg wird erst nach bestätigter Annahme durch das tenantbezogene Ziel angezeigt.
- `mein-kuechenexperte.de` ist Einstieg und erster Tenant, **nicht** das Produktrepository. Weitere Küchenstudios müssen ohne Kopie des Kernsystems mit eigener Marke, Ansprache, Limits und Übergabeziel anschließbar sein.

## 6. Reihenfolge und messbare Abnahme

1. **Funktionierender vertikaler Textpfad:** Ein realer Textimpuls erzeugt ohne Rückfragen drei echte Bilder im selben Beispielraum, drei passende Kuratierungsberichte, Auswahl, eine Material- und eine Aufbauänderung, Versionswahl und privaten Download. Keine Demo als Ersatz. Einzelne Bilder treffen ein, sobald sie fertig sind; Fehler eines Bildes blockieren die übrigen nicht.
2. **Realer Foto- und Grundrisspfad:** Geeignete Testmedien durchlaufen Qualitätsprüfung, Provenienz, gemeinsame Raumgrundlage und drei echte Entwürfe. Ungeeignete Medien werden vor Bildkosten zurückgewiesen. Sichtbare Fenster, Türen, Wände, Proportionen und Durchgänge werden manuell gegen die Vorlage bewertet.
3. **15-Bilder-PoC:** Je Text, Foto und Grundriss A/B/C plus Material- und Aufbauänderung aus ursprünglichem A. Laufzeit und **tatsächliche** Kosten je Versuch einschließlich Fehlversuchen messen. Kritische Raumfehler einzeln protokollieren. Automatische Bildprüfung nur im Shadow-Modus; die fachliche Abnahme bleibt menschlich.
4. **Produktgates:** Bot- und Lasttest, Kostenstopp, Datenschutz/Löschung, Tenant-Isolation, sichere Fortsetzung, selektiver Handoff, mobile und assistive Bedienung sowie echte Browserprüfung. Jede kritische Abweichung blockiert öffentliche Freigabe, auch wenn Bilder optisch gut aussehen.

**Abnahmeregel:** Ein Fach-Agent meldet eine Funktion erst als fertig, wenn sie mit echten Ergebnissen und überprüfbaren Tests funktioniert. Der Lead System Controller schreibt keinen Anwendungscode, sondern beauftragt Fach-Agenten, überprüft Kosten und Qualität und protokolliert PASS/BLOCKED mit Belegen. Zwischenstände werden als Zwischenstände bezeichnet. Weder ein lokaler HTTP-200-Status noch ein hübscher Mock beweist den Nutzermehrwert.

## 7. Sicherer Projektwechsel

Der vorhandene `OPENAI_API_KEY` liegt nach bisheriger Prüfung in `C:\Users\konst\Documents\Codex\2026-10-18\new-chat\.env.local` **außerhalb** des alten Projektordners. Sein Wert darf nicht in diese Datei oder Chat-Ausgaben übernommen werden. Nach tatsächlicher Anlage des Zielrepositories wird geprüft, ob der Schlüssel zum OpenAI-Projekt `Design-Studio-AI` gehört; dann wird er in eine ignorierte private Serverumgebung am neuen Ziel übernommen. Nur wenn er unbrauchbar ist, wird ein neuer projektspezifischer Schlüssel erstellt und der alte kontrolliert widerrufen. Das 25-USD-Hard-Limit bleibt gesondert zu prüfen.

**Der alte Ordner wird erst gelöscht, nachdem** das neue Ziel am exakten D:-Pfad existiert, diese Ausführungsregeln dort vorliegen, Git und Secret-Ausschluss geprüft sind, der Schlüssel ohne Offenlegung verfügbar ist und ein unabhängiger Funktionstest sowie eine gesicherte Rückfallkopie vorliegen. Die Löschung bezieht sich nur auf den explizit genannten alten Ordner, niemals auf dessen Elternverzeichnis oder die dort liegende `.env.local`.
