"""The order PipelineCache::WarmUp depends on. The renderer's tests do not run on Windows, so this
reads the two constructors."""
from pathlib import Path
import re
import unittest

VULKAN = Path(__file__).resolve().parents[1] / 'gpu' / 'shadps4' / 'video_core' / 'renderer_vulkan'


def body(source, start, end):
    return source[source.index(start):source.index(end)]


class WarmUpOrderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.presenter = (VULKAN / 'vk_presenter.cpp').read_text(encoding='utf-8')
        cls.rasterizer = (VULKAN / 'vk_rasterizer.cpp').read_text(encoding='utf-8')

    def test_warm_up_comes_after_object_motion_and_what_the_screen_needs(self):
        constructor = body(self.presenter, 'Presenter::Presenter(', 'void Presenter::WarmUpShaders()')
        # The rasterizer makes object motion (a member initialiser, so first): motion shader
        # variants embed its buffer addresses.
        self.assertIn('make_unique<Rasterizer>', constructor)
        warm_up = constructor.index('WarmUpShaders();')
        for needed in ('BbOverlay::Init(', 'sdr_present_pass.Create(', 'frame_generator = '):
            self.assertLess(constructor.index(needed), warm_up, needed)
        self.assertEqual(constructor[warm_up:].split(), ['WarmUpShaders();', '}'],
                         'the last step: no other thread presents yet')

    def test_the_rasterizer_does_not_warm_up_itself(self):
        constructor = body(self.rasterizer, 'Rasterizer::Rasterizer(', 'Rasterizer::~Rasterizer()')
        self.assertIn('object_motion = ', constructor)
        self.assertIsNone(re.search(r'WarmUp\s*\(', constructor))


if __name__ == '__main__':
    unittest.main()
