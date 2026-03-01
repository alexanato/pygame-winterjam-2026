import numpy as np
import pygame
import pygame.surfarray as surfarray
def lerp(a, b, t):
    return a + (b - a) * t


def load_grayscale_as_alpha(path):
    gray_img = pygame.image.load(path).convert()
    size = gray_img.get_size()

    light_surf = pygame.Surface(size, pygame.SRCALPHA)
    light_surf.fill((0, 0, 0, 0))  # schwarz, transparent

    brightness = pygame.surfarray.array3d(gray_img)[:, :, 0]
    pygame.surfarray.pixels_alpha(light_surf)[:] = brightness.astype(np.uint8)

    return light_surf