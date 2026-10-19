# Sicherheitsgrenzen und Freigabe

## Schutzmodell

Anonyme Nutzung ersetzt keine Zugriffskontrolle. Jede private Operation benötigt gültige Sitzungsberechtigung und serverseitig aus dem tatsächlichen Host bestimmten Tenant. Fortsetzungstokens müssen hochentropisch und widerrufbar sein; sie gehören weder in Serverlogs noch in öffentliche URLs. Fremde Tenant-IDs, Medien-IDs oder Revisionen dürfen keinen Zugriff ermöglichen. Caddy leitet den tatsächlichen Host einschließlich Port für Origin-Prüfungen weiter; `X-Forwarded-Host` ist keine Tenant-Quelle. API/DB/Worker haben keine veröffentlichten Ports. Proxy-TLS und echte Host-Allowlist sind vor Freigabe zu prüfen.

Same-Origin vermeidet eine allgemeine CORS-Freigabe. Mutationen brauchen korrekte Origin-/CSRF-Kontrolle, Cookies passende Secure-/HttpOnly-/SameSite-Einstellungen. CSP erlaubt Turnstile explizit und sperrt Fremdframes; die reale Integration muss im Browser abgenommen werden. Uploads benötigen Größen-, Typ-, Dekodierungs- und Pixelgrenzen, Entfernung unerwünschter Metadaten, private Speicherung und eindeutige Fehler vor kostenpflichtigen Bildern. Dateitypen oder Benutzernamen dürfen keine Pfade bestimmen.

## Schlüssel und Kosten

`.env` ist privat und ignoriert; `.env.example` enthält keine Geheimnisse. Docker-Buildkontext schließt `.env*`, Git, Laufzeit- und private Daten aus. Public Site-Key ist kein Server-Secret. Keine Tokens, Prompts oder Bilddaten loggen. Der Provider bleibt ohne Schlüssel und ausdrücklich bestätigte Budgetfreigabe gesperrt. Jeder kostenverursachende Aufruf braucht eine konservative Reservierung, Tenant-/Globalstop und atomare Quoten. Ein Client kann keinen Freigabeschalter setzen.

Reservierungen sind eine interne Schutzschicht und kein Ersatz für einen belegten externen Hard-Stop. Technische Fehlversuche können echte Anbietergebühren verursachen. Vor PoC müssen gültige Preise, reservierte parallele Aufträge und externer Kill-Switch zusammen getestet werden. Keine bezahlten Calls als beiläufiger Infrastrukturtest.

## Betrieb und offene Nachweise

Containerdateisysteme sind schreibgeschützt, Anwendung und Caddy laufen als unprivilegierte Benutzer mit entfernten Linux-Capabilities. Private Volumes benötigen verschlüsselte Hostdatenträger und gesicherte Backups. Docker-Socket ist administrativer Vollzugriff und gehört niemals in Anwendungskontainer. Secrets in einer privaten Compose-Umgebung sind für Docker-Administratoren sichtbar; für Mehrbenutzerproduktion gehört die Provisionierung in einen kontrollierten Secret-Manager.

Keine öffentliche Freigabe allein aufgrund dieses Dokuments: erforderlich sind negative Mandantentests, reale Botprüfung, Budget-/Lasttests, sichere Wiederaufnahme, sofortige Löschung, 30-Tage-Bereinigung samt Backups und externen Empfängern, ein isolierter Restoretest, TLS-/Hostprüfung sowie menschliche Bildabnahme. Konkrete Ergebnisse und Blocker stehen im Abnahmeprotokoll. Sicherheitslücken nicht mit aktivierten Testschlüsseln, deaktivierter TLS-Prüfung oder Demoantworten verdecken.

Die Datenbankanwendung verwendet `studio_app` als Nicht-Superuser ohne CREATEDB, CREATEROLE, REPLICATION oder BYPASSRLS. Ein separates zufälliges Administratorkennwort ist nur für PostgreSQL-Bootstrap vorgesehen. App/Migrationen teilen derzeit Schemaownership; eine zusätzliche Trennung von Migrations- und Runtime-Rolle ist weitere Härtung.
