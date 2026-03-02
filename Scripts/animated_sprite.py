import pygame
from animation import Animation


class AnimatedSprite(pygame.sprite.Sprite):
    def __init__(self):
        super().__init__()
        self.animations = {}
        self.current = None
        self.index = 0
        self.elapsed = 0
        self.finished = False
        self.image = pygame.Surface((1, 1), pygame.SRCALPHA)
        self.rect = self.image.get_rect()

    def add_animation(self, name: str, animation: Animation):
        self.animations[name] = animation

    def play(self, name: str, restart: bool = False):
        if self.current is self.animations.get(name) and not restart:
            return
        self.current = self.animations[name]
        self.index = 0
        self.elapsed = 0
        self.finished = False

    def update(self, dt: int):
        if not self.current or self.finished:
            return

        self.elapsed += dt
        while self.elapsed >= self.current.durations[self._index]:
            self.elapsed -= self.current.durations[self._index]
            self.index += 1
            if self.index >= len(self.current.frames):
                if self.current.loop:
                    self.index = 0
                else:
                    self.index -= 1
                    self.finished = True
                    break

        self.image = self.current.frames[self.index]
