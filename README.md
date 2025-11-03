

# 🔥 Fighting Fire with Fire

<img width="1271" height="711" alt="firestopsfirescreenshot" src="https://github.com/user-attachments/assets/1dc1267c-3771-4cdb-a117-fa94fac5998a" />


A real-time 3D fire simulation and strategy game built using Python, Pygame, and OpenGL. Battle a spreading wildfire on a procedurally generated, low-poly island, utilizing controlled burns to save forests and houses before they turn to ash.

This project focuses on a unique blend of 2D cellular automata logic running on a 3D low-resolution, PSX-inspired world rendered with OpenGL.

## ✨ Key Features

*   **Procedural World Generation:** Unique island maps generated on the fly using Perlin Noise for terrain features (Forests, Grasslands, Water, Houses, Fields).
*   **PSX Aesthetic Mode:** Utilizes a Frame Buffer Object (FBO) and low-resolution rendering (`GL_NEAREST` filtering) to achieve a distinct, retro, pixelated 3D look.
*   **Cellular Automata Fire Simulation:** A robust fire spread system based on neighbor flammability, aging, and ash transition.
*   **Dynamic 3D Sprites (Billboards):** Trees, grass, houses, and fire particles are rendered as camera-facing sprites, complete with simple burning animations.
*   **Interactive Strategy:** Players use controlled burns to create firebreaks and strategically redirect the wildfire's spread.
*   **Dynamic Soundscape:** Fire sound volume adjusts dynamically based on the camera's proximity to the closest fire and the total number of burning cells.
*   **Full Camera Control:** Rotate (Mouse Drag) and Zoom (Scroll Wheel) around the island to get the best vantage point.

## 🕹️ How to Play

1.  **Start:** Select your difficulty and click "START GAME" from the menu.
2.  **Camera:**
    *   **Drag Mouse (Left Click & Hold):** Rotate the camera around the island.
    *   **Scroll Wheel:** Zoom in and out.
3.  **Action (Controlled Burn):**
    *   **Left Click:** Click on a patch of unburnt, non-water land to initiate a controlled burn. This will instantly consume a small area, creating a temporary firebreak.
4.  **Goal:** Save as many houses and as much of the remaining forest as possible before the fire consumes the entire island or runs out of fuel.
5.  **Pause:** Press `ESC` or `F11` (for Fullscreen Toggle).

## 💻 Installation and Setup

### Prerequisites

You need **Python 3.x** installed on your system.

### Dependencies

This project relies on the following Python packages:

```bash
pip install pygame PyOpenGL numpy pynoise
```

### Running the Game

1.  **Download the files:**
    download python file

2.  **Make sure you also download the assets:**
    The game requires several assets to run correctly. Ensure the following files/directories are present in the root directory:
    *   `pixel_font.ttf` (Any small, pixelated font will work)
    *   `firesound.mp3`
    *   `ignite.mp3`
    *   `Fire stops Fire ico.png`
    *   A directory named `Assets` containing subfolders for `light tree`, `fieldgrass`, and `house` with the necessary image files (as referenced in `load_tree_textures`, `load_fieldgrass_texture`, and `load_house_textures`).

3.  **Execute:**
    ```bash
    python firewithfire3d.py
    ```

## ⚙️ PSX Effect

The game features an optional PSX-style low-resolution rendering mode which is **ON** by default.

*   **Toggle:** You can switch this effect **ON/OFF** via the checkbox in the **Main Menu** or **Pause Menu**.
*   **Implementation:** The effect is achieved by rendering the entire 3D scene to a low-resolution Frame Buffer Object (FBO) and then drawing that texture onto the main screen using `GL_NEAREST` filtering, resulting in the pixelated look.

## 🛠️ Technologies Used

*   **Python 3.x**
*   **Pygame:** Windowing, Input Handling, Audio Management, and Font Rendering.
*   **PyOpenGL:** All 3D rendering, including the GLSL-less billboard system, VBO particle rendering, and FBO management.
*   **NumPy:** Efficient matrix and vector operations.
*   **Noise (pynoise):** Procedural generation of the island terrain.



