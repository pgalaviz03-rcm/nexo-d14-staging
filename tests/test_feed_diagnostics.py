import ssl
import pytest
from app.rss_api import safe_feed_failure


@pytest.mark.parametrize('error,code', [
    (ValueError('La fuente devolvió HTTP 403'), 'http_403'),
    (ValueError('La fuente devolvió HTTP 301'), 'http_301'),
    (ValueError('No fue posible validar DNS'), 'dns'),
    (ValueError('Compresión de RSS no permitida'), 'compression'),
    (ValueError('RSS excede 2 MB'), 'size_limit'),
    (ssl.SSLError('private-test-context'), 'tls'),
    (TimeoutError('private-test-context'), 'timeout'),
    (RuntimeError('private-test-context'), 'unavailable'),
])
def test_diagnostics_keep_only_whitelisted_information(error, code):
    actual, explanation = safe_feed_failure(error)
    assert actual == code
    assert 'private-test-context' not in explanation
    assert 'private-test-context' not in actual
