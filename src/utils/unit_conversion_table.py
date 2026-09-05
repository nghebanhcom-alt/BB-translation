"""Standard baking unit conversion table injected into the translation prompt.

Source: Architecture.md section 6.2 ("Bang chuyen doi nguyen lieu" +
volume/temperature conversions), implementing BR-UNIT-01/02/03 (PRD section
4.7). Hard-coded per Dev task instructions rather than a DB table — the
values are an industry-standard baking reference, not user-editable data.
"""

VOLUME_TEMPERATURE_CONVERSIONS: list[tuple[str, str]] = [
    ("cups", "ml (1 cup = 240ml)"),
    ("tablespoon (tbsp)", "ml (1 tbsp = 15ml)"),
    ("teaspoon (tsp)", "ml (1 tsp = 5ml)"),
    ("ounces (oz)", "grams (theo bang nguyen lieu ben duoi)"),
    ("degrees Fahrenheit (°F)", "°C (cong thuc: (°F - 32) × 5/9, lam tron)"),
    ("inches", "cm (1 inch = 2.54cm)"),
]

INGREDIENT_CUP_WEIGHT_TABLE: list[tuple[str, str]] = [
    ("Bot mi (flour)", "120g"),
    ("Duong (sugar)", "200g"),
    ("Bo (butter)", "225g"),
    ("Sua (milk)", "240ml"),
    ("Kem tuoi (heavy cream)", "240ml"),
    ("Cacao (cocoa powder)", "85g"),
    ("Bot ngu coc (oats)", "90g"),
    ("Mat ong (honey)", "340g"),
    ("Dau an (oil)", "215ml"),
]


def build_unit_conversion_section() -> str:
    """Render the conversion rules + ingredient table as Markdown for the system prompt."""
    lines = ["3. Chuyen doi don vi do luong trong cong thuc:"]
    for unit, rule in VOLUME_TEMPERATURE_CONVERSIONS:
        lines.append(f"   - {unit} → {rule}")
    lines.append(
        "   CHI chuyen doi trong cong thuc/recipe. Trong van xuat, giu nguyen don vi goc."
    )
    lines.append("")
    lines.append("Bang chuyen doi nguyen lieu (1 cup US):")
    lines.append("| Nguyen lieu | 1 cup (US) |")
    lines.append("|------------|-----------|")
    for ingredient, weight in INGREDIENT_CUP_WEIGHT_TABLE:
        lines.append(f"| {ingredient} | {weight} |")
    return "\n".join(lines)
