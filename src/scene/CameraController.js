import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';

const DEFAULT_CAM_POS = new THREE.Vector3(3.15, 1.32, 3.45);
const DEFAULT_TARGET = new THREE.Vector3(0, 0.52, 0);
const DEFAULT_FOV = 40;

// Driver POV in Three.js (+X = car left/driver, +Y = up, +Z = front)
const COCKPIT_EYE_POS = new THREE.Vector3(0.253, 0.88, -0.07);
const COCKPIT_LOOK_TARGET = new THREE.Vector3(0.253, 0.83, 0.08);
const COCKPIT_FOV = 64;

export class CameraController {
  constructor(camera, domElement, onCockpitModeChange) {
    this.camera = camera;
    this.onCockpitModeChange = onCockpitModeChange;
    this.isCockpitMode = false;

    this.controls = new OrbitControls(camera, domElement);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.065;
    this.controls.autoRotate = false;
    this.controls.autoRotateSpeed = 0.75;

    this._applyExteriorConstraints();
    this.camera.position.copy(DEFAULT_CAM_POS);
    this.controls.target.copy(DEFAULT_TARGET);
    this.controls.update();

    this._tween = null;

    this.controls.addEventListener('start', () => {
      this._tween = null;
    });
  }

  _applyExteriorConstraints() {
    this.controls.enablePan = true;
    this.controls.minDistance = 1.45;
    this.controls.maxDistance = 10.5;
    this.controls.minPolarAngle = 0;
    this.controls.maxPolarAngle = Math.PI / 2 - 0.025;
    this.controls.rotateSpeed = 1.0;
  }

  _applyCockpitConstraints() {
    this.controls.enablePan = false;
    this.controls.autoRotate = false;
    this.controls.minDistance = 0.05;
    this.controls.maxDistance = 0.28;
    this.controls.minPolarAngle = 0.22;
    this.controls.maxPolarAngle = Math.PI * 0.78;
    this.controls.rotateSpeed = 0.45;
  }

  setAutoRotate(enabled) {
    if (this.isCockpitMode) {
      this.controls.autoRotate = false;
      return;
    }
    this.controls.autoRotate = enabled;
  }

  setCockpitMode(enabled) {
    const next = Boolean(enabled);
    if (this.isCockpitMode === next) return;
    this.isCockpitMode = next;

    if (next) {
      this._applyCockpitConstraints();
      this._startTween(COCKPIT_EYE_POS.clone(), COCKPIT_LOOK_TARGET.clone(), COCKPIT_FOV, 0.9);
    } else {
      this._applyExteriorConstraints();
      this._startTween(DEFAULT_CAM_POS.clone(), DEFAULT_TARGET.clone(), DEFAULT_FOV, 0.9);
    }

    if (this.onCockpitModeChange) {
      this.onCockpitModeChange(this.isCockpitMode);
    }
  }

  resetView() {
    if (this.isCockpitMode) {
      this.setCockpitMode(false);
    } else {
      this._startTween(DEFAULT_CAM_POS.clone(), DEFAULT_TARGET.clone(), DEFAULT_FOV, 0.85);
    }
  }

  focusOnObject(object3d) {
    if (!object3d) return;
    if (this.isCockpitMode) {
      this.isCockpitMode = false;
      this._applyExteriorConstraints();
      if (this.onCockpitModeChange) this.onCockpitModeChange(false);
    }

    object3d.updateWorldMatrix(true, true);
    const box = new THREE.Box3().setFromObject(object3d);
    if (box.isEmpty()) return;

    const center = box.getCenter(new THREE.Vector3());
    const size = box.getSize(new THREE.Vector3());
    const maxDim = Math.max(size.x, size.y, size.z, 0.55);

    const fovRad = THREE.MathUtils.degToRad(DEFAULT_FOV);
    const dist = THREE.MathUtils.clamp((maxDim / (2 * Math.tan(fovRad / 2))) * 1.9, 1.55, 6.2);

    const dir = this.camera.position.clone().sub(this.controls.target);
    if (dir.lengthSq() < 1e-4) dir.set(1, 0.4, 1);
    dir.y = Math.max(dir.y, 0.28 * dir.length());
    dir.normalize();

    const endPos = center.clone().addScaledVector(dir, dist);
    endPos.y = Math.max(endPos.y, 0.35);
    center.y = Math.max(center.y, 0.15);

    this._startTween(endPos, center, DEFAULT_FOV, 0.8);
  }

  _startTween(endPos, endTarget, endFov, durationSec) {
    this._tween = {
      startPos: this.camera.position.clone(),
      startTarget: this.controls.target.clone(),
      startFov: this.camera.fov,
      endPos,
      endTarget,
      endFov,
      elapsed: 0,
      duration: durationSec,
    };
  }

  update(dt) {
    if (this._tween) {
      this._tween.elapsed += dt;
      const rawT = Math.min(this._tween.elapsed / this._tween.duration, 1);
      const t = rawT < 0.5 ? 4 * rawT * rawT * rawT : 1 - Math.pow(-2 * rawT + 2, 3) / 2;

      this.camera.position.lerpVectors(this._tween.startPos, this._tween.endPos, t);
      this.controls.target.lerpVectors(this._tween.startTarget, this._tween.endTarget, t);
      const nextFov = THREE.MathUtils.lerp(this._tween.startFov, this._tween.endFov, t);
      if (Math.abs(this.camera.fov - nextFov) > 0.01) {
        this.camera.fov = nextFov;
        this.camera.updateProjectionMatrix();
      }

      if (rawT >= 1) {
        this._tween = null;
      }
    }

    if (!this.isCockpitMode && this.controls.target.y < 0.08) {
      this.controls.target.y = 0.08;
    }

    this.controls.update();
  }
}
