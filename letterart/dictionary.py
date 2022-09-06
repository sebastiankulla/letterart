import os
import xml.etree.ElementTree as ET
from svgpathtools import bezier_bounding_box, parse_path
import os

FILE_NAME = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'alphabet.svg')
ALPHABET = r'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyzäöüÄÖÜ.,:;1234567890?'

tree = ET.parse(FILE_NAME)
root = tree.getroot()


class Letter:
    stroke = "black"
    stroke_width = "50"

    def __init__(self, element: ET.Element):
        self.d = element.attrib['d'].split()
        self.box_rel = self.calc_box_rel()
        self.width = self.calc_width()
        self.height = self.calc_height()

    def calc_width(self):
        return self.box_rel[1] - self.box_rel[0]

    def calc_height(self):
        return self.box_rel[3] - self.box_rel[2]

    def __str__(self):
        return f"""<path d="{' '.join(self.d)}" stroke="{self.stroke}" stroke-width="{self.stroke_width}" fill="none"/>"""

    @property
    def abs_center(self):
        xmin, xmax, ymin, ymax = self.box_rel
        xmin += self.x_coord
        ymin += self.y_coord
        xmax += self.x_coord
        ymax += self.y_coord
        return (round(xmin + (xmax - xmin) / 2), round(ymin + (ymax - ymin) / 2))

    @property
    def x_coord(self):
        return int(self.d[0].replace('M', ''))

    @property
    def y_coord(self):
        return int(self.d[1])

    def calc_box_rel(self):
        d_string = " ".join(self.d)
        path = parse_path(d_string)

        xmin_list, xmax_list, ymin_list, ymax_list = [], [], [], [],
        for elem in path:
            xmin, xmax, ymin, ymax = (bezier_bounding_box(elem))
            xmin_list.append(xmin)
            xmax_list.append(xmax)
            ymin_list.append(ymin)
            ymax_list.append(ymax)

        xmin = round(min(xmin_list)) - self.x_coord
        ymin = round(min(ymin_list)) - self.y_coord
        xmax = round(max(xmax_list)) - self.x_coord
        ymax = round(max(ymax_list)) - self.y_coord
        return xmin, xmax, ymin, ymax

    def move_to_location(self, x: int, y: int):
        new_x = x - self.box_rel[0]
        new_y = y - self.box_rel[3]

        self.d[0] = f"M{new_x}"
        self.d[1] = str(new_y)

    def set_strokewidth(self, stroke_width: str):
        self.stroke_width = stroke_width

    def set_stroke(self, stroke: str):
        self.stroke = stroke

    def draw_box(self):
        min_x, max_x, min_y, max_y = self.box_rel
        min_x += self.x_coord
        min_y += self.y_coord
        return f"""<rect x="{min_x}" y="{min_y}" width="{self.width}" height="{self.height}" fill="none" stroke="white" stroke-width="25" /> """


svg_dict = {}
paths = root.findall(r'.//{http://www.w3.org/2000/svg}path')

for letter, path in zip(ALPHABET, paths):
    svg_dict[letter] = Letter(path)
