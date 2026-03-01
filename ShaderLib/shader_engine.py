"""
shader_engine.py  –  Pygame Shader Engine v3
=============================================
Vollständiges Post-Processing + Vertex-Shader Framework für Pygame.

Features:
  1.  Multi-Pass Pipeline       engine.set_pipeline([BLUR, VIGNETTE, ...])
  2.  Vertex-Shader Unterstützung  – screen-level UND sprite-level, optional
  3.  Lighting System            engine.lighting  + LightSource
  4.  Masking / Stencil          engine.set_mask(surface)
  5.  Auto-Uniform Mapping       uTime, uResolution, uMouse automatisch
  6.  Render-to-Layer (FBO)      with engine.layer("bg"): ...
  7.  Shader-Preprocessing       #include "noise.glsl"
  8.  Validator + GPU-Timer       engine.debug
  9.  Flexible Uniform-API        engine["uColor"] = (1, 0, 0)
  10. Vertex-Shader Presets       vertex.WAVE, vertex.RIPPLE, vertex.FISHEYE …

Abhängigkeiten:
  pip install pygame PyOpenGL PyOpenGL_accelerate numpy

Schnellstart:
    from shader_engine import ShaderEngine
    from presets import CRT

    engine = ShaderEngine(800, 600, "Mein Spiel")
    engine.use_shader(CRT)

    while running:
        engine.surface.fill((10, 10, 30))
        pygame.draw.circle(engine.surface, (255, 100, 50), (400, 300), 80)
        engine["uTime"] = time
        engine.render()
"""

from __future__ import annotations
import re, time, os, ctypes
from contextlib import contextmanager
from typing import List, Dict, Optional, Tuple, Union

import pygame
from pygame.locals import DOUBLEBUF, OPENGL
from OpenGL.GL import *
import numpy as np


# ══════════════════════════════════════════════════════════════════════════════
#  GLSL INCLUDE-BIBLIOTHEK
# ══════════════════════════════════════════════════════════════════════════════

BUILTIN_INCLUDES: Dict[str, str] = {

"math.glsl": """
#define PI   3.14159265358979
#define TAU  6.28318530717958
float remap(float v,float a,float b,float c,float d){return c+(v-a)/(b-a)*(d-c);}
float sdCircle(vec2 p,float r){return length(p)-r;}
float sdBox(vec2 p,vec2 b){vec2 d=abs(p)-b;return length(max(d,0.))+min(max(d.x,d.y),0.);}
mat2 rotate2D(float a){float c=cos(a),s=sin(a);return mat2(c,-s,s,c);}
""",

"noise.glsl": """
float _h1(float n){return fract(sin(n)*43758.5453);}
float _h2(vec2 p) {return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}
float valueNoise(vec2 p){
    vec2 i=floor(p),f=fract(p);f=f*f*(3.-2.*f);
    return mix(mix(_h2(i),_h2(i+vec2(1,0)),f.x),
               mix(_h2(i+vec2(0,1)),_h2(i+vec2(1,1)),f.x),f.y);}
float fbm(vec2 p,int oct){float v=0.,a=.5;
    for(int i=0;i<oct;i++){v+=a*valueNoise(p);p=p*2.1+vec2(1.7,9.2);a*=.5;}return v;}
""",

"color.glsl": """
vec3 rgb2hsv(vec3 c){vec4 K=vec4(0.,-1./3.,2./3.,-1.);
    vec4 p=mix(vec4(c.bg,K.wz),vec4(c.gb,K.xy),step(c.b,c.g));
    vec4 q=mix(vec4(p.xyw,c.r),vec4(c.r,p.yzx),step(p.x,c.r));
    float d=q.x-min(q.w,q.y);return vec3(abs(q.z+(q.w-q.y)/(6.*d+1e-10)),d/(q.x+1e-10),q.x);}
vec3 hsv2rgb(vec3 c){vec4 K=vec4(1.,2./3.,1./3.,3.);
    vec3 p=abs(fract(c.xxx+K.xyz)*6.-K.www);
    return c.z*mix(K.xxx,clamp(p-K.xxx,0.,1.),c.y);}
float luminance(vec3 c){return dot(c,vec3(0.2126,0.7152,0.0722));}
vec3 toLinear(vec3 c){return pow(c,vec3(2.2));}
vec3 toSRGB(vec3 c)  {return pow(clamp(c,0.,1.),vec3(1./2.2));}
""",

"blur.glsl": """
const float _GW9[9]=float[](0.0625,0.125,0.0625,0.125,0.25,0.125,0.0625,0.125,0.0625);
vec4 blur9(sampler2D t,vec2 uv,vec2 px){
    vec4 c=vec4(0.);int k=0;
    for(int y=-1;y<=1;y++)for(int x=-1;x<=1;x++)c+=texture(t,uv+vec2(x,y)*px)*_GW9[k++];
    return c;}
vec4 blur13(sampler2D t,vec2 uv,vec2 dir){
    float[7] w=float[](0.0044,0.054,0.242,0.399,0.242,0.054,0.0044);
    vec4 c=vec4(0.);for(int i=0;i<7;i++)c+=texture(t,uv+dir*(float(i)-3.))*w[i];return c;}
""",

"sdf.glsl": """
float sdCircle(vec2 p,float r){return length(p)-r;}
float sdBox(vec2 p,vec2 b){vec2 d=abs(p)-b;return length(max(d,0.))+min(max(d.x,d.y),0.);}
float sdRoundBox(vec2 p,vec2 b,float r){vec2 d=abs(p)-b+r;return length(max(d,0.))+min(max(d.x,d.y),0.)-r;}
float sdRing(vec2 p,float r,float t){return abs(length(p)-r)-t*.5;}
float sdSegment(vec2 p,vec2 a,vec2 b){vec2 pa=p-a,ba=b-a;float h=clamp(dot(pa,ba)/dot(ba,ba),0.,1.);return length(pa-ba*h);}
vec4 sdfFill(float d,vec4 col,float aa){return vec4(col.rgb,col.a*(1.-smoothstep(-aa,aa,d)));}
vec4 sdfOutline(float d,vec4 col,float w,float aa){return vec4(col.rgb,col.a*(1.-smoothstep(w-aa,w+aa,abs(d))));}
""",

}


# ══════════════════════════════════════════════════════════════════════════════
#  VERTEX SHADER PRESETS
# ══════════════════════════════════════════════════════════════════════════════

class vertex:
    """
    Fertige Vertex-Shader für Screen-Effekte und Sprites.

    Verwendung:
        # Screen-Effekt (Wellen-Verzerrung des gesamten Bildes)
        engine.set_pipeline([CRT_FRAG], vertex=vertex.PASSTHROUGH)

        # Oder mit Wellen:
        engine.set_pipeline([MY_FRAG], vertex=vertex.WAVE)
        engine["uWaveAmp"] = 0.02

        # Für ShaderSprite:
        sprite = ShaderSprite(200, 200, FIRE_FRAG, vertex=vertex.WOBBLE)
    """

    # Standard Pass-Through (default, wird immer genutzt wenn kein anderer angegeben)
    PASSTHROUGH = """
#version 330 core
layout(location=0) in vec2 position;
layout(location=1) in vec2 texCoord;
out vec2 vTexCoord;
out vec2 vPosition;
void main(){
    gl_Position = vec4(position, 0.0, 1.0);
    vTexCoord   = texCoord;
    vPosition   = position;
}
"""

    # Wellen-Verzerrung (verbiegt das gesamte Vertex-Grid)
    WAVE = """
#version 330 core
layout(location=0) in vec2 position;
layout(location=1) in vec2 texCoord;
out vec2 vTexCoord;
out vec2 vPosition;
uniform float uTime;
uniform float uWaveAmp;    // Amplitude, default: 0.02
uniform float uWaveFreq;   // Frequenz, default: 8.0
uniform float uWaveSpeed;  // Geschwindigkeit, default: 2.0

void main(){
    float amp   = uWaveAmp   > 0.0 ? uWaveAmp   : 0.02;
    float freq  = uWaveFreq  > 0.0 ? uWaveFreq  : 8.0;
    float speed = uWaveSpeed > 0.0 ? uWaveSpeed : 2.0;

    vec2 pos = position;
    pos.x += sin(pos.y * freq + uTime * speed) * amp;
    pos.y += cos(pos.x * freq + uTime * speed) * amp;

    gl_Position = vec4(pos, 0.0, 1.0);
    vTexCoord   = texCoord;
    vPosition   = position;
}
"""

    # Fisheye / Barrel-Distortion via Vertex
    FISHEYE = """
#version 330 core
layout(location=0) in vec2 position;
layout(location=1) in vec2 texCoord;
out vec2 vTexCoord;
out vec2 vPosition;
uniform float uStrength;  // Stärke, default: 0.3 (positiv=barrel, negativ=pincushion)

void main(){
    float k = uStrength != 0.0 ? uStrength : 0.3;
    vec2 uv = texCoord - 0.5;
    float r2 = dot(uv, uv);
    vec2 distorted = texCoord + uv * r2 * k;

    gl_Position = vec4(position, 0.0, 1.0);
    vTexCoord   = distorted;
    vPosition   = position;
}
"""

    # Wabber / Wobble (für Sprites: macht sie "lebendig")
    WOBBLE = """
#version 330 core
layout(location=0) in vec2 position;
layout(location=1) in vec2 texCoord;
out vec2 vTexCoord;
out vec2 vPosition;
uniform float uTime;
uniform float uWobbleAmp;   // Amplitude, default: 0.04
uniform float uWobbleFreq;  // Frequenz, default: 3.0

void main(){
    float amp  = uWobbleAmp  > 0.0 ? uWobbleAmp  : 0.04;
    float freq = uWobbleFreq > 0.0 ? uWobbleFreq : 3.0;

    vec2 pos = position;
    // Nur oberer Teil wackelt (bottom-anchored)
    float influence = (position.y + 1.0) * 0.5;  // 0 unten, 1 oben
    pos.x += sin(uTime * freq) * amp * influence;

    gl_Position = vec4(pos, 0.0, 1.0);
    vTexCoord   = texCoord;
    vPosition   = position;
}
"""

    # Zoom-Pulse (Pulsierender Zoom)
    PULSE = """
#version 330 core
layout(location=0) in vec2 position;
layout(location=1) in vec2 texCoord;
out vec2 vTexCoord;
out vec2 vPosition;
uniform float uTime;
uniform float uPulseAmp;   // Puls-Stärke, default: 0.05
uniform float uPulseFreq;  // Puls-Frequenz, default: 2.0

void main(){
    float amp  = uPulseAmp  > 0.0 ? uPulseAmp  : 0.05;
    float freq = uPulseFreq > 0.0 ? uPulseFreq : 2.0;

    float scale = 1.0 + sin(uTime * freq) * amp;
    vec2 pos = position * scale;

    gl_Position = vec4(pos, 0.0, 1.0);
    vTexCoord   = texCoord;
    vPosition   = position;
}
"""

    # Ripple (Wasser-Wellen vom Zentrum)
    RIPPLE = """
#version 330 core
layout(location=0) in vec2 position;
layout(location=1) in vec2 texCoord;
out vec2 vTexCoord;
out vec2 vPosition;
uniform float uTime;
uniform vec2  uRippleCenter;  // Zentrum in UV, default: (0.5, 0.5)
uniform float uRippleAmp;     // Amplitude, default: 0.03
uniform float uRippleFreq;    // Frequenz, default: 15.0
uniform float uRippleSpeed;   // Geschwindigkeit, default: 3.0

void main(){
    vec2  center = uRippleCenter.x + uRippleCenter.y > 0.0
                   ? uRippleCenter : vec2(0.5, 0.5);
    float amp    = uRippleAmp   > 0.0 ? uRippleAmp   : 0.03;
    float freq   = uRippleFreq  > 0.0 ? uRippleFreq  : 15.0;
    float speed  = uRippleSpeed > 0.0 ? uRippleSpeed : 3.0;

    vec2  uv     = texCoord - center;
    float dist   = length(uv);
    float ripple = sin(dist * freq - uTime * speed) * amp;

    vec2 distUV = texCoord + normalize(uv + 0.001) * ripple;

    gl_Position = vec4(position, 0.0, 1.0);
    vTexCoord   = distUV;
    vPosition   = position;
}
"""

    # Shake (Kamera-Shake / Screen-Shake)
    SHAKE = """
#version 330 core
layout(location=0) in vec2 position;
layout(location=1) in vec2 texCoord;
out vec2 vTexCoord;
out vec2 vPosition;
uniform float uTime;
uniform float uShakeAmp;    // Intensität, default: 0.01
uniform float uShakeSpeed;  // Geschwindigkeit, default: 40.0

float _sh(float n){return fract(sin(n)*43758.5453);}

void main(){
    float amp   = uShakeAmp   > 0.0 ? uShakeAmp   : 0.01;
    float speed = uShakeSpeed > 0.0 ? uShakeSpeed : 40.0;
    float t     = floor(uTime * speed);
    vec2  offset = vec2(_sh(t) - 0.5, _sh(t + 17.3) - 0.5) * amp * 2.0;

    gl_Position = vec4(position, 0.0, 1.0);
    vTexCoord   = texCoord + offset;
    vPosition   = position;
}
"""

    # Spin (Dreht das gesamte Bild / Sprite)
    SPIN = """
#version 330 core
layout(location=0) in vec2 position;
layout(location=1) in vec2 texCoord;
out vec2 vTexCoord;
out vec2 vPosition;
uniform float uTime;
uniform float uSpinSpeed;  // Grad/Sekunde, default: 30.0

void main(){
    float speed = uSpinSpeed != 0.0 ? uSpinSpeed : 30.0;
    float angle = uTime * speed * 0.01745329;  // → Radians
    float c = cos(angle), s = sin(angle);
    mat2  rot = mat2(c, -s, s, c);
    vec2  uv = (texCoord - 0.5) * rot + 0.5;

    gl_Position = vec4(position, 0.0, 1.0);
    vTexCoord   = uv;
    vPosition   = position;
}
"""


# ══════════════════════════════════════════════════════════════════════════════
#  PREPROCESSOR
# ══════════════════════════════════════════════════════════════════════════════

try:
    from pygame_shader._glsl_bundle import BUNDLE as _EXT_BUNDLE, resolve as _bundle_resolve
    _HAS_EXT_BUNDLE = True
except ImportError:
    _HAS_EXT_BUNDLE = False
    _EXT_BUNDLE = {}
    _bundle_resolve = None


class ShaderPreprocessor:
    """
    Löst #include "name.glsl" in GLSL-Quellcode auf.

    Suchpfade (in Prioritätsreihenfolge):
      1. Manuell registrierte Snippets  (preprocessor.register(...))
      2. Externes Bundle (_glsl_bundle.py)
      3. Eingebettete BUILTIN_INCLUDES
      4. Dateisystem (include_dirs)
    """
    def __init__(self, include_dirs: List[str] = None):
        self.include_dirs = include_dirs or []
        self.extra_bundle: Dict[str, str] = {}

    def register(self, name: str, source: str):
        """Registriert ein eigenes GLSL-Snippet unter dem angegebenen Namen."""
        self.extra_bundle[name] = source

    def process(self, source: str, _seen: set = None) -> str:
        if _seen is None:
            _seen = set()
        def replace(m):
            name = m.group(1)
            if name in _seen:
                return f"// [already included: {name}]"
            _seen.add(name)
            if name in self.extra_bundle:
                return self.process(self.extra_bundle[name], _seen)
            if _HAS_EXT_BUNDLE and _bundle_resolve:
                result = _bundle_resolve(name, self.include_dirs)
                if result:
                    return self.process(result, _seen)
            if name in BUILTIN_INCLUDES:
                return self.process(BUILTIN_INCLUDES[name], _seen)
            for d in self.include_dirs:
                p = os.path.join(d, name)
                if os.path.isfile(p):
                    return self.process(open(p).read(), _seen)
            all_known = set(BUILTIN_INCLUDES.keys()) | set(_EXT_BUNDLE.keys())
            print(f"[Preprocessor] WARN: '{name}' nicht gefunden. "
                  f"Verfügbar: {sorted(all_known)}")
            return f"// [missing include: {name}]"
        return re.sub(r'#include\s+"([^"]+)"', replace, source)


# ══════════════════════════════════════════════════════════════════════════════
#  ERRORS + VALIDATOR
# ══════════════════════════════════════════════════════════════════════════════

class ShaderCompileError(Exception): pass
class ShaderLinkError(Exception):    pass


class ShaderValidator:
    @staticmethod
    def compile(source: str, shader_type: int, label: str = "") -> int:
        sh = glCreateShader(shader_type)
        glShaderSource(sh, source)
        glCompileShader(sh)
        if not glGetShaderiv(sh, GL_COMPILE_STATUS):
            log   = glGetShaderInfoLog(sh).decode()
            lines = source.split("\n")
            glDeleteShader(sh)
            annotated = ShaderValidator._annotate(log, lines)
            type_name = "Vertex" if shader_type == GL_VERTEX_SHADER else "Fragment"
            raise ShaderCompileError(f"\n[{type_name} Shader '{label}'] Compile-Fehler:\n{annotated}")
        return sh

    @staticmethod
    def link(vert: int, frag: int, label: str = "") -> int:
        prog = glCreateProgram()
        glAttachShader(prog, vert)
        glAttachShader(prog, frag)
        glLinkProgram(prog)
        glDeleteShader(vert)
        glDeleteShader(frag)
        if not glGetProgramiv(prog, GL_LINK_STATUS):
            log = glGetProgramInfoLog(prog).decode()
            glDeleteProgram(prog)
            raise ShaderLinkError(f"['{label}'] Link-Fehler:\n{log}")
        return prog

    @staticmethod
    def _annotate(log: str, lines: List[str]) -> str:
        out = []
        for line in log.strip().split("\n"):
            out.append(f"  ✗  {line}")
            m = re.search(r'[:(](\d+)[):]', line)
            if m:
                ln = int(m.group(1)) - 1
                if 0 <= ln < len(lines):
                    out.append(f"     → Zeile {ln+1}: {lines[ln].strip()}")
        return "\n".join(out)


def _compile_prog(vert_src: str, frag_src: str, label: str = "") -> int:
    v = ShaderValidator.compile(vert_src, GL_VERTEX_SHADER,   label + ":vert")
    f = ShaderValidator.compile(frag_src, GL_FRAGMENT_SHADER, label + ":frag")
    return ShaderValidator.link(v, f, label)


# ══════════════════════════════════════════════════════════════════════════════
#  GPU TIMER
# ══════════════════════════════════════════════════════════════════════════════

class GpuTimer:
    def __init__(self):
        self.last_ms = 0.0
        self._history: List[float] = []
        try:
            self._q = glGenQueries(1)[0]
        except Exception:
            self._q = None

    def begin(self):
        if self._q: glBeginQuery(GL_TIME_ELAPSED, self._q)

    def end(self):
        if self._q: glEndQuery(GL_TIME_ELAPSED)

    def fetch(self):
        if not self._q: return
        if glGetQueryObjectiv(self._q, GL_QUERY_RESULT_AVAILABLE):
            ns = glGetQueryObjectuiv(self._q, GL_QUERY_RESULT)
            self.last_ms = ns / 1_000_000.0
            self._history.append(self.last_ms)
            if len(self._history) > 60: self._history.pop(0)

    @property
    def avg_ms(self) -> float:
        return sum(self._history) / len(self._history) if self._history else 0.0

    @property
    def max_ms(self) -> float:
        return max(self._history) if self._history else 0.0

    def destroy(self):
        if self._q: glDeleteQueries([self._q])


# ══════════════════════════════════════════════════════════════════════════════
#  FBO HELPER
# ══════════════════════════════════════════════════════════════════════════════

class _FBO:
    def __init__(self, w: int, h: int):
        self.width = w; self.height = h
        self.fbo = glGenFramebuffers(1)
        self.tex = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, self.tex)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, w, h, 0, GL_RGBA, GL_UNSIGNED_BYTE, None)
        for p, v in [(GL_TEXTURE_MIN_FILTER, GL_LINEAR), (GL_TEXTURE_MAG_FILTER, GL_LINEAR),
                     (GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE), (GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)]:
            glTexParameteri(GL_TEXTURE_2D, p, v)
        glBindTexture(GL_TEXTURE_2D, 0)
        glBindFramebuffer(GL_FRAMEBUFFER, self.fbo)
        glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, self.tex, 0)
        assert glCheckFramebufferStatus(GL_FRAMEBUFFER) == GL_FRAMEBUFFER_COMPLETE
        glBindFramebuffer(GL_FRAMEBUFFER, 0)

    def bind(self):
        glBindFramebuffer(GL_FRAMEBUFFER, self.fbo)
        glViewport(0, 0, self.width, self.height)

    def unbind(self):
        glBindFramebuffer(GL_FRAMEBUFFER, 0)

    def destroy(self):
        glDeleteFramebuffers(1, [self.fbo])
        glDeleteTextures([self.tex])


# ══════════════════════════════════════════════════════════════════════════════
#  BUILT-IN GLSL (intern)
# ══════════════════════════════════════════════════════════════════════════════

_DEFAULT_VERT = vertex.PASSTHROUGH

_PASSTHROUGH_FRAG = """
#version 330 core
in vec2 vTexCoord; out vec4 fragColor;
uniform sampler2D uTexture;
void main(){ fragColor=texture(uTexture,vTexCoord); }
"""

_COMPOSITE_FRAG = """
#version 330 core
in vec2 vTexCoord; out vec4 fragColor;
uniform sampler2D uBase, uLayer;
uniform float uAlpha;
void main(){
    vec4 b=texture(uBase,vTexCoord), l=texture(uLayer,vTexCoord);
    l.a *= uAlpha;
    fragColor=mix(b, vec4(l.rgb,1.), l.a);
    fragColor.a = b.a;
}
"""

_MASK_FRAG = """
#version 330 core
in vec2 vTexCoord; out vec4 fragColor;
uniform sampler2D uTexture, uMask;
uniform bool uInvert;
void main(){
    vec4 c=texture(uTexture,vTexCoord);
    float m=texture(uMask,vTexCoord).r;
    if(uInvert) m=1.-m;
    fragColor=vec4(c.rgb,c.a*m);
}
"""

_LIGHTING_FRAG = """
#version 330 core
in vec2 vTexCoord; out vec4 fragColor;
uniform sampler2D uTexture, uNormalMap;
uniform bool      uHasNormalMap;
uniform vec2      uResolution;
uniform vec3      uAmbient;
uniform int       uNumLights;
uniform vec2      uLightPos[16];
uniform vec3      uLightColor[16];
uniform float     uLightRadius[16], uLightIntensity[16];
void main(){
    vec4 albedo=texture(uTexture,vTexCoord);
    vec2 pos=vTexCoord*uResolution;
    vec3 normal=vec3(0.,0.,1.);
    if(uHasNormalMap) normal=normalize(texture(uNormalMap,vTexCoord).rgb*2.-1.);
    vec3 light=uAmbient;
    for(int i=0;i<uNumLights&&i<16;i++){
        vec2 d=uLightPos[i]-pos; float dist=length(d);
        float att=1.-clamp(dist/uLightRadius[i],0.,1.); att*=att;
        vec3 ld=normalize(vec3(d,50.));
        float diff=max(dot(normal,ld),0.);
        light+=uLightColor[i]*diff*att*uLightIntensity[i];
    }
    fragColor=vec4(albedo.rgb*light,albedo.a);
}
"""


# ══════════════════════════════════════════════════════════════════════════════
#  LIGHT SOURCE
# ══════════════════════════════════════════════════════════════════════════════

class LightSource:
    """
    Eine 2D-Lichtquelle.

    Beispiel:
        light = LightSource(400, 300, color=(1.0, 0.8, 0.5), radius=300, intensity=1.5)
        engine.lighting.add(light)

        # Im Spielloop bewegen:
        light.x, light.y = mouse_x, mouse_y
    """
    def __init__(self, x: float = 0., y: float = 0.,
                 color: tuple = (1., .9, .7),
                 radius: float = 300.,
                 intensity: float = 1.):
        self.x = x; self.y = y
        self.color = color; self.radius = radius; self.intensity = intensity

    def move_to(self, x: float, y: float):
        """Bewegt die Lichtquelle. Kurze Alternative zu light.x = x; light.y = y"""
        self.x = x; self.y = y
        return self


class LightingSystem:
    """
    Verwaltet bis zu 16 Lichtquellen. Zugriff via engine.lighting.

    Beispiel:
        light = engine.lighting.add(LightSource(400, 300))
        engine.lighting.ambient = (0.05, 0.05, 0.1)
        engine.lighting.set_normal_map(normal_surface)
    """
    MAX = 16

    def __init__(self, engine: "ShaderEngine"):
        self._e = engine
        self._lights: List[LightSource] = []
        self.ambient = (0.15, 0.15, 0.2)
        self.enabled = False
        self._nm_tex: Optional[int] = None
        self._prog   = _compile_prog(_DEFAULT_VERT, _LIGHTING_FRAG, "lighting")

    def add(self, light: LightSource) -> LightSource:
        """Fügt eine Lichtquelle hinzu und aktiviert das Lighting-System."""
        self._lights.append(light)
        self.enabled = True
        return light

    def remove(self, light: LightSource):
        if light in self._lights:
            self._lights.remove(light)

    def clear(self):
        """Entfernt alle Lichtquellen."""
        self._lights.clear()

    def set_normal_map(self, surface: pygame.Surface):
        """Setzt eine Normal-Map für Bump-Lighting."""
        if self._nm_tex: glDeleteTextures([self._nm_tex])
        self._nm_tex = _surf_to_tex(surface)

    def clear_normal_map(self):
        if self._nm_tex: glDeleteTextures([self._nm_tex]); self._nm_tex = None

    def apply(self, src_tex: int, fbo: _FBO, draw_fn) -> int:
        fbo.bind(); glClear(GL_COLOR_BUFFER_BIT)
        glUseProgram(self._prog)
        glActiveTexture(GL_TEXTURE0); glBindTexture(GL_TEXTURE_2D, src_tex)
        glUniform1i(glGetUniformLocation(self._prog, "uTexture"), 0)
        has = self._nm_tex is not None
        glUniform1i(glGetUniformLocation(self._prog, "uHasNormalMap"), int(has))
        if has:
            glActiveTexture(GL_TEXTURE1); glBindTexture(GL_TEXTURE_2D, self._nm_tex)
            glUniform1i(glGetUniformLocation(self._prog, "uNormalMap"), 1)
        e = self._e
        glUniform2f(glGetUniformLocation(self._prog, "uResolution"), float(e.width), float(e.height))
        glUniform3f(glGetUniformLocation(self._prog, "uAmbient"), *self.ambient)
        n = min(len(self._lights), self.MAX)
        glUniform1i(glGetUniformLocation(self._prog, "uNumLights"), n)
        for i, l in enumerate(self._lights[:n]):
            glUniform2f(glGetUniformLocation(self._prog, f"uLightPos[{i}]"), l.x, e.height - l.y)
            glUniform3f(glGetUniformLocation(self._prog, f"uLightColor[{i}]"), *l.color)
            glUniform1f(glGetUniformLocation(self._prog, f"uLightRadius[{i}]"), l.radius)
            glUniform1f(glGetUniformLocation(self._prog, f"uLightIntensity[{i}]"), l.intensity)
        draw_fn(); fbo.unbind()
        return fbo.tex

    def destroy(self):
        glDeleteProgram(self._prog)
        if self._nm_tex: glDeleteTextures([self._nm_tex])


# ══════════════════════════════════════════════════════════════════════════════
#  PIPELINE PASS  –  ein einzelner Shader in der Kette
# ══════════════════════════════════════════════════════════════════════════════

class PipelinePass:
    """
    Ein einzelner Shader-Pass in der Pipeline.

    Kann direkt erstellt werden:
        p = PipelinePass(FRAG_SRC, label="bloom")
        p = PipelinePass(FRAG_SRC, vert=MY_VERTEX, label="wave_distort")

    Oder via engine:
        p = engine.compile_shader(FRAG_SRC)
        engine.set_pipeline([p, OTHER_FRAG])

    Uniforms setzen:
        p["uStrength"] = 1.5          # float
        p["uColor"]    = (1, 0.5, 0)  # vec3
        p.set_float("uBrightness", 1.2)   # alt (kompatibel)
    """

    def __init__(self, frag_source: str, label: str = "",
                 vert: Optional[str] = None):
        """
        Parameters
        ----------
        frag_source : str
            GLSL Fragment-Shader Quellcode
        label : str
            Optionaler Name für Debug-Output
        vert : str, optional
            GLSL Vertex-Shader Quellcode. Wenn None, wird der Standard-Pass-Through genutzt.
            Verwende die vertex.*-Presets oder eigenen Code.
        """
        self.label  = label
        self._uniforms: Dict[str, int] = {}

        vert_src = vert if vert else _DEFAULT_VERT
        self._prog = _compile_prog(vert_src, frag_source, label)

    # ── Uniforms (flexibel) ───────────────────────────────────────────────────

    def __setitem__(self, name: str, value):
        """Kurzschreibweise: pass["uColor"] = (1.0, 0.5, 0.0)"""
        self._set(name, value)

    def _set(self, name: str, value):
        glUseProgram(self._prog)
        loc = self._loc(name)
        if loc < 0: return
        if isinstance(value, (int, float)):
            glUniform1f(loc, float(value))
        elif isinstance(value, (list, tuple)):
            n = len(value)
            if n == 2:   glUniform2f(loc, float(value[0]), float(value[1]))
            elif n == 3: glUniform3f(loc, float(value[0]), float(value[1]), float(value[2]))
            elif n == 4: glUniform4f(loc, float(value[0]), float(value[1]), float(value[2]), float(value[3]))

    def _loc(self, name: str) -> int:
        if name not in self._uniforms:
            self._uniforms[name] = glGetUniformLocation(self._prog, name)
        return self._uniforms[name]

    # Rückwärtskompatibilität
    def set_float(self, name: str, v: float):  self["name"] = v; self._set(name, v)
    def set_vec2(self, name: str, x, y):        self._set(name, (x, y))
    def set_vec3(self, name: str, x, y, z):     self._set(name, (x, y, z))
    def set_int(self, name: str, v: int):
        glUseProgram(self._prog); glUniform1i(self._loc(name), int(v))

    # ── Render ────────────────────────────────────────────────────────────────

    def apply(self, src_tex: int, fbo: _FBO, auto_uniforms: dict, draw_fn) -> int:
        fbo.bind(); glClear(GL_COLOR_BUFFER_BIT)
        glUseProgram(self._prog)
        glActiveTexture(GL_TEXTURE0); glBindTexture(GL_TEXTURE_2D, src_tex)
        glUniform1i(self._loc("uTexture"), 0)
        for uname, (kind, val) in auto_uniforms.items():
            loc = self._loc(uname)
            if loc < 0: continue
            if kind == "f":   glUniform1f(loc, val)
            elif kind == "2f": glUniform2f(loc, *val)
            elif kind == "3f": glUniform3f(loc, *val)
            elif kind == "4f": glUniform4f(loc, *val)
            elif kind == "i":  glUniform1i(loc, val)
        draw_fn(); fbo.unbind()
        return fbo.tex

    def destroy(self):
        glDeleteProgram(self._prog)


# ══════════════════════════════════════════════════════════════════════════════
#  RENDER LAYER
# ══════════════════════════════════════════════════════════════════════════════

class RenderLayer:
    """
    Benannte Render-Schicht.
    Zugriff via:  with engine.layer("name") as surf: ...

    Eigenschaften:
        layer.visible  → bool
        layer.alpha    → float (0..1)
    """
    def __init__(self, name: str, w: int, h: int):
        self.name    = name
        self.surface = pygame.Surface((w, h), pygame.SRCALPHA)
        self._fbo    = _FBO(w, h)
        self.visible = True
        self.alpha   = 1.0

    def upload(self):
        raw = pygame.image.tostring(self.surface, "RGBA", True)
        glBindTexture(GL_TEXTURE_2D, self._fbo.tex)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA,
                     self.surface.get_width(), self.surface.get_height(),
                     0, GL_RGBA, GL_UNSIGNED_BYTE, raw)
        glBindTexture(GL_TEXTURE_2D, 0)

    @property
    def texture(self) -> int: return self._fbo.tex

    def destroy(self):
        self._fbo.destroy()


# ══════════════════════════════════════════════════════════════════════════════
#  DEBUG OVERLAY
# ══════════════════════════════════════════════════════════════════════════════

class DebugOverlay:
    """
    Performance + Diagnose-Anzeige.

    engine.debug.enabled = True
    engine.debug.particle_system = ps  # optional für Partikel-Count
    """
    def __init__(self, engine: "ShaderEngine"):
        self._e = engine
        self.enabled = False
        self.particle_system = None
        self._font = None

    def _fnt(self):
        if not self._font:
            self._font = pygame.font.SysFont("monospace", 13)
        return self._font

    def draw(self, surface: pygame.Surface):
        e = self._e; t = e._timer
        vert_info = []
        for i, p in enumerate(e._pipeline):
            has_custom = p._prog != 0  # immer true wenn kompiliert
            vert_info.append(p.label or f"pass{i}")
        lines = [
            "── Shader Engine Debug ──",
            f"GPU  last:{t.last_ms:6.2f}ms  avg:{t.avg_ms:6.2f}ms  max:{t.max_ms:6.2f}ms",
            f"Pipeline : {len(e._pipeline)} pass(es)  " + "  ".join(vert_info),
            f"Vert.Shader: {'custom' if e._pipeline and hasattr(e._pipeline[0], '_has_custom_vert') else 'default'}",
            f"Layers   : {len(e._layers)}  {list(e._layers.keys())}",
            f"Lighting : {'ON' if e.lighting.enabled else 'off'}  ({len(e.lighting._lights)} lights)",
            f"Mask     : {'ON' if e._mask_tex else 'off'}",
            f"Frame    : {e._frame}",
        ]
        if self.particle_system:
            lines.append(f"Particles: {self.particle_system.total_particles}")
        fnt = self._fnt()
        w = 450; h = len(lines) * 16 + 10
        bg = pygame.Surface((w, h), pygame.SRCALPHA)
        bg.fill((0, 0, 0, 170))
        surface.blit(bg, (4, 4))
        for i, line in enumerate(lines):
            col = (50, 255, 100) if i > 0 else (255, 220, 50)
            surface.blit(fnt.render(line, True, col), (8, 8 + i * 16))


# ══════════════════════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _surf_to_tex(surface: pygame.Surface) -> int:
    w, h = surface.get_size()
    raw  = pygame.image.tostring(surface, "RGBA", True)
    tex  = glGenTextures(1)
    glBindTexture(GL_TEXTURE_2D, tex)
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, w, h, 0, GL_RGBA, GL_UNSIGNED_BYTE, raw)
    for p, v in [(GL_TEXTURE_MIN_FILTER, GL_LINEAR), (GL_TEXTURE_MAG_FILTER, GL_LINEAR),
                 (GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE), (GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)]:
        glTexParameteri(GL_TEXTURE_2D, p, v)
    glBindTexture(GL_TEXTURE_2D, 0)
    return tex


# ══════════════════════════════════════════════════════════════════════════════
#  SHADER ENGINE  –  Hauptklasse
# ══════════════════════════════════════════════════════════════════════════════

class ShaderEngine:
    """
    Zentrale Engine-Klasse. Öffnet automatisch das Pygame-Fenster.

    Schnellstart:
        engine = ShaderEngine(800, 600, "Mein Spiel")
        engine.use_shader(CRT)                   # Screen-Shader setzen

        while running:
            engine.surface.fill((10, 10, 30))    # Normal Pygame zeichnen
            engine["uTime"] = time               # Uniforms setzen
            engine.render()                      # Rendern!

    Mit Vertex-Shader:
        from shader_engine import vertex
        engine.set_pipeline([MY_FRAG], vert=vertex.WAVE)
        engine["uWaveAmp"] = 0.015

    Multi-Pass:
        engine.set_pipeline([BLUR_H, BLUR_V, COLOR_GRADE])
        engine.get_pass(2)["uContrast"] = 1.2

    Lighting:
        light = engine.lighting.add(LightSource(400, 300, radius=250))
        light.x, light.y = mx, my  # im Loop

    Named Layers:
        with engine.layer("hud") as hud:
            hud.blit(healthbar, (10, 10))
    """

    def __init__(self, width: int, height: int,
                 title: str = "Pygame Shader Engine",
                 vsync: bool = False,
                 resizable: bool = False):
        self.width  = width   # Logische Aufloesung - aendert sich NIE
        self.height = height  # Alle FBOs / Surfaces bleiben in dieser Groesse
        self._win_w = width   # Echte Fenstergroesse - aendert sich beim Resize
        self._win_h = height
        self._resizable = resizable
        pygame.init()
        pygame.display.set_caption(title)
        flags = DOUBLEBUF | OPENGL
        if resizable:
            flags |= pygame.RESIZABLE
        pygame.display.set_mode((width, height), flags)

        self._surface = pygame.Surface((width, height))
        self._setup_quad()
        self._main_tex = self._new_tex()
        self._fbos: List[_FBO] = [_FBO(width, height) for _ in range(8)]

        self._pt_prog  = _compile_prog(_DEFAULT_VERT, _PASSTHROUGH_FRAG, "passthrough")
        self._cmp_prog = _compile_prog(_DEFAULT_VERT, _COMPOSITE_FRAG,   "composite")
        self._msk_prog = _compile_prog(_DEFAULT_VERT, _MASK_FRAG,        "mask")

        self._pipeline: List[PipelinePass] = []
        self.lighting  = LightingSystem(self)
        self._mask_tex: Optional[int] = None
        self._mask_invert = False
        self._auto: Dict[str, tuple] = {}
        self._t0   = time.perf_counter()
        self._layers: Dict[str, RenderLayer] = {}
        self.preprocessor = ShaderPreprocessor(
            include_dirs=[os.path.join(os.path.dirname(__file__), "shaders")]
        )
        self._timer = GpuTimer()
        self.debug  = DebugOverlay(self)
        self._frame = 0

    # ── Quad ─────────────────────────────────────────────────────────────────

    def _setup_quad(self):
        v = np.array([-1,-1,0,0, 1,-1,1,0, 1,1,1,1, -1,1,0,1], dtype=np.float32)
        i = np.array([0,1,2,2,3,0], dtype=np.uint32)
        self._vao = glGenVertexArrays(1); glBindVertexArray(self._vao)
        self._vbo = glGenBuffers(1); glBindBuffer(GL_ARRAY_BUFFER, self._vbo)
        glBufferData(GL_ARRAY_BUFFER, v.nbytes, v, GL_STATIC_DRAW)
        self._ebo = glGenBuffers(1); glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self._ebo)
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, i.nbytes, i, GL_STATIC_DRAW)
        glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 16, ctypes.c_void_p(0)); glEnableVertexAttribArray(0)
        glVertexAttribPointer(1, 2, GL_FLOAT, GL_FALSE, 16, ctypes.c_void_p(8)); glEnableVertexAttribArray(1)
        glBindVertexArray(0)

    def _new_tex(self) -> int:
        t = glGenTextures(1); glBindTexture(GL_TEXTURE_2D, t)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, self.width, self.height, 0, GL_RGBA, GL_UNSIGNED_BYTE, None)
        for p, v in [(GL_TEXTURE_MIN_FILTER, GL_LINEAR), (GL_TEXTURE_MAG_FILTER, GL_LINEAR),
                     (GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE), (GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)]:
            glTexParameteri(GL_TEXTURE_2D, p, v)
        glBindTexture(GL_TEXTURE_2D, 0); return t

    def _quad(self):
        glBindVertexArray(self._vao)
        glDrawElements(GL_TRIANGLES, 6, GL_UNSIGNED_INT, None)
        glBindVertexArray(0)

    def _fbo(self, idx: int) -> _FBO:
        return self._fbos[idx % len(self._fbos)]

    # ── Uniform API (flexibel) ────────────────────────────────────────────────

    def __setitem__(self, name: str, value):
        """
        Kurzschreibweise für Uniforms – wird an ALLE Pipeline-Passes weitergegeben.

            engine["uTime"]      = 3.14
            engine["uColor"]     = (1.0, 0.5, 0.0)
            engine["uResOffset"] = (0.01, 0.01)
        """
        self.set_auto(name, value)

    def __getitem__(self, name: str):
        """Gibt den aktuellen Auto-Uniform-Wert zurück (oder None)."""
        entry = self._auto.get(name)
        return entry[1] if entry else None

    def set_auto(self, name: str, value):
        """
        Setzt einen Uniform-Wert der in ALLE Passes injiziert wird.
        Akzeptiert float, int, tuple(2), tuple(3), tuple(4).
        """
        if isinstance(value, bool):
            self._auto[name] = ("i", int(value))
        elif isinstance(value, int):
            self._auto[name] = ("f", float(value))
        elif isinstance(value, float):
            self._auto[name] = ("f", value)
        elif hasattr(value, '__len__'):
            n = len(value)
            kinds = {2: "2f", 3: "3f", 4: "4f"}
            if n in kinds:
                self._auto[name] = (kinds[n], tuple(float(x) for x in value))

    # Rückwärtskompatibilität
    def set_uniform_float(self, name, v):     self.set_auto(name, v)
    def set_uniform_vec2(self, name, x, y):   self.set_auto(name, (x, y))
    def set_uniform_vec3(self, name, x, y, z):self.set_auto(name, (x, y, z))
    def set_uniform_int(self, name, v):        self._auto[name] = ("i", int(v))

    def _update_builtin_autos(self):
        t  = time.perf_counter() - self._t0
        mx, my = pygame.mouse.get_pos()
        self._auto.update({
            "uTime":        ("f",  t),
            "u_time":       ("f",  t),
            "iTime":        ("f",  t),
            "uResolution":  ("2f", (float(self.width), float(self.height))),
            "u_resolution": ("2f", (float(self.width), float(self.height))),
            "iResolution":  ("2f", (float(self.width), float(self.height))),
            "uMouse":       ("2f", (float(mx), float(self.height - my))),
            "u_mouse":      ("2f", (float(mx), float(self.height - my))),
            "uFrame":       ("i",  self._frame),
        })

    # ── Pipeline ─────────────────────────────────────────────────────────────

    def set_pipeline(self, passes: List, vert: Optional[str] = None):
        """
        Setzt die Post-Processing-Kette.

        Parameters
        ----------
        passes : list
            Liste von Fragment-Shader-Strings ODER PipelinePass-Objekten.
            Strings werden automatisch preprocessed und kompiliert.
        vert : str, optional
            Vertex-Shader für ALLE Passes in dieser Pipeline.
            Wird durch pass-spezifische Vertex-Shader überschrieben wenn
            die Passes als PipelinePass-Objekte übergeben werden.
            Nutze vertex.*-Presets:  vert=vertex.WAVE

        Beispiele:
            # Einfach
            engine.set_pipeline([CRT])

            # Multi-Pass
            engine.set_pipeline([BLUR_H, BLUR_V, VIGNETTE])

            # Mit Vertex-Shader (gilt für alle Passes)
            engine.set_pipeline([MY_FRAG], vert=vertex.WAVE)

            # Passes mit individuellen Einstellungen
            p_blur = PipelinePass(BLUR_FRAG, vert=vertex.FISHEYE, label="blur+fisheye")
            p_col  = PipelinePass(COLOR_FRAG, label="color")
            engine.set_pipeline([p_blur, p_col])

            # Pro-Pass Uniforms
            engine.get_pass(0)["uRadius"] = 2.0
            engine.get_pass(1)["uContrast"] = 1.2
        """
        for p in self._pipeline: p.destroy()
        self._pipeline = []
        for i, p in enumerate(passes):
            if isinstance(p, str):
                src = self.preprocessor.process(p)
                self._pipeline.append(PipelinePass(src, label=f"pass{i}", vert=vert))
            elif isinstance(p, PipelinePass):
                self._pipeline.append(p)
        print(f"[ShaderEngine] Pipeline: {len(self._pipeline)} Pass(es)"
              + (f" | Vertex: {'custom' if vert else 'default'}") + " ✓")

    def use_shader(self, frag: str, vert: Optional[str] = None):
        """
        Kurzform für einen einzelnen Shader.

            engine.use_shader(CRT)
            engine.use_shader(MY_FRAG, vert=vertex.WAVE)
        """
        self.set_pipeline([frag], vert=vert)

    def get_pass(self, index: int) -> PipelinePass:
        """Zugriff auf einen einzelnen Pass. Wirf IndexError wenn ungültig."""
        return self._pipeline[index]

    def clear_pipeline(self):
        for p in self._pipeline: p.destroy()
        self._pipeline = []

    def compile_shader(self, frag_source: str, label: str = "",
                       vert: Optional[str] = None) -> PipelinePass:
        """Preprocessiert + kompiliert einen Shader zu einem PipelinePass."""
        processed = self.preprocessor.process(frag_source)
        return PipelinePass(processed, label, vert=vert)

    def load_shader_file(self, path: str, vert: Optional[str] = None) -> "ShaderEngine":
        """Lädt eine .glsl Datei als einzelnen Pass."""
        with open(path) as f:
            self.set_pipeline([f.read()], vert=vert)
        return self

    # ── Masking ──────────────────────────────────────────────────────────────

    def set_mask(self, surface: pygame.Surface, invert: bool = False):
        """
        Setzt eine Graustufen-Maske. Weiß = sichtbar, Schwarz = unsichtbar.

            engine.set_mask(flashlight_surface)       # Taschenlampen-Effekt
            engine.set_mask(fog_surface, invert=True) # Nebel / FoW
        """
        if self._mask_tex: glDeleteTextures([self._mask_tex])
        self._mask_tex = _surf_to_tex(surface)
        self._mask_invert = invert

    def clear_mask(self):
        if self._mask_tex:
            glDeleteTextures([self._mask_tex])
            self._mask_tex = None

    # ── Named Layers ─────────────────────────────────────────────────────────

    @contextmanager
    def layer(self, name: str, alpha: float = 1.0):
        """
        Context-Manager für benannte Render-Schichten.

            with engine.layer("hud") as hud:
                hud.fill((0, 0, 0, 0))        # transparent
                hud.blit(healthbar, (10, 10))
                pygame.draw.rect(hud, ...)

            # Layer-Transparenz:
            engine.get_layer("hud").alpha = 0.8
        """
        if name not in self._layers:
            self._layers[name] = RenderLayer(name, self.width, self.height)
        lay = self._layers[name]
        if alpha != 1.0: lay.alpha = alpha
        lay.surface.fill((0, 0, 0, 0))
        yield lay.surface
        lay.upload()

    def get_layer(self, name: str) -> Optional[RenderLayer]:
        return self._layers.get(name)

    def remove_layer(self, name: str):
        if name in self._layers:
            self._layers[name].destroy()
            del self._layers[name]

    # ── Surface ───────────────────────────────────────────────────────────────

    @property
    def surface(self) -> pygame.Surface:
        """Zeichne hier mit pygame wie gewohnt."""
        return self._surface

    def handle_resize(self, new_w: int, new_h: int):
        """
        Muss beim VIDEORESIZE-Event aufgerufen werden.

        Die logische Aufloesung (self.width / self.height) bleibt unveraendert –
        nur der finale glViewport wird auf die neue Fenstergroesse gesetzt.
        OpenGL skaliert den fertigen Frame dann automatisch hoch/runter.

            for event in pygame.event.get():
                if event.type == pygame.VIDEORESIZE:
                    engine.handle_resize(event.w, event.h)
        """
        self._win_w = new_w
        self._win_h = new_h
        # Fenster neu oeffnen mit gleichen Flags
        flags = pygame.DOUBLEBUF | pygame.OPENGL | pygame.RESIZABLE
        pygame.display.set_mode((new_w, new_h), flags)

    # ── Render ────────────────────────────────────────────────────────────────

    def render(self):
        """Hauptrender-Aufruf. Einmal am Ende jedes Frames aufrufen."""
        self._frame += 1
        self._update_builtin_autos()

        raw = pygame.image.tostring(self._surface, "RGBA", True)
        glBindTexture(GL_TEXTURE_2D, self._main_tex)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, self.width, self.height, 0,
                     GL_RGBA, GL_UNSIGNED_BYTE, raw)
        glBindTexture(GL_TEXTURE_2D, 0)
        cur = self._main_tex
        fi  = 0

        # Lighting
        if self.lighting.enabled and self.lighting._lights:
            cur = self.lighting.apply(cur, self._fbo(fi), self._quad)
            fi += 1

        # Named Layers
        for lay in self._layers.values():
            if not lay.visible: continue
            dst = self._fbo(fi); dst.bind(); glClear(GL_COLOR_BUFFER_BIT)
            glUseProgram(self._cmp_prog)
            glActiveTexture(GL_TEXTURE0); glBindTexture(GL_TEXTURE_2D, cur)
            glUniform1i(glGetUniformLocation(self._cmp_prog, "uBase"), 0)
            glActiveTexture(GL_TEXTURE1); glBindTexture(GL_TEXTURE_2D, lay.texture)
            glUniform1i(glGetUniformLocation(self._cmp_prog, "uLayer"), 1)
            glUniform1f(glGetUniformLocation(self._cmp_prog, "uAlpha"), lay.alpha)
            self._quad(); dst.unbind(); cur = dst.tex; fi += 1

        # Mask
        if self._mask_tex:
            dst = self._fbo(fi); dst.bind(); glClear(GL_COLOR_BUFFER_BIT)
            glUseProgram(self._msk_prog)
            glActiveTexture(GL_TEXTURE0); glBindTexture(GL_TEXTURE_2D, cur)
            glUniform1i(glGetUniformLocation(self._msk_prog, "uTexture"), 0)
            glActiveTexture(GL_TEXTURE1); glBindTexture(GL_TEXTURE_2D, self._mask_tex)
            glUniform1i(glGetUniformLocation(self._msk_prog, "uMask"), 1)
            glUniform1i(glGetUniformLocation(self._msk_prog, "uInvert"), int(self._mask_invert))
            self._quad(); dst.unbind(); cur = dst.tex; fi += 1

        # Post-Processing Pipeline
        self._timer.begin()
        for pass_ in self._pipeline:
            dst = self._fbo(fi)
            glViewport(0, 0, self.width, self.height)
            cur = pass_.apply(cur, dst, self._auto, self._quad)
            fi += 1
        self._timer.end(); self._timer.fetch()

        # Finaler Blit → Bildschirm (Viewport = echte Fenstergroesse fuer Skalierung)
        glBindFramebuffer(GL_FRAMEBUFFER, 0)
        glViewport(0, 0, self._win_w, self._win_h)
        glClear(GL_COLOR_BUFFER_BIT)
        glUseProgram(self._pt_prog)
        glActiveTexture(GL_TEXTURE0); glBindTexture(GL_TEXTURE_2D, cur)
        glUniform1i(glGetUniformLocation(self._pt_prog, "uTexture"), 0)
        self._quad()

        # Debug Overlay
        if self.debug.enabled:
            self.debug.draw(self._surface)
            raw2 = pygame.image.tostring(self._surface, "RGBA", True)
            glBindTexture(GL_TEXTURE_2D, self._main_tex)
            glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, self.width, self.height, 0,
                         GL_RGBA, GL_UNSIGNED_BYTE, raw2)
            glBindTexture(GL_TEXTURE_2D, 0)
            glUseProgram(self._pt_prog)
            glActiveTexture(GL_TEXTURE0); glBindTexture(GL_TEXTURE_2D, self._main_tex)
            glUniform1i(glGetUniformLocation(self._pt_prog, "uTexture"), 0)
            glEnable(GL_BLEND); glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
            self._quad(); glDisable(GL_BLEND)

        pygame.display.flip()

    # ── Cleanup ───────────────────────────────────────────────────────────────

    def quit(self):
        self.clear_pipeline()
        self.lighting.destroy()
        self._timer.destroy()
        for lay in self._layers.values(): lay.destroy()
        for fbo in self._fbos: fbo.destroy()
        glDeleteTextures([self._main_tex])
        if self._mask_tex: glDeleteTextures([self._mask_tex])
        glDeleteBuffers(1, [self._vbo]); glDeleteBuffers(1, [self._ebo])
        glDeleteVertexArrays(1, [self._vao])
        glDeleteProgram(self._pt_prog); glDeleteProgram(self._cmp_prog)
        glDeleteProgram(self._msk_prog)
        pygame.quit()