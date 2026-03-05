from Scenes.Scene import *
from Scripts.Camera import *
from Scripts.Player import *
from Scenes.LightScene import *
class GameScene(Scene):
    def __init__(self, game):
        super().__init__(game)
        self.screen = game.screen
        self.camera = Camera(game,1)
        self.enemies = pygame.sprite.Group()
        self.all_sprites = pygame.sprite.Group()
        self.player = Player(game,self,self.all_sprites)
        self.entitys = [MoveableEntity(game,self,300,100,self.game.sprites ["player"],30,self.all_sprites)]
        self.camera.bind(self.player)
        self.push_scene(LightScene,light_sources=self.all_sprites)
    def on_update(self, dt):
        self.camera.update(dt)
        self.all_sprites.update(dt)
    def on_render(self):
        for sprite in self.all_sprites:
            sprite.rect = self.camera.apply(sprite)
        self.all_sprites.draw(self.screen)
