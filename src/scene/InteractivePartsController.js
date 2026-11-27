import * as THREE from 'three';

const INTERACTIVE_DEFS = [
  {
    key: 'doorLeft',
    nodeId: 'Tuer_Links',
    label: 'Fahrertür',
    actionOpen: 'öffnen',
    actionClose: 'schließen',
    type: 'rotateY',
    angle: -1.06,
  },
  {
    key: 'doorRight',
    nodeId: 'Tuer_Rechts',
    label: 'Beifahrertür',
    actionOpen: 'öffnen',
    actionClose: 'schließen',
    type: 'rotateY',
    angle: 1.06,
  },
  {
    key: 'rearHood',
    nodeId: 'Klappe_Motor_Kofferraum',
    label: 'Motorhaube & Kofferraum',
    actionOpen: 'öffnen',
    actionClose: 'schließen',
    type: 'rotateX',
    angle: 0.80,
  },
  {
    key: 'frontHood',
    nodeId: 'Klappe_Service_Vorne',
    label: 'Front-Serviceklappen',
    actionOpen: 'öffnen',
    actionClose: 'schließen',
    type: 'rotateX',
    angle: -0.58,
  },
  {
    key: 'roof',
    nodeId: 'Dach_Hardtop',
    label: 'Hardtop-Dach',
    actionOpen: 'abnehmen',
    actionClose: 'aufsetzen',
    type: 'liftRoof',
    liftY: 0.72,
  },
];

export class InteractivePartsController {
  constructor(carAssembly, camera, domElement, { onStateChange, onHoverChange } = {}) {
    this.carAssembly = carAssembly;
    this.camera = camera;
    this.domElement = domElement;
    this.onStateChange = onStateChange;
    this.onHoverChange = onHoverChange;

    this.raycaster = new THREE.Raycaster();
    this.pointer = new THREE.Vector2();
    this._downPos = null;
    this._hoveredKey = null;

    this.items = new Map();
    this.pickMeshes = [];
    this.meshToKey = new Map();

    for (const def of INTERACTIVE_DEFS) {
      const node = this.carAssembly.getNode(def.nodeId);
      if (!node) continue;

      this.items.set(def.key, {
        def,
        node,
        basePos: node.position.clone(),
        baseRot: node.rotation.clone(),
        open: false,
        progress: 0,
      });

      node.traverse((child) => {
        if (child.isMesh) {
          this.pickMeshes.push(child);
          this.meshToKey.set(child.uuid, def.key);
        }
      });
    }

    this._bindPointerEvents();
  }

  _bindPointerEvents() {
    this.domElement.addEventListener('pointerdown', (e) => {
      if (e.button !== 0) return;
      this._downPos = { x: e.clientX, y: e.clientY };
    });

    this.domElement.addEventListener('pointermove', (e) => {
      const hitKey = this._raycastKey(e);
      if (hitKey !== this._hoveredKey) {
        this._hoveredKey = hitKey;
        this.domElement.style.cursor = hitKey ? 'pointer' : '';
        this._emitHover();
      }
    });

    this.domElement.addEventListener('pointerleave', () => {
      if (this._hoveredKey) {
        this._hoveredKey = null;
        this.domElement.style.cursor = '';
        this._emitHover();
      }
    });

    this.domElement.addEventListener('pointerup', (e) => {
      if (e.button !== 0 || !this._downPos) return;
      const dx = e.clientX - this._downPos.x;
      const dy = e.clientY - this._downPos.y;
      this._downPos = null;
      // Ignore orbit/drag gestures (> 5px movement)
      if (Math.hypot(dx, dy) > 5) return;

      const hitKey = this._raycastKey(e);
      if (hitKey) {
        this.toggle(hitKey);
      }
    });
  }

  _isVisibleInTree(obj) {
    let cur = obj;
    while (cur) {
      if (!cur.visible) return false;
      cur = cur.parent;
    }
    return true;
  }

  _raycastKey(e) {
    const rect = this.domElement.getBoundingClientRect();
    this.pointer.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
    this.pointer.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;

    this.raycaster.setFromCamera(this.pointer, this.camera);
    const visibleTargets = this.pickMeshes.filter((m) => this._isVisibleInTree(m));
    const hits = this.raycaster.intersectObjects(visibleTargets, false);
    if (!hits.length) return null;

    return this.meshToKey.get(hits[0].object.uuid) || null;
  }

  _emitHover() {
    if (!this.onHoverChange) return;
    if (!this._hoveredKey) {
      this.onHoverChange(null);
      return;
    }
    const item = this.items.get(this._hoveredKey);
    if (!item) {
      this.onHoverChange(null);
      return;
    }
    const verb = item.open ? item.def.actionClose : item.def.actionOpen;
    this.onHoverChange({
      key: item.def.key,
      text: `Klick: ${item.def.label} ${verb}`,
    });
  }

  toggle(key) {
    const item = this.items.get(key);
    if (!item) return;
    this.setOpen(key, !item.open);
  }

  setOpen(key, open) {
    const item = this.items.get(key);
    if (!item) return;
    item.open = Boolean(open);
    if (item.def.type === 'liftRoof' && !item.open) {
      item.node.visible = true;
    }
    if (this._hoveredKey === key) this._emitHover();
    if (this.onStateChange) this.onStateChange(this.getStates());
  }

  closeAll() {
    let changed = false;
    for (const item of this.items.values()) {
      if (item.open) {
        item.open = false;
        if (item.def.type === 'liftRoof') item.node.visible = true;
        changed = true;
      }
    }
    if (changed && this.onStateChange) {
      this.onStateChange(this.getStates());
    }
  }

  getStates() {
    const out = {};
    for (const [k, item] of this.items.entries()) {
      out[k] = item.open;
    }
    return out;
  }

  update(dt) {
    const speed = 1 - Math.exp(-8.5 * dt);
    for (const item of this.items.values()) {
      const target = item.open ? 1 : 0;
      const diff = target - item.progress;
      if (Math.abs(diff) < 0.0005 && item.progress === target) continue;

      item.progress = Math.abs(diff) < 0.0005 ? target : item.progress + diff * speed;
      const t =
        item.progress < 0.5
          ? 2 * item.progress * item.progress
          : 1 - Math.pow(-2 * item.progress + 2, 2) / 2;

      const { def, node, basePos, baseRot } = item;
      if (def.type === 'rotateY') {
        node.rotation.y = baseRot.y + def.angle * t;
      } else if (def.type === 'rotateX') {
        node.rotation.x = baseRot.x + def.angle * t;
      } else if (def.type === 'liftRoof') {
        node.position.y = basePos.y + def.liftY * t;
        node.visible = !(item.open && item.progress > 0.96);
      }
    }
  }
}
