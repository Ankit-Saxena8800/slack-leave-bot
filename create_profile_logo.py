#!/usr/bin/env python3
"""
Create a proper square profile logo from the stacked STAGE logo
"""
from PIL import Image

# Open the stacked logo
logo = Image.open('stage_logo_stack.png')
print(f"Stacked logo size: {logo.size}")
print(f"Stacked logo mode: {logo.mode}")

# Create a square canvas (1024x1024) with white background
square_size = 1024
square_img = Image.new('RGBA', (square_size, square_size), (255, 255, 255, 255))

# Calculate scaling to fit the logo with padding
# Use 70% of canvas to leave nice margins
target_size = int(square_size * 0.7)

# Determine which dimension to scale by
aspect_ratio = logo.width / logo.height

if aspect_ratio > 1:
    # Wider than tall
    new_width = target_size
    new_height = int(target_size / aspect_ratio)
else:
    # Taller than wide or square
    new_height = target_size
    new_width = int(target_size * aspect_ratio)

# Resize logo maintaining aspect ratio
logo_resized = logo.resize((new_width, new_height), Image.Resampling.LANCZOS)

# Calculate position to center the logo
x_offset = (square_size - new_width) // 2
y_offset = (square_size - new_height) // 2

# Paste logo onto square canvas
if logo_resized.mode == 'RGBA':
    square_img.paste(logo_resized, (x_offset, y_offset), logo_resized)
else:
    square_img.paste(logo_resized, (x_offset, y_offset))

# Convert to RGB for compatibility
square_img_rgb = square_img.convert('RGB')

# Save the profile logo
square_img_rgb.save('stage_profile_logo.png', 'PNG', quality=95)
print(f"\nCreated profile logo: 1024x1024")
print(f"Logo dimensions on canvas: {new_width}x{new_height}")
print(f"Position: ({x_offset}, {y_offset})")
print(f"\nFile saved as: stage_profile_logo.png")
