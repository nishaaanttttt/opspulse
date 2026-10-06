from io import BytesIO

import pandas as pd
import pytest

import app as app_module
from src.cleaning import REQUIRED_COLUMNS


@pytest.fixture
def client():
    app_module.app.config.update(TESTING=True)
    app_module.CLEANED_DATA_CACHE.clear()
    with app_module.app.test_client() as test_client:
        yield test_client
    app_module.CLEANED_DATA_CACHE.clear()


def sample_upload_rows():
    return pd.DataFrame(
        [
            ["D-1", "2026-01-05", "2026-01-09", "2026-01-08", "Alex Example", "Operations", "High", "Done", "Fictional Project", 4, 3, "No"],
            ["D-2", "2026-01-06", "2026-01-13", "", "Jamie Example", "Operations", "Medium", "In Progress", "Fictional Project", 6, 2, "No"],
        ],
        columns=REQUIRED_COLUMNS,
    )


def post_dates():
    return {"as_of": "2026-01-11", "created_from": "2026-01-05", "created_to": "2026-01-06"}


def test_get_dashboard_and_default_date_has_no_trailing_partial_week(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Operations overview" in response.data
    assert b"Download template CSV" in response.data

    cleaned, _quality, _source = app_module._cleaned_dataset("sample")
    default_as_of = app_module._default_report_date(cleaned)
    weekly = app_module.calculate_kpis(cleaned, as_of_date=default_as_of)["weekly"]
    assert weekly.iloc[-1]["Week End"].date().isoformat() == default_as_of
    assert bool(weekly.iloc[-1]["complete_week"])
    assert weekly.iloc[-1]["throughput"] >= weekly.iloc[-2]["throughput"]
    assert f'name="as_of" value="{default_as_of}"'.encode() in response.data


def test_use_sample_clears_upload_and_renders_sample(client):
    uploaded = sample_upload_rows().to_csv(index=False).encode()
    response = client.post(
        "/",
        data={"action": "apply", "task_file": (BytesIO(uploaded), "tasks.csv")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 200
    with client.session_transaction() as session:
        assert session.get("dataset_id")

    response = client.post("/", data={"action": "use_sample"})
    assert response.status_code == 200
    assert b"Synthetic sample data" in response.data
    with client.session_transaction() as session:
        assert "dataset_id" not in session
        assert "dataset_ext" not in session


def test_empty_filter_selection_is_a_valid_dashboard(client):
    response = client.post("/", data={"action": "apply", **post_dates()})
    assert response.status_code == 200
    assert b"No weekly throughput data in this selection." in response.data
    assert b"No tasks with usable priority deadline data." in response.data


def test_pdf_and_csv_downloads(client):
    pdf = client.post("/", data={"action": "download_pdf"})
    assert pdf.status_code == 200
    assert pdf.mimetype == "application/pdf"
    assert pdf.data.startswith(b"%PDF")

    csv = client.post("/", data={"action": "download_csv"})
    assert csv.status_code == 200
    assert csv.mimetype == "text/csv"
    assert csv.data.decode("utf-8").splitlines()[0].startswith(",".join(REQUIRED_COLUMNS) + ",")


def test_template_csv_contains_headers_and_two_fictional_rows(client):
    response = client.get("/template.csv")
    assert response.status_code == 200
    lines = response.data.decode("utf-8").splitlines()
    assert lines[0] == ",".join(REQUIRED_COLUMNS)
    assert len(lines) == 3
    assert "Fictional Project" in response.data.decode("utf-8")


def test_missing_columns_upload_falls_back_clears_session_and_get_still_works(client):
    response = client.post(
        "/",
        data={"action": "apply", "task_file": (BytesIO(b"wrong,column\n1,2\n"), "missing.csv")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 200
    assert b"Upload is missing required columns" in response.data
    assert b"Task ID" in response.data and b"Created Date" in response.data
    assert b"Synthetic sample data" in response.data
    with client.session_transaction() as session:
        assert "dataset_id" not in session
        assert "dataset_ext" not in session

    follow_up = client.get("/")
    assert follow_up.status_code == 200
    assert b"Operations overview" in follow_up.data


@pytest.mark.parametrize(
    ("filename", "payload", "expected_message"),
    [
        ("empty.csv", b"", b"The selected file is empty"),
        ("tasks.txt", b"anything", b"Choose a CSV or Excel file"),
    ],
)
def test_empty_and_wrong_type_uploads_return_dashboard(client, filename, payload, expected_message):
    response = client.post(
        "/",
        data={"action": "apply", "task_file": (BytesIO(payload), filename)},
        content_type="multipart/form-data",
    )
    assert response.status_code == 200
    assert expected_message in response.data
    assert b"Synthetic sample data" in response.data


def test_invalid_as_of_uses_default_and_displays_message(client):
    response = client.post("/", data={"action": "apply", "as_of": "2026-02-30"})
    assert response.status_code == 200
    assert b"One or more dates were invalid; default dates were used." in response.data
    cleaned, _quality, _source = app_module._cleaned_dataset("sample")
    default_as_of = app_module._default_report_date(cleaned)
    assert f'name="as_of" value="{default_as_of}"'.encode() in response.data


def test_valid_xlsx_upload_is_cleaned_and_selected(client):
    workbook = BytesIO()
    sample_upload_rows().to_excel(workbook, index=False)
    workbook.seek(0)
    response = client.post(
        "/",
        data={"action": "apply", "task_file": (workbook, "tasks.xlsx")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 200
    assert b"File uploaded and validated" in response.data
    assert b"Uploaded task file" in response.data
    with client.session_transaction() as session:
        assert session.get("dataset_id")
        assert session.get("dataset_ext") == ".xlsx"


def test_filter_requests_reuse_cleaned_dataset_cache(client, monkeypatch):
    app_module.CLEANED_DATA_CACHE.clear()
    calls = 0
    original = app_module.clean_tasks

    def counted_clean_tasks(frame):
        nonlocal calls
        calls += 1
        return original(frame)

    monkeypatch.setattr(app_module, "clean_tasks", counted_clean_tasks)
    assert client.get("/").status_code == 200
    assert calls == 1
    assert client.post("/", data={"action": "apply", **post_dates()}).status_code == 200
    assert calls == 1
