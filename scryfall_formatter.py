import enum
from uu import Error
import scrython
import imageio.v3 as imageio
import os
import numpy as np
import subprocess
from pathlib import Path
import glob
import sys

# Path to the Upscayl binary
UPSCAYL = "/Applications/Upscayl.app/Contents/Resources/bin/upscayl-bin"

UPSCAYL_ENABLE = 1

STAMP_REMOVAL_ENABLE = 0

# Path to the folder where Upscayl keeps its models
MODELS = "/Users/sandh312/Downloads/realesrgan-ncnn-vulkan-20220424-macos/models"

# Directory used for caching upscaled images to avoid re-upscaling when we just want to re-format
CACHE_DIR = "imgcache"
# Directory used for storing formatted images
FORMATTED_DIR = "formatted"
# Directory used to store upscaled emages
UPSCAYLD = "upscayld"
# ! DO NOT TOUCH. Redacting the copyright ultimately depend on these numbers
# See PNG output size at https://scryfall.com/docs/api/images
SCRYFALL_BASE_SIZE = (745, 1040)

STAMP_COLOR = [98, 99, 98]

border_factor = 3 / 4  # adjust this if the borders are overlapping with any frames

# We upscale SCRYFALL_BASE_SIZE by x2 which results in a 600dpi image at 2.5" x 3.5" (596dpi to be exact)
# If you want more DPI you might need to change this number to 4 (the upscaling model does not support x3)
UPSCALE_FACTOR = 1

# No need to touch
DEBUG = False


class CardFrame(enum.Enum):
    MODERN = 1
    RETRO = 0

    @classmethod
    def from_card(cls, card):
        card_frame = card["frame"]
        if card_frame == "2015":
            return CardFrame.MODERN
        else:
            return CardFrame.RETRO


class CardType(enum.Enum):
    CREATURE = 1
    PLANESWALKER = 2
    RETRO = 3
    OTHER = 4

    @classmethod
    def from_card(cls, card):
        if "power" and "toughness" in card:
            return CardType.CREATURE
        elif "loyalty" in card:
            return CardType.PLANESWALKER
        elif "retro" in card:
            return CardType.RETRO
        else:
            return CardType.OTHER


class RedactBoxType(enum.Enum):
    MODERN_COPYRIGHT_DEFAULT = (430, 700, 970, 1040)
    MODERN_COPYRIGHT_CREATURE = (430, 700, 990, 1040)
    MODERN_COPYRIGHT_CREATURE_EXTRA_UNIVERSES_BEYOND = (430, 575, 970, 1040)
    MODERN_COPYRIGHT_PLANESWALKER = (430, 700, 990, 1040)

    def redactBox(self) -> tuple:
        return tuple([i * UPSCALE_FACTOR for i in self.value])


def search_and_process_card(query):
    query = query.strip()

    # If advanced search syntax is used
    if ":" in query or "=" in query:
        results = scrython.cards.Search(q=query).data

        if not results:
            print(f"No results found for: {query}")
            return

        card = results[0]

    # Otherwise do a name lookup
    else:
        card = scrython.cards.Named(exact=query)

    card = card.to_dict()

    if "card_faces" in card:

        for face_number, face_card in enumerate(card["card_faces"]):
            process_card(
                card=card,
                frame=CardFrame.from_card(card),
                type=CardType.from_card(face_card),
                image_uris=face_card["image_uris"],
                face_number=face_number,
            )
    else:
        process_card(
            card=card,
            frame=CardFrame.from_card(card),
            type=CardType.from_card(card),
            image_uris=card["image_uris"],
            face_number=None,
        )


def draw_corner_triangle(im, size=48, color=(0, 0, 0)):
    h, w, _ = im.shape
    size = min(size, h, w)

    y, x = np.ogrid[:size, :size]
    mask = (x + y) < size

    # Top-left
    im[:size, :size][mask] = color

    # Top-right
    im[:size, -size:][mask[:, ::-1]] = color

    # Bottom-left
    im[-size:, :size][mask[::-1, :]] = color

    # Bottom-right
    im[-size:, -size:][mask[::-1, ::-1]] = color

    return im


def process_card(card, frame, type, image_uris, face_number=None):
    # Using / in image names does not play were well with Linux
    cardname = f"{card['name'].replace('//', '&')}#{card['set'].upper()}#{(card['collector_number'])}"
    if face_number is not None:
        cardname += f"#face{face_number + 1}"
    print(f"[[{cardname}]] Found card: {card['scryfall_uri']}")

    if DEBUG:
        debug_path = os.path.join(CACHE_DIR, cardname + "_scryfall_original" + ".png")
        imageio.imwrite(debug_path, imageio.imread(image_uris["png"]))

    formatted_path = os.path.join(FORMATTED_DIR, cardname + ".png")
    cached_path = os.path.join(CACHE_DIR, cardname + ".png")
    upscayld_path = os.path.join(UPSCAYLD, f"{cardname}_upscaled.png")

    bypass_extension = False

    if os.path.exists(upscayld_path):
        print(f"[[{cardname}]] Already upscayled")
        return
    elif os.path.exists(formatted_path):
        print(f"[[{cardname}]] Already formatted")
        bypass_extension = True
    elif os.path.exists(cached_path):
        print(f"[[{cardname}]] Using cached upscaled image, reformatting...")
        im = imageio.imread(cached_path)
    else:
        print(f"[[{cardname}]] No cached image found, downloading from Scryfall...")
        im = imageio.imread(image_uris["png"])
        imageio.imwrite(cached_path, im.astype(np.uint8))
        print(f"[[{cardname}]] Image saved to cache")

    if not bypass_extension:
        # Pick a "band" from the border of the card to use as the border colour
        bordercolour = np.median(
            im[(im.shape[0] - 32) :, 200 : (im.shape[1] - 200)], axis=(0, 1)
        )

        # Remove copyright line
        match frame:
            case CardFrame.MODERN:
                match type:
                    case CardType.CREATURE:
                        box = RedactBoxType.MODERN_COPYRIGHT_CREATURE.redactBox()
                        # Universes Beyond cards have an extra copyright line which is shifted
                        # depending on the type of the card
                        box_ub = (
                            RedactBoxType.MODERN_COPYRIGHT_CREATURE_EXTRA_UNIVERSES_BEYOND.redactBox()
                        )
                    case CardType.PLANESWALKER:
                        box = RedactBoxType.MODERN_COPYRIGHT_PLANESWALKER.redactBox()
                        box_ub = None
                    case CardType.OTHER:
                        box = RedactBoxType.MODERN_COPYRIGHT_DEFAULT.redactBox()
                        box_ub = None

                leftPix, rightPix, topPix, bottomPix = box
                im[topPix:bottomPix, leftPix:rightPix, :] = bordercolour
                if box_ub:
                    leftPix, rightPix, topPix, bottomPix = box_ub
                    im[topPix:bottomPix, leftPix:rightPix, :] = bordercolour

        # --- Normalize image before padding ---
        # If RGBA, set transparent pixels to black and drop alpha
        if im.shape[2] == 4:
            alpha = im[:, :, 3]

            # Set RGB to black where fully transparent
            im[alpha == 0, 0] = 0
            im[alpha == 0, 1] = 0
            im[alpha == 0, 2] = 0

            # Drop alpha channel
            im = im[:, :, :3]
        # Pad image
        pad = 40 * UPSCALE_FACTOR  # Pad image by 1/8th of inch on each edge
        bordertol = 32  # Overfill onto existing border by 32px to remove white corners

        if card["full_art"]:
            print("Full art card identified")
            bordertol = 0
            pad = 0

        im_padded = np.zeros([im.shape[0] + 2 * pad, im.shape[1] + 2 * pad, 3])

        for i in range(0, 3):
            im_padded[pad : im.shape[0] + pad, pad : im.shape[1] + pad, i] = im[:, :, i]
            # Ensure border colour matches image channels (RGB vs RGBA)

        bordercolour = bordercolour[: im_padded.shape[2]]

        # Only overfill if bordertol > 0
        if bordertol > 0:
            # Left
            im_padded[:, 0 : int((pad + bordertol) * border_factor), :] = bordercolour

            # Right
            im_padded[
                :,
                im_padded.shape[1]
                - int((pad + bordertol) * border_factor) : im_padded.shape[1],
                :,
            ] = bordercolour
            # Top overlap less for legendary name border
            im_padded[0 : int((pad + bordertol) * border_factor), :, :] = bordercolour
            # Bottom
            im_padded[
                im_padded.shape[0]
                - int((pad + bordertol) * border_factor) : im_padded.shape[0],
                :,
                :,
            ] = bordercolour
            im_padded = draw_corner_triangle(im_padded, size=0, color=bordercolour)

        # full art cards will need a 30 pixel offset for the stamp to be covered
        if (
            card["frame"] == "2015"
            and (card["rarity"] == "rare" or card["rarity"] == "mythic")
            and card["security_stamp"] == "oval"
            and STAMP_REMOVAL_ENABLE
            and not card["full_art"]
        ):
            h_img, w_img, _ = im_padded.shape

            # --- Holostamp position (relative, not hard-coded) ---
            cx = int(w_img * 0.50)  # centered horizontally
            cy = int(h_img * 0.90)  # near bottom

            rx = int(w_img * 0.045)  # horizontal radius
            ry = int(h_img * 0.018)  # vertical radius

            # --- Build ellipse mask ---
            y, x = np.ogrid[:h_img, :w_img]
            mask = ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1

            # --- Apply border colour ---
            im_padded[mask] = bordercolour
        elif (
            card["frame"] == "2015"
            and (card["rarity"] == "rare" or card["rarity"] == "mythic")
            and card["security_stamp"] == "triangle"
            and STAMP_REMOVAL_ENABLE
            and not card["full_art"]
        ):
            h_img, w_img, _ = im_padded.shape
            width = int(w_img * 0.1)
            height = int(h_img * 0.045)
            # --- Triangle position (relative) ---
            cx = int(w_img * 0.50)  # centered horizontally
            cy = int(h_img * 0.905)  # near bottom

            # Triangle vertices (pointing up)
            p1 = (cx, cy + height // 2)  # tip of triangle pointing down
            p2 = (cx - width // 2, cy - height // 2)  # top left
            p3 = (cx + width // 2, cy - height // 2)  # top right

            # --- Build mask using barycentric technique ---
            y, x = np.mgrid[:h_img, :w_img]

            def sign(px, py, ax, ay, bx, by):
                return (px - bx) * (ay - by) - (ax - bx) * (py - by)

            b1 = sign(x, y, *p1, *p2) < 0.0
            b2 = sign(x, y, *p2, *p3) < 0.0
            b3 = sign(x, y, *p3, *p1) < 0.0

            mask = (b1 == b2) & (b2 == b3)

            im_padded[mask] = bordercolour

        # Write image to disk
        imageio.imwrite(formatted_path, im_padded.astype(np.uint8))
        print(f"[[{cardname}]] Formatted image saved to disk")

    if UPSCAYL_ENABLE:
        # upscale using upscyl
        output_upscaled = f"{UPSCAYLD}/{cardname}_upscaled.png"

        # Build Upscayl command
        cmd = [
            UPSCAYL,
            "-i",
            str(formatted_path),  # input file
            "-o",
            str(output_upscaled),  # output file
            "-n",
            "realesr-animevideov3-x4",  # model (choose your preferred model)
            "-s",
            "4",  # scale factor
            "-m",
            str(MODELS),  # model path
        ]

        # Run Upscayl
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            print(f"Upscayl failed for {cardname}: {result.stderr}")
        else:
            print(f"Upscaled image saved to {output_upscaled}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        UPSCAYLD = f"{sys.argv[1]}_upscayld"
    if not os.path.exists(FORMATTED_DIR):
        os.makedirs(FORMATTED_DIR)
    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR)
    if not os.path.exists(UPSCAYLD):
        os.makedirs(UPSCAYLD)

    # Loop through each card in cards.txt and scan em all
    with open("cards.txt", "r") as fp:
        cardSet = {}
        for cardname in fp:  # remove duplicates
            cardSet.add(cardname)

        for cardname in cardSet:
            search_and_process_card(cardname)
