import pytest
import os
import matcher
from helpers.TestUtil import TestUtil

@pytest.fixture
def test_util (scope="class"):
    # or_baseurl = os.getenv('OPENREVIEW_BASEURL')
    or_baseurl = 'http://localhost:3000'
    flask_app_test_client = matcher.app.test_client()
    flask_app_test_client.testing = True
    silent = True
    test_util = TestUtil.get_instance(or_baseurl, flask_app_test_client, silent=silent)
    yield test_util