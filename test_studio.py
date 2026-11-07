import unittest
from studio_tools import RECIPES, CATALOG, route_request, fallback_draft, ai_prompts, _calendar

PROFILE = {'niche':'How things work', 'audience':'curious adults', 'tone':'clear', 'platform':'YouTube Shorts', 'goal':'engage', 'duration':30}

class StudioTests(unittest.TestCase):
    def test_ids_are_unique(self):
        self.assertEqual(len(RECIPES), len(set(r.slug for r in RECIPES)))
    def test_catalog_has_all_screen_groups(self):
        self.assertEqual({r.group for r in RECIPES}, {'Videos','Carousels','Trends','Content','Images','Chatbots'})
    def test_intent_router(self):
        self.assertEqual(route_request('Создай карусель про курицу'), 'carousel_idea')
        self.assertEqual(route_request('Найди тренды YouTube'), 'trends_youtube')
        self.assertEqual(route_request('Составь контент-план на 30 дней'), 'plan_30')
        self.assertEqual(route_request('Write a short reel about a dog'), 'reels_script')
    def test_makes_30_rows(self):
        rows = _calendar('chickens','EN').splitlines()
        self.assertEqual(len(rows),32)
        self.assertTrue(rows[-1].startswith('| 30 |'))
    def test_fallback_is_explicit(self):
        for slug,r in CATALOG.items():
            if r.kind == 'navigate':
                continue
            output = fallback_draft(slug,'pet care',PROFILE,'EN')
            self.assertIn('non-AI draft',output)
            self.assertGreater(len(output),180)
    def test_english_video_prompts_in_russian_carousel(self):
        x = fallback_draft('carousel_idea', 'Кошки',PROFILE,'RU')
        self.assertIn('Visual prompt (EN)', x)
        self.assertIn('### 8.',x)
    def test_ai_prompt_mentions_no_fake_stats(self):
        system,prompt=ai_prompts('plan_30','eggs',PROFILE,'EN')
        self.assertIn('Do not fabricate',system)
        self.assertIn('EXACTLY 30',prompt)

if __name__ == '__main__':
    unittest.main()
