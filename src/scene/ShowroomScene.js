import * as THREE from 'three';
import { RGBELoader } from 'three/examples/jsm/loaders/RGBELoader.js';

export const HDRI_PRESETS = [
  { id: 'dark_studio', label: 'Dark Studio', file: 'hdri/dark_studio.hdr' },
  { id: 'softbox_showroom', label: 'Softbox', file: 'hdri/softbox_showroom.hdr' },
  { id: 'night_hall', label: 'Nacht-Halle', file: 'hdri/night_hall.hdr' },
];

export class ShowroomScene {
  constructor(container) {
    this.container = container;
    this.baseUrl = import.meta.env.BASE_URL || '/';

    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0x090b10);
    this.scene.fog = new THREE.FogExp2(0x090b10, 0.048);

    this.camera = new THREE.PerspectiveCamera(
      40,
      container.clientWidth / Math.max(container.clientHeight, 1),
      0.05,
      100
    );

    this.renderer = new THREE.WebGLRenderer({
      antialias: true,
      powerPreference: 'high-performance',
    });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.setSize(container.clientWidth, container.clientHeight);
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.15;
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    container.appendChild(this.renderer.domElement);

    this.pmremGenerator = new THREE.PMREMGenerator(this.renderer);
    this.pmremGenerator.compileEquirectangularShader();
    this.rgbeLoader = new RGBELoader();
    this.envCache = new Map();

    this.contactShadowMesh = null;
    this._setupBackdropAndFloor();
    this._setupLights();

    window.addEventListener('resize', () => this.onResize());
  }

  _setupBackdropAndFloor() {
    // Subtle dark luxury studio dome gradient
    const domeGeo = new THREE.SphereGeometry(28, 32, 24);
    const domeMat = new THREE.ShaderMaterial({
      side: THREE.BackSide,
      depthWrite: false,
      uniforms: {
        uTop: { value: new THREE.Color(0x06080c) },
        uMid: { value: new THREE.Color(0x111722) },
        uBottom: { value: new THREE.Color(0x07090d) },
      },
      vertexShader: `
        varying vec3 vWorldPos;
        void main() {
          vec4 wp = modelMatrix * vec4(position, 1.0);
          vWorldPos = wp.xyz;
          gl_Position = projectionMatrix * viewMatrix * wp;
        }
      `,
      fragmentShader: `
        uniform vec3 uTop;
        uniform vec3 uMid;
        uniform vec3 uBottom;
        varying vec3 vWorldPos;
        void main() {
          float h = normalize(vWorldPos).y;
          vec3 col = mix(uBottom, uMid, smoothstep(-0.25, 0.08, h));
          col = mix(col, uTop, smoothstep(0.08, 0.65, h));
          gl_FragColor = vec4(col, 1.0);
        }
      `,
    });
    this.scene.add(new THREE.Mesh(domeGeo, domeMat));

    // Procedural radial alpha vignette for seamless showroom floor fade
    const size = 256;
    const canvas = document.createElement('canvas');
    canvas.width = size;
    canvas.height = size;
    const ctx = canvas.getContext('2d');
    const grad = ctx.createRadialGradient(size / 2, size / 2, size * 0.08, size / 2, size / 2, size * 0.5);
    grad.addColorStop(0.0, 'rgba(255,255,255,1.0)');
    grad.addColorStop(0.55, 'rgba(255,255,255,0.65)');
    grad.addColorStop(1.0, 'rgba(255,255,255,0.0)');
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, size, size);
    const floorAlphaTex = new THREE.CanvasTexture(canvas);

    const floorGeo = new THREE.CircleGeometry(14, 72);
    floorGeo.rotateX(-Math.PI / 2);
    const floorMat = new THREE.MeshStandardMaterial({
      color: 0x0b0e14,
      metalness: 0.35,
      roughness: 0.32,
      alphaMap: floorAlphaTex,
      transparent: true,
      envMapIntensity: 0.75,
    });
    const floor = new THREE.Mesh(floorGeo, floorMat);
    floor.position.y = -0.002;
    floor.receiveShadow = true;
    this.scene.add(floor);

    // Shadow catcher plane right at y = 0
    const shadowGeo = new THREE.PlaneGeometry(14, 14);
    shadowGeo.rotateX(-Math.PI / 2);
    const shadowMat = new THREE.ShadowMaterial({ opacity: 0.52 });
    const shadowPlane = new THREE.Mesh(shadowGeo, shadowMat);
    shadowPlane.position.y = 0.0005;
    shadowPlane.receiveShadow = true;
    this.scene.add(shadowPlane);

    // Soft elliptical ground contact AO shadow directly under the car
    const aoCanvas = document.createElement('canvas');
    aoCanvas.width = 256;
    aoCanvas.height = 512;
    const aoCtx = aoCanvas.getContext('2d');
    const aoGrad = aoCtx.createRadialGradient(128, 256, 20, 128, 256, 128);
    aoGrad.addColorStop(0.0, 'rgba(0,0,0,0.88)');
    aoGrad.addColorStop(0.55, 'rgba(0,0,0,0.52)');
    aoGrad.addColorStop(1.0, 'rgba(0,0,0,0.0)');
    aoCtx.fillStyle = aoGrad;
    aoCtx.fillRect(0, 0, 256, 512);
    const aoTex = new THREE.CanvasTexture(aoCanvas);

    const aoGeo = new THREE.PlaneGeometry(2.35, 4.35);
    aoGeo.rotateX(-Math.PI / 2);
    const aoMat = new THREE.MeshBasicMaterial({
      map: aoTex,
      transparent: true,
      depthWrite: false,
      opacity: 0.85,
    });
    this.contactShadowMesh = new THREE.Mesh(aoGeo, aoMat);
    this.contactShadowMesh.position.y = 0.001;
    this.scene.add(this.contactShadowMesh);
  }

  _setupLights() {
    // Soft overhead key light for studio speculars & ground shadow
    const keyLight = new THREE.DirectionalLight(0xfff8ee, 1.55);
    keyLight.position.set(2.5, 6.2, 3.4);
    keyLight.castShadow = true;
    keyLight.shadow.mapSize.set(2048, 2048);
    keyLight.shadow.camera.near = 1;
    keyLight.shadow.camera.far = 16;
    keyLight.shadow.camera.left = -3.5;
    keyLight.shadow.camera.right = 3.5;
    keyLight.shadow.camera.top = 3.5;
    keyLight.shadow.camera.bottom = -3.5;
    keyLight.shadow.bias = -0.0004;
    keyLight.shadow.normalBias = 0.02;
    this.scene.add(keyLight);

    // Subtle cool rim light from rear-right to sculpt silhouette
    const rimLight = new THREE.DirectionalLight(0x9ec5ff, 0.85);
    rimLight.position.set(-3.8, 2.8, -4.2);
    this.scene.add(rimLight);

    // Soft under-fill so chassis & suspension stay readable in dark showroom
    const hemi = new THREE.HemisphereLight(0xdce6f5, 0x161a22, 0.35);
    this.scene.add(hemi);
  }

  async setHDRI(hdriId) {
    const preset = HDRI_PRESETS.find((h) => h.id === hdriId) || HDRI_PRESETS[0];
    if (this.envCache.has(preset.id)) {
      this.scene.environment = this.envCache.get(preset.id);
      return preset.id;
    }

    const url = `${this.baseUrl}${preset.file}`;
    const hdrTexture = await this.rgbeLoader.loadAsync(url);
    hdrTexture.mapping = THREE.EquirectangularReflectionMapping;
    const envRT = this.pmremGenerator.fromEquirectangular(hdrTexture);
    hdrTexture.dispose();

    this.envCache.set(preset.id, envRT.texture);
    this.scene.environment = envRT.texture;
    return preset.id;
  }

  setExposure(value) {
    this.renderer.toneMappingExposure = value;
  }

  setExplosionFade(explosionProgress) {
    if (this.contactShadowMesh) {
      this.contactShadowMesh.material.opacity = THREE.MathUtils.lerp(0.85, 0.2, explosionProgress);
    }
  }

  onResize() {
    const w = this.container.clientWidth;
    const h = Math.max(this.container.clientHeight, 1);
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(w, h);
  }

  render() {
    this.renderer.render(this.scene, this.camera);
  }
}
