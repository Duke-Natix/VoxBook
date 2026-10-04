# VoxBook – Entwurf Datensicherheit für Google Play

Stand: 4. Oktober 2026

Dieser Entwurf basiert auf VoxBook 1.4.0 und muss vor der Einreichung noch einmal gegen die tatsächlich hochgeladene Play-Version geprüft werden.

## Werden Nutzerdaten erhoben oder weitergegeben?

Nach aktuellem Stand: **Nein**, soweit Google Play unter „Erhebung“ die Übertragung von Nutzerdaten vom Gerät weg versteht.

VoxBook verarbeitet folgende Inhalte lokal auf dem Gerät:
- vom Nutzer ausgewählte PDF- und Textdateien;
- Mikrofonaufnahmen für eigene Stimmprofile;
- gespeicherte Stimmprofile;
- Lesepositionen und Sammlungseinträge;
- App-Einstellungen;
- aktuellen Hörbuch-Wiedergabestand für Mediensteuerung und Android Auto.

Diese Inhalte werden nicht an einen VoxBook-Server übertragen.

## Netzwerkzugriffe

VoxBook benötigt Netzwerkzugriff für den Download lokaler Sprachmodelle. VoxBook 1.4.0 besitzt keinen eigenen APK-/Selbst-Updater und fordert keine Berechtigung zum Installieren unbekannter Apps an. App-Updates werden ausschließlich über Google Play verwaltet.

Modelldownloads erfolgen über HTTPS. Externe Hosting-Dienste können dabei die üblichen technischen Verbindungsdaten wie die IP-Adresse sehen.

## Android Auto

VoxBook stellt Android Auto grundlegende Medienmetadaten und Transportsteuerungen für das aktuelle Hörbuch bereit. Dokumentinhalte und Stimmaufnahmen werden dadurch nicht an einen VoxBook-Server übertragen.

## Mikrofon

Mikrofonzugriff ist optional und wird nur benötigt, wenn der Nutzer bewusst ein eigenes Stimmprofil aufnimmt. Die Aufnahme wird lokal gespeichert und lokal für die Spracherzeugung verwendet.

## Dateien

VoxBook verwendet den Android-Dateiauswahldialog für die vom Nutzer ausgewählten PDF-/Textdateien. Es wird kein allgemeiner Vollzugriff auf den Gerätespeicher benötigt.

## Konten

VoxBook besitzt kein eigenes Benutzerkonto-System. Daher gibt es kein VoxBook-Konto und keine serverseitigen Kontodaten zu löschen.

## Werbung / Analytics

Nach aktuellem Stand enthält VoxBook kein eigenes Werbe-SDK und keine absichtlich eingebundene Nutzungsanalyse oder Werbe-ID-Verarbeitung.

## Antworten für die Play Console – Arbeitsentwurf

- Erhebt oder teilt die App erforderliche Arten von Nutzerdaten? **Nein**, sofern die finale Play-Version keine zusätzlichen SDKs oder Telemetrie enthält.
- Werden Dokumente oder Mikrofonaufnahmen vom Gerät übertragen? **Nein**.
- Enthält die App Werbung? **Nein**.
- Gibt es Nutzerkonten? **Nein**.
- Verwendet die App einen eigenen APK-Updater? **Nein**.
- Datenschutzrichtlinie: `https://github.com/Duke-Natix/VoxBook/blob/main/PRIVACY.md`

Vor dem Absenden muss insbesondere noch einmal geprüft werden, ob alle eingebundenen Bibliotheken in der finalen AAB-Version eigenständig Daten übertragen. Dieser Entwurf ist keine automatische Google-Play-Freigabe.