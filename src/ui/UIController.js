import { PARTS_CATALOG } from '../scene/CarAssembly.js';
import { PAINT_SWATCHES, RIM_FINISHES } from '../scene/MaterialManager.js';
import { HDRI_PRESETS } from '../scene/ShowroomScene.js';

const EYE_OPEN_SVG = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>`;
const EYE_OFF_SVG = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>`;
const ISOLATE_SVG = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="3"/></svg>`;
const CHEVRON_SVG = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><polyline points="9 18 15 12 9 6"/></svg>`;

export class UIController {
  constructor({ showroom, cameraCtrl, carAssembly, explosionCtrl, materialMgr, hotspotMgr }) {
    this.showroom = showroom;
    this.cameraCtrl = cameraCtrl;
    this.carAssembly = carAssembly;
    this.explosionCtrl = explosionCtrl;
    this.materialMgr = materialMgr;
    this.hotspotMgr = hotspotMgr;

    this.isolatedId = null;
    this.leftCollapsed = false;
    this.rightCollapsed = false;

    this.els = {
      leftPanel: document.getElementById('left-panel'),
      rightPanel: document.getElementById('right-panel'),
      toggleLeftBtn: document.getElementById('toggle-left-btn'),
      toggleRightBtn: document.getElementById('toggle-right-btn'),
      toggleFocusBtn: document.getElementById('toggle-focus-btn'),
      explosionSlider: document.getElementById('explosion-slider'),
      explosionValue: document.getElementById('explosion-value'),
      presetBtns: document.querySelectorAll('.preset-btn'),
      partsList: document.getElementById('parts-list'),
      visibleCount: document.getElementById('visible-count'),
      showAllBtn: document.getElementById('show-all-btn'),
      paintSwatches: document.getElementById('paint-swatches'),
      paintName: document.getElementById('paint-name'),
      rimOptions: document.getElementById('rim-options'),
      rimName: document.getElementById('rim-name'),
      viewModeBtns: document.querySelectorAll('#view-mode-control .seg-btn'),
      hdriOptions: document.getElementById('hdri-options'),
      exposureSlider: document.getElementById('exposure-slider'),
      exposureValue: document.getElementById('exposure-value'),
      autorotateToggle: document.getElementById('autorotate-toggle'),
      hotspotsToggle: document.getElementById('hotspots-toggle'),
      resetViewBtn: document.getElementById('reset-view-btn'),
      hotspotCard: document.getElementById('hotspot-card'),
      hotspotBadge: document.getElementById('hotspot-badge'),
      hotspotTitle: document.getElementById('hotspot-title'),
      hotspotDesc: document.getElementById('hotspot-desc'),
      hotspotSpecs: document.getElementById('hotspot-specs'),
      hotspotClose: document.getElementById('hotspot-close'),
      hotspotIsolateBtn: document.getElementById('hotspot-isolate-btn'),
    };

    this._activeHotspot = null;
    this._bindHeaderAndPanels();
    this._bindExplosion();
    this._buildPartsList();
    this._buildPaintSwatches();
    this._buildRimOptions();
    this._bindViewModes();
    this._buildHdriOptions();
    this._bindComfortControls();
    this._bindHotspotCard();
  }

  _bindHeaderAndPanels() {
    const syncPanels = () => {
      this.els.leftPanel.classList.toggle('collapsed', this.leftCollapsed);
      this.els.rightPanel.classList.toggle('collapsed', this.rightCollapsed);
      this.els.toggleLeftBtn.classList.toggle('active', !this.leftCollapsed);
      this.els.toggleRightBtn.classList.toggle('active', !this.rightCollapsed);
      this.els.toggleFocusBtn.classList.toggle('active', this.leftCollapsed && this.rightCollapsed);
    };

    this.els.toggleLeftBtn.addEventListener('click', () => {
      this.leftCollapsed = !this.leftCollapsed;
      syncPanels();
    });

    this.els.toggleRightBtn.addEventListener('click', () => {
      this.rightCollapsed = !this.rightCollapsed;
      syncPanels();
    });

    this.els.toggleFocusBtn.addEventListener('click', () => {
      const enterFocus = !(this.leftCollapsed && this.rightCollapsed);
      this.leftCollapsed = enterFocus;
      this.rightCollapsed = enterFocus;
      syncPanels();
    });
  }

  _bindExplosion() {
    const setPercent = (val) => {
      const clamped = Math.max(0, Math.min(100, Number(val)));
      this.els.explosionSlider.value = String(clamped);
      this.els.explosionValue.textContent = `${clamped} %`;
      this.explosionCtrl.setTargetPercent(clamped);
      this.els.presetBtns.forEach((btn) => {
        btn.classList.toggle('active', Number(btn.dataset.explode) === clamped);
      });
    };

    this.els.explosionSlider.addEventListener('input', (e) => {
      setPercent(e.target.value);
    });

    this.els.presetBtns.forEach((btn) => {
      btn.addEventListener('click', () => setPercent(btn.dataset.explode));
    });

    this._setExplosionPercent = setPercent;
  }

  _buildPartsList() {
    this.els.partsList.innerHTML = '';

    const createRow = (item, hasChildren = false) => {
      const row = document.createElement('div');
      row.className = 'part-row';
      row.dataset.partId = item.id;

      const left = document.createElement('div');
      left.className = 'part-left';

      let expandBtn = null;
      if (hasChildren) {
        expandBtn = document.createElement('button');
        expandBtn.type = 'button';
        expandBtn.className = 'expand-btn';
        expandBtn.innerHTML = CHEVRON_SVG;
        expandBtn.setAttribute('aria-label', `${item.label} aufklappen`);
        left.appendChild(expandBtn);
      }

      const label = document.createElement('span');
      label.className = 'part-label';
      label.textContent = item.label;
      left.appendChild(label);

      const actions = document.createElement('div');
      actions.className = 'part-actions';

      const eyeBtn = document.createElement('button');
      eyeBtn.type = 'button';
      eyeBtn.className = 'part-icon-btn';
      eyeBtn.title = 'Ein-/Ausblenden';
      eyeBtn.innerHTML = EYE_OPEN_SVG;
      eyeBtn.addEventListener('click', () => this._toggleVisibility(item.id));

      const isoBtn = document.createElement('button');
      isoBtn.type = 'button';
      isoBtn.className = 'part-icon-btn';
      isoBtn.title = 'Bauteil isolieren & fokussieren';
      isoBtn.innerHTML = ISOLATE_SVG;
      isoBtn.addEventListener('click', () => this._toggleIsolate(item.id));

      actions.append(eyeBtn, isoBtn);
      row.append(left, actions);
      return { row, expandBtn, eyeBtn, isoBtn };
    };

    for (const grp of PARTS_CATALOG) {
      const wrap = document.createElement('div');
      wrap.className = 'part-group';

      const hasKids = Array.isArray(grp.children) && grp.children.length > 0;
      const { row, expandBtn } = createRow(grp, hasKids);
      wrap.appendChild(row);

      if (hasKids) {
        const kidsEl = document.createElement('div');
        kidsEl.className = 'part-children';
        for (const child of grp.children) {
          const { row: childRow } = createRow(child, false);
          kidsEl.appendChild(childRow);
        }
        wrap.appendChild(kidsEl);

        expandBtn.addEventListener('click', () => {
          const isOpen = kidsEl.classList.toggle('open');
          expandBtn.classList.toggle('expanded', isOpen);
        });
      }

      this.els.partsList.appendChild(wrap);
    }

    this.els.showAllBtn.addEventListener('click', () => this.showAllParts());
    this._syncPartsUI();
  }

  _toggleVisibility(partId) {
    const node = this.carAssembly.getNode(partId);
    if (!node) return;
    node.visible = !node.visible;
    if (this.isolatedId === partId && !node.visible) {
      this.isolatedId = null;
      this.materialMgr.setIsolatedId(null);
    }
    this._syncPartsUI();
  }

  _toggleIsolate(partId) {
    const node = this.carAssembly.getNode(partId);
    if (!node) return;

    if (this.isolatedId === partId) {
      this.isolatedId = null;
      this.materialMgr.setIsolatedId(null);
      this.cameraCtrl.resetView();
    } else {
      // Ensure target node and its ancestors are visible
      let cur = node;
      while (cur) {
        cur.visible = true;
        cur = cur.parent;
      }
      this.isolatedId = partId;
      this.materialMgr.setIsolatedId(partId);
      this.cameraCtrl.focusOnObject(node);
    }
    this._syncPartsUI();
  }

  showAllParts() {
    for (const grp of PARTS_CATALOG) {
      const gNode = this.carAssembly.getNode(grp.id);
      if (gNode) gNode.visible = true;
      if (grp.children) {
        for (const ch of grp.children) {
          const cNode = this.carAssembly.getNode(ch.id);
          if (cNode) cNode.visible = true;
        }
      }
    }
    this.isolatedId = null;
    this.materialMgr.setIsolatedId(null);
    this._syncPartsUI();
  }

  _syncPartsUI() {
    let visibleTopCount = 0;
    for (const grp of PARTS_CATALOG) {
      const n = this.carAssembly.getNode(grp.id);
      if (n && n.visible) visibleTopCount++;
    }
    this.els.visibleCount.textContent = `${visibleTopCount} / ${PARTS_CATALOG.length}`;

    const rows = this.els.partsList.querySelectorAll('.part-row');
    rows.forEach((row) => {
      const id = row.dataset.partId;
      const node = this.carAssembly.getNode(id);
      const isVis = node ? node.visible : true;
      const isIso = this.isolatedId === id;

      row.classList.toggle('is-hidden', !isVis);
      row.classList.toggle('is-isolated', isIso);

      const [eyeBtn, isoBtn] = row.querySelectorAll('.part-icon-btn');
      if (eyeBtn) {
        eyeBtn.innerHTML = isVis ? EYE_OPEN_SVG : EYE_OFF_SVG;
        eyeBtn.classList.toggle('off', !isVis);
      }
      if (isoBtn) {
        isoBtn.classList.toggle('active', isIso);
      }
    });
  }

  _buildPaintSwatches() {
    this.els.paintSwatches.innerHTML = '';
    PAINT_SWATCHES.forEach((swatch, idx) => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = `swatch-btn${idx === 0 ? ' active' : ''}`;
      btn.style.background = `radial-gradient(circle at 32% 28%, rgba(255,255,255,0.42), transparent 55%), ${swatch.hex}`;
      btn.title = swatch.name;
      btn.setAttribute('aria-label', swatch.name);
      btn.addEventListener('click', () => {
        this.materialMgr.setPaint(swatch.id);
        this.els.paintName.textContent = swatch.name;
        this.els.paintSwatches.querySelectorAll('.swatch-btn').forEach((b) => b.classList.remove('active'));
        btn.classList.add('active');
      });
      this.els.paintSwatches.appendChild(btn);
    });
  }

  _buildRimOptions() {
    this.els.rimOptions.innerHTML = '';
    RIM_FINISHES.forEach((fin, idx) => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = `chip-btn${idx === 0 ? ' active' : ''}`;
      btn.textContent = fin.name;
      btn.addEventListener('click', () => {
        this.materialMgr.setRimFinish(fin.id);
        this.els.rimName.textContent = fin.name;
        this.els.rimOptions.querySelectorAll('.chip-btn').forEach((b) => b.classList.remove('active'));
        btn.classList.add('active');
      });
      this.els.rimOptions.appendChild(btn);
    });
  }

  _bindViewModes() {
    this.els.viewModeBtns.forEach((btn) => {
      btn.addEventListener('click', () => {
        const mode = btn.dataset.mode;
        this.materialMgr.setViewMode(mode);
        this.els.viewModeBtns.forEach((b) => b.classList.toggle('active', b === btn));
      });
    });
  }

  _buildHdriOptions() {
    this.els.hdriOptions.innerHTML = '';
    HDRI_PRESETS.forEach((hdri, idx) => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = `chip-btn${idx === 0 ? ' active' : ''}`;
      btn.textContent = hdri.label;
      btn.addEventListener('click', async () => {
        this.els.hdriOptions.querySelectorAll('.chip-btn').forEach((b) => b.classList.remove('active'));
        btn.classList.add('active');
        await this.showroom.setHDRI(hdri.id);
      });
      this.els.hdriOptions.appendChild(btn);
    });

    this.els.exposureSlider.addEventListener('input', (e) => {
      const val = Number(e.target.value);
      this.els.exposureValue.textContent = val.toFixed(2);
      this.showroom.setExposure(val);
    });
  }

  _bindComfortControls() {
    this.els.autorotateToggle.addEventListener('change', (e) => {
      this.cameraCtrl.setAutoRotate(e.target.checked);
    });

    this.els.hotspotsToggle.addEventListener('change', (e) => {
      this.hotspotMgr.setEnabled(e.target.checked);
      if (!e.target.checked) {
        this.hideHotspotCard();
      }
    });

    this.els.resetViewBtn.addEventListener('click', () => {
      this.showAllParts();
      this._setExplosionPercent(0);
      this.hideHotspotCard();
      this.cameraCtrl.resetView();
    });
  }

  _bindHotspotCard() {
    this.els.hotspotClose.addEventListener('click', () => this.hideHotspotCard());
    this.els.hotspotIsolateBtn.addEventListener('click', () => {
      if (!this._activeHotspot) return;
      this._toggleIsolate(this._activeHotspot.nodeId);
    });
  }

  showHotspotCard(hs) {
    this._activeHotspot = hs;
    this.els.hotspotBadge.textContent = hs.badge;
    this.els.hotspotTitle.textContent = hs.title;
    this.els.hotspotDesc.textContent = hs.description;
    this.els.hotspotSpecs.innerHTML = hs.specs
      .map(
        (s) => `
      <div class="hotspot-spec-item">
        <dt>${s.label}</dt>
        <dd>${s.value}</dd>
      </div>`
      )
      .join('');
    this.els.hotspotCard.classList.remove('hidden');
  }

  hideHotspotCard() {
    this._activeHotspot = null;
    this.hotspotMgr.setActive(null);
    this.els.hotspotCard.classList.add('hidden');
  }
}
