import os
from PIL import Image, ImageDraw

def generate_friday_icon():
    """
    Generates a high-resolution cyan glowing AI core icon for ECHO
    and saves it to assets/friday.ico with multiple Windows icon resolutions.
    """
    assets_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")
    os.makedirs(assets_dir, exist_ok=True)
    icon_path = os.path.join(assets_dir, "friday.ico")

    size = 256
    image = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    # Styling colors
    bg_dark = (15, 23, 42, 255)         # Deep slate dark background
    ring_color = (0, 210, 255, 255)      # Cyan ring
    core_color = (0, 140, 240, 255)      # Deep cyan core
    inner_glow = (180, 245, 255, 255)    # Glowing highlight
    white_center = (255, 255, 255, 255)  # Bright white core center

    # Outer rounded dark base
    draw.ellipse((16, 16, size - 16, size - 16), fill=bg_dark, outline=ring_color, width=12)

    # Outer cyan glow ring segment
    draw.ellipse((36, 36, size - 36, size - 36), outline=(0, 180, 235, 180), width=6)

    # Inner glowing core
    draw.ellipse((70, 70, size - 70, size - 70), fill=core_color)

    # Core highlight ring
    draw.ellipse((95, 95, size - 95, size - 95), fill=inner_glow)

    # Bright center dot
    draw.ellipse((112, 112, size - 112, size - 112), fill=white_center)

    # Save as multi-resolution Windows .ico file
    image.save(
        icon_path,
        format='ICO',
        sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    )
    print(f"Successfully generated ECHO icon at: {icon_path}")

if __name__ == "__main__":
    generate_friday_icon()
