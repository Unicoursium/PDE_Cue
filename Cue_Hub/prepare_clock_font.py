from pathlib import Path

from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "assets" / "clock_font.ttf"
OUTPUT = ROOT / "assets" / "clock_font_regular.ttf"
REGULAR_WEIGHT = 400


def main():
    if not SOURCE.exists():
        raise SystemExit(f"Missing source font: {SOURCE}")

    font = TTFont(SOURCE)

    if "fvar" not in font:
        raise SystemExit(f"{SOURCE.name} is not a variable font.")

    axes = {axis.axisTag for axis in font["fvar"].axes}
    if "wght" not in axes:
        raise SystemExit(f"{SOURCE.name} does not contain a wght axis.")

    regular = instantiateVariableFont(font, {"wght": REGULAR_WEIGHT})
    regular.save(OUTPUT)
    print(f"Created Regular clock font: {OUTPUT}")


if __name__ == "__main__":
    main()
