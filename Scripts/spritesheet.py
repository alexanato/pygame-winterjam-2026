import pygame


class SpriteSheet:
    def __init__(self, path: str, frame_width: int, frame_height: int):
        self._sheet = pygame.image.load(path).convert_alpha()
        self.frame_width = frame_width
        self.frame_height = frame_height

    def get_frames(self, row, count):
        return [
            self._sheet.subsurface(pygame.Rect(col * self.frame_width, row * self.frame_height, self.frame_width, self.frame_height)).copy()
            for col in range(count)
        ]
