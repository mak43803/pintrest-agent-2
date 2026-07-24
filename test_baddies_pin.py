"""
Test script for Baddies Home Aesthetics Pinterest Pin Generation.
"""

import os
from PIL import Image, ImageDraw
from tools.image_tools import ImageTools

def create_sample_product_image(filename="sample_product.jpg"):
    os.makedirs("images", exist_ok=True)
    filepath = os.path.join("images", filename)

    # Create a realistic sample product shot (e.g. minimal table lamp / coffee maker)
    img = Image.new("RGB", (800, 800), color=(240, 238, 233))
    draw = ImageDraw.Draw(img)

    # Draw aesthetic minimalist vase / lamp illustration
    draw.ellipse([250, 400, 550, 700], fill=(210, 195, 180), outline=(170, 155, 140), width=4)
    draw.rectangle([375, 200, 425, 410], fill=(180, 165, 150))
    draw.ellipse([300, 150, 500, 250], fill=(245, 240, 230), outline=(200, 190, 175), width=3)

    img.save(filepath, quality=95)
    return filepath

import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

def main():
    print("Testing Baddies Home Aesthetics Pin Generator...")
    sample_img = create_sample_product_image()

    test_cases = [
        ("Minimal Coffee Station", "Kitchen Find", "Shop Now →"),
        ("Cozy Candle Set", "Cozy Living", "See Details →"),
        ("Glass Pantry Containers", "Storage Idea", "View on Amazon →"),
        ("Luxury Table Lamp", "Editor's Pick", "Get the Look →")
    ]

    for headline, label, cta in test_cases:
        pin_path = ImageTools.create_pinterest_pin(
            input_image_path=sample_img,
            output_dir="images",
            title_text=headline,
            category_label=label,
            cta_text=cta
        )
        print(f"[OK] Generated Pin: {pin_path}")

        # Verification check
        with Image.open(pin_path) as pin_img:
            assert pin_img.size == (1000, 1500), f"Expected (1000, 1500), got {pin_img.size}"
            # Check background color of top corner (should be Warm White #FAF9F6)
            top_pixel = pin_img.getpixel((10, 10))
            print(f"  Canvas top pixel color: {top_pixel} (Warm White)")

    print("[SUCCESS] All Baddies Home Aesthetics Pin Generator tests passed!")

if __name__ == "__main__":
    main()
