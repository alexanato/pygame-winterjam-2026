import pygame
from Scripts.animated_sprite import *

class MoveableEntity(AnimatedSprite):
    def __init__(self, game, scene, x, y, img, speed, groups):
        super().__init__(groups,game)
        self.game = game
        self.scene = scene
        self.image = img
        self.rect = self.image.get_rect(topleft=(x, y))

        self.pos = pygame.Vector2(self.rect.centerx, self.rect.centery)
        self.speed = speed
        self.direction = pygame.Vector2(0, 0)

        self.obstacle = None

    def set_obstacles(self, obstacles):
        self.obstacle = obstacles

    def move(self, dt):
        collision_type = self.check_collision(self.direction)

        if collision_type != 1:
            self.pos.x += self.direction.x * self.speed * dt
        if collision_type != -1:
            self.pos.y += self.direction.y * self.speed * dt

        # Keep rect in sync with pos so collision detection stays accurate
        self.rect.centerx = int(self.pos.x)
        self.rect.centery = int(self.pos.y)

    def check_collision(self, direction):
        if not self.obstacle:
            return 0

        for sprite in self.obstacle:
            if sprite is self:
                continue
            if sprite.rect.colliderect(self.rect):
                rect_x = self.rect.copy()
                rect_x.x += direction.x
                rect_y = self.rect.copy()
                rect_y.y += direction.y
                if rect_x.colliderect(sprite.rect):
                    return 1
                if rect_y.colliderect(sprite.rect):
                    return -1
        return 0

    def update(self, dt):
        super().update(dt)
        self.move(dt)