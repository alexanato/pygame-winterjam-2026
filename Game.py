import pygame
import os
from Scenes.GameScene import GameScene
from Scenes.Scene import Scene
from Scripts.Util import *
from ShaderLib.shader_engine import *
class Game():
    def __init__(self):
        pygame.init()
        #self.screen = pygame.display.set_mode((1280, 720), pygame.SCALED | pygame.RESIZABLE)
        self.engine = ShaderEngine(1280, 720, "Mein Spiel")
        self.screen = self.engine.surface
        self.clock = pygame.time.Clock()
        self.stack = []

        self.sprites = self.load_sprites()
        self.light = {}
        self.push_scene(GameScene)
        self.run()

    def push_scene(self, scene_class):
        new_scene = scene_class(self)
        new_scene.start()
        self.stack.append(new_scene)

    def pop_scene(self):
        if len(self.stack) > 1:
            self.stack[-1].exit()
            self.stack.pop()
        else:
            pygame.quit()
            exit()

    def run(self):
        while True:
            dt = self.clock.tick(60) / 1000.0
            events = pygame.event.get()

            for event in events:
                if event.type == pygame.QUIT:
                    pygame.quit()
                    return

                if self.stack:
                    self.stack[-1].handle_event(event)

            if self.stack:
                self.stack[-1].update(dt)

            self.screen.fill((30, 30, 30))

            for scene in self.stack:
                scene.render()
            self.engine.render()
    def load_sprites(self):
        sprites = {}
        for x in os.listdir("./sprites"):
            sprites[x.split(".")[0]] = pygame.image.load("./sprites/" + x).convert_alpha()
        return sprites
    def load_light(self,len):
        if len in self.light and self.light[len] is not None:
            return self.light[len]
        elif str(f"{len}.png") in os.listdir("./light_presets"):
            #self.light[len] = load_grayscale_as_alpha("./light_presets_gray/" +str(f"{len}.png"))
            self.light[len] = pygame.image.load("./light_presets/" +str(f"{len}.png")).convert_alpha()
            self.light[len] = pygame.transform.scale_by(self.light[len],4)
        return self.light[len]
Game()