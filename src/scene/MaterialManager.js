import * as THREE from 'three';

export const PAINT_SWATCHES = [
  {
    id: 'phantom_black',
    name: 'Phantom Black Metallic',
    hex: '#11141a',
    metalness: 0.78,
    roughness: 0.18,
    clearcoat: 1.0,
    clearcoatRoughness: 0.04,
  },
  {
    id: 'british_racing_green',
    name: 'British Racing Green',
    hex: '#0b3d24',
    metalness: 0.62,
    roughness: 0.2,
    clearcoat: 1.0,
    clearcoatRoughness: 0.04,
  },
  {
    id: 'krypton_green',
    name: 'Krypton Green',
    hex: '#67d112',
    metalness: 0.42,
    roughness: 0.16,
    clearcoat: 1.0,
    clearcoatRoughness: 0.035,
  },
  {
    id: 'solar_yellow',
    name: 'Solar Yellow',
    hex: '#efb900',
    metalness: 0.36,
    roughness: 0.17,
    clearcoat: 1.0,
    clearcoatRoughness: 0.035,
  },
  {
    id: 'ardent_red',
    name: 'Ardent Red',
    hex: '#b8111b',
    metalness: 0.46,
    roughness: 0.16,
    clearcoat: 1.0,
    clearcoatRoughness: 0.04,
  },
  {
    id: 'chrome_orange',
    name: 'Chrome Orange',
    hex: '#eb5c09',
    metalness: 0.65,
    roughness: 0.17,
    clearcoat: 1.0,
    clearcoatRoughness: 0.035,
  },
];

export const RIM_FINISHES = [
  { id: 'satin_black', name: 'Satin Schwarz', hex: '#191b20', metalness: 0.84, roughness: 0.28 },
  { id: 'silver_metallic', name: 'Silber Metallic', hex: '#d3d8e0', metalness: 0.94, roughness: 0.16 },
  { id: 'bronze_gold', name: 'Bronze / Gold', hex: '#a98245', metalness: 0.88, roughness: 0.23 },
  { id: 'gunmetal', name: 'Gunmetal', hex: '#4a505b', metalness: 0.88, roughness: 0.22 },
];

const MECHANICAL_GROUPS = new Set([
  'GRP_Chassis',
  'GRP_Motor_Antrieb',
  'GRP_Fahrwerk',
  'GRP_Bremsen',
]);

export class MaterialManager {
  constructor(carAssembly) {
    this.carAssembly = carAssembly;
    this.viewMode = 'realistic'; // 'realistic' | 'wireframe' | 'xray'
    this.isolatedId = null;

    this.paintMaterials = [];
    this.rimMaterials = [];

    this._wireframeMat = new THREE.MeshBasicMaterial({
      color: 0x70c7ff,
      wireframe: true,
      transparent: true,
      opacity: 0.72,
    });

    this._xrayBodyMat = this._createXRayMaterial(new THREE.Color(0x52b8ff), 0.18, 2.3);
    this._xrayMechMat = this._createXRayMaterial(new THREE.Color(0xdfb15b), 0.52, 1.4);

    this._ghostMat = new THREE.MeshStandardMaterial({
      color: 0x62738c,
      metalness: 0.2,
      roughness: 0.6,
      transparent: true,
      opacity: 0.08,
      depthWrite: false,
    });

    this._collectNamedMaterials();
    this.setPaint(PAINT_SWATCHES[0].id);
    this.setRimFinish(RIM_FINISHES[0].id);
  }

  _createXRayMaterial(color, baseOpacity, power) {
    return new THREE.ShaderMaterial({
      transparent: true,
      depthWrite: false,
      side: THREE.DoubleSide,
      blending: THREE.AdditiveBlending,
      uniforms: {
        uColor: { value: color },
        uBaseOpacity: { value: baseOpacity },
        uPower: { value: power },
      },
      vertexShader: `
        varying vec3 vNormalView;
        varying vec3 vViewDir;
        void main() {
          vec4 mvPos = modelViewMatrix * vec4(position, 1.0);
          vNormalView = normalize(normalMatrix * normal);
          vViewDir = normalize(-mvPos.xyz);
          gl_Position = projectionMatrix * mvPos;
        }
      `,
      fragmentShader: `
        uniform vec3 uColor;
        uniform float uBaseOpacity;
        uniform float uPower;
        varying vec3 vNormalView;
        varying vec3 vViewDir;
        void main() {
          float ndotv = abs(dot(normalize(vNormalView), normalize(vViewDir)));
          float fresnel = pow(1.0 - clamp(ndotv, 0.0, 1.0), uPower);
          float alpha = clamp(uBaseOpacity * 0.35 + fresnel * 0.85, 0.04, 0.92);
          gl_FragColor = vec4(uColor * (0.65 + fresnel * 0.9), alpha);
        }
      `,
    });
  }

  _collectNamedMaterials() {
    const seenPaint = new Set();
    const seenRim = new Set();

    for (const rec of this.carAssembly.meshRecords) {
      const mats = Array.isArray(rec.originalMaterial)
        ? rec.originalMaterial
        : [rec.originalMaterial];

      mats.forEach((m) => {
        if (!m) return;
        if (m.name.startsWith('MAT_CarPaint') && !seenPaint.has(m)) {
          seenPaint.add(m);
          this.paintMaterials.push(m);
        } else if (m.name.startsWith('MAT_Rim') && !seenRim.has(m)) {
          seenRim.add(m);
          this.rimMaterials.push(m);
        }
      });
    }
  }

  setPaint(swatchId) {
    const swatch = PAINT_SWATCHES.find((s) => s.id === swatchId) || PAINT_SWATCHES[0];
    for (const mat of this.paintMaterials) {
      mat.color.set(swatch.hex);
      mat.metalness = swatch.metalness;
      mat.roughness = swatch.roughness;
      if ('clearcoat' in mat) {
        mat.clearcoat = swatch.clearcoat;
        mat.clearcoatRoughness = swatch.clearcoatRoughness;
      }
      mat.needsUpdate = true;
    }
    return swatch;
  }

  setRimFinish(finishId) {
    const finish = RIM_FINISHES.find((f) => f.id === finishId) || RIM_FINISHES[0];
    for (const mat of this.rimMaterials) {
      mat.color.set(finish.hex);
      mat.metalness = finish.metalness;
      mat.roughness = finish.roughness;
      mat.needsUpdate = true;
    }
    return finish;
  }

  setViewMode(mode) {
    this.viewMode = mode;
    this.refreshMaterials();
  }

  setIsolatedId(nodeId) {
    this.isolatedId = nodeId;
    this.refreshMaterials();
  }

  _isMeshInsideIsolated(mesh) {
    if (!this.isolatedId) return true;
    let cur = mesh;
    while (cur) {
      if (cur.name === this.isolatedId) return true;
      cur = cur.parent;
    }
    return false;
  }

  refreshMaterials() {
    for (const rec of this.carAssembly.meshRecords) {
      const inIsolated = this._isMeshInsideIsolated(rec.mesh);

      if (this.isolatedId && !inIsolated) {
        rec.mesh.material = this._ghostMat;
        rec.mesh.castShadow = false;
        continue;
      }

      if (this.viewMode === 'wireframe') {
        rec.mesh.material = this._wireframeMat;
        rec.mesh.castShadow = false;
      } else if (this.viewMode === 'xray') {
        rec.mesh.material = MECHANICAL_GROUPS.has(rec.groupId)
          ? this._xrayMechMat
          : this._xrayBodyMat;
        rec.mesh.castShadow = false;
      } else {
        rec.mesh.material = rec.originalMaterial;
        rec.mesh.castShadow = !rec.isGlass;
      }
    }
  }
}
