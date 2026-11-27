import * as THREE from 'three';

export const HOTSPOTS_DATA = [
  {
    id: 'hs_engine',
    nodeId: 'GRP_Motor_Antrieb',
    localOffset: new THREE.Vector3(0.0, 0.34, 0.0),
    badge: 'ANTRIEB & KOMPRESSOR',
    title: '1,8-L-Toyota-2ZZ-GE-Motor',
    description:
      'Quer eingebauter Hochdrehzahl-Vierzylinder mit VVTL-i-Ventilsteuerung (Yamaha-Zylinderkopf), Eaton-M62-Kompressor und obenliegendem Ladeluftkühler.',
    specs: [
      { label: 'Leistung', value: '221 – 243 PS @ 8.000 U/min' },
      { label: 'Drehmoment', value: '215 – 230 Nm @ 5.500 U/min' },
      { label: 'Getriebe', value: '6-Gang C64 Schaltgetriebe' },
      { label: '0 – 100 km/h', value: 'ca. 4,1 – 4,3 s' },
    ],
  },
  {
    id: 'hs_chassis',
    nodeId: 'GRP_Chassis',
    localOffset: new THREE.Vector3(0.0, 0.42, -0.05),
    badge: 'STRUKTUR-MONOCOQUE',
    title: 'Extrudiertes Aluminium-Chassis',
    description:
      'Legendäres, aus stranggepresstem Aluminium epoxidharzgeklebtes und vernietetes Monocoque-Tub – extrem verwindungssteif bei nur 68 kg Eigengewicht.',
    specs: [
      { label: 'Bauweise', value: 'Geklebtes Alu-Monocoque' },
      { label: 'Chassis-Gewicht', value: 'ca. 68 kg' },
      { label: 'Leergewicht', value: 'ca. 935 kg (DIN)' },
      { label: 'Torsionssteifigkeit', value: 'ca. 10.500 Nm/Grad' },
    ],
  },
  {
    id: 'hs_suspension',
    nodeId: 'Fahrwerk_VL',
    localOffset: new THREE.Vector3(0.18, 0.16, 0.0),
    badge: 'FAHRWERK & KINEMATIK',
    title: 'Doppelquerlenker-Fahrwerk',
    description:
      'Rennsporterprobte Einzelradaufhängung mit ungleich langen Doppelquerlenkern rundum, Bilstein-Gasdruckdämpfern und Eibach-Schraubenfedern.',
    specs: [
      { label: 'Konstruktion', value: 'Doppelquerlenker (v/h)' },
      { label: 'Dämpfer / Federn', value: 'Bilstein / Eibach' },
      { label: 'Bereifung VA / HA', value: '195/50 R16 · 225/45 R17' },
      { label: 'Gewichtsverteilung', value: 'ca. 38 % : 62 % (v/h)' },
    ],
  },
  {
    id: 'hs_brakes',
    nodeId: 'Bremse_VL',
    localOffset: new THREE.Vector3(0.06, 0.18, 0.0),
    badge: 'VERZÖGERUNG',
    title: 'Hochleistungs-Bremsanlage',
    description:
      'Gelochte, innenbelüftete Bremsscheiben mit AP-Racing-Zweikolben-Festsätteln vorne und Brembo-Sätteln hinten für maximale Standfestigkeit auf Trackdays.',
    specs: [
      { label: 'Scheiben VA / HA', value: '288 mm gelocht/belüftet' },
      { label: 'Bremssättel VA', value: 'AP Racing Leichtmetall' },
      { label: 'Bremssättel HA', value: 'Brembo Einkolben' },
      { label: 'Assistenz', value: 'Track-kalibriertes ABS' },
    ],
  },
  {
    id: 'hs_aero',
    nodeId: 'Aero_Heckfluegel',
    localOffset: new THREE.Vector3(0.0, 0.12, 0.0),
    badge: 'AERODYNAMIK',
    title: 'Heckflügel, Diffusor & Roof Scoop',
    description:
      'Dach-Lufthutze zur direkten Anströmung des Ladeluftkühlers, gepaart mit Frontsplitter, Unterboden-Diffusor und feststehendem Heckflügel.',
    specs: [
      { label: 'Abtrieb (160 km/h)', value: 'ca. 42 kg' },
      { label: 'Höchstgeschwindigkeit', value: 'ca. 238 – 245 km/h' },
      { label: 'Ladeluft-Zufuhr', value: 'Dach-Lufthutze (Roof Scoop)' },
      { label: 'Unterboden', value: 'Glatt verkleidet + Diffusor' },
    ],
  },
  {
    id: 'hs_interior',
    nodeId: 'GRP_Interieur',
    localOffset: new THREE.Vector3(0.24, 0.34, -0.1),
    badge: 'COCKPIT & LEICHTBAU',
    title: 'Puristisches Fahrer-Cockpit',
    description:
      'Auf Wesentliches reduzierter Innenraum mit tiefen Schalensitzen, unverkleideten Aluminium-Schwellern, gefräster Pedalerie und Momo-Sportlenkrad.',
    specs: [
      { label: 'Sitzposition', value: 'Tief integrierte Schalensitze' },
      { label: 'Lenkung', value: 'Unservounterstützt (direkt)' },
      { label: 'Pedalerie', value: 'Extrudiertes Aluminium' },
      { label: 'Philosophie', value: 'Simplify, then add lightness' },
    ],
  },
];

export class HotspotManager {
  constructor(layerEl, camera, carAssembly, onSelectHotspot) {
    this.layerEl = layerEl;
    this.camera = camera;
    this.carAssembly = carAssembly;
    this.onSelectHotspot = onSelectHotspot;
    this.enabled = true;
    this.activeId = null;

    this.items = [];
    this._tempVec = new THREE.Vector3();
    this._buildPins();
  }

  _buildPins() {
    this.layerEl.innerHTML = '';
    for (const hs of HOTSPOTS_DATA) {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'hotspot-pin';
      btn.dataset.hotspotId = hs.id;
      btn.setAttribute('aria-label', hs.title);
      btn.innerHTML = `
        <span class="hotspot-dot"></span>
        <span class="hotspot-tag">${hs.title}</span>
      `;
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        this.setActive(hs.id);
        if (this.onSelectHotspot) this.onSelectHotspot(hs);
      });
      this.layerEl.appendChild(btn);

      this.items.push({
        data: hs,
        el: btn,
        node: this.carAssembly.getNode(hs.nodeId),
      });
    }
  }

  setEnabled(enabled) {
    this.enabled = enabled;
    this.layerEl.style.display = enabled ? 'block' : 'none';
    if (!enabled) {
      this.setActive(null);
    }
  }

  setActive(id) {
    this.activeId = id;
    for (const item of this.items) {
      item.el.classList.toggle('active', item.data.id === id);
    }
  }

  _isVisibleInHierarchy(obj) {
    let cur = obj;
    while (cur) {
      if (!cur.visible) return false;
      cur = cur.parent;
    }
    return true;
  }

  update() {
    if (!this.enabled) return;
    const width = window.innerWidth;
    const height = window.innerHeight;

    for (const item of this.items) {
      if (!item.node || !this._isVisibleInHierarchy(item.node)) {
        item.el.style.opacity = '0';
        item.el.style.pointerEvents = 'none';
        continue;
      }

      item.node.getWorldPosition(this._tempVec);
      this._tempVec.add(item.data.localOffset);
      this._tempVec.project(this.camera);

      // Behind camera check
      if (this._tempVec.z > 1 || this._tempVec.z < -1) {
        item.el.style.opacity = '0';
        item.el.style.pointerEvents = 'none';
        continue;
      }

      const x = (this._tempVec.x * 0.5 + 0.5) * width;
      const y = (-this._tempVec.y * 0.5 + 0.5) * height;

      item.el.style.left = `${x.toFixed(1)}px`;
      item.el.style.top = `${y.toFixed(1)}px`;
      item.el.style.opacity = '1';
      item.el.style.pointerEvents = 'auto';
    }
  }
}
