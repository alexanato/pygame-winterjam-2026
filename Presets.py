import pygame
import os


def generate_alpha_presets(base_color, start_radius, end_radius, step, folder="light_presets"):
    if not os.path.exists(folder):
        os.makedirs(folder)

    pygame.init()  # Notwendig für Surface-Operationen

    for radius in range(start_radius, end_radius + step, step):
        size = radius * 2
        # WICHTIG: SRCALPHA aktiviert den echten Alpha-Kanal für diese Surface
        surface = pygame.Surface((size, size), pygame.SRCALPHA)

        # Wir füllen die Surface von innen nach außen mit abnehmendem Alpha
        for r in range(radius, 0, -1):
            # Berechne Alpha: 255 im Zentrum, 0 am Rand
            # (r/radius)**2 sorgt für einen weicheren, natürlicheren Abfall
            alpha = int(255 * (1 - (r / radius) ** 1.1))
            alpha = max(0, min(255, alpha))

            # Zeichne einen Kreis mit der Wunschfarbe + berechnetem Alpha
            pygame.draw.circle(surface, (*base_color, alpha), (radius, radius), r)

        # Speichern als PNG (behält den Alpha-Kanal bei)
        path = os.path.join(folder, f"{radius}.png")
        new_size = pygame.Vector2(surface.get_size())
        scaled_surface = pygame.transform.scale(surface, new_size)
        pygame.image.save(scaled_surface, path)
        print(f"Preset mit Alpha gespeichert: {path}")


# Aufruf: Warmweißes Licht (255, 250, 200)
import pygame
import os


def generate_grayscale_presets(start_radius, end_radius, step, folder="light_presets_gray"):
    if not os.path.exists(folder):
        os.makedirs(folder)

    pygame.init()

    for radius in range(start_radius, end_radius + step, step):
        size = radius * 2
        # Wir erstellen eine Surface OHNE Alpha-Kanal (Standard RGB)
        # Für echtes Grayscale-Speichern nutzen wir später eine 8-bit Paletten-Surface
        surface = pygame.Surface((size, size))
        surface.fill((0, 0, 0))  # Hintergrund Schwarz

        for r in range(radius, 0, -1):
            # Hier ist der Helligkeitswert (0 bis 255)
            # Da es Grayscale ist, setzen wir R, G und B auf den gleichen Wert
            val = int(255 * (1 - (r / radius) ** 1.1))
            val = max(0, min(255, val))

            pygame.draw.circle(surface, (val, val, val), (radius, radius), r)

        # Um wirklich Platz zu sparen, konvertieren wir zu 8-bit (256 Farben)
        gray_8bit = surface.convert(8)

        path = os.path.join(folder, f"{radius}.png")
        pygame.image.save(gray_8bit, path)
        print(f"Grayscale-Preset gespeichert: {path}")


# Generiere zum Vergleich die gleichen Größen
#generate_grayscale_presets(10, 100, 2)
generate_alpha_presets((255, 255, 255), 1, 100, 1)