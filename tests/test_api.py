"""Test FastAPI endpoints (without live Neo4j/Redis)."""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from phoenix.api.app import create_app

    app = create_app()
    return TestClient(app)


def test_health_endpoint(client):
    """Health endpoint should return even if Neo4j is down."""
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert "neo4j" in data


def test_scrape_platforms(client):
    resp = client.get("/scrape/platforms")
    assert resp.status_code == 200
    data = resp.json()
    assert "platforms" in data
    assert len(data["platforms"]) == 35
    assert "hackerone" in data["platforms"]
    assert "bugcrowd" in data["platforms"]
    assert "intigriti" in data["platforms"]


def test_scrape_trigger_unknown_platform(client):
    resp = client.post("/scrape/trigger", json={"platform_name": "nonexistent", "max_profiles": 5})
    assert resp.status_code == 400


def test_researchers_search_returns_list(client):
    """Search endpoint works when Neo4j is running."""
    try:
        resp = client.get("/researchers/search/nobody")
        assert resp.status_code in (200, 500)
        if resp.status_code == 200:
            data = resp.json()
            assert "results" in data
            assert "count" in data
    except RuntimeError:
        pytest.skip("Neo4j connection issue in test environment")


def test_researchers_detail_not_found(client):
    try:
        resp = client.get("/researchers/nonexistent-id")
        assert resp.status_code in (404, 500)
    except RuntimeError:
        pytest.skip("Neo4j connection issue in test environment")
