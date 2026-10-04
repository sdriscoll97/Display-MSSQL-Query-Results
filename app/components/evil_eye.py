import reflex as rx

from reflex.utils.imports import ImportVar

from app.states.appearance_state import AppearanceState


EVIL_EYE_BRIDGE = r"""
/*!
 * React Bits EvilEye — David Haz (DavidHDev).
 * https://reactbits.dev/backgrounds/evil-eye
 * https://github.com/DavidHDev/react-bits/blob/main/LICENSE.md
 * MIT License + Commons Clause.
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 * The above copyright notice and this permission notice shall be included in
 * all copies or substantial portions of the Software.
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
 * THE SOFTWARE.
 *
 * Commons Clause License Condition v1.0
 * The Software is provided to you by the Licensor under the License, as defined
 * below, subject to the following condition.
 * Without limiting other conditions in the License, the grant of rights under
 * the License will not include, and the License does not grant to you, the
 * right to Sell the Software.
 * For purposes of the foregoing, "Sell" means practicing any or all of the
 * rights granted to you under the License to provide to third parties, for a
 * fee or other consideration (including without limitation fees for hosting or
 * consulting/support services related to the Software), a product or service
 * whose value derives, entirely or substantially, from the functionality of
 * the Software. Any license notice or attribution required by the License
 * must also include this Commons Clause License Condition notice.
 * Software: React Bits. License: MIT. Licensor: David Haz.
 *
 * Local integration: scoped names, createElement instead of the JSX return,
 * Tailwind container sizing, and guarded WebGL lifecycle.
 */
function rbEyeHexToVec3(hex) {
  const h = hex.replace('#', '');
  return [
    parseInt(h.slice(0, 2), 16) / 255,
    parseInt(h.slice(2, 4), 16) / 255,
    parseInt(h.slice(4, 6), 16) / 255
  ];
}

function rbEyeGenerateNoiseTexture(size = 256) {
  const data = new Uint8Array(size * size * 4);
  function hash(x, y, s) {
    let n = x * 374761393 + y * 668265263 + s * 1274126177;
    n = Math.imul(n ^ (n >>> 13), 1274126177);
    return ((n ^ (n >>> 16)) >>> 0) / 4294967296;
  }
  function noise(px, py, freq, seed) {
    const fx = (px / size) * freq;
    const fy = (py / size) * freq;
    const ix = Math.floor(fx);
    const iy = Math.floor(fy);
    const tx = fx - ix;
    const ty = fy - iy;
    const w = freq | 0;
    const v00 = hash(((ix % w) + w) % w, ((iy % w) + w) % w, seed);
    const v10 = hash((((ix + 1) % w) + w) % w, ((iy % w) + w) % w, seed);
    const v01 = hash(((ix % w) + w) % w, (((iy + 1) % w) + w) % w, seed);
    const v11 = hash((((ix + 1) % w) + w) % w, (((iy + 1) % w) + w) % w, seed);
    return v00 * (1 - tx) * (1 - ty) + v10 * tx * (1 - ty) + v01 * (1 - tx) * ty + v11 * tx * ty;
  }
  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      let v = 0;
      let amp = 0.4;
      let totalAmp = 0;
      for (let o = 0; o < 8; o++) {
        const f = 32 * (1 << o);
        v += amp * noise(x, y, f, o * 31);
        totalAmp += amp;
        amp *= 0.65;
      }
      v /= totalAmp;
      v = (v - 0.5) * 2.2 + 0.5;
      v = Math.max(0, Math.min(1, v));
      const val = Math.round(v * 255);
      const i = (y * size + x) * 4;
      data[i] = val;
      data[i + 1] = val;
      data[i + 2] = val;
      data[i + 3] = 255;
    }
  }
  return data;
}

const rbEyeVertexShader = `
attribute vec2 uv;
attribute vec2 position;
varying vec2 vUv;
void main() {
  vUv = uv;
  gl_Position = vec4(position, 0, 1);
}
`;

const rbEyeFragmentShader = `
precision highp float;
uniform float uTime;
uniform vec3 uResolution;
uniform sampler2D uNoiseTexture;
uniform float uPupilSize;
uniform float uIrisWidth;
uniform float uGlowIntensity;
uniform float uIntensity;
uniform float uScale;
uniform float uNoiseScale;
uniform vec2 uMouse;
uniform float uPupilFollow;
uniform float uFlameSpeed;
uniform vec3 uEyeColor;
uniform vec3 uBgColor;
uniform bool uLightMode;

void main() {
  vec2 uv = (gl_FragCoord.xy * 2.0 - uResolution.xy) / uResolution.y;
  uv /= uScale;
  float ft = uTime * uFlameSpeed;
  float polarRadius = length(uv) * 2.0;
  float polarAngle = (2.0 * atan(uv.x, uv.y)) / 6.28 * 0.3;
  vec2 polarUv = vec2(polarRadius, polarAngle);
  vec4 noiseA = texture2D(uNoiseTexture, polarUv * vec2(0.2, 7.0) * uNoiseScale + vec2(-ft * 0.1, 0.0));
  vec4 noiseB = texture2D(uNoiseTexture, polarUv * vec2(0.3, 4.0) * uNoiseScale + vec2(-ft * 0.2, 0.0));
  vec4 noiseC = texture2D(uNoiseTexture, polarUv * vec2(0.1, 5.0) * uNoiseScale + vec2(-ft * 0.1, 0.0));
  float distanceMask = 1.0 - length(uv);

  float innerRing = clamp(-1.0 * ((distanceMask - 0.7) / uIrisWidth), 0.0, 1.0);
  innerRing = (innerRing * distanceMask - 0.2) / 0.8;
  innerRing = clamp(innerRing, 0.0, 1.0);
  float iris = innerRing * (noiseA.r + noiseB.r) * 2.0;
  float flame = pow(max(noiseA.r * noiseB.r * 2.0, 0.0), 2.0);
  float outerRing = smoothstep(0.0, 0.35, distanceMask) * (1.0 - smoothstep(0.35, 0.75, distanceMask));
  iris += flame * outerRing;
  vec2 pupilUv = uv - uMouse * uPupilFollow * 0.15;
  float pupilShape = length(pupilUv * vec2(6.0, 1.0));
  float pupil = (1.0 - smoothstep(uPupilSize * 0.35, uPupilSize, pupilShape)) * uIntensity;
  float outerEyeGlow = pow(max(distanceMask, 0.0), 2.0) * uGlowIntensity;
  float outerBgGlow = exp(-length(uv) * 2.0) * noiseC.r * uGlowIntensity;
  vec3 eyeEnergy = uEyeColor * uIntensity * clamp(iris + max(flame * outerRing, outerEyeGlow + outerBgGlow) - pupil, 0.0, 3.0);
  vec3 color;
  if (uLightMode) {
    vec3 mapped = vec3(1.0) - exp(-max(eyeEnergy, vec3(0.0)) * 1.3);
    float energy = clamp(max(mapped.r, max(mapped.g, mapped.b)), 0.0, 1.0);
    vec3 hue = mapped / max(energy, 0.0001);
    hue = pow(clamp(hue, 0.0, 1.0), vec3(1.2));
    color = mix(uBgColor, hue, smoothstep(0.02, 0.82, energy) * 0.96);
  } else {
    color = eyeEnergy + uBgColor;
  }
  gl_FragColor = vec4(color, 1.0);
}
`;

function RBEvilEye({
  eyeColor = '#FF6F37', intensity = 1.5, pupilSize = 0.6,
  irisWidth = 0.25, glowIntensity = 0.35, scale = 0.8,
  noiseScale = 1.0, pupilFollow = 1.0, flameSpeed = 1.0,
  backgroundColor = '#000000', lightMode = false, onUnavailable
}) {
  const containerRef = RBReact.useRef(null);
  RBReact.useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    let gl;
    let geometry;
    let program;
    let noiseTexture;
    let observer;
    let animationFrameId = 0;
    let disposed = false;
    let renderer;
    const mouse = { x: 0, y: 0, tx: 0, ty: 0 };

    function onMouseMove(e) {
      const rect = container.getBoundingClientRect();
      if (!rect.width || !rect.height) return;
      mouse.tx = ((e.clientX - rect.left) / rect.width) * 2 - 1;
      mouse.ty = -(((e.clientY - rect.top) / rect.height) * 2 - 1);
    }
    function onMouseLeave() { mouse.tx = 0; mouse.ty = 0; }
    function resize() {
      if (disposed || !renderer) return;
      renderer.setSize(Math.max(1, container.offsetWidth), Math.max(1, container.offsetHeight));
      if (program) {
        program.uniforms.uResolution.value = [gl.canvas.width, gl.canvas.height, gl.canvas.width / gl.canvas.height];
      }
    }
    function cleanup() {
      if (disposed) return;
      disposed = true;
      cancelAnimationFrame(animationFrameId);
      observer?.disconnect();
      window.removeEventListener('resize', resize);
      container.removeEventListener('mousemove', onMouseMove);
      container.removeEventListener('mouseleave', onMouseLeave);
      if (gl) {
        gl.canvas.removeEventListener('webglcontextlost', onContextLost);
        gl.canvas.remove();
        if (!gl.isContextLost()) {
          geometry?.remove();
          program?.remove();
          if (noiseTexture?.texture) gl.deleteTexture(noiseTexture.texture);
          gl.getExtension('WEBGL_lose_context')?.loseContext();
        }
      }
    }
    function onContextLost(event) {
      event.preventDefault();
      cleanup();
      onUnavailable?.();
    }
    try {
      renderer = new Renderer({ alpha: true, premultipliedAlpha: false, dpr: Math.min(window.devicePixelRatio || 1, 1.5) });
      gl = renderer.gl;
      if (!gl) throw new Error('WebGL unavailable');
      gl.clearColor(0, 0, 0, 0);
      noiseTexture = new Texture(gl, {
        image: rbEyeGenerateNoiseTexture(256), width: 256, height: 256,
        generateMipmaps: false, flipY: false
      });
      noiseTexture.minFilter = gl.LINEAR;
      noiseTexture.magFilter = gl.LINEAR;
      noiseTexture.wrapS = gl.REPEAT;
      noiseTexture.wrapT = gl.REPEAT;
      geometry = new Triangle(gl);
      program = new Program(gl, {
        vertex: rbEyeVertexShader, fragment: rbEyeFragmentShader,
        uniforms: {
          uTime: { value: 0 },
          uResolution: { value: [1, 1, 1] },
          uNoiseTexture: { value: noiseTexture },
          uPupilSize: { value: pupilSize },
          uIrisWidth: { value: irisWidth },
          uGlowIntensity: { value: glowIntensity },
          uIntensity: { value: intensity },
          uScale: { value: scale },
          uNoiseScale: { value: noiseScale },
          uMouse: { value: [0, 0] },
          uPupilFollow: { value: pupilFollow },
          uFlameSpeed: { value: flameSpeed },
          uEyeColor: { value: rbEyeHexToVec3(eyeColor) },
          uBgColor: { value: rbEyeHexToVec3(backgroundColor) },
          uLightMode: { value: lightMode }
        }
      });
      if (!gl.getProgramParameter(program.program, gl.LINK_STATUS)) {
        throw new Error('EvilEye shader unavailable');
      }
      const mesh = new Mesh(gl, { geometry, program });
      container.appendChild(gl.canvas);
      gl.canvas.addEventListener('webglcontextlost', onContextLost);
      container.addEventListener('mousemove', onMouseMove);
      container.addEventListener('mouseleave', onMouseLeave);
      window.addEventListener('resize', resize);
      if (typeof ResizeObserver !== 'undefined') {
        observer = new ResizeObserver(resize);
        observer.observe(container);
      }
      resize();
      function update(time) {
        if (disposed) return;
        try {
          mouse.x += (mouse.tx - mouse.x) * 0.05;
          mouse.y += (mouse.ty - mouse.y) * 0.05;
          program.uniforms.uMouse.value = [mouse.x, mouse.y];
          program.uniforms.uTime.value = time * 0.001;
          renderer.render({ scene: mesh });
          animationFrameId = requestAnimationFrame(update);
        } catch (error) {
          cleanup();
          onUnavailable?.();
        }
      }
      animationFrameId = requestAnimationFrame(update);
    } catch (error) {
      cleanup();
      onUnavailable?.();
    }
    return cleanup;
  }, [eyeColor, intensity, pupilSize, irisWidth, glowIntensity, scale, noiseScale, pupilFollow, flameSpeed, backgroundColor, lightMode, onUnavailable]);
  return RBReact.createElement('div', { ref: containerRef, className: 'h-full w-full [&>canvas]:block [&>canvas]:h-full [&>canvas]:w-full' });
}

class EvilEyeBoundary extends RBReact.Component {
  constructor(props) { super(props); this.state = { failed: false }; }
  static getDerivedStateFromError() { return { failed: true }; }
  render() { return this.state.failed ? null : this.props.children; }
}
function EvilEyeBackground() {
  const [reduced, setReduced] = RBReact.useState(true);
  const [failed, setFailed] = RBReact.useState(false);
  const unavailable = RBReact.useCallback(() => setFailed(true), []);
  RBReact.useEffect(() => {
    if (typeof window.matchMedia !== 'function') return;
    const media = window.matchMedia('(prefers-reduced-motion: reduce)');
    const update = () => setReduced(media.matches);
    update();
    media.addEventListener('change', update);
    return () => media.removeEventListener('change', update);
  }, []);
  if (reduced) return null;
  if (failed) return RBReact.createElement('span', {className: 'pointer-events-none fixed bottom-2 right-3 text-xs text-stone-600'}, 'Evil Eye unavailable; workbench unaffected.');
  return RBReact.createElement('div', {className: 'pointer-events-none fixed inset-0 z-0 opacity-[0.12]', 'aria-hidden': true},
    RBReact.createElement(EvilEyeBoundary, null, RBReact.createElement(RBEvilEye, {eyeColor:'#16766b', intensity:0.8, pupilSize:0.6, irisWidth:0.25, glowIntensity:0.12, scale:0.8, noiseScale:1, pupilFollow:0, flameSpeed:0.3, backgroundColor:'#f4f5f0', lightMode:true, onUnavailable:unavailable})));
}
"""


class EvilEye(rx.Component):
    """Compile the bundled React/WebGL code with Reflex's custom-code API."""

    tag = "EvilEyeBackground"
    lib_dependencies: list[str] = ["ogl@1.0.11"]

    def add_imports(self) -> dict[str, list[ImportVar]]:
        return {
            "react": [ImportVar(tag="React", alias="RBReact", is_default=True)],
            "ogl": [
                ImportVar(tag="Renderer"),
                ImportVar(tag="Program"),
                ImportVar(tag="Mesh"),
                ImportVar(tag="Triangle"),
                ImportVar(tag="Texture"),
            ],
        }

    def add_custom_code(self) -> list[str]:
        return [EVIL_EYE_BRIDGE]


def evil_eye_background() -> rx.Component:
    return rx.cond(
        AppearanceState.evil_eye_enabled, EvilEye.create(), rx.fragment()
    )


def appearance_toggle() -> rx.Component:
    return rx.el.div(
        rx.el.button(
            rx.icon("eye", class_name="h-3.5 w-3.5"),
            rx.cond(
                AppearanceState.evil_eye_enabled,
                "Evil Eye · on",
                "Evil Eye · off",
            ),
            type="button",
            aria_pressed=AppearanceState.evil_eye_enabled,
            on_click=AppearanceState.toggle_evil_eye,
            class_name="flex items-center gap-2 rounded-lg border border-[#dce3dc] bg-white px-3 py-2 text-xs text-[#26364b] hover:bg-teal-50",
        ),
        rx.el.p(
            "Disabled for reduced motion. WebGL required.",
            class_name="mt-1 text-[10px] text-[#73808a]",
        ),
        rx.el.a(
            "React Bits · MIT + Commons Clause",
            href="https://github.com/DavidHDev/react-bits/blob/main/LICENSE.md",
            target="_blank",
            rel="noopener noreferrer",
            class_name="text-[10px] text-teal-700 underline",
        ),
        class_name="flex flex-col items-start",
    )
