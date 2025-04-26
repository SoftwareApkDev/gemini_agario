import pygame
import random
import math
import os
from dotenv import load_dotenv
import google.generativeai as genai

# --- Gemini Integration Setup ---
try:
    load_dotenv()
    genai.configure(api_key=os.environ['GEMINI_API_KEY'])
    GEMINI_MODEL = genai.GenerativeModel("gemini-2.5-flash-preview-04-17")
    gemini_available = True
    print("Gemini API configured successfully.")
    print("Press 'G' in-game to get a cell description from Gemini.")

except ImportError:
    gemini_available = False
    print("Libraries for Gemini (google-generativeai, python-dotenv) not found.")
    print("Gemini integration disabled. Please install them: pip install google-generativeai python-dotenv")
    print("Press 'G' will do nothing.")
except Exception as e:
    gemini_available = False
    print(f"Error configuring Gemini API: {e}")
    print("Gemini integration disabled. Press 'G' will do nothing.")


# --- Pygame Setup ---
pygame.init()

# Screen dimensions
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("Simple Agar.io Clone with Gemini")

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (255, 0, 0)
GREEN = (0, 255, 0)
BLUE = (0, 0, 255)
GRAY = (200, 200, 200)
DARK_GRAY = (150, 150, 150)

# Game settings
WORLD_WIDTH = 2000
WORLD_HEIGHT = 2000
FOOD_COUNT = 200
INITIAL_PLAYER_RADIUS = 20
PLAYER_SPEED_FACTOR = 0.1 # Smaller is faster relative to size
MIN_PLAYER_RADIUS = 5 # Prevent player from disappearing entirely
FOOD_RADIUS = 5

# Font
font = pygame.font.Font(None, 36)
small_font = pygame.font.Font(None, 24)


# --- Game Objects ---

class GameObject:
    def __init__(self, x, y, radius, color):
        self.x = x
        self.y = y
        self.radius = radius
        self.color = color

    def draw(self, surface, camera_x, camera_y):
        # Draw circle relative to camera position
        screen_x = self.x - camera_x
        screen_y = self.y - camera_y

        # Only draw if on screen
        if -self.radius <= screen_x <= SCREEN_WIDTH + self.radius and \
           -self.radius <= screen_y <= SCREEN_HEIGHT + self.radius:
            pygame.draw.circle(surface, self.color, (int(screen_x), int(screen_y)), int(self.radius))

class Food(GameObject):
    def __init__(self):
        x = random.uniform(-WORLD_WIDTH/2, WORLD_WIDTH/2)
        y = random.uniform(-WORLD_HEIGHT/2, WORLD_HEIGHT/2)
        color = (random.randint(50, 255), random.randint(50, 255), random.randint(50, 255))
        super().__init__(x, y, FOOD_RADIUS, color)

class Player(GameObject):
    def __init__(self, name="Player", color=(0, 150, 255)):
        x = 0 # Start at the center of the world
        y = 0
        super().__init__(x, y, INITIAL_PLAYER_RADIUS, color)
        self.name = name
        self.mass = self.radius**2 # Mass is proportional to area
        self.target_x = self.x
        self.target_y = self.y
        self.gemini_description = ""
        self.description_timer = 0

    def update_target(self, mouse_x, mouse_y, camera_x, camera_y):
        # Convert mouse screen coordinates to world coordinates
        self.target_x = mouse_x + camera_x
        self.target_y = mouse_y + camera_y

    def move(self):
        dx = self.target_x - self.x
        dy = self.target_y - self.y
        distance = math.sqrt(dx**2 + dy**2)

        if distance > 1: # Only move if far enough
            # Speed decreases as size increases
            speed = PLAYER_SPEED_FACTOR * (INITIAL_PLAYER_RADIUS / self.radius)
            speed = max(speed, 0.1) # Minimum speed

            move_x = dx / distance * speed
            move_y = dy / distance * speed

            self.x += move_x
            self.y += move_y

            # Clamp player position to world bounds
            self.x = max(-WORLD_WIDTH/2 + self.radius, min(WORLD_WIDTH/2 - self.radius, self.x))
            self.y = max(-WORLD_HEIGHT/2 + self.radius, min(WORLD_HEIGHT/2 - self.radius, self.y))


    def grow(self, mass_increase):
        self.mass += mass_increase
        self.radius = math.sqrt(self.mass) # Update radius based on new mass
        self.radius = max(self.radius, MIN_PLAYER_RADIUS) # Don't shrink below minimum

    def eat(self, food):
        # Simple collision check: distance between centers < player_radius
        # A more accurate check would be distance < player_radius + food_radius
        # But for eating smaller things, player_radius is often sufficient
        distance = math.sqrt((self.x - food.x)**2 + (self.y - food.y)**2)
        if distance < self.radius:
            self.grow(food.radius**2) # Gain mass proportional to food area
            return True # Indicate food was eaten
        return False

    def draw(self, surface, camera_x, camera_y):
        super().draw(surface, camera_x, camera_y) # Draw the circle

        # Draw player name
        screen_x = self.x - camera_x
        screen_y = self.y - camera_y

        # Render name text
        name_surface = font.render(self.name, True, WHITE)
        name_rect = name_surface.get_rect(center=(int(screen_x), int(screen_y)))
        surface.blit(name_surface, name_rect)

        # Render Gemini description if active
        if self.gemini_description and self.description_timer > 0:
            desc_surface = small_font.render(self.gemini_description, True, WHITE)
            desc_rect = desc_surface.get_rect(center=(int(screen_x), int(screen_y) + self.radius + 15)) # Below the cell
            # Clamp text position to screen bounds
            desc_rect.x = max(0, min(SCREEN_WIDTH - desc_rect.width, desc_rect.x))
            desc_rect.y = max(0, min(SCREEN_HEIGHT - desc_rect.height, desc_rect.y))
            surface.blit(desc_surface, desc_rect)

    def update_description_timer(self, dt):
         if self.description_timer > 0:
             self.description_timer -= dt
             if self.description_timer <= 0:
                 self.gemini_description = "" # Clear description when timer runs out


# --- Game Functions ---

def spawn_food(count):
    food_list = []
    for _ in range(count):
        food_list.append(Food())
    return food_list

def draw_grid(surface, camera_x, camera_y, grid_size=50, color=DARK_GRAY):
    start_x = int(camera_x - SCREEN_WIDTH/2)
    start_y = int(camera_y - SCREEN_HEIGHT/2)
    end_x = int(camera_x + SCREEN_WIDTH/2)
    end_y = int(camera_y + SCREEN_HEIGHT/2)

    # Calculate visible grid lines relative to camera
    first_grid_x = (int(start_x / grid_size) - 1) * grid_size
    first_grid_y = (int(start_y / grid_size) - 1) * grid_size

    # Draw vertical lines
    for x in range(first_grid_x, end_x + grid_size, grid_size):
        screen_x = int(x - camera_x)
        if -WORLD_WIDTH/2 <= x <= WORLD_WIDTH/2:
             pygame.draw.line(surface, color, (screen_x, 0), (screen_x, SCREEN_HEIGHT))

    # Draw horizontal lines
    for y in range(first_grid_y, end_y + grid_size, grid_size):
        screen_y = int(y - camera_y)
        if -WORLD_HEIGHT/2 <= y <= WORLD_HEIGHT/2:
            pygame.draw.line(surface, color, (0, screen_y), (SCREEN_WIDTH, screen_y))


# --- Main Game Loop ---
def main():
    running = True
    clock = pygame.time.Clock()

    player = Player("MyCell", color=(random.randint(50, 200), random.randint(50, 200), random.randint(50, 200)))
    food_list = spawn_food(FOOD_COUNT)

    # Camera position (centered on player initially)
    camera_x = player.x - SCREEN_WIDTH / 2
    camera_y = player.y - SCREEN_HEIGHT / 2

    # Gemini description state
    gemini_request_in_progress = False
    gemini_description_text = ""
    gemini_description_timer = 0 # How long to show the description for (in seconds)
    DESCRIPTION_DURATION = 5 # seconds

    while running:
        dt = clock.tick(60) / 1000.0 # Delta time in seconds

        # --- Event Handling ---
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                # Trigger Gemini description on 'G' key press
                if event.key == pygame.K_g and gemini_available and not gemini_request_in_progress:
                    print("Requesting Gemini description...")
                    gemini_request_in_progress = True
                    player.gemini_description = "Getting description..." # Temporary message
                    player.description_timer = 2 # Show "Getting..." for a bit
                    # Run the Gemini call potentially in a thread to avoid freezing
                    # But for a simple example, we'll do it synchronously for now.
                    # A real game would use threading or asyncio.
                    try:
                        prompt = f"Generate a very short, quirky, one-sentence description for an Agar.io cell that is color {player.color} and has a mass of approximately {int(player.mass)}. Keep it under 15 words."
                        response = GEMINI_MODEL.generate_content(prompt)
                        gemini_description_text = response.text.strip().replace('"', '') # Remove quotes
                        print(f"Gemini response: {gemini_description_text}")
                        player.gemini_description = gemini_description_text
                        player.description_timer = DESCRIPTION_DURATION # Show response for longer
                    except Exception as e:
                        print(f"Error during Gemini API call: {e}")
                        player.gemini_description = "Gemini error :("
                        player.description_timer = 2 # Show error for a bit
                    finally:
                        gemini_request_in_progress = False


        # --- Game State Updates ---
        # Player movement target follows mouse
        mouse_x, mouse_y = pygame.mouse.get_pos()
        player.update_target(mouse_x, mouse_y, camera_x, camera_y)
        player.move()

        # Update camera to follow player
        camera_x = player.x - SCREEN_WIDTH / 2
        camera_y = player.y - SCREEN_HEIGHT / 2

        # Ensure camera stays within world bounds (simplified)
        # This prevents drawing areas outside the world
        camera_x = max(-WORLD_WIDTH/2 + SCREEN_WIDTH/2, min(WORLD_WIDTH/2 - SCREEN_WIDTH/2, camera_x))
        camera_y = max(-WORLD_HEIGHT/2 + SCREEN_HEIGHT/2, min(WORLD_HEIGHT/2 - SCREEN_HEIGHT/2, camera_y))


        # Check for food consumption
        eaten_food_indices = []
        for i, food in enumerate(food_list):
            if player.eat(food):
                eaten_food_indices.append(i)

        # Remove eaten food and spawn new food
        for i in sorted(eaten_food_indices, reverse=True):
            food_list.pop(i)
            food_list.append(Food()) # Replace with a new food item

        # Update description timer
        player.update_description_timer(dt)


        # --- Drawing ---
        # Draw background (world area indicator or solid color)
        screen.fill(BLACK) # Dark background

        # Draw world boundaries (optional)
        world_left = -WORLD_WIDTH/2 - camera_x
        world_top = -WORLD_HEIGHT/2 - camera_y
        world_rect = pygame.Rect(world_left, world_top, WORLD_WIDTH, WORLD_HEIGHT)
        pygame.draw.rect(screen, (20, 20, 20), world_rect) # Dark gray background for the world area

        # Draw grid lines
        draw_grid(screen, camera_x, camera_y)

        # Draw food
        for food in food_list:
            food.draw(screen, camera_x, camera_y)

        # Draw player
        player.draw(screen, camera_x, camera_y)

        # Draw UI (Score/Mass)
        score_text = font.render(f"Mass: {int(player.mass)}", True, WHITE)
        screen.blit(score_text, (10, 10))

        # Draw instructions
        instruction_text = small_font.render("Move mouse to move. Press G for Gemini description.", True, GRAY)
        screen.blit(instruction_text, (10, SCREEN_HEIGHT - 30))

        # Update the display
        pygame.display.flip()

    pygame.quit()

if __name__ == "__main__":
    main()