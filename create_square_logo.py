#!/usr/bin/env python3
"""
Create a properly centered square logo without stretching
"""
from PIL import Image

# Open the original horizontal logo
logo = Image.open('stage_logo.png')
print(f"Original logo size: {logo.size}")

# Create a square canvas (1024x1024) with white background
square_size = 1024
square_img = Image.new('RGB', (square_size, square_size), 'white')

# Calculate scaling to fit the logo with padding
# We'll use 80% of the canvas width to leave some padding
target_width = int(square_size * 0.8)
aspect_ratio = logo.height / logo.width
target_height = int(target_width * aspect_ratio)

# Resize logo maintaining aspect ratio
logo_resized = logo.resize((target_width, target_height), Image.Resampling.LANCZOS)

# Calculate position to center the logo
x_offset = (square_size - target_width) // 2
y_offset = (square_size - target_height) // 2

# Paste logo onto square canvas
if logo_resized.mode == 'RGBA':
    square_img.paste(logo_resized, (x_offset, y_offset), logo_resized)
else:
    square_img.paste(logo_resized, (x_offset, y_offset))

# Save the new square logo
square_img.save('stage_logo_square_centered.png')
print(f"\nCreated centered square logo: 1024x1024")
print(f"Logo dimensions on canvas: {target_width}x{target_height}")
print(f"Position: ({x_offset}, {y_offset})")
print(f"\nThis version maintains aspect ratio without stretching!")
