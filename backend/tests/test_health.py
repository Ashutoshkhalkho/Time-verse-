import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_liveness_probe(client: AsyncClient):
    """Test that the /healthz liveness probe returns 200 OK and expected payload."""
    response = await client.get("/healthz")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["app_name"] in ["Timeverse", "TIMEWISE"]
    assert "version" in data
    assert "timestamp" in data


@pytest.mark.asyncio
async def test_readiness_probe(client: AsyncClient):
    """Test that the /healthz/ready readiness probe verifies database status."""
    response = await client.get("/healthz/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["database_connected"] is True


@pytest.mark.asyncio
async def test_api_v1_health_alias(client: AsyncClient):
    """Test the /api/v1/health route alias."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_not_found_rfc7807_error_handling(client: AsyncClient):
    """Test that non-existent routes return RFC 7807 problem details."""
    response = await client.get("/non-existent-endpoint-test")
    assert response.status_code == 404
    data = response.json()
    assert data["status"] == 404
    assert data["title"] == "HTTP Error"
    assert "instance" in data
    assert data["code"] == "HTTP_404"


@pytest.mark.asyncio
async def test_request_headers_and_timing(client: AsyncClient):
    """Test that custom X-Request-ID and X-Process-Time headers are set."""
    response = await client.get("/healthz")
    assert response.status_code == 200
    assert "x-request-id" in response.headers
    assert "x-process-time" in response.headers
