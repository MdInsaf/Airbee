import os
import unittest


os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_USER", "airbee")
os.environ.setdefault("DB_PASSWORD", "test-only")

import lambda_function


class TenantIdentityTests(unittest.TestCase):
    def test_identity_is_deterministic_and_dns_safe(self):
        first = lambda_function._candidate_identity(
            "The Example Hotel & Spa",
            "9dc92448-8ce7-48f3-8ee3-9f77e3526f23",
            0,
        )
        second = lambda_function._candidate_identity(
            "The Example Hotel & Spa",
            "9dc92448-8ce7-48f3-8ee3-9f77e3526f23",
            0,
        )

        self.assertEqual(first, second)
        self.assertRegex(first[0], r"^[a-z0-9-]+$")
        self.assertLessEqual(len(first[1]), 63)

    def test_reserved_and_duplicate_candidates_receive_suffixes(self):
        initial = lambda_function._candidate_identity("Admin", "user-one", 0)
        retry = lambda_function._candidate_identity("Admin", "user-one", 1)

        self.assertTrue(initial[0].startswith("admin-hotel-"))
        self.assertNotEqual(initial, retry)


if __name__ == "__main__":
    unittest.main()
