from pathlib import Path

from django.conf import settings
from ezdxf import colors
from PIL import Image

"""
    Collection of utilities
"""


def cad2hex(color):
    if isinstance(color, tuple):
        return "#{:02x}{:02x}{:02x}".format(color[0], color[1], color[2])
    rgb24 = colors.DXF_DEFAULT_COLORS[color]
    return "#{:06X}".format(rgb24)


def check_wide_image(fb_image):
    """
    Checks if image is suitable for wide version. Performs 'version_generate',
    then controls dimensions. If small, pastes the image on a 1600x800 black
    background replacing original wide version. fb_image is a Fileobject.
    """
    img = fb_image.version_generate("wide")
    if img.width < 1600 or img.height < 800:
        path = Path(settings.MEDIA_ROOT).joinpath(fb_image.version_path("wide"))
        img = Image.open(path)
        back = Image.new(img.mode, (1600, 800))
        position = (
            int((back.width - img.width) / 2),
            int((back.height - img.height) / 2),
        )
        back.paste(img, position)
        back.save(path)
