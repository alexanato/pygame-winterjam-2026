import pygame
import os
class Game():
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("pyjump")
        self.screen = pygame.display.set_mode((1280 , 720 ), pygame.SCALED | pygame.RESIZABLE)
        self.clock = pygame.time.Clock()
        self.dt = self.clock.tick() / 1000
        self.sprites = self.load_sprites()
        self.run()

    def run(self):
        self.start()
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
            self.dt = self.clock.tick() / 1000
            self.screen.fill((30, 30, 30))
            self.render()
            self.update()
            pygame.display.update()

    def start(self):
        pass

    def update(self):
        pass

    def render(self):
        self.screen.blit(self.sprites["player"],(100,199))
        pass
    def load_sprites(self):
        sprites = {}
        for x in os.listdir("./sprites"):
            sprites[x.split(".")[0]] = pygame.image.load("./sprites/" + x).convert_alpha()
        return sprites
Game()