import pygame
import random
import math
import noise
import sys # NEW: Import sys module
import os # NEW: Import os module

# NEW: Helper function to get resource path for PyInstaller
def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".") # Fallback to current directory if not in PyInstaller bundle

    return os.path.join(base_path, relative_path)

# NEW: Import OpenGL libraries
from OpenGL.GL import *
from OpenGL.GLU import *
import numpy as np

# Initialize Pygame
pygame.init()

# Constants
WINDOW_WIDTH = 1280 # Changed for 16:9 aspect ratio
WINDOW_HEIGHT = 720 # Changed for 16:9 aspect ratio
# NOTE: The game logic still uses the grid size for its arrays,
# but the visual size is now determined by the 3D projection.
# Let's reduce the grid density for better 3D performance.
GRID_DENSITY_FACTOR = 2 # Lower number = more dense. 2 is a good balance.
GRID_SIZE = 8 * GRID_DENSITY_FACTOR
GRID_WIDTH = WINDOW_WIDTH // GRID_SIZE
GRID_HEIGHT = WINDOW_HEIGHT // GRID_SIZE

# NEW: Game state constants
MENU_STATE = 0
GAME_STATE = 1
PAUSED_STATE = 2 # NEW: Pause game state
TRANSITIONING_TO_GAME_STATE = 3 # NEW: State for fade transition
MENU_FADE_SPEED = 8
MENU_ROTATION_SPEED = 0.3

# NEW: Difficulty Constants
DIFFICULTY_EASY_SPREAD = 55
DIFFICULTY_NORMAL_SPREAD = 35
DIFFICULTY_HARD_SPREAD = 20

# NEW: PSX Effect Constants
PSX_RESOLUTION_FACTOR = 2 # Divide original resolution by this factor (e.g., 1280/4 = 320)

# NEW: Sound Constants
MAX_HEAR_DISTANCE = 100.0 # Max distance in world units to hear fire sound
MAX_FIRE_VOLUME = 0.6 # NEW: Max volume for fire sound (0.0 to 1.0)
MASTER_VOLUME_DEFAULT = 0.7 # NEW: Default master volume for all sounds (0.0 to 1.0)
FIRE_CELLS_FOR_MAX_SOUND = 150 # NEW: Number of fire cells for maximum fire sound volume

# Colors (remain the same)
DARK_GREEN = (94, 178, 94) # Swapped with LIGHT_GREEN, further darkened
LIGHT_GREEN = (14, 99, 14) # Swapped with DARK_GREEN, further darkened
GRASS_GREEN = (54, 162, 0) # Darkened from (74, 182, 0)
FIELD_YELLOW = (170, 130, 0)
BROWN = (60, 35, 10)
RED = (180, 30, 0)
ORANGE = (180, 90, 0)
YELLOW = (180, 180, 0)
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
GRAY = (80, 80, 80)
DARK_GRAY = (30, 30, 30)
BLUE = (60, 100, 180)
HOUSE_RED = (90, 30, 10)
CYAN_SKY = (45, 110, 180)

# Cell states (remain the same)
FOREST_DENSE = 0
FOREST_LIGHT = 1
GRASSLAND = 2
FIELD = 3
HOUSE = 4
WATER = 5
BURNT = 6
FIRE = 7
CONTROLLED_BURN = 8

# Flammability (remains the same)
FLAMMABILITY = {
    FOREST_DENSE: 0.8, FOREST_LIGHT: 0.6, GRASSLAND: 0.4, FIELD: 0.3,
    HOUSE: 0.9, WATER: 0.0, BURNT: 0.0, FIRE: 1.0, CONTROLLED_BURN: 1.0
}

# NEW: Constants for fire aging and ash transition
MAX_ASH_TIMER = 420 # How many updates before fire turns to ash

# NEW: Particle class for fire effects
class Particle:
    def __init__(self, x, z):
        self.pos = np.array([x, 0.5, z], dtype=float)
        self.vel = np.array([random.uniform(-0.02, 0.02),
                             random.uniform(0.05, 0.1),
                             random.uniform(-0.02, 0.02)], dtype=float)
        self.lifetime = random.randint(100, 200)
        self.max_lifetime = self.lifetime
        self.size = random.uniform(0.3, 0.6)
        # Start as bright yellow/orange, fade to dark smoke
        self.start_color = random.choice([(180, 60, 0), (180, 20, 0)])
        self.end_color = (40, 40, 40)

    def update(self, dt):
        self.pos += self.vel * dt * 60 # Scale movement by dt
        self.vel[1] *= (0.99 ** (dt * 60)) # Slow down upward movement (gravity/drag) adjusted by dt
        self.lifetime -= dt * 60 # Decrease lifetime by dt

    def get_color(self):
        fade_factor = self.lifetime / self.max_lifetime
        # Fade from start color to end color
        r = int(self.start_color[0] * fade_factor + self.end_color[0] * (1 - fade_factor))
        g = int(self.start_color[1] * fade_factor + self.end_color[1] * (1 - fade_factor))
        b = int(self.start_color[2] * fade_factor + self.end_color[2] * (1 - fade_factor))
        # Alpha fades out
        a = fade_factor
        return (r/255.0, g/255.0, b/255.0, a)

### NEW ###
# Class to manage individual tree sprites
class Tree:
    # States for animation
    NORMAL = 0
    BURNING = 1
    BURNT = 2

    def __init__(self, grid_x, grid_y):
        # Add a random offset so trees aren't perfectly centered in grid cells
        offset_x = random.uniform(-0.3, 0.3)
        offset_z = random.uniform(-0.3, 0.3)
        self.pos = np.array([
            grid_x - GRID_WIDTH / 2 + 0.5 + offset_x,
            0.0,  # Base of the tree is on the ground plane (y=0)
            grid_y - GRID_HEIGHT / 2 + 0.5 + offset_z
        ], dtype=float)
        self.grid_x = grid_x
        self.grid_y = grid_y
        self.state = self.NORMAL
        self.animation_timer = 0
        # Frame indices will map to the loaded texture list:
        # 0: normal, 1-3: burning animation, 4: burnt
        self.current_frame_index = 0
        self.height = 3.5  # Adjust size as needed
        self.width = 2.5   # Adjust size as needed

    # NEW: Method to return current texture ID for unified drawing
    def get_texture_id(self, game_instance):
        return game_instance.tree_textures[self.current_frame_index]
    
    # NEW: Method to return dimensions for unified drawing
    def get_dimensions(self):
        return self.width, self.height

### NEW ###
# Class to manage individual field grass sprites
class FieldGrass:
    NORMAL = 0

    def __init__(self, grid_x, grid_y):
        offset_x = random.uniform(-0.4, 0.4)
        offset_z = random.uniform(-0.4, 0.4)
        self.pos = np.array([
            grid_x - GRID_WIDTH / 2 + 0.5 + offset_x,
            0.0,
            grid_y - GRID_HEIGHT / 2 + 0.5 + offset_z
        ], dtype=float)
        self.grid_x = grid_x
        self.grid_y = grid_y
        self.state = self.NORMAL
        self.height = 0.8 # Smaller than trees
        self.width = 0.8  # Smaller than trees

    # NEW: Method to return current texture ID for unified drawing
    def get_texture_id(self, game_instance):
        # Field grass only has one texture
        return game_instance.fieldgrass_texture

    # NEW: Method to return dimensions for unified drawing
    def get_dimensions(self):
        return self.width, self.height

### NEW ###
# Class to manage individual house sprites
class HouseSprite:
    NORMAL = 0
    BURNT = 1

    def __init__(self, grid_x, grid_y):
        self.pos = np.array([
            grid_x - GRID_WIDTH / 2 + 0.5,
            0.0, # Houses sit on the ground
            grid_y - GRID_HEIGHT / 2 + 0.5
        ], dtype=float)
        self.grid_x = grid_x
        self.grid_y = grid_y
        self.state = self.NORMAL
        self.height = 1.8 # Reduced further from 2.5
        self.width = 1.8  # Reduced further from 2.5

    # NEW: Method to return current texture ID for unified drawing
    def get_texture_id(self, game_instance):
        return game_instance.house_textures[self.state]

    # NEW: Method to return dimensions for unified drawing
    def get_dimensions(self):
        return self.width, self.height

### NEW: Button class for stylized menu buttons
class MenuButton:
    def __init__(self, x, y, width, height, text, font, is_checkbox=False): # NEW: Add is_checkbox parameter
        self.rect = pygame.Rect(x, y, width, height)
        self.text = text
        self.font = font
        self.hovered = False
        self.is_checkbox = is_checkbox # NEW: Store checkbox state
        
    def update(self, mouse_pos):
        self.hovered = self.rect.collidepoint(mouse_pos)
    
    def draw_gl(self, x, y, is_selected=False):
        # Draw button background with fire-themed styling
        glDisable(GL_TEXTURE_2D)
        
        # Button background - dark red/brown
        if is_selected: # NEW: Highlight color for selected button
            bg_color = (0.8, 0.4, 0.2)
        elif self.hovered:
            bg_color = (0.6, 0.2, 0.1)
        else:
            bg_color = (0.4, 0.15, 0.08)
        glColor3f(*bg_color)
        
        # NEW: Handle drawing based on is_checkbox
        if self.is_checkbox:
            checkbox_size = self.rect.height * 0.7 # Make checkbox smaller than full height
            # NEW: Position checkbox at the left edge of its rect, not centered.
            box_x = x # Use the passed x, which is self.rect.x
            box_y = y + (self.rect.height - checkbox_size) / 2 # Center box vertically within its rect height

            # Draw the checkbox background
            glBegin(GL_QUADS)
            glVertex2f(box_x, box_y)
            glVertex2f(box_x + checkbox_size, box_y)
            glVertex2f(box_x + checkbox_size, box_y + checkbox_size)
            glVertex2f(box_x, box_y + checkbox_size)
            glEnd()

            # Draw the checkbox border
            if is_selected: 
                border_color = (1.0, 0.6, 0.2) # Active/checked color
            elif self.hovered:
                border_color = (1.0, 0.4, 0.0)
            else:
                border_color = (0.8, 0.2, 0.0)
            glColor3f(*border_color)
            glLineWidth(3)
            glBegin(GL_LINE_LOOP)
            glVertex2f(box_x, box_y)
            glVertex2f(box_x + checkbox_size, box_y)
            glVertex2f(box_x + checkbox_size, box_y + checkbox_size)
            glVertex2f(box_x, box_y + checkbox_size)
            glEnd()

            # If selected, draw a checkmark (simple square for now)
            if is_selected:
                check_color = (1.0, 1.0, 0.0) # Yellowish checkmark
                glColor3f(*check_color)
                check_padding = checkbox_size * 0.2
                glBegin(GL_QUADS)
                glVertex2f(box_x + check_padding, box_y + check_padding)
                glVertex2f(box_x + checkbox_size - check_padding, box_y + check_padding)
                glVertex2f(box_x + checkbox_size - check_padding, box_y + checkbox_size - check_padding)
                glVertex2f(box_x + check_padding, box_y + checkbox_size - check_padding)
                glEnd()

        else: # Original button drawing logic
            glBegin(GL_QUADS)
            glVertex2f(x, y)
            glVertex2f(x + self.rect.width, y)
            glVertex2f(x + self.rect.width, y + self.rect.height)
            glVertex2f(x, y + self.rect.height)
            glEnd()
            
            # Button border - bright red/orange
            if is_selected: # NEW: Highlight color for selected button
                border_color = (1.0, 0.6, 0.2)
            elif self.hovered:
                border_color = (1.0, 0.4, 0.0)
            else:
                border_color = (0.8, 0.2, 0.0)
            glColor3f(*border_color)
            glLineWidth(3)
            
            glBegin(GL_LINE_LOOP)
            glVertex2f(x, y)
            glVertex2f(x + self.rect.width, y)
            glVertex2f(x + self.rect.width, y + self.rect.height)
            glVertex2f(x, y + self.rect.height)
            glEnd()

        # NEW: Draw text for both button and checkbox types within the button's rect
        # This ensures the text is part of the button's clickable area. (Moved from draw_menu_ui/draw_pause_menu)
        text_surface = self.font.render(self.text, True, WHITE)
        if self.is_checkbox: # Position text to the right of the checkbox square
            checkbox_size = self.rect.height * 0.7 # Needs to match the size calculated above
            text_x = x + checkbox_size + 10 # 10px padding from checkbox
            text_y = y + (self.rect.height - text_surface.get_height()) / 2
        else: # Original button text positioning (centered)
            text_x = x + (self.rect.width - text_surface.get_width()) // 2
            text_y = y + (self.rect.height - text_surface.get_height()) // 2
        
        text_data = pygame.image.tostring(text_surface, "RGBA", True)
        glRasterPos2d(text_x, text_y + text_surface.get_height()) # Pygame uses top-left for render, OpenGL bottom-left for rasterPos
        glDrawPixels(text_surface.get_width(), text_surface.get_height(), 
                    GL_RGBA, GL_UNSIGNED_BYTE, text_data)

class FireGame:
    def __init__(self, is_fullscreen_init=False): # NEW: Add is_fullscreen_init parameter
        # Initialize Pygame display, but don't set mode yet as it depends on is_fullscreen_init
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.DOUBLEBUF | pygame.OPENGL)
        pygame.display.set_caption("Fighting Fire with Fire - 3D Island View")
        self.clock = pygame.time.Clock()

        self.camera_rot_y = 45
        self.camera_rot_x = 30
        self.camera_zoom = -150
        self.mouse_down = False
        self.last_mouse_pos = (0, 0)
        self.click_start_pos = (0, 0)
        self.CLICK_THRESHOLD = 5

        self.grid = [[FOREST_DENSE for _ in range(GRID_WIDTH)] for _ in range(GRID_HEIGHT)]
        self.burnt_timers = [[0 for _ in range(GRID_WIDTH)] for _ in range(GRID_HEIGHT)]
        self.ash_colors = [[None for _ in range(GRID_WIDTH)] for _ in range(GRID_HEIGHT)]

        self.running = True
        self.game_over = False
        self.victory = False
        self.fire_spread_timer = 0
        self.fire_spread_delay = 35

        self.houses_saved = 0
        self.houses_total = 0
        self.forest_saved = 0
        self.total_burnable = 0
        self.controlled_burns_used = 0
        
        self.dt = 0.0 # NEW: Delta time for framerate independence
        self.terrain_base_colors = {} # NEW: Store initial terrain colors to avoid per-frame noise

        self.difficulty = "Normal" # NEW: Default difficulty setting
        self.psx_effect_enabled = True # NEW: Flag for PSX effect - changed to True by default
        self.master_volume = MASTER_VOLUME_DEFAULT # NEW: Initialize master volume
        self.fbo = 0 # NEW: Framebuffer object ID
        self.fbo_texture = 0 # NEW: Texture attached to FBO
        self.fbo_depth_rb = 0 # NEW: Depth render buffer for FBO
        self.fbo_width = WINDOW_WIDTH // PSX_RESOLUTION_FACTOR # NEW: FBO resolution
        self.fbo_height = WINDOW_HEIGHT // PSX_RESOLUTION_FACTOR # NEW: FBO resolution

        # NEW: Load pixelated font with a fallback
        try:
            # IMPORTANT: You need to have 'pixel_font.ttf' in the same folder
            self.font = pygame.font.Font(resource_path('pixel_font.ttf'), 24)
            self.small_font = pygame.font.Font(resource_path('pixel_font.ttf'), 16)
            print("Pixel font loaded successfully.")
        except pygame.error:
            print("Warning: 'pixel_font.ttf' not found. Falling back to default font.")
            self.font = pygame.font.Font(None, 28)
            self.small_font = pygame.font.Font(None, 20)
        
        # NEW: Particle system list
        self.particles = []

        ### NEW ###
        # Tree sprite management
        self.trees = []
        self.tree_textures = []
        # NEW: Field grass sprite management
        self.fieldgrass_sprites = []
        self.fieldgrass_texture = None # Single texture for field grass
        # NEW: House sprite management
        self.house_sprites = []
        self.house_textures = {} # Dictionary to hold normal and burnt textures
        self.particle_vbo_v = glGenBuffers(1) # VBO for particle vertex positions
        self.particle_vbo_c = glGenBuffers(1) # VBO for particle colors
        self.particle_buffer = np.array([], dtype='f4') # Pre-allocate numpy array

        # NEW: Game state management
        self.game_state = MENU_STATE
        self.menu_fade_alpha = 255
        self.menu_rotation = 0
        self.is_fullscreen = is_fullscreen_init # NEW: Set fullscreen from parameter
        
        # Set display mode based on the is_fullscreen_init parameter
        if self.is_fullscreen:
            info = pygame.display.Info()
            self.screen = pygame.display.set_mode((info.current_w, info.current_h), pygame.DOUBLEBUF | pygame.OPENGL | pygame.FULLSCREEN)
        else:
            self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.DOUBLEBUF | pygame.OPENGL)
        
        # Update viewport and projection for the current resolution
        current_size = pygame.display.get_surface().get_size()
        glViewport(0, 0, current_size[0], current_size[1])
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluPerspective(45, (current_size[0] / current_size[1]), 0.1, 500.0)
        glMatrixMode(GL_MODELVIEW)

        # NEW: Load title texture
        try:
            self.title_texture = self.load_texture(resource_path('Fire stops Fire ico.png')) # Storing (texid, width, height)
            print("Title texture loaded successfully.")
        except Exception as e:
            print(f"Warning: Could not load title texture. {e}")
            self.title_texture = None, 0, 0 # Store default dimensions if load fails

        self.init_gl()
        ### NEW ###
        # Load tree assets before generating terrain that uses them
        self.load_tree_textures()
        # NEW: Load field grass texture
        self.load_fieldgrass_texture()
        # NEW: Load house textures
        self.load_house_textures()
        
        # NEW: Initialize menu buttons
        self.init_menu_buttons()
        
        # NEW: Initialize pause buttons
        self.init_pause_buttons()

        self.generate_terrain()

        # NEW: Sound initialization and loading
        pygame.mixer.init()
        try:
            self.fire_sound = pygame.mixer.Sound(resource_path('firesound.mp3'))
            self.fire_sound.play(-1) # Play indefinitely
            self.fire_sound.set_volume(0.0) # Start silently
            print("Fire sound loaded successfully.")
        except pygame.error as e:
            print(f"Warning: Could not load fire sound: {e}")
            self.fire_sound = None
        
        try:
            self.ignite_sound = pygame.mixer.Sound(resource_path('ignite.mp3'))
            print("Ignite sound loaded successfully.")
        except pygame.error as e:
            print(f"Warning: Could not load ignite sound: {e}")
            self.ignite_sound = None

    def init_gl(self):
        glViewport(0, 0, WINDOW_WIDTH, WINDOW_HEIGHT)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluPerspective(45, (WINDOW_WIDTH / WINDOW_HEIGHT), 0.1, 500.0)
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()
        glEnable(GL_DEPTH_TEST)
        sky_color = [c / 255.0 for c in CYAN_SKY]
        glClearColor(sky_color[0], sky_color[1], sky_color[2], 1.0)
        glEnable(GL_LIGHTING)
        glEnable(GL_LIGHT0)
        glLightfv(GL_LIGHT0, GL_POSITION, (0, 100, 0, 1))
        glLightfv(GL_LIGHT0, GL_AMBIENT, (0.3, 0.3, 0.3, 1))
        glLightfv(GL_LIGHT0, GL_DIFFUSE, (0.7, 0.7, 0.7, 1))
        glEnable(GL_COLOR_MATERIAL)

        # NEW: FBO setup for PSX effect
        # Create FBO
        self.fbo = glGenFramebuffers(1)
        glBindFramebuffer(GL_FRAMEBUFFER, self.fbo)

        # Create texture for FBO color attachment
        self.fbo_texture = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, self.fbo_texture)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, self.fbo_width, self.fbo_height, 0, GL_RGB, GL_UNSIGNED_BYTE, None)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST) # For pixelation
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST) # For pixelation
        glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, self.fbo_texture, 0)

        # Create render buffer for FBO depth attachment
        self.fbo_depth_rb = glGenRenderbuffers(1)
        glBindRenderbuffer(GL_RENDERBUFFER, self.fbo_depth_rb)
        glRenderbufferStorage(GL_RENDERBUFFER, GL_DEPTH_COMPONENT, self.fbo_width, self.fbo_height)
        glFramebufferRenderbuffer(GL_FRAMEBUFFER, GL_DEPTH_ATTACHMENT, GL_RENDERBUFFER, self.fbo_depth_rb)

        # Check FBO status
        if glCheckFramebufferStatus(GL_FRAMEBUFFER) != GL_FRAMEBUFFER_COMPLETE:
            print("ERROR: FBO not complete!")
            self.running = False
        
        glBindFramebuffer(GL_FRAMEBUFFER, 0) # Unbind FBO, render to default framebuffer

    ### NEW ###
    # Helper function to load a single image file into an OpenGL texture
    def load_texture(self, path):
        # NOTE: Make sure the 'Assets' folder is in the same directory as the script
        try:
            textureSurface = pygame.image.load(path).convert_alpha()
        except pygame.error as e:
            print(f"ERROR: Unable to load texture at '{path}'. {e}")
            raise
        textureData = pygame.image.tostring(textureSurface, "RGBA", True)
        width = textureSurface.get_width()
        height = textureSurface.get_height()

        texid = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, texid)
        
        # --- FIX FOR BLURRY TEXTURES ---
        # Use GL_NEAREST to get a sharp, pixelated look instead of a blurry one.
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
        
        # Upload the texture data.
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, width, height, 0, GL_RGBA, GL_UNSIGNED_BYTE, textureData)
        return texid, width, height # NEW: Return width and height as well

    ### NEW ###
    # Load all the tree animation frames into a list of textures
    def load_tree_textures(self):
        # The order of paths is crucial for the animation logic
        image_paths = [
            resource_path('Assets/light tree/tree_normal.png'),
            resource_path('Assets/light tree/tree_burning_01.png'),
            resource_path('Assets/light tree/tree_burning_02.png'),
            resource_path('Assets/light tree/tree_burning_03.png'),
            resource_path('Assets/light tree/tree_burnt.png')
        ]
        print("Loading tree textures...")
        for path in image_paths:
            try:
                texture_id, _, _ = self.load_texture(path) # NEW: Unpack the tuple, only keep texture_id
                self.tree_textures.append(texture_id)
            except Exception as e:
                print(f"FATAL: Could not load texture ' {path}'. Make sure it exists.")
                print(f"Error: {e}")
                self.running = False # Critical asset is missing
                return
        if self.running:
            print(f"Successfully loaded {len(self.tree_textures)} tree textures.")

    ### NEW ###
    # Load the field grass texture
    def load_fieldgrass_texture(self):
        print("Loading field grass texture...")
        try:
            self.fieldgrass_texture, _, _ = self.load_texture(resource_path('Assets/fieldgrass/fieldgrass.png')) # NEW: Unpack the tuple
            print("Field grass texture loaded successfully.")
        except Exception as e:
            print(f"FATAL: Could not load field grass texture 'Assets/fieldgrass/fieldgrass.png'. Make sure it exists.")
            print(f"Error: {e}")
            self.running = False # Critical asset is missing

    ### NEW ###
    # Load house textures (normal and burnt)
    def load_house_textures(self):
        print("Loading house textures...")
        try:
            self.house_textures[HouseSprite.NORMAL], _, _ = self.load_texture(resource_path('Assets/house/house.png')) # NEW: Unpack the tuple
            self.house_textures[HouseSprite.BURNT], _, _ = self.load_texture(resource_path('Assets/house/house_burnt.png')) # NEW: Unpack the tuple
            print("House textures loaded successfully.")
        except Exception as e:
            print(f"FATAL: Could not load house textures. Make sure Assets/house/house.png and Assets/house/house_burnt.png exist.")
            print(f"Error: {e}")
            self.running = False # Critical assets are missing

    ### NEW ###
    # Initialize menu buttons
    def init_menu_buttons(self):
        button_width, button_height = 200, 60
        center_x = WINDOW_WIDTH // 2 - button_width // 2
        
        self.start_button = MenuButton(center_x, 400, button_width, button_height, "START GAME", self.font)
        self.fullscreen_button = MenuButton(center_x, 480, button_width, button_height, "FULLSCREEN", self.font)
        self.quit_button = MenuButton(center_x, 560, button_width, button_height, "QUIT", self.font)

        # NEW: Difficulty selection buttons
        diff_button_width, diff_button_height = 100, 40
        diff_y = 650 # Position below existing buttons
        diff_spacing = 10
        # Calculate total width of difficulty buttons + spacing
        total_diff_width = (diff_button_width * 3) + (diff_spacing * 2)
        # Center the group of difficulty buttons
        diff_start_x = WINDOW_WIDTH // 2 - total_diff_width // 2

        self.easy_button = MenuButton(diff_start_x, diff_y, diff_button_width, diff_button_height, "EASY", self.small_font)
        self.normal_button = MenuButton(diff_start_x + diff_button_width + diff_spacing, diff_y, diff_button_width, diff_button_height, "NORMAL", self.small_font)
        self.hard_button = MenuButton(diff_start_x + (diff_button_width + diff_spacing) * 2, diff_y, diff_button_width, diff_button_height, "HARD", self.small_font)

        # NEW: PSX Effect checkbox (Main Menu)
        # Positioned in top-right corner, now with a wider clickable area to include text.
        checkbox_box_size = 40 # Size of the visible checkbox square
        psx_text_surface_temp = self.small_font.render("PSX Effect", True, WHITE) # Render once to get width
        psx_text_width = psx_text_surface_temp.get_width() # Get width of the text
        
        # Total width for the button's rect to cover both checkbox and text, plus padding
        # This rect will be used for hover/click detection.
        total_psx_button_width = checkbox_box_size + 10 + psx_text_width # 10px padding between box and text
        
        self.psx_effect_button_menu = MenuButton(WINDOW_WIDTH - total_psx_button_width - 20, # x position (20px padding from right)
                                                20, # y position (20px padding from top)
                                                total_psx_button_width, # width of clickable area
                                                checkbox_box_size, # height of clickable area (same as checkbox size)
                                                "PSX Effect", # text (still passed for internal use if needed)
                                                self.small_font, 
                                                is_checkbox=True)

    # NEW: Toggle fullscreen function
    def toggle_fullscreen(self):
        self.is_fullscreen = not self.is_fullscreen
        if self.is_fullscreen:
            info = pygame.display.Info() # Get current display info
            self.screen = pygame.display.set_mode((info.current_w, info.current_h), pygame.DOUBLEBUF | pygame.OPENGL | pygame.FULLSCREEN)
        else:
            self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.DOUBLEBUF | pygame.OPENGL)
        
        # Update viewport and projection for the new resolution
        current_size = pygame.display.get_surface().get_size()
        glViewport(0, 0, current_size[0], current_size[1])
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluPerspective(45, (current_size[0] / current_size[1]), 0.1, 500.0)
        glMatrixMode(GL_MODELVIEW)

    # NEW: Start game from menu with fade transition
    def start_game_from_menu(self):
        self.game_state = GAME_STATE
        self.menu_fade_alpha = 255 # Immediately set to fully opaque for fade-out
        self.setup_game()  # Start fires on the current terrain
        if self.fire_sound: # NEW: Ensure fire sound plays when starting game
            self.fire_sound.play(-1)

    ### NEW ###
    # Populate the `self.trees` list based on the generated map
    def place_trees(self):
        self.trees = []
        for y in range(GRID_HEIGHT):
            for x in range(GRID_WIDTH):
                if self.grid[y][x] == FOREST_LIGHT:
                    # Not every light forest cell gets a tree, for a more natural look
                    if random.random() < 0.75:
                        self.trees.append(Tree(x, y))
        print(f"Placed {len(self.trees)} trees.")

    ### NEW ###
    # Populate the `self.fieldgrass_sprites` list
    def place_fieldgrass(self):
        self.fieldgrass_sprites = []
        for y in range(GRID_HEIGHT):
            for x in range(GRID_WIDTH):
                # Only spawn on every 2nd FIELD tile for performance
                if self.grid[y][x] == FIELD and (x + y) % 2 == 0: 
                    # Place multiple grass sprites per cell for density
                    for _ in range(random.randint(1, 2)): 
                        self.fieldgrass_sprites.append(FieldGrass(x, y))
        print(f"Placed {len(self.fieldgrass_sprites)} field grass sprites.")

    ### NEW ###
    # Draws all billboarded sprites (trees, field grass, houses) in correct depth order
    def draw_billboard_sprites(self):
        all_billboards = []
        all_billboards.extend(self.trees)
        all_billboards.extend(self.fieldgrass_sprites)
        all_billboards.extend(self.house_sprites)

        if not all_billboards:
            return

        glDisable(GL_LIGHTING)
        glEnable(GL_TEXTURE_2D)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glEnable(GL_ALPHA_TEST)
        glAlphaFunc(GL_GREATER, 0.1)
        
        # --- FIX: CORRECT TRANSPARENCY HANDLING ---
        # The line `glDisable(GL_DEPTH_TEST)` has been REMOVED.
        # We keep depth testing enabled, but disable writing to the depth buffer.
        # This prevents transparent objects from incorrectly blocking objects behind them.
        glDepthMask(GL_FALSE)
        
        # Get camera vectors for billboard calculation
        modelview = np.array(glGetDoublev(GL_MODELVIEW_MATRIX)).reshape((4,4))
        camera_forward = -np.array([modelview[0, 2], modelview[1, 2], modelview[2, 2]])

        # Sort all sprites by their depth along the camera's forward direction
        all_billboards.sort(key=lambda s: np.dot(s.pos, camera_forward), reverse=True)

        glColor4f(1.0, 1.0, 1.0, 1.0) # Ensure no tinting by default

        for sprite in all_billboards:
            texture_id = sprite.get_texture_id(self)
            width, height = sprite.get_dimensions()

            glBindTexture(GL_TEXTURE_2D, texture_id)
            
            glPushMatrix()
            glTranslatef(sprite.pos[0], sprite.pos[1], sprite.pos[2])
            
            # Billboard the sprite to always face the camera
            glRotatef(-self.camera_rot_y, 0, 1, 0)
            
            w = width / 2
            h = height
            
            # Apply specific tint for field grass
            if isinstance(sprite, FieldGrass):
                glColor4f(0.7, 0.7, 0.7, 1.0) # Darker tint for field grass
            else:
                glColor4f(1.0, 1.0, 1.0, 1.0) # No tint for other sprites

            glBegin(GL_QUADS)
            glTexCoord2f(0, 0); glVertex3f(-w, 0, 0)
            glTexCoord2f(1, 0); glVertex3f(w, 0, 0)
            glTexCoord2f(1, 1); glVertex3f(w, h, 0)
            glTexCoord2f(0, 1); glVertex3f(-w, h, 0)
            glEnd()
            
            glPopMatrix()

        # --- FIX: RESTORE OPENGL STATE ---
        # Re-enable writing to the depth buffer for the next rendering pass.
        glDepthMask(GL_TRUE)
        # Note: We no longer need glEnable(GL_DEPTH_TEST) here because we never disabled it.
        glDisable(GL_ALPHA_TEST)
        glDisable(GL_BLEND)
        glDisable(GL_TEXTURE_2D)
        glEnable(GL_LIGHTING)

    def init_pause_buttons(self):
        button_width, button_height = 250, 50
        # The x, y positions will be dynamically updated in the draw call
        # to support different screen sizes, so initial values are placeholders.
        self.resume_button = MenuButton(0, 250, button_width, button_height, "RESUME", self.font)
        self.restart_pause_button = MenuButton(0, 320, button_width, button_height, "RESTART", self.font)
        self.main_menu_button = MenuButton(0, 390, button_width, button_height, "MAIN MENU", self.font)

        # NEW: PSX Effect button (Pause Menu) - positioned on the right side, aligned with RESUME
        right_aligned_x = WINDOW_WIDTH - button_width - 50 # 50px padding from right edge
        psx_button_y = self.resume_button.rect.y # Align with RESUME button
        self.psx_effect_button_pause = MenuButton(right_aligned_x, psx_button_y, button_width, button_height, "PSX EFFECT", self.font)

        # NEW: Fullscreen button (Pause Menu)
        fullscreen_button_y = self.main_menu_button.rect.y + self.main_menu_button.rect.height + 20
        self.fullscreen_pause_button = MenuButton(0, fullscreen_button_y, button_width, button_height, "FULLSCREEN", self.font)

        # NEW: Volume Slider Properties
        self.volume_slider_rect = pygame.Rect(WINDOW_WIDTH // 2 - 150, fullscreen_button_y + button_height + 40, 300, 20) # Centered below fullscreen
        self.volume_slider_thumb_radius = 10
        self.is_dragging_volume_slider = False

    def generate_terrain(self):
        seed = random.randint(0, 1000)
        jitter = [[(random.random()*0.05, random.random()*0.05)
                   for _ in range(GRID_WIDTH)] for _ in range(GRID_HEIGHT)]

        for y in range(GRID_HEIGHT):
            for x in range(GRID_WIDTH):
                nx, ny = x/GRID_WIDTH, y/GRID_HEIGHT
                jx, jy = jitter[y][x]
                nx += jx; ny += jy
                low = noise.pnoise2(nx*3.0, ny*3.0, octaves=4, persistence=0.5, lacunarity=2.0, base=seed)
                high = noise.pnoise2(nx*10.0, ny*10.0, octaves=1, persistence=0.4, lacunarity=2.5, base=seed+1)
                combined = low * 0.85 + high * 0.15
                elevation = noise.pnoise2(nx*1.0+50, ny*1.0+50, octaves=2, persistence=0.5, lacunarity=2.0, base=seed+2)
                value = combined + 0.3*elevation
                value = math.tanh(value * 1.2)

                if value < -0.4: self.grid[y][x] = WATER
                elif value < -0.15: self.grid[y][x] = FIELD
                elif value < 0.05: self.grid[y][x] = GRASSLAND
                elif value < 0.25: self.grid[y][x] = FOREST_LIGHT
                else: self.grid[y][x] = FOREST_DENSE

        # NEW: Reordered to generate water features BEFORE houses.
        self.add_rivers()
        self.add_lakes()
        self.add_houses()
        self.add_clearings()
        
        ### NEW ###
        # After all terrain is generated, place the tree objects on top.
        self.place_trees()
        # NEW: Place field grass objects after terrain generation
        self.place_fieldgrass()

        # NEW: Initialize and store base colors for terrain types (excluding FIRE, BURNT, WATER)
        base_colors_dict = { FOREST_DENSE: DARK_GREEN, FOREST_LIGHT: LIGHT_GREEN, GRASSLAND: GRASS_GREEN, FIELD: FIELD_YELLOW, HOUSE: HOUSE_RED }
        for y in range(GRID_HEIGHT):
            for x in range(GRID_WIDTH):
                terrain_type = self.grid[y][x]
                if terrain_type in [FOREST_DENSE, FOREST_LIGHT, GRASSLAND, FIELD, HOUSE]:
                    base_color = base_colors_dict.get(terrain_type, BLACK)
                    # Apply variation once at generation
                    variation = random.randint(-5, 5)
                    self.terrain_base_colors[(x,y)] = tuple(max(0, min(255, c + variation)) for c in base_color)

    # [UNCHANGED METHODS: add_rivers, add_houses, add_clearings, add_lakes, setup_game, get_neighbors, etc.]
    # ... All the methods from the previous version are here ...
    def add_rivers(self):
        num_rivers = random.randint(1, 3)
        for _ in range(num_rivers):
            if random.choice([True, False]):
                start_x, start_y, direction = 0, random.randint(GRID_HEIGHT // 4, 3 * GRID_HEIGHT // 4), 1
            else:
                start_x, start_y, direction = random.randint(GRID_WIDTH // 4, 3 * GRID_WIDTH // 4), 0, 1
            x, y, river_length = start_x, start_y, random.randint(30, 80)
            for i in range(river_length):
                if 0 <= x < GRID_WIDTH and 0 <= y < GRID_HEIGHT:
                    self.grid[y][x] = WATER
                    for dx_r in range(-1, 2):
                        for dy_r in range(-1, 2):
                            if (dx_r == 0 and dy_r == 0): continue
                            prob = 0.6 / (abs(dx_r) + abs(dy_r) + 0.5)
                            if random.random() < prob:
                                nx_r, ny_r = x + dx_r, y + dy_r
                                if 0 <= nx_r < GRID_WIDTH and 0 <= ny_r < GRID_HEIGHT:
                                    self.grid[ny_r][nx_r] = WATER
                if random.random() < 0.3: direction = random.choice([-1, 0, 1])
                if start_x == 0: x += 1; y += direction
                else: y += 1; x += direction
                x, y = max(0, min(GRID_WIDTH - 1, x)), max(0, min(GRID_HEIGHT - 1, y))

    def add_houses(self):
        self.houses_total = 0
        # NEW: Clear existing house sprites before adding new ones (for restarts)
        self.house_sprites = []
        for _ in range(random.randint(3, 7)):
            for _ in range(50):
                cx, cy = random.randint(5, GRID_WIDTH - 5), random.randint(5, GRID_HEIGHT - 5)
                # FIX: Check ensures we don't try to build a house cluster in water
                if self.grid[cy][cx] in [GRASSLAND, FIELD]:
                    for _ in range(random.randint(2, 6)):
                        hx, hy = cx + random.randint(-3, 3), cy + random.randint(-3, 3)
                        # FIX: Check ensures individual houses aren't placed in water either
                        if (0 <= hx < GRID_WIDTH and 0 <= hy < GRID_HEIGHT and
                                self.grid[hy][hx] not in [WATER, HOUSE]):
                            self.grid[hy][hx] = HOUSE
                            # NEW: Create a HouseSprite instance for each house
                            self.house_sprites.append(HouseSprite(hx, hy))
                            self.houses_total += 1
                    break

    def add_clearings(self):
        for _ in range(random.randint(5, 10)):
            cx, cy = random.randint(3, GRID_WIDTH - 3), random.randint(3, GRID_HEIGHT - 3)
            if self.grid[cy][cx] == FOREST_DENSE:
                clearing_size = random.randint(2, 5)
                for dx in range(-clearing_size//2, clearing_size//2 + 1):
                    for dy in range(-clearing_size//2, clearing_size//2 + 1):
                        if (0 <= cx + dx < GRID_WIDTH and 0 <= cy + dy < GRID_HEIGHT and random.random() < 0.6):
                            self.grid[cy + dy][cx + dx] = GRASSLAND

    def add_lakes(self):
        num_lakes = random.randint(1, 3)
        for _ in range(num_lakes):
            for _ in range(50):
                center_x, center_y = random.randint(5, GRID_WIDTH - 5), random.randint(5, GRID_HEIGHT - 5)
                if self.grid[center_y][center_x] != WATER:
                    lake_radius = random.randint(4, 8)
                    for y_offset in range(-lake_radius, lake_radius + 1):
                        for x_offset in range(-lake_radius, lake_radius + 1):
                            dist = math.sqrt(x_offset**2 + y_offset**2)
                            if dist <= lake_radius + random.uniform(-1, 1):
                                lx, ly = center_x + x_offset, center_y + y_offset
                                if 0 <= lx < GRID_WIDTH and 0 <= ly < GRID_HEIGHT:
                                    if self.grid[ly][lx] != HOUSE:
                                        self.grid[ly][lx] = WATER
                    break

    def setup_game(self):
        self.total_burnable = sum(1 for y in range(GRID_HEIGHT) for x in range(GRID_WIDTH) if self.grid[y][x] != WATER)
        
        # NEW: Set fire spread delay based on difficulty
        if self.difficulty == "Easy":
            self.fire_spread_delay = DIFFICULTY_EASY_SPREAD
        elif self.difficulty == "Hard":
            self.fire_spread_delay = DIFFICULTY_HARD_SPREAD
        else: # Normal or any other value
            self.fire_spread_delay = DIFFICULTY_NORMAL_SPREAD

        for _ in range(2):
            found_start = False
            for attempt in range(100):
                side = random.randint(0,3)
                if side == 0: sx, sy = random.randint(0, GRID_WIDTH - 1), 0
                elif side == 1: sx, sy = GRID_WIDTH - 1, random.randint(0, GRID_HEIGHT - 1)
                elif side == 2: sx, sy = random.randint(0, GRID_WIDTH - 1), GRID_HEIGHT - 1
                else: sx, sy = 0, random.randint(0, GRID_HEIGHT - 1)
                
                if FLAMMABILITY.get(self.grid[sy][sx], 0) > 0 and self.grid[sy][sx] != FIRE:
                    self.grid[sy][sx] = FIRE
                    for _ in range(random.randint(1, 3)):
                        fx, fy = max(0, min(GRID_WIDTH-1, sx+random.randint(-1,1))), max(0, min(GRID_HEIGHT-1, sy+random.randint(-1,1)))
                        if self.grid[fy][fx] not in [WATER, FIRE, BURNT] and FLAMMABILITY.get(self.grid[fy][fx], 0) > 0:
                            self.grid[fy][fx] = FIRE
                    found_start = True
                    break
            if not found_start:
                print("Warning: Could not find a suitable second fire start location.")

    def get_neighbors(self, x, y):
        neighbors = []
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                if dx == 0 and dy == 0: continue
                nx, ny = x + dx, y + dy
                if 0 <= nx < GRID_WIDTH and 0 <= ny < GRID_HEIGHT:
                    neighbors.append((nx, ny))
        return neighbors
    def spread_fire(self):
        new_fires = []
        for y in range(GRID_HEIGHT):
            for x in range(GRID_WIDTH):
                if self.grid[y][x] == FIRE:
                    for nx, ny in self.get_neighbors(x, y):
                        terrain = self.grid[ny][nx]
                        if terrain not in [FIRE, BURNT, CONTROLLED_BURN, WATER]:
                            if random.random() < FLAMMABILITY[terrain] * 0.39: # Increased from 0.325 to further increase spread by ~20%
                                new_fires.append((nx, ny))
        for x, y in new_fires:
            self.grid[y][x] = FIRE
            self.burnt_timers[y][x] = 0 # NEW: Reset timer for new fires
        return len(new_fires) > 0
    def start_controlled_burn(self, x, y):
        if not (0 <= x < GRID_WIDTH and 0 <= y < GRID_HEIGHT): return
        terrain = self.grid[y][x]
        if terrain not in [FIRE, BURNT, CONTROLLED_BURN, WATER, HOUSE]:
            self.grid[y][x] = CONTROLLED_BURN
            self.controlled_burns_used += 1
            burn_queue, burn_size = [(x, y)], random.randint(10, 20)
            while burn_queue and burn_size > 0:
                cx, cy = burn_queue.pop(0)
                for nx, ny in self.get_neighbors(cx, cy):
                    n_terrain = self.grid[ny][nx]
                    if (n_terrain not in [FIRE, BURNT, CONTROLLED_BURN, WATER, HOUSE] and random.random() < FLAMMABILITY[n_terrain] * 0.4 and burn_size > 0):
                        self.grid[ny][nx] = CONTROLLED_BURN
                        burn_queue.append((nx, ny))
                        burn_size -= 1
    def update_controlled_burns(self, dt):
        for y in range(GRID_HEIGHT):
            for x in range(GRID_WIDTH):
                if self.grid[y][x] == CONTROLLED_BURN and random.random() < (0.2 * dt * 60): # Scale by dt * 60
                    self.grid[y][x] = BURNT
    def age_fire(self, dt):
        for y in range(GRID_HEIGHT):
            for x in range(GRID_WIDTH):
                if self.grid[y][x] == FIRE:
                    self.burnt_timers[y][x] += (self.dt * 60) # Scale by dt * 60
                    if self.burnt_timers[y][x] >= MAX_ASH_TIMER:
                        self.grid[y][x] = BURNT
                        self.burnt_timers[y][x] = 0
                        self.ash_colors[y][x] = random.randint(50, 70)
    def check_victory_condition(self):
        has_fire, can_spread = False, False
        for y in range(GRID_HEIGHT):
            for x in range(GRID_WIDTH):
                if self.grid[y][x] == FIRE:
                    has_fire = True
                    for nx, ny in self.get_neighbors(x, y):
                        if self.grid[ny][nx] not in [FIRE, BURNT, CONTROLLED_BURN, WATER] and FLAMMABILITY[self.grid[ny][nx]] > 0:
                            can_spread = True
                            break
                if can_spread: break
        if not has_fire: self.victory = True; return True
        return False
    def calculate_stats(self):
        houses_rem = sum(1 for y in range(GRID_HEIGHT) for x in range(GRID_WIDTH) if self.grid[y][x] == HOUSE)
        burnable_rem = sum(1 for y in range(GRID_HEIGHT) for x in range(GRID_WIDTH) if self.grid[y][x] not in [WATER, FIRE, BURNT, CONTROLLED_BURN])
        self.houses_saved = houses_rem
        if self.total_burnable > 0:
            self.forest_saved = (burnable_rem / self.total_burnable) * 100
        self.score = int(self.houses_saved * 100 + self.forest_saved * 10)

    # MODIFIED: Update handle_events method
    def handle_events(self):
        mouse_pos = pygame.mouse.get_pos()
        
        # Update button hover states based on current state
        if self.game_state == MENU_STATE:
            self.start_button.update(mouse_pos)
            self.fullscreen_button.update(mouse_pos)
            self.quit_button.update(mouse_pos)
            self.easy_button.update(mouse_pos)
            self.normal_button.update(mouse_pos)
            self.hard_button.update(mouse_pos)
            self.psx_effect_button_menu.update(mouse_pos) # NEW: Update PSX effect button hover state
        elif self.game_state == PAUSED_STATE:
            self.resume_button.update(mouse_pos)
            self.restart_pause_button.update(mouse_pos)
            self.main_menu_button.update(mouse_pos)
            self.psx_effect_button_pause.update(mouse_pos) # NEW: Update PSX effect button hover state
            self.fullscreen_pause_button.update(mouse_pos) # NEW: Update Fullscreen button hover state
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_F11:
                    self.toggle_fullscreen()
                # Allow restarting from the game over screen
                elif event.key == pygame.K_r and self.game_over and self.game_state == GAME_STATE:
                    self.restart_game()
                # --- NEW ESC BEHAVIOR ---
                elif event.key == pygame.K_ESCAPE:
                    if self.game_state == GAME_STATE:
                        self.game_state = PAUSED_STATE # Pause the game
                        if self.fire_sound: # NEW: Stop all sounds when pausing
                            pygame.mixer.pause()
                    elif self.game_state == PAUSED_STATE:
                        self.game_state = GAME_STATE # Resume the game
                        if self.fire_sound: # NEW: Resume all sounds when unpausing
                            pygame.mixer.unpause()

            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:  # Left click
                    if self.game_state == MENU_STATE:
                        if self.start_button.hovered: self.start_game_from_menu()
                        elif self.fullscreen_button.hovered: self.toggle_fullscreen()
                        elif self.quit_button.hovered: self.running = False
                        elif self.easy_button.hovered: self.difficulty = "Easy"
                        elif self.normal_button.hovered: self.difficulty = "Normal"
                        elif self.hard_button.hovered: self.difficulty = "Hard"
                        elif self.psx_effect_button_menu.hovered: # NEW: Handle PSX effect button click
                            self.psx_effect_enabled = not self.psx_effect_enabled
                            print(f"PSX Effect: {self.psx_effect_enabled}") # For debugging
                    
                    # --- NEW PAUSE MENU CLICK HANDLING ---
                    elif self.game_state == PAUSED_STATE:
                        if self.resume_button.hovered: 
                            self.game_state = GAME_STATE
                            if self.fire_sound: # NEW: Resume all sounds when clicking resume
                                pygame.mixer.unpause()
                        elif self.restart_pause_button.hovered: self.restart_game()
                        elif self.main_menu_button.hovered: self.reset_for_menu() # Go to main menu, using soft reset
                        elif self.psx_effect_button_pause.hovered: # NEW: Handle PSX effect button click
                            self.psx_effect_enabled = not self.psx_effect_enabled
                            print(f"PSX Effect: {self.psx_effect_enabled}") # For debugging
                        elif self.fullscreen_pause_button.hovered: # NEW: Handle Fullscreen button click
                            self.toggle_fullscreen()
                        # NEW: Handle volume slider click
                        elif self.volume_slider_rect.collidepoint(event.pos):
                            self.is_dragging_volume_slider = True
                            self._update_volume_from_slider(event.pos[0])
                    
                    # Original game click logic
                    elif self.game_state == GAME_STATE:
                        self.mouse_down = True
                        self.last_mouse_pos = event.pos
                        self.click_start_pos = event.pos
                
                elif event.button == 4 and self.game_state == GAME_STATE: self.camera_zoom += 10
                elif event.button == 5 and self.game_state == GAME_STATE: self.camera_zoom -= 10

            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1:  # Left click
                    if self.game_state == GAME_STATE:
                        move_distance = math.sqrt((event.pos[0] - self.click_start_pos[0])**2 + 
                                            (event.pos[1] - self.click_start_pos[1])**2)
                        if move_distance < self.CLICK_THRESHOLD and not self.game_over:
                            self.handle_3d_click(event.pos)
                        # self.mouse_down = False # This line needs to be moved out of this specific if-block
                    # NEW: Stop dragging volume slider
                    elif self.game_state == PAUSED_STATE:
                        self.is_dragging_volume_slider = False
                    # This applies to any left mouse button release event, whether in game or paused menu
                    self.mouse_down = False

            elif event.type == pygame.MOUSEMOTION:
                if self.mouse_down and self.game_state == GAME_STATE:
                    dx = event.pos[0] - self.last_mouse_pos[0]
                    dy = event.pos[1] - self.last_mouse_pos[1]
                    self.camera_rot_y += dx * 0.2
                    self.camera_rot_x += dy * 0.2
                    self.last_mouse_pos = event.pos
                # NEW: Handle volume slider drag
                elif self.game_state == PAUSED_STATE and self.is_dragging_volume_slider:
                    self._update_volume_from_slider(event.pos[0])

    def handle_3d_click(self, mouse_pos):
        mv = np.array(glGetDoublev(GL_MODELVIEW_MATRIX)).reshape((4,4)).T
        pr = np.array(glGetDoublev(GL_PROJECTION_MATRIX)).reshape((4,4)).T
        inv_mat = np.linalg.inv(pr @ mv)
        mx, my = mouse_pos
        ndc_x = (2.0 * mx) / WINDOW_WIDTH - 1.0
        ndc_y = 1.0 - (2.0 * my) / WINDOW_HEIGHT
        ndc_near = np.array([ndc_x, ndc_y, -1.0, 1.0])
        ndc_far = np.array([ndc_x, ndc_y, 1.0, 1.0])
        world_near = inv_mat @ ndc_near
        world_near /= world_near[3]
        world_far = inv_mat @ ndc_far
        world_far /= world_far[3]
        dir_vec = world_far[:3] - world_near[:3]
        if abs(dir_vec[1]) < 1e-6: return
        t = -world_near[1] / dir_vec[1]
        if t < 0: return
        intersect = world_near[:3] + t * dir_vec
        gx = int(intersect[0] + GRID_WIDTH / 2)
        gy = int(intersect[2] + GRID_HEIGHT / 2)

        # NEW: Only proceed if the calculated grid coordinates are within the actual grid boundaries
        if 0 <= gx < GRID_WIDTH and 0 <= gy < GRID_HEIGHT:
            self.start_controlled_burn(gx, gy)
            # NEW: Play ignite sound when controlled burn is initiated, only if click was on terrain
            if self.ignite_sound:
                self.ignite_sound.set_volume(self.master_volume) # Use master volume for effect
                self.ignite_sound.play()

    def get_terrain_color(self, terrain_type, x, y):
        # Use pre-calculated base color for terrain, or the default if not found
        base_color = self.terrain_base_colors.get((x,y), BLACK)

        if terrain_type == FIRE:
            ash_color_base = 50
            ash_color = (ash_color_base, ash_color_base, ash_color_base)
            fade_factor = min(1.0, self.burnt_timers[y][x] / MAX_ASH_TIMER)
            r = int(RED[0] * (1.0 - fade_factor) + ash_color[0] * fade_factor)
            g = int(RED[1] * (1.0 - fade_factor) + ash_color[1] * fade_factor)
            b = int(RED[2] * (1.0 - fade_factor) + ash_color[2] * fade_factor)
            return (r, g, b)
        elif terrain_type == BURNT:
            if self.ash_colors[y][x] is None:
                self.ash_colors[y][x] = random.randint(50, 70)
            ash_value = self.ash_colors[y][x]
            return (ash_value, ash_value, ash_value)
        elif terrain_type == WATER: # Water always has a fixed color
            return BLUE
        elif terrain_type == HOUSE: # House always has a fixed color
            return HOUSE_RED
        elif terrain_type == CONTROLLED_BURN: # Controlled burn always has a fixed color
            return ORANGE
        
        return base_color # For other terrain types (Forest, Grassland, Field), return the pre-calculated color

    # NEW: Method to update and spawn particles
    def update_particles(self, dt):
        # Update existing particles
        self.particles = [p for p in self.particles if p.lifetime > 0]
        for p in self.particles:
            p.update(dt)

        # Spawn new particles only from fire edge cells and at a reduced rate
        if not self.game_over:
            for y in range(GRID_HEIGHT):
                for x in range(GRID_WIDTH):
                    if self.grid[y][x] == FIRE: # Check if it's a fire cell
                        is_edge_cell = False
                        for nx, ny in self.get_neighbors(x, y):
                            # An edge cell is a fire cell next to a non-fire, non-burnt, non-water cell
                            if self.grid[ny][nx] not in [FIRE, BURNT, WATER]:
                                is_edge_cell = True
                                break
                        
                        if is_edge_cell and random.random() < (0.03 * dt * 60): # Reduced spawn chance scaled by dt
                            cx, cz = x - GRID_WIDTH / 2, y - GRID_HEIGHT / 2
                            self.particles.append(Particle(cx, cz))
    
    ### NEW ###
    # Update tree animations based on grid state
    def update_trees(self, dt):
        # Constants for animation speed and frame counts
        ANIMATION_SPEED = 20  # Ticks per animation frame change
        BURNING_FRAMES_START = 1 # Index of first burning texture
        BURNING_FRAMES_END = 3   # Index of last burning texture
        BURNT_FRAME = 4          # Index of the final burnt texture

        for tree in self.trees:
            # Check the state of the ground beneath the tree
            grid_state = self.grid[tree.grid_y][tree.grid_x]

            # If tree is normal and ground catches fire, start burning
            if tree.state == Tree.NORMAL and grid_state == FIRE:
                tree.state = Tree.BURNING
                tree.animation_timer = 0
                tree.current_frame_index = BURNING_FRAMES_START

            # If tree is burning, advance animation
            elif tree.state == Tree.BURNING:
                tree.animation_timer += (dt * 60) # Scale by dt
                if tree.animation_timer >= ANIMATION_SPEED:
                    tree.animation_timer = 0
                    # Advance frame, but don't go past the last burning frame
                    if tree.current_frame_index < BURNING_FRAMES_END:
                        tree.current_frame_index += 1
                
                # If ground becomes burnt, tree becomes fully burnt too
                if grid_state == BURNT:
                    tree.state = Tree.BURNT
                    tree.current_frame_index = BURNT_FRAME

            # If ground is burnt and tree wasn't already marked as such
            elif tree.state != Tree.BURNT and grid_state == BURNT:
                tree.state = Tree.BURNT
                tree.current_frame_index = BURNT_FRAME

    ### NEW ###
    # Update field grass sprites based on grid state
    def update_fieldgrass(self):
        updated_grass_sprites = []
        for fg in self.fieldgrass_sprites:
            grid_state = self.grid[fg.grid_y][fg.grid_x]

            # If ground is on fire or burnt, grass despawns (removed from list)
            if grid_state == FIRE or grid_state == BURNT:
                pass 
            else: # Not fire or burnt, keep it as is
                updated_grass_sprites.append(fg)
        self.fieldgrass_sprites = updated_grass_sprites

    ### NEW ###
    # Update house sprites based on grid state
    def update_houses(self):
        for house_sprite in self.house_sprites:
            grid_state = self.grid[house_sprite.grid_y][house_sprite.grid_x]
            if grid_state == BURNT or grid_state == FIRE:
                house_sprite.state = HouseSprite.BURNT
            # Removed the else clause, so burnt houses stay burnt

    # NEW: Draw menu
    def draw_menu(self):
        # --- NEW: Apply PSX effect to menu background if enabled ---
        if self.psx_effect_enabled:
            glBindFramebuffer(GL_FRAMEBUFFER, self.fbo)
            glViewport(0, 0, self.fbo_width, self.fbo_height)
        
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        
        # Draw rotating terrain
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()
        glTranslatef(0.0, 0.0, -80.0) # Moved menu camera closer to spinning terrain
        glRotatef(30, 1, 0, 0)  # Fixed X rotation
        glRotatef(self.menu_rotation, 0, 1, 0)  # Rotating Y
        
        # Draw terrain (same as game)
        glDisable(GL_LIGHTING)
        glBegin(GL_QUADS)
        for y in range(GRID_HEIGHT):
            for x in range(GRID_WIDTH):
                terrain = self.grid[y][x]
                color = self.get_terrain_color(terrain, x, y)
                glColor3f(color[0] / 255.0, color[1] / 255.0, color[2] / 255.0)
                cx, cz = x - GRID_WIDTH / 2, y - GRID_HEIGHT / 2
                glVertex3f(cx, 0, cz)
                glVertex3f(cx + 1, 0, cz)
                glVertex3f(cx + 1, 0, cz + 1)
                glVertex3f(cx, 0, cz + 1)
        glEnd()

        # Draw billboarded sprites
        self.draw_billboard_sprites()
        
        # --- NEW: Render FBO texture to screen if PSX effect is enabled ---
        if self.psx_effect_enabled:
            glBindFramebuffer(GL_FRAMEBUFFER, 0) # Bind back to default framebuffer
            glViewport(0, 0, WINDOW_WIDTH, WINDOW_HEIGHT) # Restore original viewport

            # No need to clear here as the next draw will cover the entire screen.
            # glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT) 

            glMatrixMode(GL_PROJECTION)
            glPushMatrix()
            glLoadIdentity()
            gluOrtho2D(0, WINDOW_WIDTH, WINDOW_HEIGHT, 0) # Set up 2D orthographic projection
            glMatrixMode(GL_MODELVIEW)
            glPushMatrix()
            glLoadIdentity()

            glDisable(GL_LIGHTING) # No lighting for 2D quad
            glDisable(GL_DEPTH_TEST) # No depth testing for 2D quad
            glEnable(GL_TEXTURE_2D)
            glBindTexture(GL_TEXTURE_2D, self.fbo_texture)
            glColor4f(1.0, 1.0, 1.0, 1.0) # Ensure full white color to see texture as is

            glBegin(GL_QUADS)
            glTexCoord2f(0, 1); glVertex2f(0, 0) # Top-left of quad maps to bottom-left of texture
            glTexCoord2f(1, 1); glVertex2f(WINDOW_WIDTH, 0)
            glTexCoord2f(1, 0); glVertex2f(WINDOW_WIDTH, WINDOW_HEIGHT)
            glTexCoord2f(0, 0); glVertex2f(0, WINDOW_HEIGHT)
            glEnd()

            glDisable(GL_TEXTURE_2D)
            glEnable(GL_DEPTH_TEST)
            glEnable(GL_LIGHTING)

            glMatrixMode(GL_PROJECTION)
            glPopMatrix()
            glMatrixMode(GL_MODELVIEW)
            glPopMatrix()

        # Draw menu UI overlay (always on top)
        self.draw_menu_ui()

    # NEW: Draw menu UI overlay
    def draw_menu_ui(self):
        glMatrixMode(GL_PROJECTION)
        glPushMatrix()
        glLoadIdentity()
        current_size = pygame.display.get_surface().get_size()
        gluOrtho2D(0, current_size[0], current_size[1], 0)
        glMatrixMode(GL_MODELVIEW)
        glPushMatrix()
        glLoadIdentity()
        glDisable(GL_LIGHTING)
        glDisable(GL_DEPTH_TEST)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        
        # Draw title
        if self.title_texture and self.title_texture[0]: # Check if texture_id exists
            title_id, title_original_width, title_original_height = self.title_texture
            
            # NEW: Calculate dimensions based on aspect ratio
            title_display_height = 300 # Make it significantly bigger
            aspect_ratio = title_original_width / title_original_height
            title_display_width = int(title_display_height * aspect_ratio)

            title_x = current_size[0] // 2 - title_display_width // 2
            title_y = 20 # Moved up from 50 (and 100 before)
            
            glEnable(GL_TEXTURE_2D)
            glBindTexture(GL_TEXTURE_2D, title_id) # Use the texture ID
            glColor4f(1.0, 1.0, 1.0, self.menu_fade_alpha / 255.0)
            
            glBegin(GL_QUADS)
            # Fix for inverted title texture (assuming Y-inversion is the primary issue)
            glTexCoord2f(0, 1); glVertex2f(title_x, title_y)        # Top-left of quad maps to bottom-left of texture
            glTexCoord2f(1, 1); glVertex2f(title_x + title_display_width, title_y)    # Top-right of quad maps to bottom-right of texture
            glTexCoord2f(1, 0); glVertex2f(title_x + title_display_width, title_y + title_display_height) # Bottom-right of quad maps to top-right of texture
            glTexCoord2f(0, 0); glVertex2f(title_x, title_y + title_display_height) # Bottom-left of quad maps to top-left of texture
            glEnd()
            glDisable(GL_TEXTURE_2D)
        
        # Draw buttons with fade
        glColor4f(1.0, 1.0, 1.0, self.menu_fade_alpha / 255.0)
        
        # Draw all menu buttons (backgrounds and text)
        all_menu_buttons = [
            self.start_button,
            self.fullscreen_button,
            self.quit_button,
            self.easy_button,
            self.normal_button,
            self.hard_button,
            self.psx_effect_button_menu
        ]

        for button in all_menu_buttons:
            is_selected = False
            if button == self.psx_effect_button_menu:
                is_selected = self.psx_effect_enabled
            elif button == self.easy_button:
                is_selected = (self.difficulty == "Easy")
            elif button == self.normal_button:
                is_selected = (self.difficulty == "Normal")
            elif button == self.hard_button:
                is_selected = (self.difficulty == "Hard")
            
            button.draw_gl(button.rect.x, button.rect.y, is_selected=is_selected)
        
        # Restore OpenGL state
        glDisable(GL_BLEND)
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_LIGHTING)
        glMatrixMode(GL_PROJECTION)
        glPopMatrix()
        glMatrixMode(GL_MODELVIEW)
        glPopMatrix()

    # NEW: Draw fade overlay (placeholder as not explicitly provided)
    def draw_fade_overlay(self):
        current_size = pygame.display.get_surface().get_size()
        glMatrixMode(GL_PROJECTION)
        glPushMatrix()
        glLoadIdentity()
        gluOrtho2D(0, current_size[0], current_size[1], 0)
        glMatrixMode(GL_MODELVIEW)
        glPushMatrix()
        glLoadIdentity()
        glDisable(GL_LIGHTING)
        glDisable(GL_DEPTH_TEST)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        glColor4f(0.0, 0.0, 0.0, self.menu_fade_alpha / 255.0) # Black overlay fading out
        
        glBegin(GL_QUADS)
        glVertex2f(0, 0)
        glVertex2f(current_size[0], 0)
        glVertex2f(current_size[0], current_size[1])
        glVertex2f(0, current_size[1])
        glEnd()
        
        glDisable(GL_BLEND)
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_LIGHTING)
        glMatrixMode(GL_PROJECTION)
        glPopMatrix()
        glMatrixMode(GL_MODELVIEW)
        glPopMatrix()

    # MODIFIED: Update main update method
    def update(self, dt):
        # NEW: If the game is paused, do not update any game logic.
        if self.game_state == PAUSED_STATE:
            return # Effectively freezes the game

        if self.game_state == MENU_STATE:
            # Rotate terrain in menu
            self.menu_rotation += MENU_ROTATION_SPEED * dt * 60 # Scale by dt * 60 if MENU_ROTATION_SPEED was per-frame
            if self.menu_rotation >= 360:
                self.menu_rotation -= 360
            
            # Update sprites for visual effect
            self.update_trees(dt)
            self.update_fieldgrass()
            self.update_houses()
            
        elif self.game_state == GAME_STATE:
            # Handle menu fade transition (unfade from black)
            if self.menu_fade_alpha > 0:
                self.menu_fade_alpha -= MENU_FADE_SPEED * dt * 60 * 2 # Faster unfade, scaled by dt
                if self.menu_fade_alpha < 0:
                    self.menu_fade_alpha = 0
            
            # Existing game update logic
            if not self.game_over:
                self.fire_spread_timer += dt * 60 # Scale by dt * 60 to maintain original 'frame' based speed
                self.age_fire(dt)
                if self.fire_spread_timer >= self.fire_spread_delay:
                    self.fire_spread_timer = 0
                    still_spreading = self.spread_fire()
                    burnable_left = sum(1 for y in range(GRID_HEIGHT) for x in range(GRID_WIDTH) 
                                      if self.grid[y][x] not in [WATER, FIRE, BURNT, CONTROLLED_BURN])
                    if burnable_left < self.total_burnable * 0.15:
                        self.game_over = True
                        self.victory = False
                self.update_controlled_burns(dt)
                if self.check_victory_condition():
                    self.game_over = True
                self.calculate_stats()
            
            # Always update visual elements
            self.update_particles(dt)
            self.update_trees(dt)
            self.update_fieldgrass()
            self.update_houses()

            # NEW: Dynamic fire sound volume control
            if self.fire_sound:
                # Get camera position from modelview matrix
                modelview = glGetDoublev(GL_MODELVIEW_MATRIX)
                # The camera's position is the inverse of the translation part of the modelview matrix
                # This extracts the camera's X, Y, Z coordinates in world space
                camera_pos = np.array([-modelview[3][0], -modelview[3][1], -modelview[3][2]])
                
                closest_fire_distance = float('inf')
                active_fire_cells = 0 # Initialize active fire cells count outside the loop

                # Iterate through grid to find burning cells and closest fire
                for y in range(GRID_HEIGHT):
                    for x in range(GRID_WIDTH):
                        if self.grid[y][x] == FIRE: # Check if this cell is on fire
                            active_fire_cells += 1 # Count fire cells
                            # Calculate world coordinates of the center of the fire cell
                            fire_world_x = x - GRID_WIDTH / 2 + 0.5
                            fire_world_z = y - GRID_HEIGHT / 2 + 0.5
                            
                            # Calculate distance from camera to this fire cell
                            # We only care about X and Z for horizontal distance on the map
                            dist = math.sqrt((camera_pos[0] - fire_world_x)**2 + (camera_pos[2] - fire_world_z)**2)
                            closest_fire_distance = min(closest_fire_distance, dist)

                # Calculate distance-based volume factor
                distance_factor = 0.0
                if closest_fire_distance < MAX_HEAR_DISTANCE:
                    distance_factor = (1.0 - (closest_fire_distance / MAX_HEAR_DISTANCE))

                # Calculate fire presence factor for sound fade-out
                fire_presence_factor = min(1.0, active_fire_cells / FIRE_CELLS_FOR_MAX_SOUND)
                # If no fire cells, ensure sound is 0, even if the ratio is tiny but non-zero
                if active_fire_cells == 0:
                    fire_presence_factor = 0.0

                # Combine all factors for the final volume
                final_volume = distance_factor * fire_presence_factor * MAX_FIRE_VOLUME * self.master_volume
                self.fire_sound.set_volume(max(0.0, min(1.0, final_volume))) # Clamp between 0 and 1

    # MODIFIED: Update main draw method
    def draw(self):
        if self.game_state == MENU_STATE:
            self.draw_menu()
        else: # This now covers GAME_STATE and PAUSED_STATE
            # --- DRAW THE MAIN GAME SCENE --- Before drawing anything, check if PSX effect is enabled.
            if self.psx_effect_enabled:
                glBindFramebuffer(GL_FRAMEBUFFER, self.fbo)
                glViewport(0, 0, self.fbo_width, self.fbo_height)
                
            glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
            glMatrixMode(GL_MODELVIEW)
            glLoadIdentity()
            glTranslatef(0.0, 0.0, self.camera_zoom)
            glRotatef(self.camera_rot_x, 1, 0, 0)
            glRotatef(self.camera_rot_y, 0, 1, 0)
            
            # Draw terrain and sprites (existing code)
            glDisable(GL_LIGHTING) # Disable lighting for the terrain
            glBegin(GL_QUADS)
            for y in range(GRID_HEIGHT):
                for x in range(GRID_WIDTH):
                    terrain = self.grid[y][x]
                    color = self.get_terrain_color(terrain, x, y)
                    glColor3f(color[0] / 255.0, color[1] / 255.0, color[2] / 255.0)
                    cx, cz = x - GRID_WIDTH / 2, y - GRID_HEIGHT / 2
                    glVertex3f(cx, 0, cz)
                    glVertex3f(cx + 1, 0, cz)
                    glVertex3f(cx + 1, 0, cz + 1)
                    glVertex3f(cx, 0, cz + 1)
            glEnd()
            glEnable(GL_LIGHTING) # Re-enable lighting for other objects

            self.draw_billboard_sprites()
            self.draw_particles()
            
            # --- NEW: Render FBO texture to screen if PSX effect is enabled ---
            if self.psx_effect_enabled:
                glBindFramebuffer(GL_FRAMEBUFFER, 0) # Bind back to default framebuffer
                glViewport(0, 0, WINDOW_WIDTH, WINDOW_HEIGHT) # Restore original viewport

                glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT) # Clear the default framebuffer
                glMatrixMode(GL_PROJECTION)
                glPushMatrix()
                glLoadIdentity()
                gluOrtho2D(0, WINDOW_WIDTH, WINDOW_HEIGHT, 0) # Set up 2D orthographic projection
                glMatrixMode(GL_MODELVIEW)
                glPushMatrix()
                glLoadIdentity()

                glDisable(GL_LIGHTING) # No lighting for 2D quad
                glDisable(GL_DEPTH_TEST) # No depth testing for 2D quad
                glEnable(GL_TEXTURE_2D)
                glBindTexture(GL_TEXTURE_2D, self.fbo_texture)
                glColor4f(1.0, 1.0, 1.0, 1.0) # Ensure full white color to see texture as is

                glBegin(GL_QUADS)
                glTexCoord2f(0, 1); glVertex2f(0, 0) # Top-left of quad maps to bottom-left of texture
                glTexCoord2f(1, 1); glVertex2f(WINDOW_WIDTH, 0)
                glTexCoord2f(1, 0); glVertex2f(WINDOW_WIDTH, WINDOW_HEIGHT)
                glTexCoord2f(0, 0); glVertex2f(0, WINDOW_HEIGHT)
                glEnd()

                glDisable(GL_TEXTURE_2D)
                glEnable(GL_DEPTH_TEST)
                glEnable(GL_LIGHTING)

                glMatrixMode(GL_PROJECTION)
                glPopMatrix()
                glMatrixMode(GL_MODELVIEW)
                glPopMatrix()

            # --- NEW: DRAW PAUSE MENU ON TOP IF PAUSED ---
            if self.game_state == PAUSED_STATE:
                self.draw_pause_menu()
            
            # Draw the regular UI (score, etc.)
            self.draw_ui_gl()

        pygame.display.flip()

    def run(self):
        while self.running:
            self.handle_events()
            self.dt = self.clock.tick(60) / 1000.0 # Calculate delta time in seconds
            self.update(self.dt)
            self.draw()
        pygame.quit()

    def restart_game(self):
        """
        Resets the game state for a new round without re-initializing the
        entire application, preserving window and fullscreen settings.
        """
        # Reset game logic variables
        self.grid = [[FOREST_DENSE for _ in range(GRID_WIDTH)] for _ in range(GRID_HEIGHT)]
        self.burnt_timers = [[0 for _ in range(GRID_WIDTH)] for _ in range(GRID_HEIGHT)]
        self.ash_colors = [[None for _ in range(GRID_WIDTH)] for _ in range(GRID_HEIGHT)]
        self.game_over = False
        self.victory = False
        self.fire_spread_timer = 0
        self.controlled_burns_used = 0
        self.particles = []

        # Regenerate the entire world
        # This automatically clears and repopulates houses, trees, etc.
        self.generate_terrain()
        
        # Start the fires on the new map and calculate initial stats
        self.setup_game()

        # Ensure we are in the game state
        self.game_state = GAME_STATE

    # NEW: Method to reset game state and prepare for main menu without re-initializing Pygame display
    def reset_for_menu(self):
        # Reset game logic variables to initial menu state
        self.grid = [[FOREST_DENSE for _ in range(GRID_WIDTH)] for _ in range(GRID_HEIGHT)]
        self.burnt_timers = [[0 for _ in range(GRID_WIDTH)] for _ in range(GRID_HEIGHT)]
        self.ash_colors = [[None for _ in range(GRID_WIDTH)] for _ in range(GRID_HEIGHT)]
        self.game_over = False
        self.victory = False
        self.fire_spread_timer = 0
        self.controlled_burns_used = 0
        self.particles = []
        self.houses_saved = 0
        self.houses_total = 0
        self.forest_saved = 0
        self.total_burnable = 0
        self.difficulty = "Normal" # Reset difficulty to default

        # Regenerate a new terrain for the menu background
        self.generate_terrain()

        # Reset menu-specific states
        self.game_state = MENU_STATE
        self.menu_fade_alpha = 255 # Ensure it fades in correctly
        self.menu_rotation = 0 # Reset menu rotation

        # Ensure UI elements are re-initialized for the menu (if necessary, though init_menu_buttons is called in __init__)
        self.init_menu_buttons() # Re-create buttons to ensure correct state/positioning

        # NEW: Stop fire sound when returning to menu
        if self.fire_sound:
            self.fire_sound.stop()

    # MODIFIED: Draw fullscreen button in game UI
    def draw_ui_gl(self):
        glMatrixMode(GL_PROJECTION)
        glPushMatrix()
        glLoadIdentity()
        current_size = pygame.display.get_surface().get_size()
        gluOrtho2D(0, current_size[0], current_size[1], 0)
        glMatrixMode(GL_MODELVIEW)
        glPushMatrix()
        glLoadIdentity()
        glDisable(GL_LIGHTING)
        glDisable(GL_DEPTH_TEST)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        def draw_text(x, y, text_surface):
            text_data = pygame.image.tostring(text_surface, "RGBA", True)
            glRasterPos2d(x, y + text_surface.get_height())
            glDrawPixels(text_surface.get_width(), text_surface.get_height(), GL_RGBA, GL_UNSIGNED_BYTE, text_data)

        if not self.game_over:
            draw_text(10, 10, self.small_font.render("Drag to rotate, Scroll to zoom, Click to start controlled burn.", True, WHITE))
            stats = f"Burns: {self.controlled_burns_used} | Houses: {self.houses_saved}/{self.houses_total} | Forest: {self.forest_saved:.1f}% | Score: {self.score}"
            draw_text(10, 30, self.small_font.render(stats, True, WHITE))
        else:
            result_color = DARK_GREEN if self.victory else RED # Result text is DARK_GREEN for success, RED for failure
            result = f"SUCCESS! Houses saved: {self.houses_saved}/{self.houses_total}, Forest: {self.forest_saved:.1f}% | Score: {self.score}" if self.victory else f"FIRE SPREAD! Houses saved: {self.houses_saved}/{self.houses_total}, Forest: {self.forest_saved:.1f}% | Score: {self.score}"
            draw_text(10, 10, self.font.render(result, True, result_color))
            draw_text(10, 40, self.small_font.render("Press R to restart with new terrain", True, result_color))
        
        # Add fullscreen button in top-right corner (Removed this text as per user request)
        # if not self.game_over:
        #     fs_text = "F11: Fullscreen" if not self.is_fullscreen else "F11: Windowed"
        #     current_size = pygame.display.get_surface().get_size()
        #     draw_text(current_size[0] - 200, 10, 
        #              self.small_font.render(fs_text, True, WHITE))

        glDisable(GL_BLEND)
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_LIGHTING)
        glMatrixMode(GL_PROJECTION)
        glPopMatrix()
        glMatrixMode(GL_MODELVIEW)
        glPopMatrix()

    # NEW: Method to draw particles as camera-facing billboards
    def draw_particles(self):
        if not self.particles:
            return

        # --- VBO-BASED PARTICLE RENDERING ---

        # 1. Get camera vectors for billboard calculation
        modelview = glGetDoublev(GL_MODELVIEW_MATRIX)
        camera_right = np.array([modelview[0][0], modelview[1][0], modelview[2][0]])
        camera_up = np.array([modelview[0][1], modelview[1][1], modelview[2][1]])

        # 2. Create vertex and color data on the CPU (fast with numpy)
        num_particles = len(self.particles)
        # Each particle needs 4 vertices, each vertex has 3 components (x,y,z)
        vertex_data = np.zeros((num_particles, 4, 3), dtype='f4')
        # Each particle needs 4 vertices, each vertex has 4 components (r,g,b,a)
        color_data = np.zeros((num_particles, 4, 4), dtype='f4')

        for i, p in enumerate(self.particles):
            p_pos = p.pos
            half_size_right = camera_right * p.size / 2
            half_size_up = camera_up * p.size / 2
            
            # Calculate the 4 corners of the billboard
            v1 = p_pos - half_size_right - half_size_up
            v2 = p_pos + half_size_right - half_size_up
            v3 = p_pos + half_size_right + half_size_up
            v4 = p_pos - half_size_right + half_size_up
            
            vertex_data[i] = v1, v2, v3, v4
            color_data[i,:] = p.get_color() # Assign color to all 4 vertices

        # 3. Send data to GPU
        # Bind the vertex VBO and upload the data
        glBindBuffer(GL_ARRAY_BUFFER, self.particle_vbo_v)
        glBufferData(GL_ARRAY_BUFFER, vertex_data.nbytes, vertex_data, GL_STREAM_DRAW)
        
        # Bind the color VBO and upload the data
        glBindBuffer(GL_ARRAY_BUFFER, self.particle_vbo_c)
        glBufferData(GL_ARRAY_BUFFER, color_data.nbytes, color_data, GL_STREAM_DRAW)
        
        # 4. Set up OpenGL state for drawing from arrays
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glDepthMask(GL_FALSE)
        glDisable(GL_LIGHTING) # Particles should not be lit

        # Enable array pointers
        glEnableClientState(GL_VERTEX_ARRAY)
        glEnableClientState(GL_COLOR_ARRAY)

        # Point to the data in the VBOs
        glBindBuffer(GL_ARRAY_BUFFER, self.particle_vbo_v)
        glVertexPointer(3, GL_FLOAT, 0, None)
        
        glBindBuffer(GL_ARRAY_BUFFER, self.particle_vbo_c)
        glColorPointer(4, GL_FLOAT, 0, None)

        # 5. Draw everything with a single command!
        glDrawArrays(GL_QUADS, 0, num_particles * 4)

        # 6. Clean up state
        glDisableClientState(GL_COLOR_ARRAY)
        glDisableClientState(GL_VERTEX_ARRAY)
        glBindBuffer(GL_ARRAY_BUFFER, 0) # Unbind VBO

        glEnable(GL_LIGHTING)
        glDepthMask(GL_TRUE)
        glDisable(GL_BLEND)

    # Add this new method to the FireGame class to draw the pause menu UI:
    def draw_pause_menu(self):
        current_size = pygame.display.get_surface().get_size()
        glMatrixMode(GL_PROJECTION)
        glPushMatrix(); glLoadIdentity()
        gluOrtho2D(0, current_size[0], current_size[1], 0)
        glMatrixMode(GL_MODELVIEW)
        glPushMatrix(); glLoadIdentity()
        
        glDisable(GL_LIGHTING)
        glDisable(GL_DEPTH_TEST)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        # Draw a semi-transparent dark overlay
        glColor4f(0.0, 0.0, 0.0, 0.7)
        glBegin(GL_QUADS)
        glVertex2f(0, 0); glVertex2f(current_size[0], 0)
        glVertex2f(current_size[0], current_size[1]); glVertex2f(0, current_size[1])
        glEnd()

        # Draw "PAUSED" text
        paused_text = self.font.render("PAUSED", True, WHITE)
        text_x = current_size[0] // 2 - paused_text.get_width() // 2
        text_data = pygame.image.tostring(paused_text, "RGBA", True)
        glRasterPos2d(text_x, 150 + paused_text.get_height())
        glDrawPixels(paused_text.get_width(), paused_text.get_height(), GL_RGBA, GL_UNSIGNED_BYTE, text_data)
        
        # Draw centered buttons and their text
        all_pause_buttons_centered = [
            self.resume_button,
            self.restart_pause_button,
            self.main_menu_button,
            self.fullscreen_pause_button # Include fullscreen button in the centered group
        ]

        for button in all_pause_buttons_centered:
            is_selected = False
            if button == self.fullscreen_pause_button:
                is_selected = self.is_fullscreen
            
            # Center the buttons on the current screen (these buttons remain centered)
            center_x = current_size[0] // 2 - button.rect.width // 2
            button.rect.x = center_x

            button.draw_gl(button.rect.x, button.rect.y, is_selected=is_selected)

        # Draw PSX Effect button (pause menu) - this one is intentionally not centered
        is_psx_selected = self.psx_effect_enabled
        # Its x is already set in init_pause_buttons to be right-aligned
        self.psx_effect_button_pause.draw_gl(self.psx_effect_button_pause.rect.x, self.psx_effect_button_pause.rect.y, is_selected=is_psx_selected)
        
        # NEW: Draw Volume Slider
        # Slider track
        glColor3f(0.3, 0.3, 0.3) # Dark gray track
        glBegin(GL_QUADS)
        glVertex2f(self.volume_slider_rect.x, self.volume_slider_rect.y)
        glVertex2f(self.volume_slider_rect.x + self.volume_slider_rect.width, self.volume_slider_rect.y)
        glVertex2f(self.volume_slider_rect.x + self.volume_slider_rect.width, self.volume_slider_rect.y + self.volume_slider_rect.height)
        glVertex2f(self.volume_slider_rect.x, self.volume_slider_rect.y + self.volume_slider_rect.height)
        glEnd()

        # Current volume level indicator (brighter bar)
        glColor3f(0.8, 0.8, 0.0) # Yellowish indicator
        glBegin(GL_QUADS)
        glVertex2f(self.volume_slider_rect.x, self.volume_slider_rect.y)
        glVertex2f(self.volume_slider_rect.x + self.volume_slider_rect.width * self.master_volume, self.volume_slider_rect.y)
        glVertex2f(self.volume_slider_rect.x + self.volume_slider_rect.width * self.master_volume, self.volume_slider_rect.y + self.volume_slider_rect.height)
        glVertex2f(self.volume_slider_rect.x, self.volume_slider_rect.y + self.volume_slider_rect.height)
        glEnd()

        # Slider thumb (draggable part)
        thumb_x = self.volume_slider_rect.x + self.volume_slider_rect.width * self.master_volume
        thumb_y = self.volume_slider_rect.centery
        glColor3f(1.0, 1.0, 1.0) # White thumb
        glBegin(GL_TRIANGLE_FAN)
        glVertex2f(thumb_x, thumb_y)
        for i in range(20): # Draw a circle (approx. 20 segments)
            angle = 2 * math.pi * i / 19
            glVertex2f(thumb_x + math.cos(angle) * self.volume_slider_thumb_radius, thumb_y + math.sin(angle) * self.volume_slider_thumb_radius)
        glEnd()

        # Volume label
        volume_text = f"Volume: {int(self.master_volume * 100)}%"
        volume_label_surf = self.small_font.render(volume_text, True, WHITE)
        volume_label_x = self.volume_slider_rect.x + self.volume_slider_rect.width // 2 - volume_label_surf.get_width() // 2
        volume_label_y = self.volume_slider_rect.y - volume_label_surf.get_height() - 5 # 5px above slider
        text_data = pygame.image.tostring(volume_label_surf, "RGBA", True)
        glRasterPos2d(volume_label_x, volume_label_y + volume_label_surf.get_height())
        glDrawPixels(volume_label_surf.get_width(), volume_label_surf.get_height(), GL_RGBA, GL_UNSIGNED_BYTE, text_data)

        # Restore OpenGL state
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_LIGHTING)
        glMatrixMode(GL_PROJECTION); glPopMatrix()
        glMatrixMode(GL_MODELVIEW); glPopMatrix()

    # NEW: Helper method to update master volume from slider position
    def _update_volume_from_slider(self, mouse_x):
        # Calculate the position of the mouse relative to the slider track
        relative_x = mouse_x - self.volume_slider_rect.x
        # Convert relative position to a volume ratio (0.0 to 1.0)
        new_volume = relative_x / self.volume_slider_rect.width
        # Clamp the volume to be between 0.0 and 1.0
        self.master_volume = max(0.0, min(1.0, new_volume))

if __name__ == "__main__":
    game = FireGame()
    game.run()