"""Shared fixtures for hardware integration tests."""

import pytest

from config.constants import ZONE_IP


@pytest.fixture(scope="session")
def zone_controller_online():
    """True when Modbus TCP to the zone controller answers."""
    from utils.modbus_utils import create_client

    client = create_client(ZONE_IP)
    try:
        return client.connect()
    finally:
        client.close()


@pytest.fixture(autouse=True)
def require_zone_controller(zone_controller_online):
    if not zone_controller_online:
        pytest.skip(
            f"Zone controller not reachable at {ZONE_IP}:502 — "
            "connect to the plant network and verify ZONE_IP in config/constants.py"
        )
