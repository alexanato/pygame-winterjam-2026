import pygame
from dataclasses import dataclass


@dataclass
class Animation:
    frames: list[pygame.Surface]
    durations: list[int] | int  # ms pro Frame, oder ein Wert für alle int oder list
    loop: bool = True

    def __post_init__(self):
        if isinstance(self.durations, int):
            self.durations = [self.durations] * len(self.frames)
