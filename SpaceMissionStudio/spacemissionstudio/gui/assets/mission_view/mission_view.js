/*
 * SpaceMissionStudio, Results › 3D View: the page's script.
 * Licensed under the EUPL. SPDX-License-Identifier: EUPL-1.2
 *
 * gui/mission_view_widget.py drives it through the global MV:
 *   MV.setStyle(style)      the theme's colours and overlay CSS (theme/mission_view_style.py)
 *   MV.load(scene, opts)    a run (engine/scene3d.py via mission_view_widget.scene_payload);
 *                           opts.keepCamera keeps the view and the camera as they are
 *   MV.append(frames)       a live run's new frames (mission_view_widget.frames_payload);
 *                           frames.follow shows the newest
 *   MV.setLive(on)          the LIVE badge (the view follows a run being computed)
 *   MV.setFrame(n)          the frame shown
 *   MV.setView(spec)        the camera: {mode: 'orbit' | 'earth' | 'follow' | 'instrument', craft, axis, item}
 *   MV.setToggle(name, on)  paths, trails, axes, headings, cones, stations, labels, stars, groundTrack
 *   MV.setQuality(q)        'full' or 'reduced' (2k textures, no atmosphere, pixel ratio 1)
 *   MV.setPlayback(p)       {speed: text, playing: bool} for the overlay
 *   MV.state()              what is drawn, for the tests
 *
 * Positions are kilometres in the run's inertial frame N (x, y, z of
 * three.js), held in double precision (JavaScript numbers). Every frame
 * they are taken relative to the camera's focus (the floating origin: the
 * central body's centre, or the followed spacecraft) before they reach the
 * GPU's single precision, so a spacecraft 7,000 km out is drawn steady at
 * its true size. Frames are drawn on requestAnimationFrame, only when
 * something changed. The scene's arrays are plain growable arrays and the
 * frame logic reads their current length, so samples can be appended.
 */
'use strict';

const MV = {
  ready: false, pageReady: false, data: null, frame: 0, style: null, quality: 'full', autoQuality: true,
  autoReduced: false, reduceAboveMs: 50, frameMs: null, dirty: true, view: {mode: 'orbit'}, origin: [0, 0, 0],
  toggles: {paths: true, trails: true, axes: true, headings: true, cones: true, stations: true, labels: true,
            stars: true, groundTrack: false},
  loaded: {earth: '', stars: ''}, textures: {}, playback: {speed: '', playing: false}, live: false,
  crafts: [], stations: [], links: [], labels: [], lastRotation: 0, rendererName: '', software: false,
};
const SOFTWARE_RENDERER = /swiftshader|llvmpipe|softpipe|software/i;  // no graphics card: start in reduced quality
const TRACK_REBUILD_MS = 500;  // [ms] a live ground track is rebuilt at most this often
const ZAXIS = new THREE.Vector3(0, 0, 1);
const TRAIL_FRACTION = 0.1;  // [-] of the run's frames shown as each spacecraft's trail
const ORBIT_VIEW = new THREE.Vector3(1.0, 1.0, 0.6).normalize();  // [-] Whole orbit looks from here without a Sun

// ---------------------------------------------------------------- setup
MV.init = function () {
  MV.scene = new THREE.Scene();
  MV.camera = new THREE.PerspectiveCamera(45, MV.aspect(), 1e-6, 1e9);
  MV.camera.up.copy(ZAXIS);
  MV.sunLight = new THREE.DirectionalLight(new THREE.Color(1, 1, 1), 2.6);
  MV.scene.add(MV.sunLight, MV.sunLight.target);
  MV.ambient = new THREE.AmbientLight(new THREE.Color(1, 1, 1), 0.1);
  MV.scene.add(MV.ambient);
  MV.sky = new THREE.Mesh(MV.sphereGeometry(5e6, 48, 96, 'sky'),
                          new THREE.MeshBasicMaterial({side: THREE.DoubleSide, depthTest: false, depthWrite: false}));
  MV.sky.renderOrder = -10;
  MV.sky.frustumCulled = false;
  MV.sky.visible = false;  // until its texture is loaded
  MV.scene.add(MV.sky);
  MV.sun = new THREE.Sprite(new THREE.SpriteMaterial({blending: THREE.AdditiveBlending, sizeAttenuation: false,
                                                      depthWrite: false, transparent: true}));
  MV.sun.visible = false;
  MV.scene.add(MV.sun);
  MV.earthGroup = new THREE.Group();  // the central body's centre, turning with it
  MV.scene.add(MV.earthGroup);
  MV.craftRoot = new THREE.Group();
  MV.scene.add(MV.craftRoot);
  MV.makeRenderer();
  MV.rendererName = MV.glRenderer();
  MV.software = SOFTWARE_RENDERER.test(MV.rendererName);
  if (MV.software && MV.autoQuality) {  // reduced from the start, not after slow frames
    MV.quality = 'reduced';
    MV.autoReduced = true;
    MV.makeRenderer();
  }
  window.addEventListener('resize', MV.resize);
  MV.loadTextures();
  MV.pageReady = true;
  document.title = MV.software && MV.autoReduced ? 'mv:reduced-software' : 'mv:ready';
  requestAnimationFrame(MV.loop);
};

// The WebGL renderer's name (the unmasked one where the browser gives it).
MV.glRenderer = function () {
  try {
    const gl = MV.renderer.getContext(), info = gl.getExtension('WEBGL_debug_renderer_info');
    return String((info && gl.getParameter(info.UNMASKED_RENDERER_WEBGL)) || gl.getParameter(gl.RENDERER) || '');
  } catch (e) {
    return '';
  }
};

MV.aspect = function () {
  const host = document.getElementById('view');
  return Math.max(1, host.clientWidth || window.innerWidth) / Math.max(1, host.clientHeight || window.innerHeight);
};

MV.resize = function () {
  const host = document.getElementById('view');
  if (MV.renderer) MV.renderer.setSize(host.clientWidth || window.innerWidth, host.clientHeight || window.innerHeight);
  MV.camera.aspect = MV.aspect();
  MV.camera.updateProjectionMatrix();
  MV.dirty = true;
};

// three.js's WebGL renderer; it throws where no WebGL context can start.
MV.createRenderer = function (options) {
  return new THREE.WebGLRenderer(options);
};

// The WebGL renderer, made once: antialiased if the page starts in full
// quality, not if it starts reduced (multisampling is most of a software
// renderer's cost); a later quality switch keeps it. The logarithmic
// depth buffer keeps millimetres and the Moon's distance in one view.
MV.makeRenderer = function () {
  const host = document.getElementById('view'), full = MV.quality === 'full';
  if (MV.renderer) {
    host.removeChild(MV.renderer.domElement);
    MV.renderer.dispose();
    MV.renderer = null;
  }
  let renderer;
  try {
    renderer = MV.createRenderer({antialias: full, logarithmicDepthBuffer: true});
  } catch (e) {
    // No WebGL (no graphics driver and no software fallback): say so in
    // the view instead of failing on every frame.
    MV.webgl = false;
    host.textContent = 'This computer could not start WebGL, which the 3D View draws with. ' +
      'Update the graphics driver, or start the app where a graphics card or software rendering is available.';
    host.className = 'no-webgl';
    MV.makeControls();
    return;
  }
  MV.webgl = true;
  renderer.setPixelRatio(full ? (window.devicePixelRatio || 1) : 1);
  renderer.setSize(host.clientWidth || window.innerWidth, host.clientHeight || window.innerHeight);
  host.appendChild(renderer.domElement);
  renderer.domElement.addEventListener('dblclick', function () { MV.resetView(); });
  MV.renderer = renderer;
  if (MV.style) renderer.setClearColor(new THREE.Color(MV.style.space), 1);
  const target = MV.controls ? MV.controls.target.clone() : null, enabled = MV.controls ? MV.controls.enabled : true;
  MV.makeControls();
  if (target) MV.controls.target.copy(target);
  MV.controls.enabled = enabled;
  MV.dirty = true;
};

// The drawing surface: the renderer's canvas, or the view's own element
// while there is no renderer (no WebGL).
MV.canvas = function () {
  return MV.renderer ? MV.renderer.domElement : document.getElementById('view');
};

MV.makeControls = function () {
  if (MV.controls) MV.controls.dispose();
  MV.controls = new THREE.OrbitControls(MV.camera, MV.canvas());
  MV.controls.enableDamping = false;
  MV.controls.zoomSpeed = 1.5;
  MV.controls.addEventListener('change', function () { MV.dirty = true; });
};

// A latitude/longitude sphere: 'earth' maps longitude -180..180 deg left
// to right (the Earth texture, body-fixed); 'sky' maps right ascension 0 h
// to the middle, increasing to the left (the star map, seen from inside).
MV.sphereGeometry = function (radius, rows, columns, kind) {
  const position = [], normal = [], uv = [], index = [];
  for (let i = 0; i <= rows; i++) {
    const lat = -Math.PI / 2 + Math.PI * i / rows;
    for (let j = 0; j <= columns; j++) {
      const lon = -Math.PI + 2 * Math.PI * j / columns;
      const x = Math.cos(lat) * Math.cos(lon), y = Math.cos(lat) * Math.sin(lon), z = Math.sin(lat);
      position.push(radius * x, radius * y, radius * z);
      normal.push(x, y, z);
      uv.push(kind === 'sky' ? 0.5 - lon / (2 * Math.PI) : (lon + Math.PI) / (2 * Math.PI), i / rows);
    }
  }
  for (let i = 0; i < rows; i++) {
    for (let j = 0; j < columns; j++) {
      const a = i * (columns + 1) + j, b = a + 1, c = a + columns + 1, d = c + 1;
      index.push(a, b, d, a, d, c);
    }
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(position, 3));
  g.setAttribute('normal', new THREE.Float32BufferAttribute(normal, 3));
  g.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2));
  g.setIndex(index);
  return g;
};

MV.loadTextures = function () {
  const size = MV.quality === 'reduced' ? '2k' : '4k';
  const files = {earth: 'earth_day_' + size + '.jpg', stars: 'stars_' + size + '.jpg'};
  const loader = new THREE.TextureLoader();
  Object.keys(files).forEach(function (kind) {
    const file = files[kind];
    const done = function (texture) {
      MV.textures[file] = texture;
      if ((MV.quality === 'reduced' ? '2k' : '4k') !== size) return;  // the quality changed meanwhile
      MV.loaded[kind] = file;
      MV.applyTextures();
    };
    if (MV.textures[file]) { done(MV.textures[file]); return; }
    loader.load(file, function (texture) {
      texture.colorSpace = THREE.SRGBColorSpace;
      if (MV.renderer) texture.anisotropy = Math.min(4, MV.renderer.capabilities.getMaxAnisotropy());
      done(texture);
    }, undefined, function () { MV.loaded[kind] = 'failed: ' + file; });
  });
};

MV.applyTextures = function () {
  const stars = MV.textures[MV.loaded.stars];
  if (stars && MV.sky.material.map !== stars) { MV.sky.material.map = stars; MV.sky.material.needsUpdate = true; }
  const earth = MV.textures[MV.loaded.earth];
  if (earth && MV.body && MV.body.userData.earth && MV.body.material.map !== earth) {
    MV.body.material.map = earth;
    MV.body.material.color.setRGB(1, 1, 1);
    MV.body.material.needsUpdate = true;
  }
  MV.dirty = true;
};

// ---------------------------------------------------------------- style
MV.setStyle = function (style) {
  MV.style = style;
  document.getElementById('theme').textContent = style.css;
  if (!MV.renderer) return;
  MV.renderer.setClearColor(new THREE.Color(style.space), 1);
  MV.drawSunGlow();
  MV.restyle();
};

MV.colour = function (text) { return new THREE.Color(text); };

MV.craftColour = function (n) { return MV.style.crafts[n % MV.style.crafts.length]; };

MV.drawSunGlow = function () {
  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = 128;
  const ctx = canvas.getContext('2d');
  const c = {};
  MV.colour(MV.style.sun).getRGB(c, THREE.SRGBColorSpace);
  const rgba = function (a) {
    return 'rgba(' + Math.round(c.r * 255) + ',' + Math.round(c.g * 255) + ',' + Math.round(c.b * 255) + ',' + a + ')';
  };
  const g = ctx.createRadialGradient(64, 64, 0, 64, 64, 64);
  g.addColorStop(0.0, rgba(1));
  g.addColorStop(0.12, rgba(1));
  g.addColorStop(0.3, rgba(0.35));
  g.addColorStop(1.0, rgba(0));
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, 128, 128);
  if (MV.sun.material.map) MV.sun.material.map.dispose();
  MV.sun.material.map = new THREE.CanvasTexture(canvas);
  MV.sun.material.map.colorSpace = THREE.SRGBColorSpace;
  MV.sun.material.needsUpdate = true;
};

MV.restyle = function () {
  const st = MV.style;
  if (!st || !MV.data) { MV.dirty = true; return; }
  if (MV.body && !MV.body.userData.earth) MV.body.material.color.set(MV.data.body.name === 'Sun' ? st.sun : st.plain);
  if (MV.moon) MV.moon.material.color.set(st.plain);
  if (MV.atmosphere) MV.atmosphere.material.uniforms.colour.value.set(st.atmosphere);
  if (MV.stationPoints) {
    MV.stationPoints.material.color.set(st.station);
    MV.stationPoints.material.size = st.station_px;
  }
  MV.links.forEach(function (link) { link.line.material.color.set(st.link); });
  MV.crafts.forEach(function (c, n) {
    const colour = MV.craftColour(n);
    c.path.material.color.set(colour);
    c.path.material.opacity = st.path_opacity;
    c.trail.material.color.set(colour);
    if (c.track) c.track.material.color.set(colour);
    c.axes.forEach(function (arrow, k) { arrow.setColor(MV.colour(st.axes[k])); });
    c.sunArrow.setColor(MV.colour(st.sun));
    c.nadirArrow.setColor(MV.colour(st.nadir));
    c.velocityArrow.setColor(MV.colour(st.velocity));
    c.cones.forEach(function (cone) {
      cone.material.color.set(cone.userData.plume ? st.plume : st.fov);
      cone.material.opacity = st.cone_opacity;
    });
  });
  MV.labels.forEach(function (label) {
    const dot = label.el.querySelector('.dot');
    if (dot) dot.style.background = label.colour();
  });
  MV.dirty = true;
};

// ---------------------------------------------------------------- the scene
MV.clearScene = function () {
  const drop = function (object) {
    object.traverse(function (o) {
      if (o.geometry) o.geometry.dispose();
      if (o.material && !o.material.map) o.material.dispose();
    });
    if (object.parent) object.parent.remove(object);
  };
  MV.earthGroup.children.slice().forEach(drop);
  MV.craftRoot.children.slice().forEach(drop);
  if (MV.moon) drop(MV.moon);
  if (MV.atmosphere) drop(MV.atmosphere);
  MV.links.forEach(function (link) { drop(link.line); });
  MV.body = MV.atmosphere = MV.moon = MV.stationPoints = null;
  MV.crafts = [];
  MV.links = [];
  MV.labels = [];
  document.getElementById('labels').textContent = '';
};

MV.lineMaterial = function (opacity) {
  return new THREE.LineBasicMaterial({transparent: opacity < 1, opacity: opacity, depthWrite: opacity >= 1});
};

MV.load = function (d, options) {
  const keep = options && options.keepCamera && MV.data ? {position: MV.camera.position.clone(),
    up: MV.camera.up.clone(), target: MV.controls.target.clone(), fov: MV.camera.fov, view: MV.view,
    lastRotation: MV.lastRotation} : null;
  MV.clearScene();
  MV.data = d;
  const body = d.body;
  if (body.radius > 0) {
    const earth = body.earth;
    const material = earth ? new THREE.MeshLambertMaterial() : (body.name === 'Sun' ? new THREE.MeshBasicMaterial()
      : new THREE.MeshLambertMaterial());
    MV.body = new THREE.Mesh(MV.sphereGeometry(body.radius, 96, 192, 'earth'), material);
    MV.body.userData.earth = earth;
    MV.body.scale.z = 1 - (body.flattening || 0);
    MV.earthGroup.add(MV.body);
    if (earth) {
      MV.atmosphere = new THREE.Mesh(new THREE.RingGeometry(0.97, 1.06, 256, 1), MV.atmosphereMaterial());
      MV.atmosphere.frustumCulled = false;
      MV.scene.add(MV.atmosphere);
    }
  }
  if (d.moon) {
    MV.moon = new THREE.Mesh(MV.sphereGeometry(d.moon_radius, 32, 64, 'earth'), new THREE.MeshLambertMaterial());
    MV.scene.add(MV.moon);
    MV.addLabel('Moon', function () { return null; }, function () {
      const m = d.moon[MV.frame];
      return [m[0] - MV.origin[0], m[1] - MV.origin[1], m[2] - MV.origin[2]];
    }, 'moon');
  }
  MV.buildStations();
  d.crafts.forEach(function (c, n) { MV.crafts.push(MV.buildCraft(c, n)); });
  MV.buildLinks();
  MV.applyTextures();
  if (MV.frame >= d.times.length) MV.frame = 0;
  const v = MV.view;
  const valid = v.mode === 'orbit' || (v.mode === 'earth' && body.earth) || (v.craft !== undefined && v.craft < d.crafts.length);
  MV.ready = true;
  MV.restyle();
  MV.setView(valid ? v : {mode: 'orbit'});
  if (keep && valid) {  // the same view, the camera where it was (a live run's result replacing its frames)
    MV.camera.position.copy(keep.position);
    MV.camera.up.copy(keep.up);
    MV.camera.fov = keep.fov;
    MV.camera.updateProjectionMatrix();
    if (MV.view.mode !== 'instrument') {
      MV.makeControls();
      MV.controls.target.copy(keep.target);
      MV.controls.update();
    }
    MV.lastRotation = keep.lastRotation;
  }
  if (MV.autoQuality && MV.quality === 'full') setTimeout(MV.checkFrameTime, 50);
  return d.times.length;
};

// The atmosphere's rim: a ring around the Earth's outline, facing the
// camera (MV.placeAtmosphere), brightest just outside the limb and on the
// Sun's side. A ring, not a shell, so only its few pixels are shaded.
MV.atmosphereMaterial = function () {
  return new THREE.ShaderMaterial({
    uniforms: {colour: {value: new THREE.Color(1, 1, 1)}, sunView: {value: new THREE.Vector3(1, 0, 0)}},
    vertexShader: [
      '#include <common>', '#include <logdepthbuf_pars_vertex>',
      'varying vec2 vPlane;',
      'void main() {',
      '  vPlane = position.xy;',
      '  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);',
      '  #include <logdepthbuf_vertex>',
      '}'].join('\n'),
    fragmentShader: [
      '#include <logdepthbuf_pars_fragment>',
      'uniform vec3 colour; uniform vec3 sunView; varying vec2 vPlane;',
      'void main() {',
      '  #include <logdepthbuf_fragment>',
      '  float r = length(vPlane);',
      '  float glow = r < 1.0 ? smoothstep(0.97, 1.0, r) : 1.0 - smoothstep(1.0, 1.06, r);',
      '  float lit = clamp(dot(vec3(vPlane / max(r, 1e-6), 0.0), sunView) * 0.8 + 0.45, 0.0, 1.0);',
      '  float a = glow * glow * lit * 0.85;',
      '  gl_FragColor = vec4(colour * a, a);',
      '}'].join('\n'),
    transparent: true, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide,
  });
};

// Where the Earth's outline is seen from the camera: the circle where the
// lines of sight touch the sphere, at R^2/d from its centre towards the
// camera, of radius R sqrt(1 - R^2/d^2). The ring is turned so that its
// x and y axes are the camera's (its shader's light direction).
MV.placeAtmosphere = function (light) {
  const atmosphere = MV.atmosphere, cam = MV.camera;
  atmosphere.visible = MV.quality === 'full';
  if (!atmosphere.visible) return;
  const centre = MV.earthGroup.position, toCamera = cam.position.clone().sub(centre), d = toCamera.length();
  const radius = MV.data.body.radius;
  if (d <= radius * 1.001) { atmosphere.visible = false; return; }
  toCamera.normalize();
  atmosphere.position.copy(centre).addScaledVector(toCamera, radius * radius / d);
  atmosphere.quaternion.copy(cam.quaternion);
  atmosphere.scale.setScalar(radius * Math.sqrt(1 - radius * radius / (d * d)));
  atmosphere.material.uniforms.sunView.value.copy(light).transformDirection(cam.matrixWorldInverse);
};

MV.buildStations = function () {
  const d = MV.data;
  if (!d.stations.length) return;
  const p = [];
  d.stations.forEach(function (s) { p.push(s.p[0] * 1.0005, s.p[1] * 1.0005, s.p[2] * 1.0005); });
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(p, 3));
  MV.stationPoints = new THREE.Points(g, new THREE.PointsMaterial({sizeAttenuation: false}));
  MV.earthGroup.add(MV.stationPoints);
  d.stations.forEach(function (s, k) {
    MV.addLabel(s.name, function () { return null; }, function () { return MV.stationWorld(k); }, 'station');
  });
};

MV.stationWorld = function (k) {  // a station in the scene, relative to the floating origin
  const s = MV.data.stations[k].p, a = MV.rotation(), c = Math.cos(a), sn = Math.sin(a);
  return [c * s[0] - sn * s[1] - MV.origin[0], sn * s[0] + c * s[1] - MV.origin[1], s[2] - MV.origin[2]];
};

MV.buildLinks = function () {
  const d = MV.data;
  d.stations.forEach(function (s, k) {
    d.crafts.forEach(function (c, n) {
      const g = new THREE.BufferGeometry();
      g.setAttribute('position', new THREE.Float32BufferAttribute(new Float32Array(6), 3));
      const line = new THREE.Line(g, MV.lineMaterial(0.9));
      line.frustumCulled = false;
      MV.scene.add(line);
      MV.links.push({station: k, craft: n, line: line});
    });
  });
};

MV.arrow = function (length) {
  return new THREE.ArrowHelper(new THREE.Vector3(1, 0, 0), new THREE.Vector3(0, 0, 0), length, 0, 0.2 * length,
                               0.08 * length);
};

// A cone: apex at `apex`, about the unit `axis`, of half-angle `half` [deg]
// (up to 180), slant length `slant` (as gui/model_view_widget.cone_mesh).
MV.coneGeometry = function (apex, axis, half, slant, segments) {
  const a = new THREE.Vector3().fromArray(axis).normalize();
  const helper = Math.abs(a.x) < 0.9 ? new THREE.Vector3(1, 0, 0) : new THREE.Vector3(0, 1, 0);
  const u = new THREE.Vector3().crossVectors(a, helper).normalize(), w = new THREE.Vector3().crossVectors(a, u);
  const h = Math.min(Math.max(half, 0), 180) * Math.PI / 180;
  const centre = new THREE.Vector3().fromArray(apex).addScaledVector(a, slant * Math.cos(h));
  const radius = slant * Math.sin(h), p = [apex[0], apex[1], apex[2]], index = [];
  for (let k = 0; k < segments; k++) {
    const t = 2 * Math.PI * k / segments;
    const r = centre.clone().addScaledVector(u, radius * Math.cos(t)).addScaledVector(w, radius * Math.sin(t));
    p.push(r.x, r.y, r.z);
  }
  p.push(centre.x, centre.y, centre.z);
  for (let k = 0; k < segments; k++) {
    index.push(0, 1 + k, 1 + (k + 1) % segments, segments + 1, 1 + (k + 1) % segments, 1 + k);
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(p, 3));
  g.setIndex(index);
  return g;
};

MV.buildCraft = function (c, n) {
  const group = new THREE.Group(), body = new THREE.Group(), headings = new THREE.Group();
  group.add(body, headings);
  MV.craftRoot.add(group);
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(c.mesh.p, 3));
  g.setAttribute('normal', new THREE.Float32BufferAttribute(c.mesh.n, 3));
  g.setAttribute('color', new THREE.Float32BufferAttribute(c.mesh.c, 3));
  const mesh = new THREE.Mesh(g, new THREE.MeshStandardMaterial({vertexColors: true, metalness: 0.15, roughness: 0.6,
                                                                 side: THREE.DoubleSide}));
  body.add(mesh);
  const axes = [0, 1, 2].map(function (k) {
    const arrow = MV.arrow(1.2 * c.size), e = [0, 0, 0];
    e[k] = 1;
    arrow.setDirection(new THREE.Vector3().fromArray(e));
    body.add(arrow);
    return arrow;
  });
  const cones = [];
  c.equipment.forEach(function (item, k) {
    const slant = 0.45 * c.size;
    [[item.fov, item.b, false], [item.plume, item.b.map(function (v) { return -v; }), true]].forEach(function (spec) {
      if (spec[0] === null || spec[0] === undefined) return;
      const half = spec[2] ? spec[0] : spec[0] / 2;
      const cone = new THREE.Mesh(MV.coneGeometry(item.p, spec[1], half, slant, 32),
        new THREE.MeshBasicMaterial({transparent: true, depthWrite: false, side: THREE.DoubleSide}));
      cone.userData = {item: k, plume: spec[2]};
      body.add(cone);
      cones.push(cone);
    });
  });
  const sunArrow = MV.arrow(1.6 * c.size), nadirArrow = MV.arrow(1.6 * c.size), velocityArrow = MV.arrow(1.6 * c.size);
  headings.add(sunArrow, nadirArrow, velocityArrow);
  const path = new THREE.Line(new THREE.BufferGeometry(), MV.lineMaterial(0.45));
  path.geometry.setAttribute('position', new THREE.BufferAttribute(new Float32Array(3 * Math.max(2, c.path.length)), 3));
  path.geometry.setDrawRange(0, c.path.length);
  path.frustumCulled = false;
  MV.scene.add(path);
  const trailLength = MV.data.trail_frames || Math.max(2, Math.round(TRAIL_FRACTION * MV.data.times.length) + 1);
  const trail = new THREE.Line(new THREE.BufferGeometry(), MV.lineMaterial(1));
  trail.geometry.setAttribute('position', new THREE.BufferAttribute(new Float32Array(3 * trailLength), 3));
  trail.frustumCulled = false;
  MV.scene.add(trail);
  let track = null;
  if (c.track && MV.data.body.earth) {
    track = new THREE.Line(MV.trackGeometry(c.track), MV.lineMaterial(0.8));
    track.frustumCulled = false;
    MV.earthGroup.add(track);
  }
  const craft = {data: c, group: group, body: body, headings: headings, mesh: mesh, axes: axes, cones: cones,
                 sunArrow: sunArrow, nadirArrow: nadirArrow, velocityArrow: velocityArrow, path: path, trail: trail,
                 trailLength: trailLength, track: track, pathOrigin: null, trackBuilt: 0, trackDirty: false};
  MV.addLabel(c.name, function () { return MV.craftColour(n); }, function () {
    const p = c.pos[MV.frame];
    return [p[0] - MV.origin[0], p[1] - MV.origin[1], p[2] - MV.origin[2]];
  }, 'craft', n);
  return craft;
};

// The ground track on the body's surface, subdivided so that no chord
// between points cuts below it (at most 1 degree apart).
MV.trackGeometry = function (track) {
  const a = MV.data.body.radius * 1.0015, b = a * (1 - (MV.data.body.flattening || 0)), p = [];
  const unit = function (lat, lon) {
    const f = Math.PI / 180;
    return new THREE.Vector3(Math.cos(lat * f) * Math.cos(lon * f), Math.cos(lat * f) * Math.sin(lon * f),
                             Math.sin(lat * f));
  };
  const push = function (u) {
    const t = 1 / Math.sqrt((u.x * u.x + u.y * u.y) / (a * a) + u.z * u.z / (b * b));
    p.push(u.x * t, u.y * t, u.z * t);
  };
  let previous = null;
  track.forEach(function (point) {
    const u = unit(point[0], point[1]);
    if (previous) {
      const angle = previous.angleTo(u), steps = Math.ceil(angle / (Math.PI / 180));
      for (let k = 1; k < steps; k++) {
        push(previous.clone().lerp(u, k / steps).normalize());
      }
    }
    push(u);
    previous = u;
  });
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(p, 3));
  return g;
};

MV.addLabel = function (text, colour, where, kind, craft) {
  const el = document.createElement('div');
  el.className = 'label';
  if (kind === 'craft') {
    const dot = document.createElement('span');
    dot.className = 'dot';
    el.appendChild(dot);
  }
  el.appendChild(document.createTextNode(text));
  document.getElementById('labels').appendChild(el);
  MV.labels.push({el: el, text: text, colour: colour, where: where, kind: kind, craft: craft, shown: false});
};

// ---------------------------------------------------------------- frames and views
MV.rotation = function () {
  const r = MV.data && MV.data.body.rotation;
  return r ? r[Math.min(MV.frame, r.length - 1)] : 0;
};

MV.setFrame = function (frame) {
  if (!MV.data) return;
  MV.frame = Math.max(0, Math.min(frame, MV.data.times.length - 1));
  MV.dirty = true;
};

MV.scaleFor = function (c) {
  const mode = MV.view.mode;
  if (mode === 'follow' || mode === 'instrument') return 1;
  return Math.max(1, MV.data.orbit_fraction * MV.data.extent / c.size);
};

MV.dcm = function (c) { return c.dcm ? c.dcm[MV.frame] : [1, 0, 0, 0, 1, 0, 0, 0, 1]; };

MV.toN = function (d, v) {  // C^T v, C = [BN] row-major: a body vector in N
  return new THREE.Vector3(d[0] * v[0] + d[3] * v[1] + d[6] * v[2], d[1] * v[0] + d[4] * v[1] + d[7] * v[2],
                           d[2] * v[0] + d[5] * v[1] + d[8] * v[2]);
};

MV.setView = function (spec) {
  if (!MV.data) { MV.view = spec; return; }
  MV.view = spec;
  MV.resetView();
};

MV.resetView = function () {
  if (!MV.data) return;
  const d = MV.data, v = MV.view, cam = MV.camera;
  MV.update();
  cam.fov = 45;
  if (v.mode === 'orbit' || v.mode === 'earth') {
    cam.up.copy(ZAXIS);
    MV.makeControls();
    const distance = d.extent / Math.tan(cam.fov * Math.PI / 360) * 1.1;
    cam.position.copy(MV.orbitDirection()).multiplyScalar(distance);
    MV.controls.target.set(0, 0, 0);
    MV.controls.update();
    MV.controls.minDistance = Math.max(d.body.radius * 1.02, 1e-3);
    MV.controls.maxDistance = distance * 20;
    MV.controls.enabled = true;
    MV.lastRotation = MV.rotation();
  } else if (v.mode === 'follow') {
    const c = d.crafts[v.craft], p = c.pos[MV.frame], vel = c.vel[MV.frame];
    const up = new THREE.Vector3().fromArray(p).normalize();
    const back = new THREE.Vector3().fromArray(vel).normalize().negate();
    if (!isFinite(back.x) || back.lengthSq() === 0) back.set(-1, -1, 0).normalize();
    cam.up.copy(up);
    MV.makeControls();
    cam.position.copy(back.multiplyScalar(2.6 * c.size).addScaledVector(up, 1.1 * c.size));
    MV.controls.target.set(0, 0, 0);
    MV.controls.update();
    MV.controls.minDistance = 0.3 * c.size;
    MV.controls.maxDistance = 1e6;
    MV.controls.enabled = true;
  } else if (v.mode === 'instrument') {
    if (MV.controls) MV.controls.enabled = false;
    const item = v.item !== undefined ? d.crafts[v.craft].equipment[v.item] : null;
    if (item && item.fov) cam.fov = Math.min(150, Math.max(1, item.fov));
    else cam.fov = 60;
  }
  cam.near = 1e-6;
  cam.far = 1e9;
  cam.updateProjectionMatrix();
  MV.dirty = true;
};

// Whole orbit looks from three quarters towards the Sun and a little from
// the north, so the body is seen mostly lit.
MV.orbitDirection = function () {
  const d = MV.data;
  if (!d.sun) return ORBIT_VIEW.clone();
  const sun = new THREE.Vector3().fromArray(d.sun[MV.frame]);
  const side = new THREE.Vector3().crossVectors(ZAXIS, sun);
  if (side.lengthSq() < 1e-6) side.set(1, 0, 0);
  return sun.multiplyScalar(0.75).addScaledVector(side.normalize(), 0.6).addScaledVector(ZAXIS, 0.35).normalize();
};

// Where the camera of an instrument view is, and where it looks: from a
// body axis (`axis`, e.g. [0, 0, 1]), just outside the model along it, or
// from a mounted item (`item`), a little in front of it; in N.
MV.instrumentPose = function () {
  const d = MV.data, v = MV.view, c = d.crafts[v.craft], dcm = MV.dcm(c);
  let position = [0, 0, 0], look = v.axis || [1, 0, 0];
  if (v.item !== undefined) {
    const item = c.equipment[v.item];
    look = item.b;
    position = [0, 1, 2].map(function (k) { return item.p[k] + 0.02 * c.size * look[k]; });
  } else {
    let reach = 0;
    for (let i = 0; i < c.mesh.p.length; i += 3) {
      reach = Math.max(reach, c.mesh.p[i] * look[0] + c.mesh.p[i + 1] * look[1] + c.mesh.p[i + 2] * look[2]);
    }
    position = look.map(function (x) { return x * (reach + 0.02 * c.size); });
  }
  const lookN = MV.toN(dcm, look).normalize();
  const ref = Math.abs(look[2]) < 0.9 ? [0, 0, 1] : [1, 0, 0];
  const upN = MV.toN(dcm, ref);
  upN.addScaledVector(lookN, -upN.dot(lookN)).normalize();
  return {position: MV.toN(dcm, position), look: lookN, up: upN};
};

MV.update = function () {
  const d = MV.data;
  if (!d) return;
  const f = MV.frame, v = MV.view, st = MV.style, t = MV.toggles;
  const focus = (v.mode === 'follow' || v.mode === 'instrument') ? d.crafts[v.craft] : null;
  const o = focus ? focus.pos[f] : [0, 0, 0];
  MV.origin = o;
  const rotation = MV.rotation();
  MV.earthGroup.position.set(-o[0], -o[1], -o[2]);
  MV.earthGroup.rotation.set(0, 0, rotation);
  if (v.mode === 'earth') {  // the camera turns with the Earth
    MV.camera.position.applyAxisAngle(ZAXIS, rotation - MV.lastRotation);
    MV.controls.update();
  }
  MV.lastRotation = rotation;
  if (MV.stationPoints) MV.stationPoints.visible = t.stations;
  const sun = d.sun ? new THREE.Vector3().fromArray(d.sun[f]) : null;
  if (MV.moon) {
    const m = d.moon[f];
    MV.moon.position.set(m[0] - o[0], m[1] - o[1], m[2] - o[2]);
  }
  MV.crafts.forEach(function (c, n) {
    const p = c.data.pos[f], k = MV.scaleFor(c.data), dcm = MV.dcm(c.data);
    c.group.position.set(p[0] - o[0], p[1] - o[1], p[2] - o[2]);
    c.group.scale.setScalar(k);
    const m = new THREE.Matrix4().set(dcm[0], dcm[3], dcm[6], 0, dcm[1], dcm[4], dcm[7], 0, dcm[2], dcm[5], dcm[8], 0,
                                      0, 0, 0, 1);
    c.body.quaternion.setFromRotationMatrix(m);
    const instrument = v.mode === 'instrument' && v.craft === n;  // seen from it: its own arrows are not drawn
    c.axes.forEach(function (a) { a.visible = t.axes && !instrument; });
    c.cones.forEach(function (cone) {
      cone.visible = t.cones && !(instrument && v.item === cone.userData.item && !cone.userData.plume);
    });
    c.sunArrow.visible = t.headings && sun !== null && !instrument;
    if (sun) c.sunArrow.setDirection(sun);
    c.nadirArrow.visible = t.headings && !instrument;
    c.nadirArrow.setDirection(new THREE.Vector3(-p[0], -p[1], -p[2]).normalize());
    const vel = new THREE.Vector3().fromArray(c.data.vel[f]);
    c.velocityArrow.visible = t.headings && vel.lengthSq() > 0 && !instrument;
    if (vel.lengthSq() > 0) c.velocityArrow.setDirection(vel.normalize());
    // The path and the trail, relative to the floating origin.
    c.path.visible = t.paths;
    if (t.paths && (!c.pathOrigin || c.pathOrigin[0] !== o[0] || c.pathOrigin[1] !== o[1] || c.pathOrigin[2] !== o[2])) {
      const path = c.data.path;
      if (c.path.geometry.attributes.position.count < path.length) {  // a live path outgrew its buffer: double it
        c.path.geometry.dispose();
        c.path.geometry = new THREE.BufferGeometry();
        c.path.geometry.setAttribute('position', new THREE.BufferAttribute(new Float32Array(6 * path.length), 3));
      }
      c.path.geometry.setDrawRange(0, path.length);
      const a = c.path.geometry.attributes.position;
      for (let i = 0; i < path.length; i++) a.setXYZ(i, path[i][0] - o[0], path[i][1] - o[1], path[i][2] - o[2]);
      a.needsUpdate = true;
      c.pathOrigin = o.slice();
    }
    c.trail.visible = t.trails;
    if (t.trails) {
      const a = c.trail.geometry.attributes.position, first = Math.max(0, f - c.trailLength + 1);
      for (let i = first; i <= f; i++) {
        const q = c.data.pos[i];
        a.setXYZ(i - first, q[0] - o[0], q[1] - o[1], q[2] - o[2]);
      }
      a.needsUpdate = true;
      c.trail.geometry.setDrawRange(0, f - first + 1);
    }
    if (c.track) {
      c.track.visible = t.groundTrack;
      if (t.groundTrack && c.trackDirty && performance.now() - c.trackBuilt > TRACK_REBUILD_MS) {
        c.track.geometry.dispose();
        c.track.geometry = MV.trackGeometry(c.data.track);
        c.trackDirty = false;
        c.trackBuilt = performance.now();
      }
    }
  });
  MV.links.forEach(function (link) {
    const seen = d.stations[link.station].visible[link.craft][f];
    link.line.visible = t.stations && Boolean(seen);
    if (link.line.visible) {
      const s = MV.stationWorld(link.station), p = d.crafts[link.craft].pos[f], a = link.line.geometry.attributes.position;
      a.setXYZ(0, s[0], s[1], s[2]);
      a.setXYZ(1, p[0] - o[0], p[1] - o[1], p[2] - o[2]);
      a.needsUpdate = true;
    }
  });
  const cam = MV.camera;
  if (v.mode === 'instrument') {
    const pose = MV.instrumentPose();
    cam.position.copy(pose.position);
    cam.up.copy(pose.up);
    cam.lookAt(pose.position.clone().add(pose.look));
  }
  cam.updateMatrixWorld();
  // Lighting: the Sun's direction, or a light from the camera without one.
  const light = sun ? sun.clone() : cam.position.clone().normalize();
  MV.sunLight.position.copy(light);
  MV.sunLight.target.position.set(0, 0, 0);
  if (MV.atmosphere) MV.placeAtmosphere(light);
  MV.sun.visible = sun !== null && Boolean(st);
  if (sun) {
    MV.sun.position.copy(cam.position).addScaledVector(sun, 1e7);
    const px = st ? st.sun_px : 0, h = MV.canvas().clientHeight || window.innerHeight;
    const scale = px * Math.tan(cam.fov * Math.PI / 360) * 2 / Math.max(1, h);
    MV.sun.scale.set(scale, scale, 1);
  }
  MV.sky.visible = t.stars && Boolean(MV.sky.material.map);
  MV.sky.position.copy(cam.position);
  MV.updateHud();
};

MV.elapsed = function (seconds) {
  const whole = Math.round(seconds), days = Math.floor(whole / 86400);
  let rest = whole - 86400 * days;
  const h = Math.floor(rest / 3600);
  rest -= 3600 * h;
  const m = Math.floor(rest / 60), s = rest - 60 * m, two = function (x) { return (x < 10 ? '0' : '') + x; };
  return (days ? days + 'd ' : '') + two(h) + ':' + two(m) + ':' + two(s);
};

MV.utc = function (seconds) {  // ISO 8601, UTC, whole seconds, with Z
  return new Date(MV.data.epoch_ms + seconds * 1000).toISOString().replace(/\.\d{3}Z$/, 'Z');
};

MV.updateHud = function () {
  const d = MV.data, f = MV.frame, t = d.times[f], v = MV.view;
  const speed = MV.playback.speed ? '  ' + MV.playback.speed + (MV.playback.playing ? '' : ' (paused)') : '';
  document.getElementById('hud-time').textContent = MV.utc(t) + '\nT+' + MV.elapsed(t - d.times[0]) + speed;
  let text = '';
  if (v.mode === 'follow' || v.mode === 'instrument') {
    const c = d.crafts[v.craft], vel = c.vel[f];
    const speedKm = Math.sqrt(vel[0] * vel[0] + vel[1] * vel[1] + vel[2] * vel[2]);
    text = '\n' + c.name + (c.alt ? '  altitude ' + c.alt[f].toFixed(1) + ' km' : '') + '  speed ' +
      speedKm.toFixed(3) + ' km/s';
  }
  document.getElementById('hud-craft').textContent = text;
  document.getElementById('live').style.display = MV.live ? 'inline-block' : 'none';
};

MV.updateLabels = function () {
  const cam = MV.camera, w = MV.canvas().clientWidth, h = MV.canvas().clientHeight;
  const centre = MV.earthGroup.position, radius = MV.data.body.radius;
  MV.labels.forEach(function (label) {
    let show = MV.toggles.labels && !(label.kind === 'station' && !MV.toggles.stations);
    const v = MV.view;
    if (label.kind === 'craft' && (v.mode === 'follow' || v.mode === 'instrument') && v.craft === label.craft) show = false;
    let p = null;
    if (show) {
      p = new THREE.Vector3().fromArray(label.where());
      // Hidden behind the central body?
      const ray = p.clone().sub(cam.position), length = ray.length();
      ray.normalize();
      const oc = cam.position.clone().sub(centre), b = oc.dot(ray), c = oc.lengthSq() - radius * radius;
      const disc = b * b - c;
      if (radius > 0 && disc > 0 && -b - Math.sqrt(disc) > 0 && -b - Math.sqrt(disc) < length * 0.999) show = false;
      p.project(cam);
      if (p.z > 1 || p.z < -1 || Math.abs(p.x) > 1.05 || Math.abs(p.y) > 1.05) show = false;
    }
    label.shown = show;
    label.el.style.display = show ? 'block' : 'none';
    if (show) {
      label.el.style.left = ((p.x + 1) / 2 * w).toFixed(1) + 'px';
      label.el.style.top = ((1 - p.y) / 2 * h).toFixed(1) + 'px';
    }
  });
};

// Without WebGL the scene is still updated (time, views, lines of sight,
// labels), only not drawn.
MV.render = function () {
  MV.update();
  if (MV.renderer) MV.renderer.render(MV.scene, MV.camera);
  MV.updateLabels();
  MV.dirty = false;
};

MV.loop = function () {
  if (MV.dirty && MV.data && MV.style) MV.render();
  requestAnimationFrame(MV.loop);
};

// ---------------------------------------------------------------- toggles, quality, playback
MV.setToggle = function (name, on) {
  if (!(name in MV.toggles)) return false;
  MV.toggles[name] = Boolean(on);
  MV.dirty = true;
  return true;
};

MV.setQuality = function (quality) {
  const wanted = quality === 'reduced' ? 'reduced' : 'full';
  if (wanted === MV.quality) return;
  MV.quality = wanted;
  // The same renderer: a new WebGL context per switch is slow, and on
  // software GL the second one could fail (Windows CI). Antialiasing
  // stays as the renderer was made; the pixel ratio, textures and
  // atmosphere follow the quality.
  if (MV.renderer) {
    MV.renderer.setPixelRatio(wanted === 'full' ? (window.devicePixelRatio || 1) : 1);
    MV.resize();
  }
  MV.loadTextures();
  MV.dirty = true;
};

MV.setPlayback = function (p) { MV.playback = p; MV.dirty = true; };

MV.setLive = function (on) { MV.live = Boolean(on); MV.dirty = true; };

// A live run's new frames, appended to the scene's arrays (the frame
// logic reads their current length); `f.follow` shows the newest.
MV.append = function (f) {
  const d = MV.data;
  if (!d || !f.times.length) return d ? d.times.length : 0;
  const push = function (target, rows) { for (let i = 0; i < rows.length; i++) target.push(rows[i]); };
  push(d.times, f.times);
  if (d.body.rotation && f.rotation) push(d.body.rotation, f.rotation);
  if (d.sun && f.sun) push(d.sun, f.sun);
  if (d.moon && f.moon) push(d.moon, f.moon);
  f.crafts.forEach(function (n, k) {
    const c = d.crafts[k], craft = MV.crafts[k];
    push(c.pos, n.pos);
    push(c.vel, n.vel);
    if (c.alt && n.alt) push(c.alt, n.alt);
    if (c.dcm && n.dcm) push(c.dcm, n.dcm);
    push(c.path, n.path);
    craft.pathOrigin = null;
    if (c.track && n.track) {
      push(c.track, n.track);
      craft.trackDirty = true;
    }
  });
  d.stations.forEach(function (s, k) {
    s.visible.forEach(function (row, n) { push(row, f.visible[k][n]); });
  });
  d.extent = Math.max(d.extent, f.extent);
  if (f.follow) MV.frame = d.times.length - 1;
  MV.dirty = true;
  return d.times.length;
};

MV.configure = function (options) {
  if ('auto_quality' in options) MV.autoQuality = Boolean(options.auto_quality);
  if ('reduce_above_ms' in options) MV.reduceAboveMs = options.reduce_above_ms;
};

// Draw `count` frames, each waited for (reading a pixel back waits for
// the frame to be drawn), and time them [ms].
MV.benchmark = function (count) {
  if (!MV.renderer) return null;
  const gl = MV.renderer.getContext(), times = [], pixel = new Uint8Array(4);
  for (let k = 0; k < count; k++) {
    const start = performance.now();
    MV.render();
    gl.readPixels(0, 0, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, pixel);
    times.push(performance.now() - start);
  }
  times.sort(function (a, b) { return a - b; });
  const mean = times.reduce(function (a, b) { return a + b; }, 0) / times.length;
  return {count: count, mean: mean, median: times[Math.floor(times.length / 2)], min: times[0],
          max: times[times.length - 1], width: MV.renderer.domElement.width, height: MV.renderer.domElement.height,
          quality: MV.quality};
};

// Reduced quality when the median of a few frames takes longer than
// reduceAboveMs (under 20 frames a second, as in software rendering).
MV.shouldReduce = function (times) {
  if (!times.length) return false;
  const sorted = times.slice().sort(function (a, b) { return a - b; });
  return sorted[Math.floor(sorted.length / 2)] > MV.reduceAboveMs;
};

MV.checkFrameTime = function () {
  if (!MV.data || !MV.style || MV.quality !== 'full' || !MV.autoQuality) return;
  if (!MV.loaded.earth && MV.data.body.earth || !MV.loaded.stars) { setTimeout(MV.checkFrameTime, 200); return; }
  const result = MV.benchmark(5);
  if (!result) return;  // no WebGL: nothing to time
  MV.frameMs = result.median;
  if (MV.shouldReduce([result.median])) {
    MV.autoReduced = true;
    MV.setQuality('reduced');
    document.title = 'mv:reduced-auto';
  }
};

MV.state = function () {
  const d = MV.data, v = MV.view;
  const crafts = MV.crafts.map(function (c) {
    const world = new THREE.Vector3();
    c.group.getWorldPosition(world);
    const x = new THREE.Vector3(1, 0, 0).applyQuaternion(c.body.quaternion);
    return {world: world.toArray(), scale: c.group.scale.x, axes: c.axes[0].visible, xAxis: x.toArray(),
            path: c.path.visible, trail: c.trail.visible, headings: c.nadirArrow.visible,
            cones: c.cones.map(function (k) { return k.visible; }), track: c.track ? c.track.visible : null,
            colour: '#' + c.trail.material.color.getHexString(THREE.SRGBColorSpace)};
  });
  const earth = MV.body && MV.body.material.map ? MV.body.material.map.image : null;
  return {
    ready: MV.ready, frame: MV.frame, frames: d ? d.times.length : 0, view: v, quality: MV.quality,
    autoReduced: MV.autoReduced, loaded: MV.loaded, toggles: MV.toggles, origin: MV.origin, crafts: crafts,
    earthTexture: earth ? [earth.width, earth.height] : null, stars: MV.sky.visible,
    starsTexture: MV.sky.material.map ? [MV.sky.material.map.image.width, MV.sky.material.map.image.height] : null,
    atmosphere: MV.atmosphere ? MV.atmosphere.visible : null, moon: MV.moon ? MV.moon.position.toArray() : null,
    links: MV.links.map(function (l) { return l.line.visible; }),
    labels: MV.labels.filter(function (l) { return l.shown; }).map(function (l) { return l.text; }),
    hud: document.getElementById('hud-time').textContent + document.getElementById('hud-craft').textContent,
    styleMode: MV.style ? MV.style.mode : null, webgl: MV.webgl,
    clear: '#' + (MV.renderer ? MV.renderer.getClearColor(new THREE.Color())
      : new THREE.Color(MV.style ? MV.style.space : 0)).getHexString(THREE.SRGBColorSpace),
    hudBackground: getComputedStyle(document.getElementById('hud')).backgroundColor,
    fov: MV.camera.fov, pixelRatio: MV.renderer ? MV.renderer.getPixelRatio() : null,
    gl2: MV.renderer ? MV.renderer.capabilities.isWebGL2 : false,
    cameraDistance: MV.camera.position.length(), live: MV.live, software: MV.software,
    rendererName: MV.rendererName, times: d ? [d.times[0], d.times[d.times.length - 1]] : null,
    pathPoints: MV.crafts.map(function (c) { return c.path.geometry.drawRange.count; }),
    trackPoints: MV.crafts.map(function (c) { return c.data.track ? c.data.track.length : null; }),
  };
};

MV.init();
