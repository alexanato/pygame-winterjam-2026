import pygame
from Scripts.animated_sprite import *


class StaticEntity(AnimatedSprite):
    def __init__(self, game, scene, x, y, img, groups):
        super().__init__(groups, game)
        self.game = game
        self.scene = scene
        self.image = img
        self.rect = self.image.get_rect(topleft=(x, y))
        self.pos = pygame.Vector2(self.rect.centerx, self.rect.centery)

        self.active = True
        self.interactable = True
        self.interaction_range = 50
        self._in_range_last = False

    def get_target(self):
        return getattr(self.scene, "player", None)

    def in_range(self, other):
        dx = self.rect.centerx - other.rect.centerx
        dy = self.rect.centery - other.rect.centery
        return (dx * dx + dy * dy) <= self.interaction_range ** 2

    def interaction_condition(self, other):
        return self.scene.is_pressed(pygame.K_e)

    def collides_with(self, other):
        return self.rect.colliderect(other.rect)

    def on_interact(self, other):
        pass

    def on_enter_range(self, other):
        pass

    def on_exit_range(self, other):
        pass

    def update(self, dt):
        if not self.active:
            return
        super().update(dt)

        if not self.interactable:
            return

        target = self.get_target()
        if target is None:
            return

        in_range_now = self.in_range(target)

        if in_range_now and not self._in_range_last:
            self.on_enter_range(target)
        elif not in_range_now and self._in_range_last:
            self.on_exit_range(target)

        if in_range_now and self.interaction_condition(target):
            self.on_interact(target)

        self._in_range_last = in_range_now