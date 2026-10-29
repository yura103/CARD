import os
import tempfile
import unittest
from fastapi.testclient import TestClient
from app import main


class API(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        main.DB = os.path.join(self.tmp.name, "test.db")
        self.client = TestClient(main.app)

    def tearDown(self):
        self.client.close()
        self.tmp.cleanup()

    def test_compound_search(self):
        data = self.client.post('/api/search', json={'query': '주유랑 카페 전월 실적 30만 원 이하'}).json()
        self.assertEqual([c['id'] for c in data['cards']], ['weekend', 'all'])
        self.assertEqual(self.client.post('/api/search', json={'query': '여행'}).json()['cards'], [])

    def test_limits_and_eligibility(self):
        data = self.client.post('/api/recommend', json={'merchant': '스타벅스', 'amount': 8000}).json()
        self.assertEqual(data['best_card_id'], 'weekend')
        self.assertEqual({c['id']: c['discount'] for c in data['cards']}, {'daily': 500, 'weekend': 640, 'all': 160})
        card = main.get_sale({**main.CARDS[0], 'threshold': 400000}, 'cafe', 8000)
        self.assertFalse(card['eligible'])
        self.assertEqual(card['discount'], 0)
        self.assertEqual(self.client.post('/api/recommend', json={'merchant': '미등록', 'amount': 1}).status_code, 422)

    def test_settlement_and_idempotency(self):
        data = self.client.post('/api/settlements', json={'merchant': '모임', 'total': 1000001, 'friends': ['A', 'B', 'C']}).json()
        self.assertEqual(data['own_share'], 250001)
        self.assertEqual(sum(p['amount'] for p in data['participants'])+data['own_share'], data['total'])
        for p in data['participants']:
            url = f"/api/settlements/{data['id']}/participants/{p['id']}/confirm-demo"
            self.assertEqual(self.client.post(url).status_code, 200)
            result = self.client.post(url).json()
        self.assertEqual(result['received'], 750000)
        self.assertEqual(result['net_expense'], 250001)
        self.assertEqual(self.client.get('/api/settlements').json()[0]['received'], 750000)

    def test_validation(self):
        for friends in [['A', ' A '], ['']]:
            self.assertEqual(self.client.post('/api/settlements', json={'merchant': 'x', 'total': 10, 'friends': friends}).status_code, 422)
        self.assertEqual(self.client.post('/api/recommend', json={'merchant': 'x', 'amount': -1}).status_code, 422)
        self.assertEqual(self.client.post('/api/settlements/no/participants/no/confirm-demo').status_code, 404)


if __name__ == '__main__':
    unittest.main()
