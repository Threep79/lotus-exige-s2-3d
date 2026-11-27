import './styles/main.css';
import * as THREE from 'three';
import { ShowroomScene, HDRI_PRESETS } from './scene/ShowroomScene.js';
import { CameraController } from './scene/CameraController.js';
import { CarAssembly } from './scene/CarAssembly.js';
import { ExplosionController } from './scene/ExplosionController.js';
import { MaterialManager } from './scene/MaterialManager.js';
import { HotspotManager } from './scene/HotspotManager.js';
import { UIController } from './ui/UIController.js';

async function bootstrap() {
  const container = document.getElementById('canvas-container');
  const hotspotsLayer = document.getElementById('hotspots-layer');
  const loadingOverlay = document.getElementById('loading-overlay');
  const loadingBar = document.getElementById('loading-bar');
  const loadingPercent = document.getElementById('loading-percent');
  const loadingStatus = document.getElementById('loading-status');

  const setProgress = (pct, msg) => {
    const rounded = Math.round(pct);
    loadingBar.style.width = `${rounded}%`;
    loadingPercent.textContent = `${rounded} %`;
    if (msg) loadingStatus.textContent = msg;
  };

  const showroom = new ShowroomScene(container);
  const cameraCtrl = new CameraController(showroom.camera, showroom.renderer.domElement);
  const carAssembly = new CarAssembly(showroom.scene);

  try {
    setProgress(10, 'Lade Showroom-Beleuchtung (HDRI) …');
    await showroom.setHDRI(HDRI_PRESETS[0].id);

    setProgress(25, 'Lade Lotus Exige S2 3D-Baugruppen …');
    await carAssembly.load((frac) => {
      setProgress(25 + frac * 70);
    });

    setProgress(98, 'Initialisiere Explosions- & Shader-System …');
    const explosionCtrl = new ExplosionController(carAssembly, showroom);
    const materialMgr = new MaterialManager(carAssembly);

    let uiCtrl = null;
    const hotspotMgr = new HotspotManager(
      hotspotsLayer,
      showroom.camera,
      carAssembly,
      (hs) => {
        if (uiCtrl) uiCtrl.showHotspotCard(hs);
      }
    );

    uiCtrl = new UIController({
      showroom,
      cameraCtrl,
      carAssembly,
      explosionCtrl,
      materialMgr,
      hotspotMgr,
    });

    setProgress(100, 'Bereit');
    setTimeout(() => {
      loadingOverlay.classList.add('hidden');
    }, 260);

    const clock = new THREE.Clock();
    const animate = () => {
      requestAnimationFrame(animate);
      const dt = Math.min(clock.getDelta(), 0.05);
      explosionCtrl.update(dt);
      cameraCtrl.update(dt);
      hotspotMgr.update();
      showroom.render();
    };
    animate();
  } catch (err) {
    console.error('Fehler beim Initialisieren des 3D-Showrooms:', err);
    loadingStatus.textContent =
      'Fehler beim Laden der 3D-Daten. Bitte Konsole prüfen und Seite neu laden.';
  }
}

bootstrap();
