"""Session debug logging (NDJSON)."""

import json
import os
import time

_LOG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "debug-6aa286.log",
)


def agent_log(hypothesis_id, location, message, data=None, run_id="pre-fix"):
    # #region agent log
    try:
        with open(_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(
                json.dumps(
                    {
                        "sessionId": "6aa286",
                        "hypothesisId": hypothesis_id,
                        "location": location,
                        "message": message,
                        "data": data or {},
                        "timestamp": int(time.time() * 1000),
                        "runId": run_id,
                    }
                )
                + "\n"
            )
    except Exception:
        pass
    # #endregion
