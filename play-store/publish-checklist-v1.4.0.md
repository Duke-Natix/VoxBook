# VoxBook 1.4.0 – Google Play Veröffentlichungs-Checkliste

## Technischer Release

- App-ID: `com.varoxan.voxbook`
- Version: `1.4.0`
- VersionCode: `40`
- Target SDK: Android 16 / API 36
- Release-Format: Android App Bundle (`.aab`)
- Google-Play-Updates: ja
- Eigener APK-/Selbst-Updater: nein
- `REQUEST_INSTALL_PACKAGES`: nein
- Android Auto: MediaBrowserService + MediaSession + `automotive_app_desc.xml`
- Native ARM64-Bibliotheken: 16-KB-Prüfung im Release-Workflow
- Datenschutzerklärung: `https://github.com/Duke-Natix/VoxBook/blob/main/PRIVACY.md`

## Verkauf

- App von Anfang an **kostenpflichtig** veröffentlichen
- Gewünschter Basispreis: **1,20 €**
- Kein Abo
- Keine In-App-Käufe vorgesehen
- Keine Werbung vorgesehen

Hinweis: Den eigentlichen App-Preis setzt man in der Google Play Console unter **Produkte > App-Preise**. Google berechnet daraus lokale Preise und berücksichtigt je nach Markt Steuern und Preismuster.

## Angaben, die der Entwickler in der Play Console bereitstellen/bestätigen muss

1. Verifiziertes Google-Play-Entwicklerkonto.
2. Google-Zahlungsprofil / Händlerkonto für kostenpflichtige Apps, inklusive Auszahlungs-/Steuerangaben.
3. Öffentlicher Entwicklername.
4. Support-/Kontakt-E-Mail für den Store-Eintrag.
5. Gewünschte Vertriebsländer/Regionen.
6. Zielgruppe: VoxBook ist eine allgemeine Hörbuch-/Reader-App und nicht speziell für Kinder entwickelt. Die konkrete Altersauswahl muss in der Play Console bestätigt werden.
7. Fragebogen zur Altersfreigabe.
8. App-Zugriff: kein Konto/Login erforderlich.
9. Werbung: nein.
10. Data-Safety-Angaben anhand `play-store/data-safety-de-DE.md` prüfen und bestätigen.
11. Android-Auto/Car-Qualitätsangaben und Tests bestätigen.

## Store-Eintrag / Assets

Erforderlich bzw. für den Launch vorzubereiten:

- App-Name: `VoxBook`
- kurze Beschreibung
- vollständige Beschreibung
- Play-Store-App-Icon: 512 × 512 PNG
- Feature Graphic: 1024 × 500 PNG/JPEG
- mindestens 2 Smartphone-Screenshots
- optional weitere Screenshots, z. B. Stimmen, PDF-Ansicht, Player und Android Auto

Vorhandene Textentwürfe liegen im Ordner `play-store/`.

## Empfohlener Ablauf

1. Finales `VoxBook-1.4.0-play.aab` aus dem erfolgreichen Release-Workflow verwenden.
2. Neue App in Play Console mit Paket `com.varoxan.voxbook` anlegen.
3. Play App Signing aktivieren und AAB hochladen.
4. Store-Eintrag und Assets ausfüllen.
5. Datenschutz, Data Safety, Zielgruppe, Altersfreigabe, App-Zugriff und Werbeangabe abschließen.
6. Händler-/Zahlungsprofil abschließen.
7. App als **kostenpflichtig** festlegen und Basispreis **1,20 €** setzen.
8. Android-Auto-Qualitätsprüfung durchführen.
9. Zuerst internen/geschlossenen Test veröffentlichen und anschließend Produktion einreichen.
