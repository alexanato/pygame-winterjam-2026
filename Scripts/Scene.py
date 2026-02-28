import pygame
import pygame_gui


class Scene:
    def __init__(self, game):
        self.game = game
        self.screen = game.screen
        self.sub_scenes = []

        self.ui_manager = pygame_gui.UIManager(self.game.screen.get_size())

        self.is_visible = True
        self.is_active = True
        self.block_events = False

    def push_scene(self, scene_class):
        new_scene = scene_class(self.game)
        new_scene.start()
        self.sub_scenes.append(new_scene)
        return new_scene

    def pop_scene(self):
        if self.sub_scenes:
            last_scene = self.sub_scenes.pop()
            last_scene.exit()

    def handle_event(self, event):
        if not self.is_active:
            return False

        for sub in reversed(self.sub_scenes):
            if sub.handle_event(event):
                return True

        if self.ui_manager.process_events(event):
            return True

        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.on_click(event.pos, event.button):
                return True
        elif event.type in (pygame.KEYDOWN, pygame.KEYUP):
            if self.on_key(event.key, event.type == pygame.KEYDOWN):
                return True

        return self.block_events

    def update(self, dt):
        if not self.is_active:
            return

        self.ui_manager.update(dt)
        self.on_update(dt)

        for sub in self.sub_scenes:
            sub.update(dt)

    def render(self):
        if not self.is_visible:
            return

        self.on_render()

        self.ui_manager.draw_ui(self.screen)

        for sub in self.sub_scenes:
            sub.render()

    def start(self):
        pass

    def exit(self):
        pass

    def on_update(self, dt):
        pass

    def on_render(self):
        pass

    def on_click(self, pos, button):
        return False

    def on_key(self, key, is_down):
        return False