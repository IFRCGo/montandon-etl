from django.test import TestCase


class FakeTest(TestCase):
    """Trivial test used to apply migrations against a fresh CI database.

    Run via: ./manage.py test --keepdb -v 2 main.tests.fake_test
    """

    def test_fake(self):
        pass
