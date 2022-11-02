from __future__ import annotations
from lxml import etree
from typing import Optional
from enum import Enum
from copy import deepcopy
from functools import cache
import re
from fontTools import ttx

SVG_LETTER_DICT = {",": "comma", ":": "colon", ".": "period", "0": "zero", "1": "one", "2": "two", "3": "three",
                   "4": "four", "5": "five", "6": "six", "7": "seven", "8": "eight", "9": "nine"}


class SVGCommands(Enum):
    M = "M"
    L = "L"
    Q = "Q"
    Z = "Z"
    l = "l"
    q = "q"


class TTFInstruction:
    def __init__(self, point_xml: etree.Element = None):
        self.x = int(point_xml.attrib["x"])
        self.y = int(point_xml.attrib["y"])
        self.on_line = True if point_xml.attrib["on"] == "1" else False

    def __repr__(self):
        return f"TTFInstruction(x={self.x}, y={self.y}, on_line={self.on_line})"


class SVGInstruction:
    def __init__(self, command: SVGCommands, coordinates: list[int]):
        self.command = command
        self.coordinates = coordinates
        if len(coordinates) == 0:
            self.has_coordinates = False
        else:
            self.has_coordinates = True

    @property
    def text(self) -> str:
        return f"{self.command.value} {' '.join(map(str, self.coordinates))} "

    def __str__(self):
        return f"{self.command.value} {' '.join(map(str, self.coordinates))} "


class Contour:
    def __init__(self):
        self.svg_instructions: list[SVGInstruction] = []
        self.fill: str = "none"
        self.stroke_width: int = 10
        self.stroke: str = "black"
        self.transform: str = ""

    def add_svg_instructions(self, list_svg_instructions: list[SVGInstruction]):
        self.svg_instructions = list_svg_instructions
        self.initial_mx = self.svg_instructions[0].coordinates[0]
        self.initial_my = self.svg_instructions[0].coordinates[1]

    @property
    def text(self) -> str:
        temp_string = "\n"
        for instruction in self.svg_instructions:
            temp_string += instruction.text
        temp_string += "\n"
        return temp_string

    def transform_to_relative_coordinates(self):
        copied_instructions = deepcopy(self.svg_instructions)
        need_transformation = any(instruction.command.value.isupper() for instruction in copied_instructions[1:])
        if not need_transformation:
            return
        for idx in range(1, len(self.svg_instructions)):
            previous_instruction = copied_instructions[idx - 1]
            instruction = self.svg_instructions[idx]
            if len(instruction.coordinates) == 2:
                prev_coords = previous_instruction.coordinates[-2:]
                instruction.command = SVGCommands(instruction.command.value.lower())
                instruction.coordinates[0] = instruction.coordinates[0] - prev_coords[0]
                instruction.coordinates[1] = instruction.coordinates[1] - prev_coords[1]
            elif len(instruction.coordinates) == 4:
                instruction.command = SVGCommands(instruction.command.value.lower())
                prev_coords = previous_instruction.coordinates[-2:]
                instruction.coordinates[0] = instruction.coordinates[0] - prev_coords[0]
                instruction.coordinates[1] = instruction.coordinates[1] - prev_coords[1]
                instruction.coordinates[2] = instruction.coordinates[2] - prev_coords[0]
                instruction.coordinates[3] = instruction.coordinates[3] - prev_coords[1]

    def flip_horizontally(self):
        for instruction in self.svg_instructions:
            if len(instruction.coordinates) == 0:
                continue
            if instruction.command == SVGCommands.M:
                instruction.coordinates[1] = -instruction.coordinates[1]
                continue

            instruction.coordinates[1] = -instruction.coordinates[1]
            if len(instruction.coordinates) == 4:
                instruction.coordinates[3] = -instruction.coordinates[3]

    def flip_vertically(self):
        for instruction in self.svg_instructions:
            if len(instruction.coordinates) == 0:
                continue
            if instruction.command == SVGCommands.M:
                instruction.coordinates[0] = -instruction.coordinates[0]
                continue
            instruction.coordinates[0] = -instruction.coordinates[0]
            if len(instruction.coordinates) == 4:
                instruction.coordinates[2] = -instruction.coordinates[2]

    def __getitem__(self, item):
        return self.svg_instructions[item]

    def anchor_contour(self):
        self.initial_mx = self.svg_instructions[0].coordinates[0]
        self.initial_my = self.svg_instructions[0].coordinates[1]

    def move_to(self, x_coord, y_coord):
        entry_point = self.svg_instructions[0]
        entry_point.coordinates[0] = self.initial_mx + x_coord
        entry_point.coordinates[1] = self.initial_my + y_coord

    def __str__(self):
        result = """<path d=" """
        for instruction in self.svg_instructions:
            result += str(instruction)
        result += f""" " fill="{self.fill}" stroke="{self.stroke}" stroke-width="{self.stroke_width}"/>\n"""
        return result


class Glyph:
    def __init__(self, name: str, viewbox: list[int]):
        self.name = name
        self.viewbox = viewbox
        self.initial_viewbox = viewbox
        self.contours: list[Contour] = []
        self.x_coord: int = 0
        self.y_coord: int = 0

    def add_contours(self, contour_list: list[Contour]):
        self.contours.extend(contour_list)

    def __getitem__(self, item):
        try:
            return self.contours[item]
        except Exception:
            raise IndexError(f"Glyph only has {len(self.contours)} contours")

    def flip_horizontally(self):
        for contour in self.contours:
            contour.flip_horizontally()
        self.viewbox[1] = -self.viewbox[3]
        self.viewbox[3] = -self.viewbox[1]

    def flip_vertically(self):
        for contour in self.contours:
            contour.flip_horizontally()
            self.viewbox[0] = -self.viewbox[2]
            self.viewbox[2] = -self.viewbox[0]

    @property
    def viewbox_str(self):
        return f"{' '.join(map(str, self.viewbox))}"

    def transform_to_relative_coordinates(self):
        for contour in self.contours:
            contour.transform_to_relative_coordinates()

    def move_to(self, x_coord, y_coord):
        self.x_coord = x_coord
        self.y_coord = y_coord
        self.viewbox[0] = self.initial_viewbox[0] + x_coord
        self.viewbox[1] = self.initial_viewbox[1] + y_coord
        self.viewbox[2] = self.initial_viewbox[2] + x_coord
        self.viewbox[3] = self.initial_viewbox[3] + y_coord
        for contour in self.contours:
            contour.move_to(x_coord, y_coord)


    def anchor_contours(self):
        for contour in self.contours:
            contour.anchor_contour()

    @property
    def height(self):
        return self.viewbox[3] - self.viewbox[1]

    @property
    def width(self):
        return self.viewbox[2] - self.viewbox[0]

    def set_strokewidth(self, width):
        for contour in self.contours:
            contour.stroke_width = width

    @property
    def abs_center(self):
        xmin = self.viewbox[0]
        ymin = self.viewbox[1]
        xmax = self.viewbox[2]
        ymax = self.viewbox[3]
        return (round(xmin + (xmax - xmin) / 2), round(ymin + (ymax - ymin) / 2))

    def __str__(self):
        result = ""
        for contour in self.contours:
            result += str(contour)
        return result


class Alphabet:
    def __init__(self, filename: Optional[str] = None):
        self.glyphs: list[Glyph] = []
        if filename is not None:
            self.glyphs = self.load_glyphs_from_file(filename)

    def load_glyphs_from_file(self, filename: str):
        tree = etree.parse(filename)
        root = tree.getroot()
        glyphs = root.findall(".//glyph")
        new_glyph_list = []
        for glyph in glyphs:
            new_glyph = Glyph(glyph.attrib["name"], list(map(int, glyph.attrib["viewBox"].split(" "))))
            contours = glyph.findall(".//contour")
            new_contours_list = []
            for contour in contours:
                new_contour = Contour()
                instructions = contour.findall(r".//instruction")
                new_svg_instructions = []
                for instruction in instructions:
                    command = SVGCommands(instruction.attrib["command"])
                    try:
                        coords = list(map(int, instruction.attrib['coordinates'].split(" ")))
                    except Exception:
                        coords = []
                    new_instruction = SVGInstruction(command, coords)
                    new_svg_instructions.append(new_instruction)
                new_contour.add_svg_instructions(new_svg_instructions)
                new_contours_list.append(new_contour)
            new_glyph.add_contours(new_contours_list)
            new_glyph_list.append(new_glyph)
        return new_glyph_list

    def save(self, destination: Optional[str] = None):
        if destination is None:
            destination = "alphabet.xml"
        exported_alphabet = etree.Element("alphabet")
        for glyph in self.glyphs:
            exported_glyph = etree.SubElement(exported_alphabet, "glyph",
                                              {"name": glyph.name, "viewBox": glyph.viewbox_str})
            for contour in glyph.contours:
                exported_contour = etree.SubElement(exported_glyph, "contour",
                                                    {"fill": contour.fill, "transform": contour.transform,
                                                     "stroke": contour.stroke,
                                                     "stroke-width": str(contour.stroke_width)})
                for instruction in contour.svg_instructions:
                    exported_instruction = etree.SubElement(exported_contour, "instruction",
                                                            {"command": instruction.command.value,
                                                             "coordinates": " ".join(
                                                                 map(str, instruction.coordinates))})

        et = etree.ElementTree(exported_alphabet)
        et.write(destination, pretty_print=True)

    def anchor_contours(self):
        for glyph in self.glyphs:
            glyph.anchor_contours()

    def __getitem__(self, item):
        try:
            glyph_name = SVG_LETTER_DICT.get(item, item)
            return [glyph for glyph in self.glyphs if glyph.name == glyph_name][0]
        except Exception:
            raise ModuleNotFoundError(f"{item} is not in Alphabet")

    def flip_horizontally(self):
        for glyph in self.glyphs:
            glyph.flip_horizontally()

    def flip_vertically(self):
        for glyph in self.glyphs:
            glyph.flip_vertically()

    def transform_to_relative_coordinates(self):
        for glyph in self.glyphs:
            glyph.transform_to_relative_coordinates()

    def show(self, filename):
        svg_code = ""
        svg_body = ""
        prev_x = 0
        prev_y = 1000
        MAX_X = 10000
        for glyph in self.glyphs:
            glyph.move_to(prev_x, prev_y)
            for contour in glyph.contours:
                svg_body += f"""<path d="{contour.text}" fill="{contour.fill}" stroke="{contour.stroke}" transform="{contour.transform}" stroke-width="{contour.stroke_width}"/>\n"""
            svg_body += f"""<circle cx="{prev_x}" cy="{prev_y}" r="25" fill="none" stroke="red" stroke-width="10" />\n"""
            prev_x += 1000
            if prev_x >= MAX_X:
                prev_x = 0
                prev_y += 1000

        HEADER = f"""<?xml version="1.0" standalone="no"?>
    <!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 20010904//EN"
            "http://www.w3.org/TR/2001/REC-SVG-20010904/DTD/svg10.dtd">
    <svg version="1.0" xmlns="http://www.w3.org/2000/svg"
         width="210mm" height="297mm" viewBox="0 0 {MAX_X} {abs(prev_y)}">"""

        FOOTER = "</svg>"

        svg_code += HEADER
        svg_code += svg_body
        svg_code += FOOTER
        with open(filename, 'w') as file:
            file.write(svg_code)


def load_ttx_file(filename: str) -> list:
    """
    load ttx file and return list of etree.Element with tag TTGlyph
    """
    tree = etree.parse(filename)
    root = tree.getroot()
    return root.findall(".//TTGlyph")


def get_max_y(filename: str) -> int:
    """
    load ttx file and return list of etree.Element with tag TTGlyph
    """
    tree = etree.parse(filename)
    root = tree.getroot()
    return int(root.findall(".//sxHeight")[0].attrib["value"])


def extract_alphabet(filename: str, flip_horizontally: Optional[bool] = False,
                     flip_vertically: Optional[bool] = False) -> Alphabet:
    """
    gets list of etree.Element with tag TTGlyph and returns a dict
    the key is the name of the glyph
    the value is a nested list of points
    """
    ttx.ttDump(filename, "temp.ttx", ttx.Options([], 1))
    alphabet = Alphabet()
    glyphs = load_ttx_file("temp.ttx")
    # box_size = get_max_y()

    for glyph in glyphs:
        try:
            viewbox = [int(glyph.attrib['xMin']), int(glyph.attrib['yMin']), int(glyph.attrib['xMax']),
                       int(glyph.attrib['yMax'])]
        except Exception:
            continue
        new_glyph = Glyph(glyph.attrib["name"], viewbox)
        new_glyph.add_contours(get_contours(glyph))
        components = glyph.findall(".//component")
        for component in components:
            glyph_component = [glyph for glyph in glyphs if glyph.attrib["name"] == component.attrib["glyphName"]][0]
            new_glyph.add_contours(
                get_contours(glyph_component, int(component.attrib["x"]), int(component.attrib["y"])))
        alphabet.glyphs.append(new_glyph)
    if flip_horizontally:
        alphabet.flip_horizontally()
    if flip_vertically:
        alphabet.flip_vertically()

    alphabet.anchor_contours()
    return alphabet


def get_contours(glyph: etree.Element, x_offset: int = 0, y_offset: int = 0) -> list[Contour]:
    """
    returns
    """
    contours = glyph.findall(".//contour")

    new_contour_list = []
    for contour in contours:
        new_contour = Contour()
        list_ttf_instructions = [TTFInstruction(point_xml) for point_xml in contour.findall(".//pt")]
        list_svg_instructions = transform_instruction_ttf_to_svg(list_ttf_instructions)
        new_contour.add_svg_instructions(list_svg_instructions)
        new_contour.transform_to_relative_coordinates()
        if x_offset != 0 or y_offset != 0:
            new_contour.move_to(x_offset, y_offset)
        new_contour_list.append(new_contour)
    return new_contour_list


def transform_instruction_ttf_to_svg(ttf_contour: list[TTFInstruction]) -> list[SVGInstruction]:
    if len(ttf_contour) == 0:
        return []

    svg_instructions_list = []

    idx = 1
    last_point = ttf_contour[-1]
    while idx < len(ttf_contour):
        first_point = ttf_contour[idx - 1]
        second_point = ttf_contour[idx]
        if idx == 1:
            if first_point.on_line:
                svg_instructions_list.append(SVGInstruction(SVGCommands.M, [first_point.x, first_point.y]))
            elif last_point.on_line:
                svg_instructions_list.append(SVGInstruction(SVGCommands.M, [last_point.x, last_point.y]))
            else:
                SyntaxError("Can't find the starting point")
        if first_point.on_line:
            if second_point.on_line:
                svg_instructions_list.append(SVGInstruction(SVGCommands.L, [second_point.x, second_point.y]))
                idx += 1
            else:
                idx += 1
            continue
        else:
            if second_point.on_line:
                svg_instructions_list.append(
                    SVGInstruction(SVGCommands.Q, [first_point.x, first_point.y, second_point.x, second_point.y]))
                idx += 1
                continue
            else:
                mid_point = (round((first_point.x + second_point.x) / 2), round((first_point.y + second_point.y) / 2))
                svg_instructions_list.append(
                    SVGInstruction(SVGCommands.Q, [first_point.x, first_point.y, mid_point[0], mid_point[1]]))
                idx += 1
                continue

    svg_instructions_list.append(SVGInstruction(SVGCommands.Z, []))
    return svg_instructions_list


def export_alphabet_xml(alphabet: Alphabet, destination: Optional[str] = None) -> None:
    if destination is None:
        destination = "alphabet.xml"
    exported_alphabet = etree.Element("alphabet")
    for glyph in alphabet.glyphs:
        # try:
        exported_glyph = etree.SubElement(exported_alphabet, "glyph",
                                          {"name": glyph.name, "viewBox": glyph.viewbox_str})
        for contour in glyph.contours:
            exported_contour = etree.SubElement(exported_glyph, "contour",
                                                {"fill": contour.fill, "transform": contour.transform,
                                                 "stroke": contour.stroke, "stroke-width": str(contour.stroke_width)})
            exported_contour.text = contour.text

    et = etree.ElementTree(exported_alphabet)
    et.write(destination, pretty_print=True)


def create_sentence(alphabet: Alphabet, sentence: str) -> Alphabet:
    letter_name_dict = {",": "comma", ":": "colon", ".": "period"}
    new_alphabet = Alphabet()
    for letter in sentence:
        if letter == " ":
            letter = "comma"

        letter_name = letter_name_dict.get(letter, letter)
        new_alphabet.glyphs.append(deepcopy(alphabet[letter_name]))
    return new_alphabet


class Sentence:
    def __init__(self, alphabet: Alphabet, sentence: str):
        self.alphabet = alphabet
        self.sentence = sentence
        self.sentence_glyphs = self.create_sentence_glyphs(alphabet, sentence)

    def create_sentence_glyphs(self, alphabet: Alphabet, sentence: str) -> list[Glyph]:
        letter_name_dict = {",": "comma", ":": "colon", ".": "period"}
        sentence_glyphs = []
        for letter in sentence:
            letter_name = letter_name_dict.get(letter, letter)
            sentence_glyphs.append(deepcopy(alphabet[letter_name]))

        return sentence_glyphs

    def show(self, filename):
        svg_code = ""
        svg_body = ""
        prev_x = 0
        prev_y = 1000
        MAX_X = 10000
        for glyph in self.sentence_glyphs:
            glyph.move_to(prev_x, prev_y)
            for contour in glyph.contours:
                svg_body += f"""<path d="{contour.text}" fill="{contour.fill}" stroke="{contour.stroke}" transform="{contour.transform}" stroke-width="{contour.stroke_width}"/>\n"""
            svg_body += f"""<circle cx="{prev_x}" cy="{prev_y}" r="25" fill="none" stroke="red" stroke-width="10" />\n"""
            prev_x += 1000
            if prev_x >= MAX_X:
                prev_x = 0
                prev_y += 1000

        HEADER = f"""<?xml version="1.0" standalone="no"?>
    <!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 20010904//EN"
            "http://www.w3.org/TR/2001/REC-SVG-20010904/DTD/svg10.dtd">
    <svg version="1.0" xmlns="http://www.w3.org/2000/svg"
         width="210mm" height="297mm" viewBox="0 0 {MAX_X} {abs(prev_y)}">"""

        FOOTER = "</svg>"

        svg_code += HEADER
        svg_code += svg_body
        svg_code += FOOTER
        with open(filename, 'w') as file:
            file.write(svg_code)
