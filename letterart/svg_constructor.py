from .dictionary import svg_dict
from typing import Optional
from PIL import Image, ImageEnhance


class Config:
    picture_dimension_x_mm: int = 210
    picture_dimension_y_mm: int = 297
    svg_scaling: int = 400
    padding_x_mm: int = 10
    padding_y_mm: int = 10
    space_x: int = 150
    space_y: int = 1200
    backspace: int = 350
    img_pixel_per_mm: int = 1
    contrast_enhance: float = 1.5

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
    def __init__(self, image_path: str, text_path: str, config: Config):
        self.image_path = image_path
        self.text_path = text_path
        self.text_as_str = self.get_text()
        self.config = config
        self.image = self.get_and_prepare_image()

    def get_text(self):
        with open(self.text_path, 'r') as file:
            return file.read()

    def get_and_prepare_image(self):
        raw_image = Image.open(self.image_path)
        gray_image = raw_image.convert('L')
        # new
        enhancer = ImageEnhance.Contrast(gray_image)
        gray_image = enhancer.enhance(self.config.contrast_enhance)
        #
        return gray_image.resize((self.config.picture_dimension_x_mm * self.config.img_pixel_per_mm,
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

    def get_body(self):
        body = ""
        loc_x = self.config.min_x
        loc_y = self.config.min_y
        old_max_x = 0
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
                new_letter = svg_dict[letter]
            except Exception:
                continue
            new_letter.move_to_location(loc_x, loc_y)

            abs_center_x = round(new_letter.abs_center[0] / self.config.svg_scaling * self.config.img_pixel_per_mm) % (
                        self.config.picture_dimension_x_mm * self.config.img_pixel_per_mm)
            abs_center_y = round(new_letter.abs_center[1] / self.config.svg_scaling * self.config.img_pixel_per_mm) % (
                        self.config.picture_dimension_y_mm * self.config.img_pixel_per_mm)

            color = self.image.getpixel((abs_center_x, abs_center_y))
            stroke_width = round(color * (-10 / 17) + 200)
            new_letter.set_strokewidth(stroke_width)
            body += str(new_letter)
            old_max_x = new_letter.x_coord + new_letter.box_rel[1]
            loc_x = old_max_x + self.config.space_x
            if loc_x >= self.config.max_x:
                newline = True
                loc_x = self.config.min_x
                loc_y += self.config.space_y

        return body

    def save_file(self, destination: Optional[str] = "export.svg"):
        if not destination.endswith('.svg'):
            destination += '.svg'

        header = self.get_header()
        body = self.get_body()
        footer = self.get_footer()
        with open(destination, 'w') as file:
            file.write(header)
            file.write(body)
            file.write(footer)
