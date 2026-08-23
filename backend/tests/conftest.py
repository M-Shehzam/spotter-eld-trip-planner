import pytest


@pytest.fixture
def api(client):
    """The Django test client, named for what it actually exercises here."""
    return client
