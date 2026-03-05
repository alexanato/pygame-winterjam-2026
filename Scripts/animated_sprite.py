import pygame
from Scripts.animation import Animation
from Scripts.spritesheet import SpriteSheet


class AnimatedSprite(pygame.sprite.Sprite):
    def __init__(self, groups, game):
        super().__init__(groups)
        self.game = game
        self.animations: dict[str, Animation] = {}
        self.current: Animation | None = None
        self.current_name: str = ""
        self.index = 0
        self.elapsed = 0
        self.finished = False
        self.image = pygame.Surface((1, 1), pygame.SRCALPHA)
        self.rect = self.image.get_rect()

    def add_animation(self, name: str, animation: Animation | str, duration=None, size: tuple = None, col: int = None, row: int = 0):
        if isinstance(animation, Animation):
            self.animations[name] = animation
        else:
            frames = SpriteSheet(self.game.sprites[animation], size[0], size[1]).get_frames(row=row, count=col)
            self.animations[name] = Animation(frames, duration)

    def play(self, name: str, loop: bool = True):
        if self.current_name == name:
            return  # läuft bereits, nichts resetten
        self.current_name = name
        self.current = self.animations[name]
        self.current.loop = loop
        self.index = 0
        self.elapsed = 0
        self.finished = False

    def update(self, dt: int):
        if not self.current or self.finished:
            return

        self.elapsed += dt *1000
        while self.elapsed >= self.current.durations[self.index]:
            self.elapsed -= self.current.durations[self.index]
            self.index += 1
            print(self.current.frames)
            if self.index >= len(self.current.frames):
                if self.current.loop:
                    self.index = 0
                else:
                    self.index -= 1
                    self.finished = True
                    break

        self.image = self.current.frames[self.index]