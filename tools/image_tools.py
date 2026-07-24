"""
Image Tools — Dynamic image creation for Pinterest.
===================================================

Provides utilities to download product images and automatically
format them into Pinterest-optimized vertical aspect ratios (1000x1500).
Uses Python Imaging Library (Pillow).
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from io import BytesIO

try:
    import requests
    from PIL import Image, ImageFilter, ImageDraw, ImageFont
    HAS_PILLOW = True
except ImportError:
    HAS_PILLOW = False

logger = logging.getLogger("pinterest_agent.tools.image")


class ImageTools:
    """Operations for downloading and modifying images."""

    @staticmethod
    def download_image(url: str, save_dir: str | Path = "images") -> str:
        """
        Download an image from a URL to the local filesystem.
        """
        if not HAS_PILLOW:
            logger.warning("requests module not installed. Cannot download image.")
            raise ImportError("requests is required for downloading images.")
            
        path = Path(save_dir)
        path.mkdir(parents=True, exist_ok=True)
        
        filename = f"{uuid.uuid4().hex[:8]}.jpg"
        filepath = path / filename
        
        logger.debug("Downloading image  │  url=%s", url[:50] + "...")
        response = requests.get(url, stream=True, timeout=15)
        response.raise_for_status()
        
        with open(filepath, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                
        logger.info("Image downloaded  │  path=%s", filepath)
        return str(filepath)

    @staticmethod
    def create_pinterest_pin(
        input_image_path: str,
        output_dir: str | Path = "images",
        title_text: str = "",
        category_label: str = "Editor's Pick",
        cta_text: str = "Shop Now →"
    ) -> str:
        """
        Convert a product image into a 1000x1500 'Baddies Home Aesthetics' Editorial Pinterest Pin.

        Design Style Guide:
        - Canvas: 1000x1500 Warm White (#FAF9F6).
        - Layout: Product occupies 75–80% of canvas with equal margins and generous breathing room.
        - Shadows: Soft realistic drop shadow under the product.
        - Typography:
          * Category Label: Subtitle clean Sans-Serif in Warm Charcoal (#6B6259).
          * Headline: Elegant Serif (Georgia/Times New Roman) in Deep Black (#111111).
          * CTA: Minimalist clean Sans-Serif with arrow (→) in Warm Charcoal (#6B6259).
        - Restrictions: NO pink/red/neon, NO bright gradients, NO colored buttons, NO stickers/emojis/fake badges.
        - Total word limit: ≤ 18 words across all text blocks.
        """
        if not HAS_PILLOW:
            logger.error("Pillow not installed. Cannot create Pinterest Pin.")
            raise ImportError("Pillow is required for image formatting.")

        logger.info("Formatting Baddies Home Aesthetics Pin  │  input=%s", input_image_path)

        path = Path(output_dir)
        path.mkdir(parents=True, exist_ok=True)
        out_path = path / f"pin_{Path(input_image_path).name}"

        import os

        # Palette definition
        WARM_WHITE = (250, 249, 246)    # #FAF9F6
        DEEP_BLACK = (17, 17, 17)       # #111111
        WARM_CHARCOAL = (107, 98, 89)   # #6B6259
        SOFT_BEIGE = (217, 210, 201)    # #D9D2C9
        SHADOW_COLOR = (210, 205, 198, 120)  # Subtle realistic drop shadow

        def get_serif_font(size=38, bold=True):
            """Safely retrieve Windows Georgia / Times New Roman serif fonts."""
            windir = os.environ.get("WINDIR", "C:\\Windows")
            font_candidates = [
                os.path.join(windir, "Fonts", "georgiab.ttf" if bold else "georgia.ttf"),
                os.path.join(windir, "Fonts", "georgia.ttf"),
                os.path.join(windir, "Fonts", "timesbd.ttf" if bold else "times.ttf"),
                os.path.join(windir, "Fonts", "times.ttf"),
            ]
            for font_path in font_candidates:
                if os.path.exists(font_path):
                    try:
                        return ImageFont.truetype(font_path, size)
                    except Exception:
                        pass
            return ImageFont.load_default()

        def get_sans_font(size=22, bold=False):
            """Safely retrieve Windows Segoe UI / Arial sans-serif fonts."""
            windir = os.environ.get("WINDIR", "C:\\Windows")
            font_candidates = [
                os.path.join(windir, "Fonts", "segoeui.ttf"),
                os.path.join(windir, "Fonts", "segoeuib.ttf" if bold else "segoeui.ttf"),
                os.path.join(windir, "Fonts", "arial.ttf"),
                os.path.join(windir, "Fonts", "arialbd.ttf" if bold else "arial.ttf"),
            ]
            for font_path in font_candidates:
                if os.path.exists(font_path):
                    try:
                        return ImageFont.truetype(font_path, size)
                    except Exception:
                        pass
            return ImageFont.load_default()

        def wrap_text(text, font, max_width, draw_ctx):
            """Word-wrap helper using Pillow textbbox metrics."""
            words = text.split()
            lines = []
            current_line = []

            for word in words:
                current_line.append(word)
                test_line = " ".join(current_line)
                bbox = draw_ctx.textbbox((0, 0), test_line, font=font)
                width = bbox[2] - bbox[0]
                if width > max_width:
                    current_line.pop()
                    if current_line:
                        lines.append(" ".join(current_line))
                    current_line = [word]
            if current_line:
                lines.append(" ".join(current_line))
            return lines

        try:
            # Open original image and handle transparency/RGBA
            img = Image.open(input_image_path)
            if img.mode in ("RGBA", "P"):
                bg_temp = Image.new("RGBA", img.size, (255, 255, 255, 255))
                img = Image.alpha_composite(bg_temp, img.convert("RGBA"))
            original = img.convert("RGB")

            # Pinterest canvas dimensions (1000 x 1500)
            canvas_w, canvas_h = 1000, 1500
            canvas = Image.new("RGB", (canvas_w, canvas_h), WARM_WHITE)

            # ── 1. PRODUCT RESIZING (Occupies 75-80% of Canvas Height) ──
            # Target product image bounding box: ~820w x 1080h
            max_prod_w, max_prod_h = 820, 1060
            scale_w = max_prod_w / original.width
            scale_h = max_prod_h / original.height
            scale = min(scale_w, scale_h)

            prod_w = int(original.width * scale)
            prod_h = int(original.height * scale)
            prod_resized = original.resize((prod_w, prod_h), Image.Resampling.LANCZOS)

            # Product position (centered horizontally, placed slightly upper to leave room for text at bottom)
            prod_x = (canvas_w - prod_w) // 2
            prod_y = 130 + (max_prod_h - prod_h) // 2  # ~130px top margin for category label

            # ── 2. REALISTIC DROP SHADOW LAYER ──
            shadow_margin = 20
            shadow_canvas = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
            shadow_draw = ImageDraw.Draw(shadow_canvas)

            # Draw rounded soft shadow rectangle behind product
            shadow_draw.rounded_rectangle(
                [
                    prod_x - 8,
                    prod_y - 4,
                    prod_x + prod_w + 8,
                    prod_y + prod_h + 12
                ],
                radius=16,
                fill=SHADOW_COLOR
            )
            # Blur shadow heavily for realistic ambient natural light feel
            shadow_canvas = shadow_canvas.filter(ImageFilter.GaussianBlur(radius=18))

            # Composite shadow onto canvas
            canvas.paste(shadow_canvas, (0, 0), shadow_canvas)

            # ── 3. PASTE PRODUCT IMAGE ──
            canvas.paste(prod_resized, (prod_x, prod_y))

            # ── 4. TYPOGRAPHY OVERLAYS (Max 3 Text Blocks) ──
            draw = ImageDraw.Draw(canvas)

            # A. CATEGORY LABEL (Top Block - Small Category Label in Warm Charcoal)
            if category_label and len(category_label.strip()) > 0 and len(category_label.strip()) <= 35:
                label_str = category_label.strip()
            else:
                label_str = "Home Favorite"
            label_text = label_str.upper()

            label_font = get_sans_font(size=20, bold=True)
            label_bbox = draw.textbbox((0, 0), label_text, font=label_font)
            label_w = label_bbox[2] - label_bbox[0]

            # Top label position (~65px from top edge)
            label_x = (canvas_w - label_w) // 2
            label_y = 65

            # Render clean Category Label in Warm Charcoal
            draw.text((label_x, label_y), label_text, fill=WARM_CHARCOAL, font=label_font)

            # B. EDITORIAL HEADLINE (Middle/Bottom Block - Large Bold Curiosity Headline 4-8 Words)
            headline_font = get_serif_font(size=40, bold=True)
            headline_text = title_text.strip() if title_text else "The Cozy Home Upgrade Everyone Wants"

            # Wrap headline to max width 860px
            headline_lines = wrap_text(headline_text, headline_font, 860, draw)[:2]

            line_box = draw.textbbox((0, 0), "Ag", font=headline_font)
            line_height = line_box[3] - line_box[1] + 12
            total_headline_h = len(headline_lines) * line_height

            # Headline Y position: placed in bottom breathing room area below product image
            headline_start_y = prod_y + prod_h + 30

            # Render Headline lines in Deep Black (#111111) for high mobile readability
            curr_y = headline_start_y
            for line in headline_lines:
                bbox = draw.textbbox((0, 0), line, font=headline_font)
                line_w = bbox[2] - bbox[0]
                draw.text(((canvas_w - line_w) // 2, curr_y), line, fill=DEEP_BLACK, font=headline_font)
                curr_y += line_height

            # C. SUBTEXT / CALL TO ACTION (Bottom Block - One Short Supporting Line)
            if cta_text and len(cta_text.strip()) > 0 and len(cta_text.strip()) <= 45:
                cta_str = cta_text.strip()
            else:
                cta_str = "Shop the look →"

            cta_font = get_sans_font(size=22, bold=False)
            cta_bbox = draw.textbbox((0, 0), cta_str, font=cta_font)
            cta_w = cta_bbox[2] - cta_bbox[0]

            cta_x = (canvas_w - cta_w) // 2
            cta_y = curr_y + 14

            # Ensure CTA fits within canvas height, else clamp to bottom margin
            if cta_y > canvas_h - 60:
                cta_y = canvas_h - 65

            # Render clean supporting line in Warm Charcoal
            draw.text((cta_x, cta_y), cta_str, fill=WARM_CHARCOAL, font=cta_font)


            # Save the final image in high quality JPEG
            final_canvas = canvas.convert("RGB")
            final_canvas.save(out_path, format="JPEG", quality=95)
            logger.info("Baddies Home Aesthetics Pin exported successfully  │  path=%s", out_path)

            return str(out_path)

        except Exception as exc:
            logger.error("Failed to generate Baddies Home Aesthetics Pin: %s", exc)
            return input_image_path

