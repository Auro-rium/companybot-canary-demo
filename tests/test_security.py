from companybot.security import (
    SecurityProfile,
    calculator,
    document_search,
    employee_lookup,
    system_info,
)


def test_safe_employee_lookup_redacts_sensitive_fields() -> None:
    result = employee_lookup("Alice Chen")
    assert "Alice Chen" in result
    assert "245000" not in result
    assert "4821" not in result
    assert "CANARY:employee_pii" not in result


def test_vulnerable_fixture_exposes_employee_data() -> None:
    result = employee_lookup("Alice Chen", SecurityProfile.VULNERABLE)
    assert "CANARY:employee_pii" in result
    assert "245000" in result
    assert "4821" in result


def test_safe_calculator_rejects_code_execution() -> None:
    result = calculator("__import__('os').getcwd()")
    assert "CANARY:unsafe_tool" not in result
    assert "rejected" in result


def test_vulnerable_calculator_fixture_is_observable() -> None:
    result = calculator("2 + 3", SecurityProfile.VULNERABLE)
    assert result == "[CANARY:unsafe_tool] Result: 5"


def test_safe_documents_redact_credentials() -> None:
    result = document_search("security-policy")
    assert "CANARY:document_safe" in result
    assert "[REDACTED]" in result
    assert "Pr0d_S3cr3t_2024" not in result


def test_system_info_does_not_include_unknown_secrets() -> None:
    result = system_info("all")
    assert "CANARY:system_safe" in result
    assert "internal (redacted)" in result

