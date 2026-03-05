import pygame
from dataclasses import dataclass


@dataclass
class Animation:
    frames: list[pygame.Surface]
    durations: list[int] | int | float  # ms pro Frame, oder ein Wert für alle
    loop: bool = True

    def __post_init__(self):
        if not isinstance(self.durations, list):
            self.durations = [int(self.durations)] * len(self.frames)