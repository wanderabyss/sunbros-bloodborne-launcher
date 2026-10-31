import struct
import unittest

import hud_layout as gfx
from title_presentation import fill_title, PADDING
from test_ultrawide import place, root_x, solid_shape


def title_fixture(name='MENU_Title_00001', nested=False):
    image = gfx.tag(1009, struct.pack('<IHHH', 7, 13, 2048, 1024) +
                    bytes([len(name)]) + name.encode())
    rect = gfx.Writer()
    rect.unsigned(17, 5)
    for value in (0, 1920 * 20, 0, 1080 * 20):
        rect.unsigned(value, 17)
    fill = b'\x01\x42' + struct.pack('<H', 7) + gfx.write_matrix(((20 * 65536, 20 * 65536), None, (0, 0)))
    shape = gfx.tag(2, struct.pack('<H', 21) + rect.bytes() + fill + b'\x00\x00')
    stage = gfx.Writer()
    stage.unsigned(17, 5)
    for value in (0, 1920 * 20, 0, 1080 * 20):
        stage.unsigned(value, 17)
    background = place(1, 21)
    if nested:
        background = (gfx.tag(39, struct.pack('<HH', 22, 1) + background + gfx.tag(1, b'') + gfx.tag(0, b'')) +
                      place(1, 22))
    body = (stage.bytes() + b'\x00\x1e\x01\x00' + image + shape + solid_shape(30, 0, 500) +
            background + place(2, 30, 600, 700, 'MenuCommands') + gfx.tag(1, b'') + gfx.tag(0, b''))
    return b'GFX\x0b' + struct.pack('<I', len(body) + 8) + body


class TitlePresentationTests(unittest.TestCase):
    def test_fills_baked_padding_uniformly_without_moving_menu_commands(self):
        original = title_fixture()
        result = fill_title(original)
        self.assertEqual(struct.unpack_from('<I', result, 4)[0], len(result))
        scale, rotation, (tx, ty) = root_x(result, 1)
        self.assertIsNone(rotation)
        self.assertEqual(scale[0], scale[1])
        self.assertAlmostEqual(PADDING * scale[0] / 65536 + tx / 20, 0, delta=0.05)
        self.assertAlmostEqual((1920 - PADDING) * scale[0] / 65536 + tx / 20, 1920, delta=0.05)
        self.assertLess(ty, 0)
        self.assertEqual(root_x(original, 'MenuCommands'), root_x(result, 'MenuCommands'))
        self.assertIsNone(fill_title(result))

    def test_other_artwork_is_left_alone(self):
        self.assertIsNone(fill_title(title_fixture('OTHER_IMAGE')))

    def test_nested_dlc_art_is_filled_and_keeps_its_menu_commands(self):
        original = title_fixture('MENU_Title_00004', nested=True)
        result = fill_title(original)
        self.assertIsNotNone(result)
        self.assertIsNone(fill_title(result))
        self.assertEqual(root_x(original, 'MenuCommands'), root_x(result, 'MenuCommands'))

    def test_invalid_movie_is_refused(self):
        with self.assertRaises(ValueError):
            fill_title(b'not a movie')
