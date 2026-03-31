from __future__ import annotations

from pitchcopytrade.api.request_trace import checkout_validation_reason, compact_stage_name


def test_compact_stage_name_shortens_trace_events() -> None:
    assert compact_stage_name("tg_webapp_auth_success") == "auth_ok"
    assert compact_stage_name("tg_webapp_auth_failed") == "auth_fail"
    assert compact_stage_name("app_catalog_render") == "app_catalog"
    assert compact_stage_name("app_checkout_submit") == "checkout_submit"


def test_checkout_validation_reason_is_machine_readable() -> None:
    assert checkout_validation_reason("Нужно принять все обязательные документы перед оплатой") == "missing_accepted_document_ids"
    assert checkout_validation_reason("Checkout недоступен: не опубликован полный комплект обязательных документов") == "checkout_documents_unpublished"
    assert checkout_validation_reason(None) == "checkout_validation_error"
