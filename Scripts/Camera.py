import pygame
from Scripts.Util import *

class Camera():
    def __init__(self, game, speed):
        self.game = game
        self.off_set = pygame.Vector2()
        self.target = None
        self.target_off_set = pygame.Vector2()
        self.speed = speed

    def bind(self, target):
        self.target = target

    def move(self, direction):
        self.target_off_set += direction

    def move_absolute(self, pos):
        self.target_off_set = pygame.Vector2(pos)

    def update(self, dt):
        if self.target:
            screen_w = self.game.screen.get_width()
            screen_h = self.game.screen.get_height()
            # Offset = player position - screen center
            # So that the player appears centered on screen
            self.target_off_set = pygame.Vector2(
                self.target.pos.x - screen_w / 2,
                self.target.pos.y - screen_h / 2
            )
        self.off_set = self.off_set.lerp(self.target_off_set, self.speed * dt)

    def apply(self, sprite):
        # Returns a Rect shifted by the camera offset
        return pygame.Rect(
            sprite.pos.x - self.off_set.x,
            sprite.pos.y - self.off_set.y,
            sprite.rect.width,
            sprite.rect.height
        )