import pygame

from  Scripts.MoveableEntity import *
class Player(MoveableEntity):
    def update(self, dt):
        super().update(dt)
        if self.scene.is_pressed(pygame.K_UP) or self.scene.is_pressed(pygame.K_w):
            self.direction += pygame.Vector2(0,-1)
        elif self.scene.is_pressed(pygame.K_DOWN) or self.scene.is_pressed(pygame.K_s):
            self.direction += pygame.Vector2(0,1)
        if self.scene.is_pressed(pygame.K_LEFT) or self.scene.is_pressed(pygame.K_a):
            self.direction += pygame.Vector2(-1,0)
        elif self.scene.is_pressed(pygame.K_RIGHT) or self.scene.is_pressed(pygame.K_d):
            self.direction += pygame.Vector2(1,0)
        self.move(dt)
        self.direction = pygame.Vector2()
