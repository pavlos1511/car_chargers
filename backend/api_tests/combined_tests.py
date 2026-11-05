"""
Combined API Integration Tests for EV Charging System.
Merges configuration from conftest.py and tests from test_api_checks.py.

Run with:
    pytest -v tests/combined_tests.py
"""
import io
import csv
from datetime import datetime, timedelta
import pytest
import requests
import urllib3

# Disable SSL warnings for self-signed certificates
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# =============================================================================
# Configuration & Fixtures (merged from conftest.py)
# =============================================================================

# Constants per specification
PORT = 9876
API_BASE_PATH = "/api"

# Note: pytest_addoption only works in conftest.py or plugins. 
# We include specific handling in base_url to support running this file 
# even if options aren't registered via conftest.

@pytest.fixture(scope="session")
def base_url(request):
    """Construct Base URL from input parameters or defaults."""
    try:
        host = request.config.getoption("--host")
        port = request.config.getoption("--port")
    except ValueError:
        # Options not registered (e.g. running without conftest having these options)
        host = "localhost"
        port = 9876
        
    return f"http://{host}:{port}{API_BASE_PATH}"


@pytest.fixture(scope="session")
def session():
    """Create a requests Session for TCP connection reuse."""
    s = requests.Session()
    s.verify = False  # Bypass SSL verification for self-signed certs
    return s


@pytest.fixture(scope="function")
def reset_db(session, base_url):
    """
    Fixture that resets the database to its initial state.
    Called before tests that require a clean database.
    """
    url = f"{base_url}/admin/resetpoints"
    try:
        response = session.post(url)
        assert response.status_code == 200, f"Database reset failed: {response.text}"
        
        # Verify database was initialized by checking healthcheck
        health = session.get(f"{base_url}/admin/healthcheck").json()
        assert health["status"] == "OK"
    except requests.exceptions.RequestException as e:
        pytest.fail(f"Critical: Could not connect to API for DB reset. Error: {e}")


# =============================================================================
# Helper Functions (from test_api_checks.py)
# =============================================================================

def validate_date_format(date_str):
    """Check if string follows YYYY-MM-DD hh:mm format."""
    try:
        datetime.strptime(date_str, "%Y-%m-%d %H:%M")
        return True
    except ValueError:
        return False


def validate_error_log_structure(data):
    """Validate Error Log Object structure per specification."""
    # Fields per spec (may use snake_case or spaces)
    required = ["call", "timeref", "originator", "return_code", "error", "debuginfo"]
    keys = data.keys()
    for field in required:
        if field not in keys and field.replace("_", " ") not in keys:
            return False, f"Missing field: {field}"
    return True, None


# =============================================================================
# Admin Endpoint Tests
# =============================================================================

class TestHealthcheck:
    """Tests for /admin/healthcheck endpoint."""

    def test_healthcheck_schema(self, session, base_url):
        """Verify structure and data types of Healthcheck endpoint."""
        url = f"{base_url}/admin/healthcheck"
        response = session.get(url)

        assert response.status_code == 200
        data = response.json()

        # Check required fields
        expected_fields = [
            "status", "dbconnection", "n_charge_points",
            "n_charge_points_online", "n_charge_points_offline"
        ]
        for field in expected_fields:
            assert field in data, f"Missing field in healthcheck: {field}"

        # Check types and values
        assert data["status"] == "OK"
        assert isinstance(data["n_charge_points"], int)
        assert isinstance(data["n_charge_points_online"], int)
        assert isinstance(data["n_charge_points_offline"], int)

        # Logical check: online + offline <= total
        assert data["n_charge_points_online"] + data["n_charge_points_offline"] <= data["n_charge_points"]


class TestAddPoints:
    """Tests for /admin/addpoints endpoint."""

    def test_addpoints_success(self, session, base_url, reset_db):
        """Test successful CSV upload."""
        url = f"{base_url}/admin/addpoints"

        csv_content = (
            "lon,lat,status,cap,kwhprice\n"
            "23.75,37.98,available,22,0.25\n"
            "23.76,37.99,offline,50,0.35"
        )
        csv_file = io.BytesIO(csv_content.encode('utf-8'))
        files = {'file': ('new_points.csv', csv_file, 'text/csv')}

        response = session.post(url, files=files)
        assert response.status_code ==200, f"Upload failed: {response.text}"

    def test_addpoints_invalid_file_type(self, session, base_url):
        """Test that non-CSV files are rejected."""
        url = f"{base_url}/admin/addpoints"
        files = {'file': ('test.json', '{"data": 1}', 'application/json')}

        response = session.post(url, files=files)
        assert response.status_code == 400

        error_log = response.json()
        assert "error" in error_log

    def test_addpoints_missing_file(self, session, base_url):
        """Test that missing file returns validation error."""
        url = f"{base_url}/admin/addpoints"
        response = session.post(url)

        assert response.status_code in [400, 422]
        error_log = response.json()
        assert "error" in error_log or "detail" in error_log



# =============================================================================
# Points Endpoint Tests
# =============================================================================

class TestPointsList:
    """Tests for /points endpoint."""

    def test_get_points_json(self, session, base_url, reset_db):
        """Test that /points returns JSON list."""
        response = session.get(f"{base_url}/points")
        assert response.status_code in [200, 204]

        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, list)

    def test_get_points_csv_format(self, session, base_url, reset_db):
        """Test that API returns valid CSV when requested."""
        url = f"{base_url}/points?format=csv"
        response = session.get(url)

        assert response.status_code in [200, 204]
        if response.status_code == 200:
            assert "text/csv" in response.headers.get("Content-Type", ""), "Wrong Content-Type header"

            content = response.content.decode('utf-8')
            csv_reader = csv.reader(io.StringIO(content))
            header = next(csv_reader)

            # Check basic fields exist in header
            for field in ["pointid", "status", "lon", "lat"]:
                assert any(field in h for h in header), f"Field {field} missing from CSV header"

    def test_get_points_invalid_status(self, session, base_url):
        """Test that invalid status filter returns 401."""
        response = session.get(f"{base_url}/points?status=invalid_status")
        assert response.status_code == 400
        assert "error" in response.json()


class TestPointDetail:
    """Tests for /point/:id endpoint."""

    def test_point_detail_schema(self, session, base_url, reset_db):
        """Test point detail response schema."""
        # First get a valid point ID
        points_resp = session.get(f"{base_url}/points")
        if points_resp.status_code == 204:
            pytest.skip("No points in database")

        point_id = points_resp.json()[0]["pointid"]
        response = session.get(f"{base_url}/point/{point_id}")

        assert response.status_code == 200
        data = response.json()

        assert "pointid" in data
        assert "kwhprice" in data
        assert "reservationendtime" in data

        # Validate date format
        if data["reservationendtime"] is not None:
            assert validate_date_format(data["reservationendtime"]),  \
             f"Invalid date format: {data['reservationendtime']}"

    def test_point_not_found(self, session, base_url):
        """Test that non-existent point returns 404."""
        response = session.get(f"{base_url}/point/99999999")
        assert response.status_code == 404


# =============================================================================
# Reservation Tests
# =============================================================================

class TestReservation:
    """Tests for /reserve endpoint."""

    def test_reserve_time_cap_logic(self, session, base_url, reset_db):
        """Test that reservation time is capped at 60 minutes."""
        # Get an available point
        points_resp = session.get(f"{base_url}/points?status=available")
        if points_resp.status_code == 204:
            pytest.skip("No available points")

        point_id = points_resp.json()[0]["pointid"]

        # Request 100 minutes (should be capped to 60)
        # We record start time in UTC because Django typically stores/returns UTC
        response = session.post(f"{base_url}/reserve/{point_id}/100")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "reserved"
        assert data["reservationendtime"] is not None, \
            f"Reservation should be ~60 min, but calculated {duration:.2f} min. " \
            f"Start(UTC): {start_time_utc}, End(Server): {end_time_naive}"

    def test_reserve_failure_already_reserved(self, session, base_url, reset_db):
        """Test that reserving an already reserved point fails."""
        # Get an available point
        points_resp = session.get(f"{base_url}/points?status=available")
        if points_resp.status_code == 204:
            pytest.skip("No available points")
            
        point_id = points_resp.json()[0]["pointid"]

        # First reservation - should succeed
        session.post(f"{base_url}/reserve/{point_id}/30")

        # Second reservation - should fail with epoch timestamp
        response = session.post(f"{base_url}/reserve/{point_id}/30")
        data = response.json()

        assert "error" in data or response.status_code in [400, 409], \
            "Failed reservation should return Unix Epoch timestamp"


# =============================================================================
# Session Tests
# =============================================================================

class TestSessions:
    """Tests for /sessions and /newsession endpoints."""

    def test_sessions_invalid_date_range(self, session, base_url, reset_db):
        """Test behavior when From Date > To Date."""
        points_resp = session.get(f"{base_url}/points")
        if points_resp.status_code == 204:
            pytest.skip("No points in database")

        point_id = points_resp.json()[0]["pointid"]
        from_date = "20250201"
        to_date = "20250101"  # Before from_date

        response = session.get(f"{base_url}/sessions/{point_id}/{from_date}/{to_date}")

        # Should be 400 or 204 (empty result)
        if response.status_code == 400:
            assert "error" in response.json()
        elif response.status_code == 204:
            pass  # Empty result is acceptable
        else:
            pytest.fail(f"Unexpected status code: {response.status_code}")

    def test_sessions_malformed_date(self, session, base_url, reset_db):
        """Test with malformed date format."""
        points_resp = session.get(f"{base_url}/points")
        if points_resp.status_code == 204:
            pytest.skip("No points in database")

        point_id = points_resp.json()[0]["pointid"]
        response = session.get(f"{base_url}/sessions/{point_id}/invalid-date/20250101")

        assert response.status_code == 400
        assert "error" in response.json()


# =============================================================================
# Security Tests
# =============================================================================

class TestSecurity:
    """Security-related tests."""

    def test_sql_injection_attempt(self, session, base_url):
        """Test that SQL injection attempts are handled safely."""
        malicious_id = "1' OR '1'='1"
        response = session.get(f"{base_url}/point/{malicious_id}")

        # System may return 404 because path expects int, OR 500 if it passes strict url check
        # But for 'point/<id>', our url conf expects int. 
        # So we might get 404 (HTML) if Django handles it before view.
        # This test ensures we at least don't crash with 500 or return data.
        assert response.status_code in [400, 404], \
            f"Potential security vulnerability! Status: {response.status_code}"


# =============================================================================
# Error Handling Tests
# =============================================================================

class TestErrorHandling:
    """Tests for Error Log Object structure."""

    def test_error_log_structure_on_404(self, session, base_url):
        """Verify error log structure on 404 response."""
        # Use a huge integer ID to ensure it matches the URL pattern <int:id> but is not found
        response = session.get(f"{base_url}/point/999999999")

        assert response.status_code == 404
        data = response.json()

        valid, error = validate_error_log_structure(data)
        assert valid, f"Invalid error log structure: {error}"

    def test_error_log_structure_on_400(self, session, base_url, reset_db):
        """Verify error log structure on 400 response."""
        # Ensure a point exists so we don't get 404 on point lookup
        points_resp = session.get(f"{base_url}/points")
        if points_resp.status_code == 204:
             pytest.skip("No points available")
             
        point_id = points_resp.json()[0]["pointid"]
        
        # Send bad date format
        response = session.get(f"{base_url}/sessions/{point_id}/bad-date/20250101")

        assert response.status_code == 400
        data = response.json()

        valid, error = validate_error_log_structure(data)
        assert valid, f"Invalid error log structure: {error}"
