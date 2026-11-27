# Lotus Exige S2 — Interaktive 3D-Explosionsansicht

Eine realistische, interaktive **3D-Explosionszeichnungs-Webseite (Interactive 3D Technical Teardown)** des **Lotus Exige S2** im Stil eines dunklen Luxus-Showrooms, umgesetzt mit **Vite**, **Three.js** und einer reproduzierbaren **Blender-Python-Pipeline**.

- **Live-Demo:** https://threep79.github.io/lotus-exige-s2-3d/
- **Repository:** https://github.com/Threep79/lotus-exige-s2-3d

---

## Features

- **Freie 3D-Showroom-Kamera & Cockpit-Ansicht:** 360°-Rotation mit weichem Damping, stufenloser Zoom, Panning, Boden-Kollisionsschutz, sanfte Kamerafahrten bei Bauteil-Isolation sowie direkter Wechsel in die **Fahrer-Cockpit-Ansicht (POV)**.
- **Direkt anklickbare Karosserie-Elemente:** Per Klick direkt auf dem 3D-Modell (oder über das Bedienpanel) lassen sich **Fahrer- & Beifahrertür** an ihren Scharnieren öffnen, die **Motorhaube samt Kofferraum-Fach** aufklappen, die **Front-Serviceklappen** (Kühlerzugang) öffnen sowie das **Hardtop-Dach inkl. Dach-Lufthutze** einzeln abnehmen.
- **Mehrstufiges Explosionssystem (0 % – 100 %):** Stufenloser Slider und Schnellwahl-Presets (*Montiert*, *Teilexplosion*, *Voll zerlegt*) über alle 11 technischen Baugruppen hinweg:
  - Front-Clamshell & Lichter (`GRP_Karosserie_FrontClam`)
  - Heck-Clamshell & Motorabdeckung (`GRP_Karosserie_HeckClam`)
  - Türen Links/Rechts inkl. Spiegel & Scheiben (`GRP_Karosserie_Tueren`)
  - Hardtop-Dach & Dach-Lufthutze (`GRP_Karosserie_Dach`)
  - Aerodynamik-Paket: Heckflügel & Heckdiffusor (`GRP_Aerodynamik`)
  - 4 einzeln adressierbare Räder (`GRP_Raeder`)
  - 4 gelochte Bremsscheiben & Bremssättel (`GRP_Bremsen`)
  - 4 Doppelquerlenker-Aufhängungen mit Bilstein/Eibach-Federbeinen (`GRP_Fahrwerk`)
  - Quer eingebauter 1,8-L-Toyota-2ZZ-GE-Kompressormotor inkl. Ladeluftkühler, 6-Gang-Getriebe & Abgasanlage (`GRP_Motor_Antrieb`)
  - Cockpit mit Schalensitzen, Lenkrad, Armaturen & gefräster Pedalerie (`GRP_Interieur`)
  - Extrudiertes Aluminium-Monocoque-Chassis als zentraler ruhender Anker (`GRP_Chassis`)
- **Live-Konfigurator:** 6 originale Lotus-Lackfarben mit physikalischem Clearcoat (*Phantom Black Metallic*, *British Racing Green*, *Krypton Green*, *Solar Yellow*, *Ardent Red*, *Chrome Orange*) und 4 Felgen-Finishes (*Satin Schwarz*, *Silber Metallic*, *Bronze / Gold*, *Gunmetal*).
- **Ansichtsmodi:** **Realistisch** (PBR), **Drahtgitter** (Wireframe) und **Röntgen** (Fresnel X-Ray mit hervorgehobener Innenmechanik).
- **Studio-Beleuchtung:** Wechsel zwischen 3 CC0-HDRIs von Poly Haven (*Dark Studio*, *Softbox*, *Nacht-Halle*) inkl. Live-Belichtungsregler (*Exposure*).
- **Bauteil-Steuerung & 3D-Info-Hotspots:** Ein-/Ausblenden, Bauteil-Isolation im Ghost-Modus sowie 6 dynamisch mitbewegte 3D-Hotspots mit technischen Eckdaten des Lotus Exige S2.

---

## Lokale Entwicklung & Build

Voraussetzung: **Node.js** (>= 20) und **npm**.

```bash
# Abhängigkeiten installieren
npm install

# Entwicklungsserver starten
npm run dev

# Produktions-Build erstellen (Ausgabe in ./dist)
npm run build

# Produktions-Build lokal testen
npm run preview
```

Die 3D-Asset-Aufbereitung in Blender ist über [`scripts/blender/build_exige_s2.py`](scripts/blender/build_exige_s2.py) dokumentiert; das optimierte Draco-GLB (`1,92 MB`) liegt direkt unter `public/models/lotus_exige_s2.glb`.

---

## Automatisches GitHub-Pages-Deployment

Das Projekt enthält den Workflow [`.github/workflows/deploy.yml`](.github/workflows/deploy.yml). Bei jedem Push auf `main` baut GitHub Actions automatisch das Vite-Projekt (`base: '/lotus-exige-s2-3d/'`) und veröffentlicht `./dist` auf **GitHub Pages**.

---

## Lizenzen & Credits

Alle verwendeten Assets und Bibliotheken sind kostenlos und frei lizenziert:

| Asset / Komponente | Autor / Quelle | Lizenz | Link |
| :--- | :--- | :--- | :--- |
| **2009 Lotus Exige S** (Karosserie, Räder & Cockpit-Basis) | `supercarmodels` (Sketchfab) | **CC Attribution (CC BY 4.0)** | https://sketchfab.com/3d-models/0cb63fb6d4d4459f8cd5bcb69b5fbe84 |
| **Car Disc Brake** (Gelochte Bremsscheiben & Bremssättel) | `joko_p` (Sketchfab) | **CC Attribution (CC BY 4.0)** | https://sketchfab.com/3d-models/9e2440a2fa624b31abd0963902217407 |
| **Wooden Studio 17** (`dark_studio.hdr`) | Alexander Scholten (Poly Haven) | **CC0 1.0 (Public Domain)** | https://polyhaven.com/a/wooden_studio_17 |
| **Monochrome Studio 03** (`softbox_showroom.hdr`) | Grzegorz Wronkowski (Poly Haven) | **CC0 1.0 (Public Domain)** | https://polyhaven.com/a/monochrome_studio_03 |
| **Dresden Station Night** (`night_hall.hdr`) | Greg Zaal (Poly Haven) | **CC0 1.0 (Public Domain)** | https://polyhaven.com/a/dresden_station_night |
| **Chassis, Fahrwerk & 2ZZ-GE-Kompressor-Baugruppen** | Prozedural erstellt per Blender Python (`build_exige_s2.py`) | Eigene Projektarbeit (MIT) | — |
| **Three.js & Draco Decoder / Vite** | mrdoob / Google Draco / Evan You | **MIT / Apache-2.0** | https://threejs.org / https://vite.dev |
