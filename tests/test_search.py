import unittest
import httpx
from app.search import hybrid_search
from app.notifications import build_notification_preview


class Search(unittest.TestCase):
    def test_hybrid_filters_and_fusion(self):
        requests = []
        def respond(request):
            import json
            body = json.loads(request.content)
            requests.append(body)
            if 'knn' in body:
                self.assertEqual(len(body['knn']['filter']['bool']['filter']), 3)
            else:
                self.assertEqual(len(body['query']['bool']['filter']), 3)
            return httpx.Response(200, json={'hits': {'hits': [
                {'_id': 'match', '_source': {'threshold': 300000, 'benefits': [{'category': 'gas'}, {'category': 'cafe'}]}},
                {'_id': 'partial', '_source': {'threshold': 0, 'benefits': [{'category': 'gas'}]}}
            ]}})
        with httpx.Client(transport=httpx.MockTransport(respond)) as client:
            result = hybrid_search('http://elasticsearch:9200', 'gas cafe', [0.1, 0.2], ['gas', 'cafe'], 300000, client)
        self.assertEqual(len(requests), 2)
        self.assertEqual([r['id'] for r in result], ['match'])
        self.assertAlmostEqual(result[0]['score'], 2/61)

    def test_notification_preview(self):
        data = build_notification_preview()
        self.assertEqual(data['delivery'], 'preview-only')
        self.assertEqual(len(data['cards']), 3)
        self.assertTrue(all(c['eligible'] for c in data['cards']))
