import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { DRACOLoader } from 'three/examples/jsm/loaders/DRACOLoader.js';

export const PARTS_CATALOG = [
  {
    id: 'GRP_Karosserie_FrontClam',
    label: 'Front-Clamshell & Lichter',
    category: 'Karosserie',
  },
  {
    id: 'GRP_Karosserie_HeckClam',
    label: 'Heck-Clamshell & Motorhaube',
    category: 'Karosserie',
  },
  {
    id: 'GRP_Karosserie_Tueren',
    label: 'Türen, Spiegel & Scheiben',
    category: 'Karosserie',
    children: [
      { id: 'Tuer_Links', label: 'Tür Links (Fahrerseite)' },
      { id: 'Tuer_Rechts', label: 'Tür Rechts (Beifahrerseite)' },
    ],
  },
  {
    id: 'GRP_Karosserie_Dach',
    label: 'Hardtop-Dach & Lufthutze',
    category: 'Karosserie',
  },
  {
    id: 'GRP_Aerodynamik',
    label: 'Aerodynamik-Paket',
    category: 'Aerodynamik',
    children: [
      { id: 'Aero_Heckfluegel', label: 'Heckflügel & Endplates' },
      { id: 'Aero_Diffusor', label: 'Unterboden-Heckdiffusor' },
    ],
  },
  {
    id: 'GRP_Raeder',
    label: 'Räder (Felgen & Reifen)',
    category: 'Fahrwerk & Räder',
    children: [
      { id: 'Rad_VL', label: 'Rad Vorne Links' },
      { id: 'Rad_VR', label: 'Rad Vorne Rechts' },
      { id: 'Rad_HL', label: 'Rad Hinten Links' },
      { id: 'Rad_HR', label: 'Rad Hinten Rechts' },
    ],
  },
  {
    id: 'GRP_Bremsen',
    label: 'Hochleistungs-Bremsanlage',
    category: 'Fahrwerk & Räder',
    children: [
      { id: 'Bremse_VL', label: 'Bremse Vorne Links' },
      { id: 'Bremse_VR', label: 'Bremse Vorne Rechts' },
      { id: 'Bremse_HL', label: 'Bremse Hinten Links' },
      { id: 'Bremse_HR', label: 'Bremse Hinten Rechts' },
    ],
  },
  {
    id: 'GRP_Fahrwerk',
    label: 'Doppelquerlenker-Fahrwerk',
    category: 'Fahrwerk & Räder',
    children: [
      { id: 'Fahrwerk_VL', label: 'Fahrwerk Vorne Links' },
      { id: 'Fahrwerk_VR', label: 'Fahrwerk Vorne Rechts' },
      { id: 'Fahrwerk_HL', label: 'Fahrwerk Hinten Links' },
      { id: 'Fahrwerk_HR', label: 'Fahrwerk Hinten Rechts' },
    ],
  },
  {
    id: 'GRP_Motor_Antrieb',
    label: '1,8-L-2ZZ-GE Kompressormotor',
    category: 'Antrieb',
  },
  {
    id: 'GRP_Interieur',
    label: 'Cockpit, Sitze & Pedalerie',
    category: 'Interieur',
  },
  {
    id: 'GRP_Chassis',
    label: 'Aluminium-Monocoque-Chassis',
    category: 'Struktur',
  },
];

export class CarAssembly {
  constructor(scene) {
    this.scene = scene;
    this.baseUrl = import.meta.env.BASE_URL || '/';
    this.root = null;
    this.nodesById = new Map();
    this.meshRecords = [];
  }

  async load(onProgress) {
    const dracoLoader = new DRACOLoader();
    dracoLoader.setDecoderPath(`${this.baseUrl}draco/`);
    dracoLoader.preload();

    const gltfLoader = new GLTFLoader();
    gltfLoader.setDRACOLoader(dracoLoader);

    const url = `${this.baseUrl}models/lotus_exige_s2.glb`;
    const gltf = await gltfLoader.loadAsync(url, (xhr) => {
      if (xhr.lengthComputable && onProgress) {
        onProgress(Math.min(1, xhr.loaded / xhr.total));
      }
    });

    this.root = gltf.scene;
    this.scene.add(this.root);

    // Ensure lowest point of tires sits flush at y = 0
    this.root.updateWorldMatrix(true, true);
    const box = new THREE.Box3().setFromObject(this.root);
    if (Math.abs(box.min.y) > 0.0005) {
      this.root.position.y -= box.min.y;
    }

    // Index all technical groups & sub-groups
    const targetIds = new Set();
    for (const grp of PARTS_CATALOG) {
      targetIds.add(grp.id);
      if (grp.children) {
        for (const ch of grp.children) targetIds.add(ch.id);
      }
    }

    this.root.traverse((obj) => {
      if (targetIds.has(obj.name)) {
        this.nodesById.set(obj.name, obj);
      }
      if (obj.isMesh) {
        const isGlass = this._isGlassMesh(obj);
        obj.castShadow = !isGlass;
        obj.receiveShadow = true;

        // Find owning top-level GRP_* id for shader/ghost categorization
        let groupId = 'unknown';
        let cur = obj;
        while (cur) {
          if (cur.name && cur.name.startsWith('GRP_')) {
            groupId = cur.name;
            break;
          }
          cur = cur.parent;
        }

        this.meshRecords.push({
          mesh: obj,
          groupId,
          isGlass,
          originalMaterial: obj.material,
        });
      }
    });

    dracoLoader.dispose();
    return this.root;
  }

  _isGlassMesh(mesh) {
    const mats = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
    return mats.some(
      (m) =>
        m &&
        (m.transparent ||
          m.name.includes('glass') ||
          m.name.includes('Vetro') ||
          m.name.includes('CAR_lights_0'))
    );
  }

  getNode(id) {
    return this.nodesById.get(id) || null;
  }
}
