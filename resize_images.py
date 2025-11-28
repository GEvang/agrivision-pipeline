#!/usr/bin/env python3
import argparse
from pathlib import Path
from PIL import Image

def resize_images(input_dir, output_dir, max_size, quality):
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Valid extensions
    exts = {".jpg", ".jpeg", ".JPG", ".JPEG"}

    files = [f for f in input_path.iterdir() if f.suffix in exts]

    if not files:
        print(f"No JPG/JPEG images found in {input_path}")
        return

    print(f"Found {len(files)} images in {input_path}")
    print(f"Resizing so longest side <= {max_size}px, quality={quality}")
    print(f"Saving to: {output_path}")
    print("-" * 40)

    for f in files:
        try:
            img = Image.open(f)
        except Exception as e:
            print(f"Skipping {f.name}: cannot open ({e})")
            continue

        w, h = img.size
        longest_side = max(w, h)

        if longest_side <= max_size:
            # No resizing needed, just recompress / copy
            new_size = (w, h)
            resized = img
        else:
            scale = max_size / longest_side
            new_size = (int(w * scale), int(h * scale))
            resized = img.resize(new_size, Image.LANCZOS)

        out_path = output_path / f.name

        # Save as JPEG with desired quality
        resized = resized.convert("RGB")
        resized.save(out_path, "JPEG", quality=quality)

        print(f"{f.name}: {w}x{h} -> {new_size[0]}x{new_size[1]}")

    print("-" * 40)
    print("Done.")

def main():
    parser = argparse.ArgumentParser(
        description="Resize and recompress JPG images in a folder."
    )
    parser.add_argument(
        "--input",
        "-i",
        default="images_full",
        help="Input folder with original images (default: images_full)",
    )
    parser.add_argument(
        "--output",
        "-o",
        default="images_resized",
        help="Output folder for resized images (default: images_resized)",
    )
    parser.add_argument(
        "--max-size",
        "-m",
        type=int,
        default=2500,
        help="Maximum size (pixels) of the longest side (default: 2500)",
    )
    parser.add_argument(
        "--quality",
        "-q",
        type=int,
        default=80,
        help="JPEG quality (1-100, default: 80)",
    )

    args = parser.parse_args()
    resize_images(args.input, args.output, args.max_size, args.quality)

if __name__ == "__main__":
    main()
