ssh torizon@192.168.95.133 #Connect to device

ssh-keygen -R 192.168.95.133  ##  Fix SSH "Host Key Changed" Error

ping 192.168.95.133  ##  Network Checks
Test-NetConnection 192.168.95.133 -Port 22


cat filename ## Open Files (Read Only)

tail -f filename  # Live file updates

tail -F filename # Safer live logs (recommended)


# Modbus suite

Integration tests and CLI tools comparing Modbus registers to REST API and MQTT on the zone controller.

## Layout

- `config/read_registers.py` — ZC read register map (used by tests)
- `config/rc_registers.py` — RC tracker offsets and write cases
- `utils/` — Modbus, API, MQTT, validators
- `tests/` — pytest suite (requires device at `ZONE_IP` in `config/constants.py`)
- `config/constants.py` — `TARGET_RCS` lists online rover device IDs for RC read/write tests
- `readZC.py` / `readRC.py` — manual ZC/RC read runners
- `writerc.py` — RC write + readback + API verify (CLI)
- `tests/test_read_zc.py` — ZC read vs API/MQTT (mode counts via MQTT + rover snapshot)
- `tests/test_write_rc.py` — RC write MODE/CFLT/HMNM/STOP/HRST + MQTT verify
- `tests/test_write_zc.py` — ZC broadcast CFLT/MODE/HMNM + MQTT verify

Root `api_utils.py` and `read_registers.py` are deprecated shims; use `utils/` and `config/`.

# Instructions to run the project

<!-- create and activate venv -->
py -m venv .venv
.\.venv\Scripts\Activate.ps1

<!-- Install dependencies -->
py -m pip install -r requirements.txt

<!-- Run all tests -->
py -m pytest

<!-- Run with live print output -->
py -m pytest -s

<!--run particular file -->
pytest tests/filename.py -v

