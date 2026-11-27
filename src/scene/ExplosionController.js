import * as THREE from 'three';

// Multi-stage explosion offsets in Three.js world space (+Z front, -Z rear, +Y up, +X left, -X right)
const EXPLOSION_VECTORS = {
  // Outer body panels expand furthest
  GRP_Karosserie_FrontClam: new THREE.Vector3(0.0, 0.34, 1.55),
  GRP_Karosserie_HeckClam: new THREE.Vector3(0.0, 0.62, -1.85),
  Tuer_Links: new THREE.Vector3(1.22, 0.14, 0.0),
  Tuer_Rechts: new THREE.Vector3(-1.22, 0.14, 0.0),
  GRP_Karosserie_Dach: new THREE.Vector3(0.0, 1.25, -0.05),
  Aero_Heckfluegel: new THREE.Vector3(0.0, 1.18, -2.38),
  Aero_Diffusor: new THREE.Vector3(0.0, -0.08, -1.45),

  // Wheels outermost radially
  Rad_VL: new THREE.Vector3(1.12, 0.08, 0.14),
  Rad_VR: new THREE.Vector3(-1.12, 0.08, 0.14),
  Rad_HL: new THREE.Vector3(1.12, 0.08, -0.14),
  Rad_HR: new THREE.Vector3(-1.12, 0.08, -0.14),

  // Brakes mid-way outward
  Bremse_VL: new THREE.Vector3(0.64, 0.05, 0.07),
  Bremse_VR: new THREE.Vector3(-0.64, 0.05, 0.07),
  Bremse_HL: new THREE.Vector3(0.64, 0.05, -0.07),
  Bremse_HR: new THREE.Vector3(-0.64, 0.05, -0.07),

  // Suspension inner mechanical layer
  Fahrwerk_VL: new THREE.Vector3(0.32, 0.03, 0.03),
  Fahrwerk_VR: new THREE.Vector3(-0.32, 0.03, 0.03),
  Fahrwerk_HL: new THREE.Vector3(0.32, 0.03, -0.03),
  Fahrwerk_HR: new THREE.Vector3(-0.32, 0.03, -0.03),

  // Engine & Interior lift clearly out of aluminum tub
  GRP_Motor_Antrieb: new THREE.Vector3(0.0, 0.48, -0.72),
  GRP_Interieur: new THREE.Vector3(0.0, 0.62, 0.06),

  // Central stationary anchor
  GRP_Chassis: new THREE.Vector3(0.0, 0.0, 0.0),
};

export class ExplosionController {
  constructor(carAssembly, showroomScene) {
    this.carAssembly = carAssembly;
    this.showroomScene = showroomScene;
    this.targetProgress = 0;
    this.currentProgress = 0;
    this.basePositions = new Map();

    for (const id of Object.keys(EXPLOSION_VECTORS)) {
      const node = this.carAssembly.getNode(id);
      if (node) {
        this.basePositions.set(id, node.position.clone());
      }
    }
  }

  setTargetPercent(percent) {
    this.targetProgress = THREE.MathUtils.clamp(percent / 100, 0, 1);
  }

  update(dt) {
    const diff = this.targetProgress - this.currentProgress;
    if (Math.abs(diff) < 0.0004) {
      if (this.currentProgress !== this.targetProgress) {
        this.currentProgress = this.targetProgress;
        this._apply(this.currentProgress);
      }
      return;
    }

    const alpha = 1 - Math.exp(-8.5 * dt);
    this.currentProgress += diff * alpha;
    this._apply(this.currentProgress);
  }

  _apply(t) {
    // Smooth cubic-out curve for crisp mechanical feel
    const eased = t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;

    for (const [id, vec] of Object.entries(EXPLOSION_VECTORS)) {
      const node = this.carAssembly.getNode(id);
      const base = this.basePositions.get(id);
      if (node && base) {
        node.position.copy(base).addScaledVector(vec, eased);
      }
    }

    if (this.showroomScene) {
      this.showroomScene.setExplosionFade(eased);
    }
  }
}
