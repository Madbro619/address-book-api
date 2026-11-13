import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sqlite3

from fastapi.testclient import TestClient
from app.main import create_app
from app.geo import distance_km

ADDRESS = {"street": "Main Road", "city": "Nagpur", "country": "India",
           "postal_code": "440001", "latitude": 21.1458, "longitude": 79.0882}


class AddressTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = str(Path(self.temp.name) / "test.db")
        self.client = self.enterContext(TestClient(create_app(self.db)))

    def create(self, **changes):
        response = self.client.post('/addresses', json={**ADDRESS, **changes})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_crud(self):
        address = self.create()
        url = f"/addresses/{address['id']}"
        self.assertEqual(self.client.get(url).json(), address)
        result = self.client.patch(url, json={"city": "Pune", "latitude": 0}).json()
        self.assertEqual(result['city'], 'Pune')
        self.assertEqual(result['latitude'], 0)
        self.assertEqual(result['street'], ADDRESS['street'])
        self.assertEqual(self.client.delete(url).status_code, 204)
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_missing_records(self):
        self.assertEqual(self.client.get('/addresses/999').status_code, 404)
        self.assertEqual(self.client.patch('/addresses/999', json={'city': 'Pune'}).status_code, 404)
        self.assertEqual(self.client.delete('/addresses/999').status_code, 404)

    def test_validation(self):
        for changes in ({'latitude': 91}, {'longitude': -181}, {'city': '  '},
                        {'street': 'x' * 201}, {'postal_code': ''}, {'country': None},
                        {'latitude': 'NaN'}, {'longitude': 'Infinity'}, {'unexpected': 'x'}):
            with self.subTest(changes=changes):
                self.assertEqual(self.client.post('/addresses', json={**ADDRESS, **changes}).status_code, 422)
        self.assertEqual(self.client.post('/addresses', json={}).status_code, 422)
        address = self.create()
        for payload in ({}, {'city': None}, {'city': ' '}, {'latitude': -91}, {'id': 42}):
            with self.subTest(payload=payload):
                self.assertEqual(self.client.patch(f"/addresses/{address['id']}", json=payload).status_code, 422)

    def test_trim_and_sql_binding(self):
        address = self.create(city='  Nagpur  ', street="Robert'); DROP TABLE addresses;--")
        self.assertEqual(address['city'], 'Nagpur')
        self.assertEqual(self.client.get('/addresses').status_code, 200)

    def test_nearby_order_boundary_and_pagination(self):
        far = self.create(latitude=0, longitude=1)
        origin = self.create(latitude=0, longitude=0)
        self.create(latitude=0, longitude=10)
        params = {'latitude': 0, 'longitude': 0, 'radius_km': distance_km(0, 0, 0, 1)}
        results = self.client.get('/addresses/nearby', params=params).json()
        self.assertEqual([x['id'] for x in results], [origin['id'], far['id']])
        self.assertEqual(results[0]['distance_km'], 0)
        page = self.client.get('/addresses/nearby', params={**params, 'limit': 1, 'offset': 1}).json()
        self.assertEqual(page[0]['id'], far['id'])
        zero = self.client.get('/addresses/nearby', params={**params, 'radius_km': 0}).json()
        self.assertEqual(len(zero), 1)

    def test_query_validation(self):
        params = {'latitude': 0, 'longitude': 0, 'radius_km': 1}
        for change in ({'latitude': 91}, {'longitude': 181}, {'radius_km': -1},
                       {'radius_km': 'nan'}, {'latitude': 'inf'}, {'limit': 101}, {'offset': -1}):
            with self.subTest(change=change):
                self.assertEqual(self.client.get('/addresses/nearby', params={**params, **change}).status_code, 422)
        self.assertEqual(self.client.get('/addresses/nearby').status_code, 422)
        self.assertEqual(self.client.get('/addresses/0').status_code, 422)

    def test_empty_and_paged_lists(self):
        self.assertEqual(self.client.get('/addresses').json(), [])
        for i in range(3):
            self.create(street=str(i))
        self.assertEqual(self.client.get('/addresses?limit=1&offset=1').json()[0]['street'], '1')
        self.assertEqual(self.client.get('/addresses?limit=0').status_code, 422)

    def test_persistence_across_app_instances(self):
        address = self.create()
        with TestClient(create_app(self.db)) as another:
            self.assertEqual(another.get(f"/addresses/{address['id']}").json(), address)

    def test_database_error_is_sanitized(self):
        with patch('app.database.AddressRepository.list_addresses', side_effect=sqlite3.OperationalError('private details')):
            response = self.client.get('/addresses')
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('private details', response.text)

    def test_docs_and_health(self):
        self.assertEqual(self.client.get('/docs').status_code, 200)
        self.assertEqual(self.client.get('/openapi.json').status_code, 200)
        self.assertEqual(self.client.get('/health').json(), {'status': 'ok'})


class DistanceTests(unittest.TestCase):
    def test_known_distance(self):
        self.assertAlmostEqual(distance_km(0, 0, 0, 1), 111.195, places=3)

    def test_antimeridian_and_poles(self):
        self.assertAlmostEqual(distance_km(0, 179.9, 0, -179.9), 22.239, places=3)
        self.assertLess(distance_km(90, 0, 90, 180), 1e-9)

    def test_antipodal_and_symmetry(self):
        self.assertAlmostEqual(distance_km(0, 0, 0, 180), math.pi * 6371.0088)
        self.assertAlmostEqual(distance_km(21, 79, 18, 73), distance_km(18, 73, 21, 79))


if __name__ == '__main__':
    unittest.main()
