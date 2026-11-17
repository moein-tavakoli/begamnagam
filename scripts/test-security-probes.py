"""Regression tests preventing redirects from turning a leak probe into a pass."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('probes', Path(__file__).with_name('check-security-probes.py'))
probes = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probes)


class RedirectBoundaryTests(unittest.TestCase):
    def test_sensitive_file_redirect_is_not_a_denial(self):
        for target in ['/download/.env', '/api/v2/document/login']:
            self.assertFalse(probes.allowed_document_redirect('https://example.test', '/.env', target))

    def test_document_redirect_must_end_at_the_same_origin_login(self):
        for target in ['http://example.test/api/v2/document/login',
                       'https://example.test:8443/api/v2/document/login',
                       '//other.test/api/v2/document/login', '/download/openapi.json',
                       'https://user@example.test/api/v2/document/login']:
            self.assertFalse(probes.allowed_document_redirect('https://example.test', '/api/v2/document/openapi.json', target))

    def test_valid_document_login_redirect(self):
        self.assertTrue(probes.allowed_document_redirect('https://example.test',
            '/api/v2/document/openapi.json', '/api/v2/document/login?next=/api/v2/document/openapi.json'))

    def test_image_http_400_after_an_upstream_fetch_does_not_pass(self):
        self.assertFalse(probes.image_refused_before_fetch(b"The requested resource isn't a valid image."))
        self.assertFalse(probes.image_refused_before_fetch(b'"url" parameter is valid but upstream response is invalid'))
        self.assertTrue(probes.image_refused_before_fetch(b'"url" parameter is not allowed'))


if __name__ == '__main__':
    unittest.main()
