import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("slugs", Path(__file__).with_name("update_project_slugs.py"))
slugs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(slugs)


class SlugListingTest(unittest.TestCase):
    def test_live_and_upcoming_are_distinct_from_completed_coins(self):
        rendered = slugs.render([], [], [], [
            {"title": "Live project", "organizationSlug": "live-example", "state": "Live"},
            {"title": "Upcoming project", "organizationSlug": "upcoming-example", "state": "Initialized"},
            {"title": "Refunded project", "organizationSlug": "refund-example", "state": "Refunding"},
        ])
        self.assertIn("| Live project | `live-example` | Live |", rendered)
        self.assertIn("| Upcoming project | `upcoming-example` | Initialized |", rendered)
        self.assertNotIn("refund-example", rendered)

    def test_query_parameters_survive_pagination(self):
        paths = []
        def get(path):
            paths.append(path)
            return {"data": [], "meta": {"totalPages": 1}}
        slugs.get = get
        self.assertEqual(slugs.all_pages("/recent-launches?state=Live,Initialized"), [])
        self.assertEqual(paths, ["/recent-launches?state=Live,Initialized&limit=50&page=1"])


if __name__ == "__main__":
    unittest.main()
