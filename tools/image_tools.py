"""
Image Tools — Dynamic image creation for Pinterest.
===================================================

BADDIES BEAUTY – PREMIUM PIN DESIGN v4.0
Creates ultra-premium Sephora / Rhode / Dior Beauty style editorial pins.

Features:
- Pinterest Vertical (1000x1500) aspect ratio.
- Dominant hero product occupying 75%–85% of visual area.
- 5 Luxury Background Color Rotations (Pure White, Warm Ivory, Soft Beige, Champagne, Pearl White).
- Subtle studio radial lighting glow & soft realistic shadows.
- Thin elegant white card frame with soft rounded border & shadow.
- 10 Auto-Rotating Top Labels (Luxury Beauty Find, Amazon Bestseller, Editor's Pick, etc.).
- 5 Auto-Rotating CTA Pill Buttons (Shop Now →, View on Amazon →, See Today's Price →, etc.).
- 5 Layout Variations (Layout A: Centered Hero, Layout B: Product Left, Layout C: Product Right, Layout D: Close-up Hero, Layout E: Dual Product / Composite Accent).
- Luxury Serif Headlines & Modern Sans-Serif Pill Buttons.
"""

from __future__ import annotations

import logging
import os
import uuid
import math
from pathlib import Path
from typing import Tuple, List, Optional

try:
    import requests
    from PIL import Image, ImageFilter, ImageDraw, ImageFont
    HAS_PILLOW = True
except ImportError:
    HAS_PILLOW = False

logger = logging.getLogger("pinterest_agent.tools.image")

# ──────────────────────────────────────────────────────────────────────
# BADDIES BEAUTY v4.0 DESIGN SYSTEM TOKENS
# ──────────────────────────────────────────────────────────────────────

BACKGROUND_PALETTE = [
    {"name": "Pure White", "rgb": (255, 255, 255), "glow": (250, 248, 246)},
    {"name": "Warm Ivory", "rgb": (250, 245, 239), "glow": (255, 252, 248)},
    {"name": "Soft Beige", "rgb": (247, 240, 230), "glow": (253, 249, 244)},
    {"name": "Champagne",  "rgb": (245, 235, 225), "glow": (252, 247, 241)},
    {"name": "Pearl White", "rgb": (248, 248, 246), "glow": (255, 255, 255)},
]

# Product-Matched Aesthetic 1-2 Word Luxury Badges (Clean Minimalist Text)
PRODUCT_MATCHED_BADGES = {
    "lighting": ["AMBIENT GLOW", "COZY LIGHTING", "WARM AMBIENCE", "MODERN LIGHT"],
    "mirror": ["VANITY EDIT", "GOLDEN FRAME", "AESTHETIC REFLECTION", "FULL LENGTH"],
    "rug": ["PLUSH COMFORT", "BOHO CHIC", "ROOM ANCHOR", "NEUTRAL TEXTURE"],
    "chair": ["ACCENT CHAIR", "LUXURY SEATING", "COZY NOOK", "MODERN FORM"],
    "shelves": ["ORGANIZED HOME", "FLOATING SHELF", "MINIMAL DISPLAY", "STORAGE GOALS"],
    "organizer": ["ACRYLIC CLEAN", "DESK NEAT", "VANITY ORG", "ZERO CLUTTER"],
    "bedding": ["CLOUD BEDDING", "HOTEL COMFORT", "LINEN DREAMS", "SLEEP SANCTUARY"],
    "art": ["WALL GALLERY", "VOGUE ART", "MINIMAL PRINT", "CANVAS EDIT"],
    "vase": ["CERAMIC CRAFT", "FLORAL DISPLAY", "SCULPTURAL VASE", "TABLETOP ESSENTIAL"],
    "universal": ["ARCHITECTURAL DIGEST", "AMAZON HOME", "COZY AESTHETIC", "HOME FIND", "EDITORS PICK"]
}

LUXURY_TOP_BADGES = PRODUCT_MATCHED_BADGES["universal"]

CATEGORY_LABELS = {
    "lighting": [
        "Aesthetic Sunset Projection Lamp For Cozy Bedroom Vibes",
        "The $24 Mushroom Table Lamp TikTok Is Obsessed With",
        "Vintage Candle Warmer Lamp For Cozy Room Ambience",
        "Dimmable Warm Amber Sunset Projection Lamp 2026",
        "Fairy String Curtain Lights For Dreamy Room Aesthetic"
    ],
    "mirror": [
        "The $24 Amazon Wavy Wall Mirror For Cozy Japandi Bedroom",
        "Aesthetic Gold Arched Full Length Floor Mirror",
        "Irregular Wavy Wall Mirror For Aesthetic Vanity Setup",
        "Minimalist Frameless Vanity Wall Mirror Ideas"
    ],
    "shelves": [
        "Minimalist Floating Wall Shelves Set For Small Apartment",
        "Walnut Wood Floating Entryway Console Table",
        "Aesthetic Display Shelves For Books & Decor",
        "Industrial Wooden Pipe Wall Shelves For Living Room"
    ],
    "organizer": [
        "Clear Acrylic Makeup & Skincare Vanity Organizer",
        "Bamboo Spice Jar Organizer Set With Minimalist Labels",
        "Aesthetic Rotating Perfume & Skincare Display Stand",
        "Clear Fridge & Pantry Organization Bins Set"
    ],
    "bedding": [
        "Chunky Knit Blanket Throw For Cozy Bed Styling",
        "100% Washed Linen Duvet Cover Set Neutral Tones",
        "Silk Satin Pillowcase Set For Glowing Skin & Hair",
        "Boho Textured Tufted Throw Pillow Covers Set"
    ],
    "art": [
        "Minimalist Line Art Prints Set For Living Room Wall Gallery",
        "Botanical Olive Branch Framed Canvas Wall Art",
        "Aesthetic Abstract Neutral Wall Decor Prints Set",
        "Vogue Gallery Wall Print Set For Small Apartment"
    ],
    "universal": [
        "Aesthetic Home Decor Deals: Top Amazon Finds Under $50",
        "The $24 Viral Room Transformation Find On Amazon",
        "10/10 Cozy Room Aesthetic Essential Every Apartment Needs",
        "The Aesthetic Amazon Decor Find Everyone Is Secretly Buying",
        "Architectural Digest Style Room Refresh Under $30",
        "The TikTok Viral Room Decor Essential Worth Every Penny"
    ]
}

CTA_BUTTONS = [
    "Shop on Amazon",
    "View on Amazon",
    "Check Price on Amazon",
    "See Today's Price",
    "Claim Deal On Amazon",
    "Shop Bestseller",
    "See Amazon Reviews",
    "Explore Collection",
    "Shop Now"
]

LAYOUT_VARIATIONS = [
    "Layout A",  # Centered Hero Product
    "Layout B",  # Product Left
    "Layout C",  # Product Right
    "Layout D",  # Close-up Hero (85% dominance)
    "Layout E"   # Dual Product / Composite Card
]

# Luxury Accent Colors
MUTED_ROSE = (216, 164, 155)      # #D8A49B
WARM_BEIGE = (239, 232, 224)      # #EFE8E0
SOFT_GOLD   = (197, 160, 89)       # #C5A059
DARK_CHARCOAL = (26, 26, 26)      # #1A1A1A
CARD_BORDER = (232, 222, 216)     # Thin off-white/rose border
CARD_BG     = (255, 255, 255)     # Clean white card frame


class ImageTools:
    """Operations for downloading and generating v4.0 luxury Pinterest pins."""

    @staticmethod
    def download_image(url: str, save_dir: str | Path = "images") -> str:
        """Download an image from a URL to the local filesystem."""
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
                
        # Validate downloaded image is valid and not blank/1x1 px
        try:
            with Image.open(filepath) as test_img:
                w, h = test_img.size
                if w < 100 or h < 100:
                    filepath.unlink(missing_ok=True)
                    raise ValueError(f"Downloaded image is too small or blank ({w}x{h} px)")
        except Exception as err:
            filepath.unlink(missing_ok=True)
            logger.warning("Image validation failed for %s: %s", url, err)
            raise ValueError(f"Invalid downloaded image from {url}: {err}") from err

        logger.info("Image downloaded  │  path=%s", filepath)
        return str(filepath)

    @staticmethod
    def _get_system_font(font_type: str = "serif", size: int = 36, category: str = "beauty") -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        """
        Safely retrieve ultra-luxury Monotype-style TTF fonts (Bodoni Moda, Cinzel, Playfair Display, Tenor Sans, Inter)
        from local project fonts/ directory, falling back to Linux / macOS / Windows system fonts if needed.
        - Headline Serif: Bodoni Moda Bold / Playfair Display Bold / Cormorant Garamond Bold / Georgia Bold
        - Badges & CTAs Sans-Serif: Inter Bold / Outfit Bold / Tenor Sans / Arial Bold
        """
        if not HAS_PILLOW:
            return ImageFont.load_default()
            
        project_root = Path(__file__).resolve().parent.parent
        local_fonts_dir = project_root / "fonts"
        
        windir = os.environ.get("WINDIR", "C:\\Windows")
        sys_fonts_dir = Path(windir) / "Fonts"

        search_dirs = [
            local_fonts_dir,
            sys_fonts_dir,
            Path("/usr/share/fonts"),
            Path("/usr/share/fonts/truetype"),
            Path("/usr/share/fonts/opentype"),
            Path("/usr/local/share/fonts"),
            Path("/System/Library/Fonts"),
            Path("/Library/Fonts")
        ]

        if font_type.lower() in ("serif", "luxury", "cormorant", "bodoni", "cinzel"):
            serif_candidates = [
                "CormorantGaramond-Bold.ttf", "CormorantGaramond-SemiBold.ttf", "PlayfairDisplay-Bold.ttf",
                "BodoniModa-Bold.ttf", "Cinzel-Regular.ttf", "PlayfairDisplay-Regular.ttf",
                "georgiab.ttf", "georgia.ttf", "bod_b.ttf", "timesbd.ttf",
                "DejaVuSerif-Bold.ttf", "FreeSerifBold.ttf", "LiberationSerif-Bold.ttf"
            ]

            for sdir in search_dirs:
                if not sdir.exists():
                    continue
                for font_file in serif_candidates:
                    full_path = sdir / font_file
                    if full_path.exists():
                        try:
                            return ImageFont.truetype(str(full_path), size)
                        except Exception:
                            pass

        # Sans-serif & Luxury Branding candidates (Inter SemiBold / Inter Bold / Inter Regular / Tenor Sans)
        if font_type.lower() in ("sans_regular", "regular", "rating_regular"):
            sans_candidates = [
                "Inter-Regular.ttf", "Inter-Bold.ttf", "Outfit-Bold.ttf", "TenorSans-Regular.ttf",
                "segoeui.ttf", "segoeuib.ttf", "arial.ttf",
                "DejaVuSans.ttf", "LiberationSans-Regular.ttf"
            ]
        elif font_type.lower() in ("sans_bold", "rating", "cta_bold", "cta"):
            sans_candidates = [
                "Inter-Bold.ttf", "Outfit-Bold.ttf", "TenorSans-Regular.ttf", "Inter-Regular.ttf",
                "segoeuib.ttf", "segoeui.ttf", "arialbd.ttf", "arial.ttf",
                "DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf", "Ubuntu-B.ttf", "Roboto-Bold.ttf"
            ]
        else:
            sans_candidates = [
                "Inter-Bold.ttf", "TenorSans-Regular.ttf", "Outfit-Bold.ttf", "Inter-Regular.ttf",
                "segoeuib.ttf", "segoeui.ttf", "arialbd.ttf", "arial.ttf",
                "DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf"
            ]
            
        for sdir in search_dirs:
            if not sdir.exists():
                continue
            for font_file in sans_candidates:
                full_path = sdir / font_file
                if full_path.exists():
                    try:
                        return ImageFont.truetype(str(full_path), size)
                    except Exception:
                        pass

        try:
            return ImageFont.load_default(size=size)
        except Exception:
            return ImageFont.load_default()

    @staticmethod
    def _draw_golden_star(draw: Any, center_x: float, center_y: float, radius: float = 12.0, fill=(245, 166, 35, 255)):
        """Draw a crisp 100% vector 5-point golden amber star."""
        import math
        points = []
        outer_r = radius
        inner_r = radius * 0.42
        for i in range(10):
            r = outer_r if i % 2 == 0 else inner_r
            angle = i * math.pi / 5.0 - math.pi / 2.0
            x = center_x + r * math.cos(angle)
            y = center_y + r * math.sin(angle)
            points.append((x, y))
        draw.polygon(points, fill=fill)

    @staticmethod
    def _clean_emoji_for_rendering(text: str) -> str:
        """Clean unsupported color emojis and symbol characters to ensure 100% clean typography without tofu box [□] glyphs."""
        if not text:
            return ""
            
        import unicodedata
        import re
        
        # 1. Convert fullwidth / special currency symbols to standard ASCII $
        text = text.replace("＄", "$").replace("\u00a0", " ").replace("\u200b", "").replace("\u202f", " ")
        
        # 2. Normalize quotes & dashes to standard ASCII
        text = text.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
        text = text.replace("—", "-").replace("–", "-")
        
        # 3. Replace arrows that cause tofu boxes on Windows serif fonts
        text = text.replace("→", ">").replace("➔", ">").replace("➜", ">")
        
        # 4. Remove unsupported emojis that cause tofu boxes, but KEEP standard star symbol ★ (\u2605)
        for char_to_remove in ["⭐", "🌟", "✨", "💫", "⚡", "🔥", "💎", "👑", "✦", "☆", "✪", "✧", "✬", "✭", "✮", "✯", "✰", "•", "●", "■", "▪"]:
            text = text.replace(char_to_remove, "")
            
        # 5. Normalize unicode characters (NFKD)
        text = unicodedata.normalize('NFKD', text)
        
        # 6. Filter out any remaining non-printable / control / symbol characters that PIL fonts fail to render
        clean_chars = []
        for ch in text:
            cat = unicodedata.category(ch)
            # Keep standard letters, numbers, punctuation, spaces, ASCII dollar sign $, and star ★
            if ch in "$★\n\r\t " or cat.startswith('L') or cat.startswith('N') or cat.startswith('P') or cat == 'So':
                clean_chars.append(ch)
                
        clean_text = "".join(clean_chars).strip()
        return re.sub(r' +', ' ', clean_text).strip()

    @staticmethod
    def _get_dynamic_cta_color(img: Image.Image) -> Tuple[int, int, int]:
        """
        Dynamically extract dominant product color and select matching luxury CTA button fill color.
        - Blue: Deep Teal (15, 76, 92)
        - Brown: Dark Charcoal (38, 38, 38)
        - Green: Forest Green (34, 76, 56)
        - Gold/Yellow: Dark Brown (74, 44, 26)
        - Pink/Red: Burgundy / Deep Rose (136, 44, 66)
        - Black/Grey: Charcoal (26, 26, 26)
        """
        import colorsys
        try:
            small_img = img.resize((40, 40)).convert("RGB")
            pixels = list(small_img.getdata())
            
            # Filter out white/near-white backgrounds (R>225, G>225, B>225)
            product_pixels = [p for p in pixels if not (p[0] > 225 and p[1] > 225 and p[2] > 225)]
            if not product_pixels:
                return (216, 164, 155)  # Muted Rose fallback
                
            avg_r = sum(p[0] for p in product_pixels) // len(product_pixels)
            avg_g = sum(p[1] for p in product_pixels) // len(product_pixels)
            avg_b = sum(p[2] for p in product_pixels) // len(product_pixels)
            
            h, s, v = colorsys.rgb_to_hsv(avg_r / 255.0, avg_g / 255.0, avg_b / 255.0)
            hue_deg = h * 360.0
            
            if v < 0.2:  # Black / Dark Grey
                return (26, 26, 26)
            elif s < 0.15:  # Neutral / Grey
                return (38, 38, 38)
            elif 170 <= hue_deg <= 250:  # Blue -> Deep Teal
                return (15, 76, 92)
            elif 60 <= hue_deg < 170:  # Green -> Forest Green
                return (34, 76, 56)
            elif 40 <= hue_deg < 60:  # Gold / Yellow -> Dark Brown
                return (74, 44, 26)
            elif 15 <= hue_deg < 40:  # Brown / Tan -> Dark Charcoal
                return (38, 38, 38)
            elif hue_deg < 15 or hue_deg >= 280:  # Pink / Red / Berry -> Burgundy Deep Rose
                return (136, 44, 66)
        except Exception as e:
            logger.debug(f"Dynamic CTA color extraction fallback: {e}")
            
        return (216, 164, 155)  # Muted Rose default


    @staticmethod
    def get_price_tag(price_str: str) -> str:
        """Extract price number and return high-converting price tag badge."""
        if not price_str:
            return ""
        import re
        clean_price = str(price_str).replace(",", "").strip()
        match = re.search(r'\$?(\d+(?:\.\d{1,2})?)', clean_price)
        if match:
            try:
                val = float(match.group(1))
                if val <= 10:
                    return f"UNDER $10 · ONLY ${val:.2f}".replace(".00", "")
                elif val <= 15:
                    return f"UNDER $15 · ONLY ${val:.2f}".replace(".00", "")
                elif val <= 20:
                    return f"UNDER $20 · ONLY ${val:.2f}".replace(".00", "")
                elif val <= 25:
                    return f"UNDER $25 · ONLY ${val:.2f}".replace(".00", "")
                elif val <= 35:
                    return f"UNDER $35 · ONLY ${val:.2f}".replace(".00", "")
                elif val <= 50:
                    return f"UNDER $50 · ONLY ${val:.2f}".replace(".00", "")
                else:
                    return f"LUXURY FIND · ${val:.2f}".replace(".00", "")
            except Exception:
                pass
        return ""

    @staticmethod
    def get_smart_badge(product_title: str, pin_index: int = 0, price_str: str = "") -> str:
        """Dynamically detect product type and select exact matching 1-2 word luxury aesthetic category badge."""
        title_lower = product_title.lower() if product_title else ""
        
        if any(w in title_lower for w in ["lamp", "light", "chandelier", "sconce", "pendant"]):
            pool = PRODUCT_MATCHED_BADGES["lighting"]
        elif any(w in title_lower for w in ["mirror", "vanity", "reflection"]):
            pool = PRODUCT_MATCHED_BADGES["mirror"]
        elif any(w in title_lower for w in ["rug", "mat", "carpet", "runner"]):
            pool = PRODUCT_MATCHED_BADGES["rug"]
        elif any(w in title_lower for w in ["chair", "sofa", "stool", "pouf", "couch"]):
            pool = PRODUCT_MATCHED_BADGES["chair"]
        elif any(w in title_lower for w in ["shelf", "shelves", "console", "table", "bookcase"]):
            pool = PRODUCT_MATCHED_BADGES["shelves"]
        elif any(w in title_lower for w in ["organizer", "tray", "acrylic", "storage", "basket"]):
            pool = PRODUCT_MATCHED_BADGES["organizer"]
        elif any(w in title_lower for w in ["duvet", "comforter", "pillow", "bedding", "blanket", "sheet"]):
            pool = PRODUCT_MATCHED_BADGES["bedding"]
        elif any(w in title_lower for w in ["art", "print", "frame", "poster", "canvas", "wall"]):
            pool = PRODUCT_MATCHED_BADGES["art"]
        elif any(w in title_lower for w in ["vase", "planter", "pot", "ceramic"]):
            pool = PRODUCT_MATCHED_BADGES["vase"]
        else:
            pool = PRODUCT_MATCHED_BADGES["universal"]
            
        return pool[pin_index % len(pool)]

    @staticmethod
    def _wrap_text(text: str, font: ImageFont.FreeTypeFont | ImageFont.ImageFont, max_width: int, draw_ctx: ImageDraw.ImageDraw) -> List[str]:
        """Word-wrap helper using modern Pillow textbbox metrics."""
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

    @staticmethod
    def normalize_and_crop_product_image(img: Image.Image, tolerance: int = 245) -> Image.Image:
        """
        PRODUCT SIZE NORMALIZATION (MANDATORY Rules 1-15):
        1. Detect actual product object.
        2. Remove unnecessary white, transparent, and empty margins.
        3. Crop tightly around product with 2% safety padding.
        """
        try:
            import numpy as np
            if img.mode != "RGBA":
                img_rgba = img.convert("RGBA")
            else:
                img_rgba = img.copy()

            np_img = np.array(img_rgba)
            r, g, b, a = np_img[:, :, 0], np_img[:, :, 1], np_img[:, :, 2], np_img[:, :, 3]
            
            # Non-background mask: Alpha > 15 and RGB not pure white/near-white
            is_non_transparent = a > 15
            is_non_white = (r < tolerance) | (g < tolerance) | (b < tolerance)
            product_mask = is_non_transparent & is_non_white
            
            coords = np.argwhere(product_mask)
            if coords.size == 0:
                return img
                
            y_min, x_min = coords.min(axis=0)
            y_max, x_max = coords.max(axis=0)
            
            # Add 2% safety padding around bounding box
            w = x_max - x_min
            h = y_max - y_min
            pad_x = max(4, int(w * 0.02))
            pad_y = max(4, int(h * 0.02))
            
            x_min = max(0, x_min - pad_x)
            y_min = max(0, y_min - pad_y)
            x_max = min(img.width, x_max + pad_x)
            y_max = min(img.height, y_max + pad_y)
            
            return img.crop((x_min, y_min, x_max, y_max))
        except Exception as exc:
            logger.debug(f"Auto-crop normalization fallback: {exc}")
            return img

    @staticmethod
    def create_pinterest_pin(
        input_image_path: str,
        output_dir: str | Path = "images",
        title_text: str = "",
        badge_text: str = "",
        cta_text: str = "",
        pin_index: int = 0,
        layout: str = "",
        bg_color: str = "",
        rating_text: str = "",
        price_text: str = ""
    ) -> str:
        """
        Convert a product image into an ultra-premium Sephora/Rhode-style 1000x1500 Pinterest Pin.
        BADDIES BEAUTY – PREMIUM PIN DESIGN v4.0
        """
        if not HAS_PILLOW:
            logger.error("Pillow not installed. Cannot create Pinterest Pin.")
            raise ImportError("Pillow is required for image formatting.")
            
        logger.info("Generating BADDIES BEAUTY v4.0 Pin  │  pin_index=%d, input=%s", pin_index, input_image_path)
        
        path = Path(output_dir)
        path.mkdir(parents=True, exist_ok=True)
        out_path = path / f"pin_v4_{pin_index}_{Path(input_image_path).name}"
        
        try:
            # Open original image cleanly with blank/1x1 px protection
            try:
                img = Image.open(input_image_path)
                if img.width < 100 or img.height < 100:
                    raise ValueError(f"Input image too small ({img.width}x{img.height} px)")
            except Exception as img_err:
                logger.warning("Product image input %s is invalid/blank (%s). Downloading luxury decor fallback image...", input_image_path, img_err)
                fallback_decor_url = "https://images.unsplash.com/photo-1513519245088-0e12902e5a38?q=80&w=1000&auto=format&fit=crop"
                fallback_local_path = ImageTools.download_image(fallback_decor_url, output_dir)
                img = Image.open(fallback_local_path)

            # Canvas dimensions (Pinterest 2:3 vertical standard)
            canvas_w, canvas_h = 1000, 1500
            
            # Determine Background Color from palette rotation
            bg_data = BACKGROUND_PALETTE[pin_index % len(BACKGROUND_PALETTE)]
            if bg_color:
                # Custom override if specified
                for item in BACKGROUND_PALETTE:
                    if item["name"].lower() == bg_color.lower():
                        bg_data = item
                        break
            
            bg_rgb = bg_data["rgb"]
            glow_rgb = bg_data["glow"]
            
            # Determine Layout Variation
            current_layout = layout if layout in LAYOUT_VARIATIONS else LAYOUT_VARIATIONS[pin_index % len(LAYOUT_VARIATIONS)]
            
            # Determine Top Label (Category-Smart Auto Rotation & Short 1-2 Word Enforcement)
            if badge_text and badge_text.strip() and len(badge_text.strip()) <= 25:
                current_badge = badge_text.strip()
            else:
                current_badge = ImageTools.get_smart_badge(title_text, pin_index)
            
            # Determine CTA Text
            current_cta = cta_text.strip() if cta_text and cta_text.strip() else CTA_BUTTONS[pin_index % len(CTA_BUTTONS)]

            # ── 1. BACKGROUND CANVAS & LUXURY CENTER GLOW ──
            canvas = Image.new("RGBA", (canvas_w, canvas_h), (*bg_rgb, 255))
            
            # Add subtle radial lighting glow behind center
            glow_mask = Image.new("L", (canvas_w, canvas_h), 0)
            glow_draw = ImageDraw.Draw(glow_mask)
            center_x, center_y = canvas_w // 2, canvas_h // 2
            
            # Draw soft radial oval glow
            glow_r_x, glow_r_y = 420, 550
            glow_draw.ellipse(
                [center_x - glow_r_x, center_y - glow_r_y, center_x + glow_r_x, center_y + glow_r_y],
                fill=180
            )
            glow_mask = glow_mask.filter(ImageFilter.GaussianBlur(radius=100))
            
            glow_layer = Image.new("RGBA", (canvas_w, canvas_h), (*glow_rgb, 255))
            canvas = Image.composite(glow_layer, canvas, glow_mask)

            # ── 2. LAYOUT SPECIFIC PARAMETERS ──
            # Target product dominance: 78% to 80% of card visual area
            card_radius = 28
            border_width = 1
            
            # ── 3. CANVAS & CARD SETUP (SEPHORA + RHODE + MERIT TEMPLATE) ──
            # Warm ivory background (#F8F5F0)
            BG_COLOR = (248, 245, 240)
            canvas = Image.new("RGBA", (canvas_w, canvas_h), (*BG_COLOR, 255))

            card_w = 840
            card_h = 800  # Balanced 800px card height to give ample room for large readable text & CTA
            card_x = (canvas_w - card_w) // 2
            card_y = 115  # Shifted to y=115
            product_scale_factor = 0.96

            # Soft, natural, elegant shadow
            shadow_offset_y = 8
            shadow_expand = 6
            card_layer = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
            card_draw = ImageDraw.Draw(card_layer)

            shadow_mask = Image.new("L", (canvas_w, canvas_h), 0)
            shadow_mask_draw = ImageDraw.Draw(shadow_mask)
            shadow_mask_draw.rounded_rectangle(
                [
                    card_x - shadow_expand,
                    card_y + shadow_offset_y - shadow_expand,
                    card_x + card_w + shadow_expand,
                    card_y + card_h + shadow_offset_y + shadow_expand,
                ],
                radius=card_radius + shadow_expand,
                fill=24,  # Very soft natural shadow
            )
            shadow_mask = shadow_mask.filter(ImageFilter.GaussianBlur(radius=18))
            shadow_layer = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 255))
            canvas = Image.composite(shadow_layer, canvas, shadow_mask)

            # Draw Large Rounded White Product Card (#FFFFFF)
            card_draw.rounded_rectangle(
                [card_x, card_y, card_x + card_w, card_y + card_h],
                radius=card_radius,
                fill=(255, 255, 255, 255),
                outline=(232, 226, 218, 255),
                width=border_width
            )
            canvas = Image.alpha_composite(canvas, card_layer)

            # ── 4. RESIZE & POSITION HERO PRODUCT (EXACT 78–80% CARD OCCUPANCY) ──
            cropped_prod = ImageTools.normalize_and_crop_product_image(img)
            
            if cropped_prod.mode in ("RGBA", "P"):
                bg_temp = Image.new("RGBA", cropped_prod.size, (255, 255, 255, 255))
                prod_rgb = Image.alpha_composite(bg_temp, cropped_prod.convert("RGBA")).convert("RGB")
            else:
                prod_rgb = cropped_prod.convert("RGB")

            prod_aspect = prod_rgb.width / prod_rgb.height
            card_padding = 40
            inner_card_w = card_w - card_padding * 2
            inner_card_h = card_h - card_padding * 2

            if prod_aspect < 0.85:
                target_w = inner_card_w * 0.80 * product_scale_factor
                target_h = inner_card_h * 0.82 * product_scale_factor
            elif prod_aspect > 1.15:
                target_w = inner_card_w * 0.82 * product_scale_factor
                target_h = inner_card_h * 0.78 * product_scale_factor
            else:
                target_w = inner_card_w * 0.80 * product_scale_factor
                target_h = inner_card_h * 0.80 * product_scale_factor

            scale_w = target_w / prod_rgb.width
            scale_h = target_h / prod_rgb.height
            scale = min(scale_w, scale_h)
            
            prod_w = max(10, int(prod_rgb.width * scale))
            prod_h = max(10, int(prod_rgb.height * scale))
            
            resized_prod = prod_rgb.resize((prod_w, prod_h), Image.Resampling.LANCZOS)

            prod_cx = card_x + card_w // 2
            prod_cy = card_y + card_h // 2
            prod_left = prod_cx - prod_w // 2
            prod_top = prod_cy - prod_h // 2

            # Soft Natural Shadow underneath product base
            prod_shadow_layer = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
            prod_shadow_draw = ImageDraw.Draw(prod_shadow_layer)
            shadow_y = prod_top + prod_h - 6
            shadow_rx = int(prod_w * 0.38)
            shadow_ry = max(8, int(prod_h * 0.06))
            
            prod_shadow_draw.ellipse(
                [prod_cx - shadow_rx, shadow_y - shadow_ry, prod_cx + shadow_rx, shadow_y + shadow_ry],
                fill=(0, 0, 0, 50)
            )
            prod_shadow_layer = prod_shadow_layer.filter(ImageFilter.GaussianBlur(radius=12))
            canvas = Image.alpha_composite(canvas, prod_shadow_layer)

            # Paste product image cleanly inside white card
            canvas.paste(resized_prod, (prod_left, prod_top))

            # ── 4.5. UPPER RIGHT LUXURY PRICE TAG STICKER (LARGE BOLD FONT 28pt) ──
            # Dynamically extract dominant product color palette for harmonized CTA & Price Tag
            product_accent_rgb = ImageTools._get_dynamic_cta_color(cropped_prod)
            ACCENT_FILL = (*product_accent_rgb, 255)

            actual_price_val = price_text.strip() if price_text else ""
            if not actual_price_val:
                import re
                m_p = re.search(r'\$?(\d+(?:\.\d{1,2})?)', title_text + " " + badge_text)
                if m_p:
                    try:
                        actual_price_val = f"${float(m_p.group(1)):.2f}".replace(".00", "")
                    except Exception:
                        pass
                        
            if actual_price_val:
                if not actual_price_val.startswith("$"):
                    actual_price_val = "$" + actual_price_val
                    
                price_badge_str = actual_price_val.upper()
                price_badge_font = ImageTools._get_system_font("sans_bold", 28, category="beauty")
                
                pt_draw = ImageDraw.Draw(canvas)
                pt_bbox = pt_draw.textbbox((0, 0), price_badge_str, font=price_badge_font)
                pt_w = pt_bbox[2] - pt_bbox[0]
                pt_h = pt_bbox[3] - pt_bbox[1]
                
                pt_px, pt_py = 24, 12
                pill_w = pt_w + pt_px * 2
                pill_h = pt_h + pt_py * 2
                
                pt_left = card_x + card_w - pill_w - 24
                pt_top = card_y + 22
                
                # Draw sleek upper-right price tag badge (Color-Harmonized ACCENT_FILL, crisp white price text)
                pt_draw.rounded_rectangle(
                    [pt_left, pt_top, pt_left + pill_w, pt_top + pill_h],
                    radius=22,
                    fill=ACCENT_FILL,
                    outline=(217, 206, 194, 255),
                    width=1
                )
                
                pt_draw.text(
                    (pt_left + pt_px, pt_top + pt_py - 2),
                    price_badge_str,
                    fill=(255, 255, 255, 255),
                    font=price_badge_font
                )

            # ── 5. TOP CENTER OUTLINED PILL BADGE (LARGE BOLD FONT 24pt) ──
            draw = ImageDraw.Draw(canvas)
            serif_font_title = ImageTools._get_system_font("cormorant", 56, category="beauty")
            sans_font_cta = ImageTools._get_system_font("sans_bold", 30, category="beauty")

            if current_badge:
                badge_str = ImageTools._clean_emoji_for_rendering(current_badge.strip().upper())
                badge_font = ImageTools._get_system_font("sans_bold", 24, category="beauty")
                
                # Apply 3px letter spacing (tracking) for luxury editorial badge text
                tracking_px = 3
                badge_lines = ImageTools._wrap_text(badge_str, badge_font, 780, draw)
                badge_lines = badge_lines[:2]
                
                max_line_w = 0
                for bline in badge_lines:
                    l_w = sum(draw.textbbox((0, 0), ch, font=badge_font)[2] - draw.textbbox((0, 0), ch, font=badge_font)[0] for ch in bline)
                    l_w += tracking_px * max(0, len(bline) - 1)
                    max_line_w = max(max_line_w, l_w)
                    
                line_bbox = draw.textbbox((0, 0), "Ag", font=badge_font)
                b_line_h = line_bbox[3] - line_bbox[1] + 8
                badge_h = len(badge_lines) * b_line_h
                
                pill_px, pill_py = 28, 12
                pill_w = max_line_w + pill_px * 2
                pill_h = badge_h + pill_py * 2
                
                pill_left = (canvas_w - pill_w) // 2
                pill_top = max(24, (card_y - pill_h) // 2)
                
                # Draw outlined pill badge (white fill, #D9CEC2 border, 1px)
                draw.rounded_rectangle(
                    [pill_left, pill_top, pill_left + pill_w, pill_top + pill_h],
                    radius=22,
                    fill=(255, 255, 255, 255),
                    outline=(217, 206, 194, 255),  # #D9CEC2
                    width=1
                )
                
                # Draw letter-spaced badge text (#222222)
                curr_b_y = pill_top + pill_py
                for bline in badge_lines:
                    l_w = sum(draw.textbbox((0, 0), ch, font=badge_font)[2] - draw.textbbox((0, 0), ch, font=badge_font)[0] for ch in bline)
                    l_w += tracking_px * max(0, len(bline) - 1)
                    
                    start_x = (canvas_w - l_w) // 2
                    curr_x = start_x
                    for ch in bline:
                        draw.text((curr_x, curr_b_y), ch, fill=(34, 34, 34, 255), font=badge_font)
                        ch_w = draw.textbbox((0, 0), ch, font=badge_font)[2] - draw.textbbox((0, 0), ch, font=badge_font)[0]
                        curr_x += ch_w + tracking_px
                    curr_b_y += b_line_h

            # ── 6. HEADLINE (LARGE BOLD SERIF 56pt, #222222) ──
            if title_text:
                clean_title = ImageTools._clean_emoji_for_rendering(title_text).strip()
                if " — " in clean_title:
                    clean_title = clean_title.split(" — ")[0].strip()
                elif " - " in clean_title:
                    clean_title = clean_title.split(" - ")[0].strip()
                elif "|" in clean_title:
                    clean_title = clean_title.split("|")[0].strip()
                    
                lines = ImageTools._wrap_text(clean_title, serif_font_title, card_w - 40, draw)
                lines = lines[:2]  # Maximum two lines
                
                line_bbox = draw.textbbox((0, 0), "Ag", font=serif_font_title)
                line_height = line_bbox[3] - line_bbox[1] + 12
                
                title_start_y = card_y + card_h + 30
                current_y = title_start_y
                for line in lines:
                    line_bbox = draw.textbbox((0, 0), line, font=serif_font_title)
                    line_w = line_bbox[2] - line_bbox[0]
                    draw.text(
                        ((canvas_w - line_w) // 2, current_y),
                        line,
                        fill=(26, 26, 26, 255),  # #1A1A1A High Contrast Text
                        font=serif_font_title
                    )
                    current_y += line_height

                # ── 7. ROUNDED COLOR-HARMONIZED CTA BUTTON (LARGE BOLD FONT 30pt) ──
                cta_str = ImageTools._clean_emoji_for_rendering(current_cta.strip())

                cta_bbox = draw.textbbox((0, 0), cta_str, font=sans_font_cta)
                cta_w = cta_bbox[2] - cta_bbox[0]
                cta_h = cta_bbox[3] - cta_bbox[1]
                
                cta_px, cta_py = 40, 16
                btn_w = cta_w + cta_px * 2
                btn_h = cta_h + cta_py * 2
                
                btn_top = current_y + 24
                if btn_top + btn_h < canvas_h - 20:
                    btn_left = (canvas_w - btn_w) // 2
                    
                    # Harmonized CTA fill (ACCENT_FILL)
                    draw.rounded_rectangle(
                        [btn_left, btn_top, btn_left + btn_w, btn_top + btn_h],
                        radius=32,
                        fill=ACCENT_FILL,
                        outline=(217, 206, 194, 255),
                        width=1
                    )
                    
                    # Crisp white CTA text
                    draw.text(
                        ((canvas_w - cta_w) // 2, btn_top + cta_py - 2),
                        cta_str,
                        fill=(255, 255, 255, 255),
                        font=sans_font_cta
                    )

            # ── 8. VERIFIED AMBER GOLDEN STAR SOCIAL PROOF RATING (LARGE 24pt FONT) ──
            if rating_text:
                clean_rating_num = rating_text.replace("★", "").replace("⭐", "").strip()
                if clean_rating_num:
                    text_font = ImageTools._get_system_font("sans_bold", 24, category="beauty")
                    t_bbox = draw.textbbox((0, 0), clean_rating_num, font=text_font)
                    t_w = t_bbox[2] - t_bbox[0]
                    
                    star_size = 24
                    gap = 10
                    total_r_w = star_size + gap + t_w
                    start_r_x = (canvas_w - total_r_w) // 2
                    r_y = btn_top + btn_h + 18 if title_text else card_y + card_h + 44
                    
                    if r_y < canvas_h - 10:
                        # 1. Draw 100% Vector Golden Amber Star ★ (#F5A623)
                        star_center_x = start_r_x + (star_size // 2)
                        star_center_y = r_y + (t_bbox[3] - t_bbox[1]) // 2 + 1
                        
                        ImageTools._draw_golden_star(draw, star_center_x, star_center_y, radius=12.0, fill=(245, 166, 35, 255))
                        
                        # 2. Draw Crystal-Clear Dark Charcoal Rating Text (#222222)
                        draw.text((start_r_x + star_size + gap, r_y), clean_rating_num, fill=(34, 34, 34, 255), font=text_font)

            # Save high resolution JPEG
            final_img = canvas.convert("RGB")
            final_img.save(out_path, format="JPEG", quality=95)
            logger.info("✅ VIOLET GREY + RHODE + SEPHORA Ultra-Luxury Pin generated! │ path=%s", out_path)
            
            return str(out_path)

        except Exception as exc:
            logger.error("Failed to generate BADDIES BEAUTY Pin: %s", exc, exc_info=True)
            return input_image_path
