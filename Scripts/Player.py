import pygame
from enums.player_state import PlayerState
from Scripts.MoveableEntity import *


class Player(MoveableEntity):
    def __init__(self, game, scene, groups):
        super().__init__(game, scene, 300, 300, game.sprites["player"], 60, groups)
        self.light_radius = 1000
        self.light_intensity = 10
        self.light_color = (247, 55, 24)
        self.state = PlayerState.NONE

        self.add_animation("idle",  "idle_player",      200, (40, 64), 2, 0)
        self.add_animation("up",    "player_go_up",     200, (40, 64), 2, 0)
        self.add_animation("down",  "player_go_down",   200, (40, 64), 2, 0)
        self.add_animation("right", "Player_go_right",  200, (32, 64), 2, 0)
        self.add_animation("left",  "Player_go_left",   200, (40, 64), 2, 0)


    def update(self, dt):
        self.direction = pygame.Vector2()
        self.state = PlayerState.NONE
        if self.scene.is_pressed(pygame.K_LEFT) or self.scene.is_pressed(pygame.K_a):
            self.direction.x -= 1
            self.state = PlayerState.LEFT
        elif self.scene.is_pressed(pygame.K_RIGHT) or self.scene.is_pressed(pygame.K_d):
            self.direction.x += 1
            self.state = PlayerState.RIGHT
        if self.scene.is_pressed(pygame.K_UP) or self.scene.is_pressed(pygame.K_w):
            self.direction.y -= 1
            self.state = PlayerState.UP
        elif self.scene.is_pressed(pygame.K_DOWN) or self.scene.is_pressed(pygame.K_s):
            self.direction.y += 1
            self.state = PlayerState.DOWN


        self.play(self.state.value)
        super().update(dt)


