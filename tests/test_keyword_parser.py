"""
Unit tests for PinterestAgent.parse_product_keyword
"""

import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from agent.pinterest_agent import PinterestAgent


def test_parse_product_keyword():
    agent = PinterestAgent()

    # Problematic abstract design inputs from user logs
    kw1 = agent.parse_product_keyword("Design Aesthetic Mid Century Modern, Retro, Minimalist, Japandi")
    assert kw1 == "Minimalist Walnut Wood Floating Shelves", f"Expected fallback, got '{kw1}'"

    kw2 = agent.parse_product_keyword("Product Focus")
    assert kw2 == "Minimalist Walnut Wood Floating Shelves", f"Expected fallback, got '{kw2}'"

    kw3 = agent.parse_product_keyword("Design Aesthetic Japandi, Organic Modern, and Soft Minimalist")
    assert kw3 == "Minimalist Walnut Wood Floating Shelves", f"Expected fallback, got '{kw3}'"

    kw4 = agent.parse_product_keyword("Featured Home Decor Product Pick")
    assert kw4 == "Minimalist Walnut Wood Floating Shelves", f"Expected fallback, got '{kw4}'"

    kw5 = agent.parse_product_keyword("Styling Placement Ideas")
    assert kw5 == "Minimalist Walnut Wood Floating Shelves", f"Expected fallback, got '{kw5}'"

    # Valid physical products with formatting issues
    kw6 = agent.parse_product_keyword("Mid Century Mushroom Table Lamp (Retro")
    assert kw6 == "Mid Century Mushroom Table Lamp Retro", f"Got '{kw6}'"

    kw7 = agent.parse_product_keyword("Selected product keyword: Aesthetic Scalloped Edge Lacquer Tray")
    assert kw7 in ["Aesthetic Scalloped Edge Lacquer Tray", "Scalloped Edge Lacquer Tray"], f"Got '{kw7}'"

    kw8 = agent.parse_product_keyword("Electric Candle Lighter Rechargeable")
    assert kw8 == "Electric Candle Lighter Rechargeable", f"Got '{kw8}'"

    kw9 = agent.parse_product_keyword("Checkered Tufted Area Rug")
    assert kw9 == "Checkered Tufted Area Rug", f"Got '{kw9}'"

    print("✅ All parse_product_keyword unit tests passed successfully!")


if __name__ == "__main__":
    test_parse_product_keyword()
