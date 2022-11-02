from typing import Optional, Tuple
from PIL import Image, ImageEnhance
from .ttf_loader import Alphabet, extract_alphabet
from typing import Optional, Dict, Callable
from PIL import Image, ImageEnhance, ImageOps
from copy import deepcopy
import json
from enum import Enum
import os


class Mode(Enum):
    fill = "fill"
    color = "color"
    grayscale = "grayscale"


class Config:

    def __init__(self, config_filename: Optional[str] = None):
        self.config_filename = config_filename
        self.picture_dimension_x_mm: int = 210
        self.picture_dimension_y_mm: int = 297
        self.svg_scaling: int = 400
        self.padding_x_mm: int = 10
        self.padding_y_mm: int = 10
        self.space_x: int = 80
        self.space_y: int = 1000
        self.backspace: int = 350
        self.img_pixel_per_mm: int = 1
        self.contrast_enhance: float = 1.5
        self.max_stroke_width: int = 120
        self.min_stroke_width: int = 20
        self.mode: Mode = Mode.fill
        self.picture_name: str = ""
        self.text_file_name: str =""
        self.font: str = ""

        if config_filename is not None:
            with open(config_filename, 'r') as file:
                self.json_config = json.load(file)

            self.load_mode_from_json()
            self.load_settings_from_json()


    def load_settings_from_json(self):
        for key, value in self.json_config.items():
            try:
                setattr(self, key, int(value))
            except Exception:
                setattr(self, key, value)

    def load_mode_from_json(self):
        json_mode = self.json_config.get("mode", None)
        if json_mode is None:
            self.mode = Mode.fill
        else:
            self.mode = Mode(json_mode)
            self.json_config.pop("mode")

    @property
    def max_x(self):
        return (self.picture_dimension_x_mm - self.padding_x_mm) * self.svg_scaling

    @property
    def max_y(self):
        return (self.picture_dimension_y_mm - self.padding_y_mm) * self.svg_scaling

    @property
    def min_x(self):
        return self.padding_x_mm * self.svg_scaling

    @property
    def min_y(self):
        return self.padding_y_mm * self.svg_scaling


class Converter:
    def __init__(self, config: Optional[Config] = Config()):
        self.config = config
        self.project_dir = os.path.dirname(self.config.config_filename)

        self.image_path = os.path.join(self.project_dir, config.picture_name)
        self.text_path = os.path.join(self.project_dir, config.text_file_name)
        self.font_path = os.path.join(self.project_dir, config.font)
        self.image = self.get_and_prepare_image()

        self.text_as_str = self.get_text()
        self.alphabet = extract_alphabet(self.font_path, flip_horizontally=True)



    def get_text(self):
        with open(self.text_path, 'r', encoding="utf-8") as file:
            return file.read().replace('\n', ' ')

    def get_and_prepare_image(self):
        image = Image.open(self.image_path)
        if self.config.mode == Mode.grayscale:
            image = image.convert('L')
        else:
            image = image.convert('RGB')

        # enhancer = ImageEnhance.Contrast(image)
        # image = enhancer.enhance(self.config.contrast_enhance)

        return image.resize((self.config.picture_dimension_x_mm * self.config.img_pixel_per_mm,
                             self.config.picture_dimension_y_mm * self.config.img_pixel_per_mm))

    def get_header(self):
        header = f"""<?xml version="1.0" standalone="no"?>
        <!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 20010904//EN"
                "http://www.w3.org/TR/2001/REC-SVG-20010904/DTD/svg10.dtd">
        <svg version="1.0" xmlns="http://www.w3.org/2000/svg"
             width="{self.config.picture_dimension_x_mm}mm" height="{self.config.picture_dimension_y_mm}mm" viewBox="0 0 {self.config.picture_dimension_x_mm * self.config.svg_scaling} {self.config.picture_dimension_y_mm * self.config.svg_scaling}">
        """
        return header

    def get_footer(self):
        footer = """
        </svg>
        """
        return footer

    def get_projected_center(self, letter) -> Tuple[int, int]:
        abs_center_x = round(letter.abs_center[0] / self.config.svg_scaling * self.config.img_pixel_per_mm) % (
                self.config.picture_dimension_x_mm * self.config.img_pixel_per_mm)
        abs_center_y = round(letter.abs_center[1] / self.config.svg_scaling * self.config.img_pixel_per_mm) % (
                self.config.picture_dimension_y_mm * self.config.img_pixel_per_mm)

        return abs_center_x, abs_center_y

    def set_strokewidth_of(self, letter):
        abs_center_x, abs_center_y = self.get_projected_center(letter)
        color = self.image.getpixel((abs_center_x, abs_center_y))
        b = self.config.max_stroke_width
        m = (self.config.min_stroke_width - b) / 255
        stroke_width = round(color * m + b)
        letter.set_strokewidth(stroke_width)

    def set_color_of(self, letter):
        abs_center_x, abs_center_y = self.get_projected_center(letter)
        color = self.image.getpixel((abs_center_x, abs_center_y))
        if isinstance(color, int):
            color_scg = f"#{color:02x}{color:02x}{color:02x}"
        else:
            color_scg = f"#{color[0]:02x}{color[1]:02x}{color[2]:02x}"
        letter.set_color(color_scg)
        letter.set_strokewidth(self.config.min_stroke_width)

    def get_body(self):
        body = ""
        loc_x = self.config.min_x
        loc_y = self.config.min_y
        newline = True
        letter_idx = 0
        while loc_y < self.config.max_y:
            letter = self.text_as_str[letter_idx % len(self.text_as_str)]

            letter_idx += 1
            if letter == " " and not newline:
                loc_x += self.config.backspace
                continue

            newline = False

            try:
                new_letter = deepcopy(self.alphabet[letter])
            except Exception:
                continue

            new_letter.move_to(loc_x, loc_y)

            body += str(new_letter)
            old_max_x = new_letter.x_coord + new_letter.width
            # todo hier ist ein Fehler. Berechnung neuer x coordinate Fehlerhaft
            loc_x = old_max_x + self.config.space_x
            if loc_x >= self.config.max_x:
                newline = True
                loc_x = self.config.min_x
                loc_y += self.config.space_y

        return body

    def calc_length_of(self, word: str) -> int:
        length = 0
        for letter in word:
            try:
                svg_letter = deepcopy(self.alphabet[letter])
                length += svg_letter.width
                length += self.config.space_x
            except Exception:
                pass
        return length

    def get_idx_and_space_size(self, words_list: list, start_idx: int) -> Tuple[Optional[int], Optional[int]]:
        num_words = 0
        previous_length = 0
        length = -self.config.backspace
        double_words_list = words_list + words_list
        max_usable_x = self.config.max_x - self.config.min_x
        for num_words, word in enumerate(double_words_list[start_idx:]):
            length += self.calc_length_of(word)
            length += self.config.backspace

            if length >= max_usable_x:
                break

            previous_length = length
        new_backspace = round((max_usable_x - previous_length) / num_words + self.config.backspace)
        return num_words, new_backspace

    def get_from_(self, wordlist, start_idx, number_words):
        stop_idx = (start_idx + number_words) % len(wordlist)
        if (start_idx <= stop_idx):
            return wordlist[start_idx:stop_idx]
        else:
            return wordlist[start_idx:] + wordlist[:stop_idx]

    def get_body2(self):
        body = ""
        loc_x = self.config.min_x
        loc_y = self.config.min_y

        words_list = self.text_as_str.split(' ')
        start_idx = 0
        while loc_y <= self.config.max_y:
            number_words, new_backspace = self.get_idx_and_space_size(words_list, start_idx)
            words_in_line_list = self.get_from_(words_list, start_idx, number_words)
            start_idx = (start_idx + number_words) % (len(words_list) - 1)
            word_in_line_str = " ".join(words_in_line_list)
            for letter in word_in_line_str:
                if letter == " ":
                    loc_x += new_backspace
                    continue
                try:
                    new_letter = deepcopy(self.alphabet[letter])
                except Exception:
                    continue

                new_letter.move_to(loc_x, loc_y)
                if self.config.mode == Mode.fill:
                    self.set_strokewidth_of(new_letter)
                elif self.config.mode == Mode.grayscale:
                    self.set_color_of(new_letter)
                elif self.config.mode == Mode.color:
                    self.set_color_of(new_letter)
                body += str(new_letter)

                old_x_max = new_letter.x_coord + new_letter.width
                loc_x = old_x_max + self.config.space_x

            loc_x = self.config.min_x
            loc_y += self.config.space_y
        return body

    def save_file(self, destination: Optional[str] = "export.svg"):
        if not destination.endswith('.svg'):
            destination += '.svg'

        destination = os.path.join(self.project_dir,destination)

        header = self.get_header()
        body = self.get_body2()
        footer = self.get_footer()
        with open(destination, 'w') as file:
            file.write(header)
            file.write(body)
            file.write(footer)
