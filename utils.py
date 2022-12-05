from math import cos, degrees, fabs, radians, sin
from pathlib import Path

from django.conf import settings
from ezdxf import colors
from PIL import Image
from pyproj import CRS
from pyproj.aoi import AreaOfInterest
from pyproj.database import query_utm_crs_info

"""
    Collection of utilities
"""


def cad2hex(color):
    if isinstance(color, tuple):
        return "#{:02x}{:02x}{:02x}".format(color[0], color[1], color[2])
    rgb24 = colors.DXF_DEFAULT_COLORS[color]
    return "#{:06X}".format(rgb24)


def xy2latlong(vert, longp, latp, rot, xsc, ysc):
    trans = []
    gy = 1 / (6371 * 1000)
    gx = gy * 1 / (fabs(cos(radians(latp))))
    for v in vert:
        # use temp variables
        x = v[0] * xsc
        y = v[1] * ysc
        # get true north
        xr = x * cos(rot) - y * sin(rot)
        yr = x * sin(rot) + y * cos(rot)
        # objects are very small with respect to earth, so our transformation
        # from CAD x,y coords to latlong is approximate
        long = longp + degrees(xr * gx)
        lat = latp + degrees(yr * gy)
        trans.append([long, lat])
    return trans


def latlong2xy(vert, longp, latp):
    trans = []
    for v in vert:
        x = -6371000 * (radians(longp - v[0])) * cos(radians(latp))
        y = -6371000 * (radians(latp - v[1]))  # verify
        trans.append((x, y))
    return trans


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


utm_crs_list = query_utm_crs_info(
    datum_name="WGS 84",
    area_of_interest=AreaOfInterest(
        west_lon_degree=-93.581543,
        south_lat_degree=42.032974,
        east_lon_degree=-93.581543,
        north_lat_degree=42.032974,
    ),
)
utm_crs = CRS.from_epsg(utm_crs_list[0].code)  # noqa
