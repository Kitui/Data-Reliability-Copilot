from pathlib import Path

import pandas as pd

from app.auditor import audit_dataframe
from app.privacy import scan_dataframe


def test_email_verification_flag_is_not_treated_as_email_or_pii():
    frame = pd.DataFrame(
        {
            "email": ["valid@example.com", "bad-email"],
            "email_verified": [True, False],
        }
    )
    result = audit_dataframe(frame, "customers.csv")
    titles = [issue.title for issue in result.issues]
    assert "Invalid email format in email" in titles
    assert "Invalid email format in email_verified" not in titles
    privacy_columns = {item["column"] for item in scan_dataframe(frame)["findings"]}
    assert "email" in privacy_columns
    assert "email_verified" not in privacy_columns


def test_audit_workspace_shows_version_source_and_nairobi_time():
    script = Path("app/static/app.js").read_text()
    assert 'const DISPLAY_TIME_ZONE = "Africa/Nairobi"' in script
    assert "['Dataset version',version]" in script
    assert "['Source file',sourceFile]" in script
    assert "formatDateTime(item.created_at)" in script
    assert "formatDateTime(audit.created_at)" in script
