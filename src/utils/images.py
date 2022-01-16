import io
from typing import Tuple, List, Union

from PIL import Image, ImageFont, ImageDraw

from resources import RESOURCE_PATH


def create_collage(
    row_size: int,
    image_list: List[bytes],
    padding: int = 0,
    resize_to: Tuple[int, int] = None,
) -> bytes:

    max_height = 0
    max_width = 0

    ims = []
    for p in image_list:
        im = Image.open(io.BytesIO(p))
        if resize_to:
            im.thumbnail(resize_to)
        max_height = max(max_height, im.height)
        max_width = max(max_width, im.width)
        ims.append(im)

    ims = list(reversed(ims))

    total_width = total_height = 0
    x = y = 0
    col_idx = 0
    max_height = 0
    to_be_pasted = []
    while ims:
        if col_idx >= row_size:
            y += max_height
            col_idx = x = max_height = 0

        im = ims.pop()
        max_height = max(max_height, im.height + padding * 2)

        to_be_pasted.append((im, (x + padding, y + padding)))

        x += im.width + padding * 2
        col_idx += 1

        total_width = max(total_width, x)
        total_height = y + max_height

    new_im = Image.new("RGBA", (total_width, total_height))
    for im, pos in to_be_pasted:
        new_im.paste(im, pos)

    with io.BytesIO() as output:
        new_im.save(output, format="PNG")
        return output.getvalue()


IMAGE_BACKGROUND_COLOR = "#A4A4A4"
LABEL_BACKGROUND_COLOR = "#E9E5DC"
LABEL_COLOR = "#495366"
LABEL_HEIGHT = 16
OFF_CORNER_SIZE = 14


font = ImageFont.truetype(str(RESOURCE_PATH / "genshin.ttf"), 12, encoding="unic")


def create_image_with_label(image: Union[bytes], label: str, resize_to=None) -> bytes:
    """
    Create an image with a label at the bottom in Genshin style.
    """
    im = Image.open(io.BytesIO(image))
    if resize_to:
        im.thumbnail(resize_to)

    # Gets font and label size
    label_width, label_height = font.getsize(label)

    # Creates a new image
    new_im = Image.new(
        "RGBA", (im.width, im.height + LABEL_HEIGHT), color=IMAGE_BACKGROUND_COLOR
    )
    draw = ImageDraw.Draw(new_im)

    # Create label layer
    label_im = Image.new(
        "RGBA", (new_im.width, OFF_CORNER_SIZE + LABEL_HEIGHT), LABEL_BACKGROUND_COLOR
    )
    label_mask = Image.new("L", label_im.size, 255)
    label_mask_draw = ImageDraw.Draw(label_mask)
    label_mask_draw.rounded_rectangle(
        (-OFF_CORNER_SIZE, -OFF_CORNER_SIZE, label_mask.width, OFF_CORNER_SIZE),
        fill=0,
        radius=OFF_CORNER_SIZE,
    )

    # Pastes in the entity image
    new_im.paste(im, (0, 0), mask=im)
    # Pastes in the label background
    new_im.paste(label_im, (0, im.height - OFF_CORNER_SIZE), mask=label_mask)
    # Add label
    label_x = (im.width - label_width) // 2
    label_y = im.height + (LABEL_HEIGHT - label_height) // 2
    draw.text((label_x, label_y), label, LABEL_COLOR, font)

    # Add rounded alpha mask
    rounded_mask = Image.new("L", new_im.size, 0)
    rounded_mask_draw = ImageDraw.Draw(rounded_mask)
    rounded_mask_draw.rounded_rectangle(
        (0, 0, new_im.width, new_im.height), fill=255, width=5, radius=5
    )
    new_im.putalpha(rounded_mask)

    with io.BytesIO() as output:
        new_im.save(output, format="PNG")
        return output.getvalue()


def create_label(label: str, color="white", padding=0) -> bytes:
    label_width, label_height = font.getsize(label)
    label_im = Image.new(
        "RGBA", (label_width + padding * 2, label_height + padding * 2)
    )
    draw = ImageDraw.Draw(label_im)
    draw.text((padding, padding), label, color, font)

    with io.BytesIO() as output:
        label_im.save(output, format="PNG")
        return output.getvalue()
