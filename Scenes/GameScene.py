from Scenes.Scene import *
from Scripts.Camera import *
from Scripts.Player import *
class GameScene(Scene):
    def __init__(self, game):
        super().__init__(game)
        self.screen = game.screen
        self.camera = Camera(game,0.999)
        self.enemies = pygame.sprite.Group()
        self.all_sprites = pygame.sprite.Group()
        self.player = Player(game,self,500,200,game.sprites["player"],400,self.all_sprites)
        self.entitys = [MoveableEntity(game,self,300,100,self.game.sprites ["player"],30,self.all_sprites)]
        self.camera.bind(self.player)
    def on_update(self, dt):
        self.camera.update(dt)
        self.all_sprites.update(dt)
    def on_render(self):
        for sprite in self.all_sprites:
            sprite.rect = self.camera.apply(sprite)
        self.all_sprites.draw(self.screen)
