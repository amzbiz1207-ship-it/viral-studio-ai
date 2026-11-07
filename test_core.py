import unittest
from core import youtube_id, format_num, iso_duration, days_since, sample_hooks, demo_script, demo_week

class CoreTests(unittest.TestCase):
    def test_youtube_watch(self):
        self.assertEqual(youtube_id('https://www.youtube.com/watch?v=ZstVgAhxaZs&t=4'), 'ZstVgAhxaZs')
    def test_youtube_shorts(self):
        self.assertEqual(youtube_id('https://www.youtube.com/shorts/ZstVgAhxaZs'), 'ZstVgAhxaZs')
    def test_youtu_be(self):
        self.assertEqual(youtube_id('https://youtu.be/ZstVgAhxaZs'), 'ZstVgAhxaZs')
    def test_bad_host_not_accepted(self):
        self.assertIsNone(youtube_id('https://youtube.com.evil.example/watch?v=ZstVgAhxaZs'))
    def test_duration(self):
        self.assertEqual(iso_duration('PT1M45S'),105)
        self.assertEqual(iso_duration('PT2H3M4S'),7384)
    def test_hooks(self):
        self.assertEqual(len(sample_hooks('Egg','Science','EN')),5)
    def test_week(self):
        self.assertEqual(len(demo_week('Animals','EN')),7)
    def test_demo_not_ai(self):
        self.assertIn('template', demo_script('Eggs','Animals','EN').lower())

if __name__=='__main__': unittest.main()
