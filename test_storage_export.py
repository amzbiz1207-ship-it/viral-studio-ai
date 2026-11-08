import unittest
import tempfile
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
from docx import Document
from storage import StateStore, validate_restore, StorageError
from exports import filename, docx_bytes, pdf_bytes
from services import search_youtube, expand_search_queries
from core import sample_hooks

class StorageExportTests(unittest.TestCase):
    def test_persistence_after_reopening(self):
        with tempfile.TemporaryDirectory() as d:
            db=str(Path(d)/'data.sqlite3')
            first=StateStore(path=db)
            state={'projects':{'My channel':{'week':[{'topic':'Chicken','status':'published'}]}},
                   'current':'My channel','library':[{'title':'Video'}], 'videos':[{'views':1637}]}
            first.save(state)
            another=StateStore(path=db)
            self.assertEqual(another.load(),state)
            state['projects']['My channel']['week'][0]['status']='ready'
            another.save(state)
            self.assertEqual(StateStore(path=db).load()['projects']['My channel']['week'][0]['status'],'ready')

    def test_restore_old_backup(self):
        old={'schema':1,'projects':{'A':{}},'current':'A','library':[],'videos':[]}
        self.assertEqual(validate_restore(old)['current'],'A')

    def test_download_formats(self):
        md='# Пример\n\n| День | Тема |\n|---|---|\n| 1 | Тест |\n'
        word=docx_bytes('План',md)
        pdf=pdf_bytes('План',md)
        self.assertGreater(len(word),20000)
        self.assertEqual(len(Document(BytesIO(word)).tables),1)
        self.assertEqual(pdf[:4],b'%PDF')
        self.assertTrue(filename('plan_30','План #1','pdf').endswith('.pdf'))

    def test_search_filters_nonviral(self):
        matches=[{'id':'x','views':45,'duration_s':20,'views_per_day':20},
                 {'id':'y','views':250000,'duration_s':21,'views_per_day':15000},
                 {'id':'z','views':800000,'duration_s':501,'views_per_day':30000}]
        with patch('services.yt_request',return_value={'items':[{'id':'x'}]}), \
             patch('services._enrich',return_value=matches):
            result=search_youtube('science', 'fake',days=7,min_views=100000,short_only=True,max_queries=1)
        self.assertEqual([r['id'] for r in result],['y'])

    def test_question_hooks_no_double_question(self):
        hooks=sample_hooks('Почему курица несёт яйца без петуха?','','RU')
        self.assertEqual(len(hooks),5)
        self.assertNotIn('??',hooks[0][1])
        self.assertNotIn('когда почему',hooks[0][1])

if __name__=='__main__': unittest.main()
