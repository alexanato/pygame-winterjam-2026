from Scenes.Scene import *
from ShaderLib.shader_engine import LightSource


class LightScene(Scene):
    def __init__(self, game, light_sources):
        super().__init__(game)
        self.light_sources = light_sources

        self._all: dict = {}

        self._engine = self.game.engine
        self._engine.lighting.enabled = True
        self._engine.lighting.ambient = getattr(game, "ambient_light", (0.04, 0.04, 0.06))

        self._sw = game.screen.get_width()
        self._sh = game.screen.get_height()

    def _is_visible(self, sx: float, sy: float, radius: float) -> bool:
        """Kreis-Rechteck-Test: Ueberlappt der Lichtkreis den Screen?"""
        nearest_x = max(0.0, min(sx, self._sw))
        nearest_y = max(0.0, min(sy, self._sh))
        dist_sq = (sx - nearest_x) ** 2 + (sy - nearest_y) ** 2
        return dist_sq <= radius * radius


    def _sync_lights(self):
        current_ids: set = set()
        for sprite in self.light_sources:
            if getattr(sprite, "light_radius", None) is None:
                continue
            sid = id(sprite)
            current_ids.add(sid)
            if sid not in self._all:
                color = _normalize_color(getattr(sprite, "light_color", (1.0, 0.78, 0.39)))
                ls = LightSource(
                    x=float(sprite.rect.centerx),
                    y=float(sprite.rect.centery),
                    color=color,
                    radius=float(sprite.light_radius),
                    intensity=float(getattr(sprite, "light_intensity", 1.0)),
                )
                self._all[sid] = (sprite, ls)

        for sid in list(self._all.keys()):
            if sid not in current_ids:
                _, ls = self._all.pop(sid)
                if ls in self._engine.lighting._lights:
                    self._engine.lighting.remove(ls)

        sw2, sh2 = self._sw / 2, self._sh / 2

        visible = []
        for sid, (sprite, ls) in self._all.items():
            sx = float(sprite.rect.centerx)
            sy = float(sprite.rect.centery)
            r  = float(getattr(sprite, "light_radius", ls.radius))
            if self._is_visible(sx, sy, r):
                dist_sq = (sx - sw2) ** 2 + (sy - sh2) ** 2
                visible.append((dist_sq, sid, sprite, ls))

        visible.sort(key=lambda t: t[0])
        visible_top16 = visible[:16]
        visible_ids = {sid for _, sid, _, _ in visible_top16}

        for _, sid, sprite, ls in visible_top16:
            ls.x         = float(sprite.rect.centerx)
            ls.y         = float(sprite.rect.centery)
            ls.radius    = float(getattr(sprite, "light_radius", ls.radius))
            ls.intensity = float(getattr(sprite, "light_intensity", ls.intensity))
            color = getattr(sprite, "light_color", None)
            if color is not None:
                ls.color = _normalize_color(color)
            if ls not in self._engine.lighting._lights:
                self._engine.lighting.add(ls)

        for sid, (sprite, ls) in self._all.items():
            if sid not in visible_ids and ls in self._engine.lighting._lights:
                self._engine.lighting.remove(ls)


    def on_update(self, dt):
        pass

    def on_render(self):
        self._sync_lights()

    def exit(self):
        for _, (_, ls) in self._all.items():
            if ls in self._engine.lighting._lights:
                self._engine.lighting.remove(ls)
        self._all.clear()


def _normalize_color(color) -> tuple:
    r, g, b = color[0], color[1], color[2]
    if isinstance(r, int) or r > 1.0 or g > 1.0 or b > 1.0:
        return (r / 255.0, g / 255.0, b / 255.0)
    return (float(r), float(g), float(b))