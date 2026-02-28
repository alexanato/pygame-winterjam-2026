import pygame


class Entity(pygame.sprite.Sprite):
    def __init__(self, game,x, y, img, speed, groups):
        super().__init__(groups)
        self.game = game
        self.image = img
        self.rect = self.image.get_rect(topleft=(x, y))

        self.pos = pygame.Vector2(self.rect.center)
        self.speed = speed
        self.direction = pygame.Vector2(0, 0)

        self.obstacle = None

    def set_obstacles(self, obstacles):
        self.obstacle = obstacles

    def move(self, dt):
        if self.direction.magnitude() != 0:
            self.direction = self.direction.normalize()
        collision_type = self.check_collision(self.direction)

        if collision_type != 1:
            self.rect.x += self.direction.x * self.speed * dt

        if collision_type != -1:
            self.rect.y += self.direction.y * self.speed * dt

    def check_collision(self,direction):
        if not self.obstacle:
            return

        for sprite in self.obstacle:
            if sprite.rect.colliderect(self.rect):
                rect_x = self.rect.copy()
                rect_x.x += direction.x
                rect_y = self.rect.copy()
                rect_y.y += direction.y
                if rect_x.colliderect(sprite.rect):
                    return 1
                if rect_y.colliderect(sprite.rect):
                    return -1
        return 0

    def update(self, dt):
        self.move(dt)