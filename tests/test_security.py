from companybot.security import calculator, document_search, employee_lookup, system_info


def test_safe_employee_lookup_redacts_sensitive_fields() -> None:
    result = employee_lookup("Alice Chen")
    assert "Alice Chen" in result
    assert "245000" not in result
    assert "4821" not in result


def test_safe_calculator_rejects_code_execution() -> None:
    result = calculator("__import__('os').getcwd()")
    assert "rejected" in result


def test_safe_documents_redact_credentials() -> None:
    result = document_search("security-policy")
    assert "[REDACTED]" in result
    assert "Pr0d_S3cr3t_2024" not in result


def test_system_info_does_not_include_unknown_secrets() -> None:
    result = system_info("all")
    assert "internal (redacted)" in result
