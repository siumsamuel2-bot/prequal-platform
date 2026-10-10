"""Unit coverage for ``app/services/pdf_service.py`` pure logic (MID-676).

PDF rendering itself needs WeasyPrint + a database, but the scoring and PII
helper functions are pure and were previously uncovered. Rendering call paths
are exercised indirectly by the router tests; these tests pin the arithmetic
and decryption-fallback contracts.
"""

import pytest

from app.services import pdf_service


class TestCalculateComplianceScore:
    def test_no_certs_no_violations_scores_100(self):
        assert pdf_service.calculate_compliance_score(0, 0, 0) == 100

    def test_no_certs_with_violations_scores_0(self):
        assert pdf_service.calculate_compliance_score(0, 0, 3) == 0

    def test_all_certs_valid_no_violations_scores_100(self):
        assert pdf_service.calculate_compliance_score(10, 10, 0) == 100

    def test_half_certs_valid_no_violations(self):
        # cert_score = 0.5 * 70 = 35, violation_score = 30 -> 65
        assert pdf_service.calculate_compliance_score(10, 5, 0) == 65

    def test_three_violations_erase_violation_component(self):
        # cert_score = 70, violation_score = max(0, 30 - 30) = 0 -> 70
        assert pdf_service.calculate_compliance_score(10, 10, 3) == 70

    def test_many_violations_never_go_negative(self):
        assert pdf_service.calculate_compliance_score(1, 0, 5) == 0

    def test_one_violation_deducts_ten(self):
        # cert_score = 70, violation_score = 20 -> 90
        assert pdf_service.calculate_compliance_score(10, 10, 1) == 90

    def test_result_is_capped_at_100(self):
        assert pdf_service.calculate_compliance_score(100, 100, 0) == 100


class _FakeSub:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class TestDecryptPii:
    def test_uses_encrypted_value_when_present(self, monkeypatch):
        monkeypatch.setattr(pdf_service, "decrypt_value", lambda value: f"dec:{value}")
        sub = _FakeSub(encrypted_email="ciphertext", email="plain@example.com")
        assert pdf_service._decrypt_pii(sub, "email") == "dec:ciphertext"

    def test_falls_back_to_plain_column_when_no_ciphertext(self):
        sub = _FakeSub(encrypted_email=None, email="plain@example.com")
        assert pdf_service._decrypt_pii(sub, "email") == "plain@example.com"

    def test_returns_none_when_absent(self):
        sub = _FakeSub(encrypted_phone=None, phone=None)
        assert pdf_service._decrypt_pii(sub, "phone") is None


class TestTemplates:
    def test_subreport_template_has_expected_placeholders(self):
        assert "{{ company_name }}" in pdf_service.SUBREPORT_TEMPLATE
        assert "{{ compliance_score }}" in pdf_service.SUBREPORT_TEMPLATE

    def test_dashboard_template_has_expected_placeholders(self):
        assert "{{ total_count }}" in pdf_service.DASHBOARD_REPORT_TEMPLATE
        assert "{% for row in rows %}" in pdf_service.DASHBOARD_REPORT_TEMPLATE


# ---------------------------------------------------------------------------
# Render paths: exercise full PDF generation with a fake WeasyPrint + fake DB
# ---------------------------------------------------------------------------

import sys  # noqa: E402
import types  # noqa: E402
import uuid  # noqa: E402
from datetime import date, datetime  # noqa: E402


class _Obj:
    """Attribute bag used to stand in for ORM rows."""

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class _FakeResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        if isinstance(self._value, list):
            return self._value[0] if self._value else None
        return self._value

    def scalar(self):
        if isinstance(self._value, list):
            return self._value[0] if self._value else None
        return self._value

    def scalars(self):
        return self

    def all(self):
        return self._value if isinstance(self._value, list) else [self._value]


class _FakeDb:
    """Async DB stand-in that replays a fixed sequence of query results."""

    def __init__(self, results):
        self._results = list(results)
        self.calls = 0

    async def execute(self, *args, **kwargs):
        self.calls += 1
        return _FakeResult(self._results.pop(0))


class _FakeHTML:
    def __init__(self, string=""):
        self.string = string

    def write_pdf(self, target):
        target.write(b"%PDF-1.4 fake-render")


@pytest.fixture
def fake_weasyprint(monkeypatch):
    module = types.ModuleType("weasyprint")
    module.HTML = _FakeHTML
    monkeypatch.setitem(sys.modules, "weasyprint", module)
    return module


class TestGenerateSubcontractorPdf:
    async def test_renders_pdf_bytes(self, fake_weasyprint):
        sub = _Obj(
            company_name="Acme Construction",
            email="ops@acme.example",
            phone="+1-555-0100",
            address_line1="1 Main St",
            city="Denver",
            state="CO",
            zip_code="80202",
            status="active",
        )
        certs = [
            _Obj(
                certification_type="OSHA 30",
                certification_number="C-1",
                issue_date=datetime(2025, 1, 1),
                expiration_date=date(2027, 1, 1),
                status="valid",
            )
        ]
        violations = [
            _Obj(
                violation_type="Safety",
                description="Open finding",
                issued_date=datetime(2025, 2, 1),
                status="open",
            )
        ]
        project = _Obj(project_name="Tower A", project_number="P-100")
        project_rows = [(project, "subcontractor", "active")]

        db = _FakeDb([[sub], certs, violations, project_rows])
        result = await pdf_service.generate_subcontractor_pdf(db, str(uuid.uuid4()))

        assert result == b"%PDF-1.4 fake-render"
        assert db.calls == 4

    async def test_raises_when_subcontractor_missing(self, fake_weasyprint):
        db = _FakeDb([[]])
        with pytest.raises(ValueError):
            await pdf_service.generate_subcontractor_pdf(db, str(uuid.uuid4()))

    async def test_none_optional_fields_render_as_na(self, fake_weasyprint):
        sub = _Obj(
            company_name="Bare Co",
            email="x@y.example",
            phone=None,
            address_line1=None,
            city=None,
            state=None,
            zip_code=None,
            status="active",
        )
        db = _FakeDb([[sub], [], [], []])
        result = await pdf_service.generate_subcontractor_pdf(db, str(uuid.uuid4()))
        assert result == b"%PDF-1.4 fake-render"


class TestGenerateComplianceDashboardPdf:
    async def test_renders_dashboard_with_one_subcontractor(self, fake_weasyprint):
        sub = _Obj(company_name="Acme Construction", id=uuid.uuid4())
        # Subs list, then per-sub counts: active, expiring, expired, open, resolved
        db = _FakeDb([[sub], [2], [1], [0], [1], [0]])
        result = await pdf_service.generate_compliance_dashboard_pdf(db)

        assert result == b"%PDF-1.4 fake-render"
        assert db.calls == 6

    async def test_renders_empty_dashboard(self, fake_weasyprint):
        db = _FakeDb([[]])
        result = await pdf_service.generate_compliance_dashboard_pdf(db)

        assert result == b"%PDF-1.4 fake-render"
        assert db.calls == 1

    async def test_compliant_subcontractor_branch(self, fake_weasyprint):
        sub = _Obj(company_name="Solid Co", id=uuid.uuid4())
        # 8 active certs, no open violations -> score 80 -> COMPLIANT
        db = _FakeDb([[sub], [8], [0], [0], [0], [0]])
        result = await pdf_service.generate_compliance_dashboard_pdf(db)
        assert result == b"%PDF-1.4 fake-render"
