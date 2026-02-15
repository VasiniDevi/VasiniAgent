"""Tests for Memory Manager — short-term, factual, GDPR cascade delete."""

import time
import pytest
from vasini.memory.manager import MemoryManager
from vasini.memory.short_term import ShortTermStore
from vasini.memory.factual import FactualStore, FactualRecord
from vasini.memory.gdpr import GDPRManager


class TestShortTermStore:
    def test_set_and_get(self):
        store = ShortTermStore(max_entries=100)
        store.set("t1", "agent-1", "ctx:session", '{"key": "value"}')
        result = store.get("t1", "agent-1", "ctx:session")
        assert result == '{"key": "value"}'

    def test_get_missing_returns_none(self):
        store = ShortTermStore(max_entries=100)
        assert store.get("t1", "agent-1", "missing") is None

    def test_ttl_expiry(self):
        store = ShortTermStore(max_entries=100, default_ttl_seconds=0.1)
        store.set("t1", "agent-1", "key", "value")
        time.sleep(0.15)
        assert store.get("t1", "agent-1", "key") is None

    def test_lru_eviction(self):
        store = ShortTermStore(max_entries=2)
        store.set("t1", "a1", "k1", "v1")
        store.set("t1", "a1", "k2", "v2")
        store.set("t1", "a1", "k3", "v3")
        assert store.get("t1", "a1", "k1") is None
        assert store.get("t1", "a1", "k2") == "v2"
        assert store.get("t1", "a1", "k3") == "v3"

    def test_tenant_isolation(self):
        store = ShortTermStore(max_entries=100)
        store.set("t1", "a1", "key", "tenant1")
        store.set("t2", "a1", "key", "tenant2")
        assert store.get("t1", "a1", "key") == "tenant1"
        assert store.get("t2", "a1", "key") == "tenant2"

    def test_delete(self):
        store = ShortTermStore(max_entries=100)
        store.set("t1", "a1", "key", "value")
        store.delete("t1", "a1", "key")
        assert store.get("t1", "a1", "key") is None

    def test_delete_all_for_tenant(self):
        store = ShortTermStore(max_entries=100)
        store.set("t1", "a1", "k1", "v1")
        store.set("t1", "a1", "k2", "v2")
        store.set("t2", "a1", "k1", "v1")
        store.delete_tenant("t1")
        assert store.get("t1", "a1", "k1") is None
        assert store.get("t1", "a1", "k2") is None
        assert store.get("t2", "a1", "k1") == "v1"


class TestFactualStore:
    def test_write_record(self):
        store = FactualStore()
        record = store.write(
            tenant_id="t1", agent_id="a1", key="python-version",
            value='{"v": "3.12"}', evidence="docs", confidence=0.99,
        )
        assert record.version == 1
        assert record.key == "python-version"

    def test_append_only_versioning(self):
        store = FactualStore()
        r1 = store.write("t1", "a1", "key", "v1", "evidence1", 0.95)
        r2 = store.write("t1", "a1", "key", "v2", "evidence2", 0.98)
        assert r1.version == 1
        assert r2.version == 2

    def test_get_latest_version(self):
        store = FactualStore()
        store.write("t1", "a1", "key", "v1", "e1", 0.95)
        store.write("t1", "a1", "key", "v2", "e2", 0.98)
        latest = store.get_latest("t1", "a1", "key")
        assert latest is not None
        assert latest.value == "v2"
        assert latest.version == 2

    def test_get_all_versions(self):
        store = FactualStore()
        store.write("t1", "a1", "key", "v1", "e1", 0.95)
        store.write("t1", "a1", "key", "v2", "e2", 0.98)
        versions = store.get_versions("t1", "a1", "key")
        assert len(versions) == 2

    def test_confidence_threshold_rejection(self):
        store = FactualStore(min_confidence=0.95)
        with pytest.raises(ValueError, match="(?i)confidence"):
            store.write("t1", "a1", "key", "v1", "e1", 0.80)

    def test_tenant_isolation(self):
        store = FactualStore()
        store.write("t1", "a1", "key", "t1-value", "e", 0.95)
        store.write("t2", "a1", "key", "t2-value", "e", 0.95)
        assert store.get_latest("t1", "a1", "key").value == "t1-value"
        assert store.get_latest("t2", "a1", "key").value == "t2-value"

    def test_delete_all_for_tenant(self):
        store = FactualStore()
        store.write("t1", "a1", "key", "v", "e", 0.95)
        store.delete_tenant("t1")
        assert store.get_latest("t1", "a1", "key") is None


class TestGDPRManager:
    def test_cascade_delete(self):
        short_term = ShortTermStore(max_entries=100)
        factual = FactualStore()

        short_term.set("t1", "a1", "k1", "v1")
        factual.write("t1", "a1", "fact", "v", "e", 0.95)

        gdpr = GDPRManager(short_term=short_term, factual=factual)
        result = gdpr.delete_tenant_data("t1")

        assert result.success
        assert short_term.get("t1", "a1", "k1") is None
        assert factual.get_latest("t1", "a1", "fact") is None

    def test_cascade_delete_preserves_other_tenants(self):
        short_term = ShortTermStore(max_entries=100)
        factual = FactualStore()

        short_term.set("t1", "a1", "k1", "v1")
        short_term.set("t2", "a1", "k1", "v2")
        factual.write("t1", "a1", "f", "v", "e", 0.95)
        factual.write("t2", "a1", "f", "v", "e", 0.95)

        gdpr = GDPRManager(short_term=short_term, factual=factual)
        gdpr.delete_tenant_data("t1")

        assert short_term.get("t2", "a1", "k1") == "v2"
        assert factual.get_latest("t2", "a1", "f") is not None

    def test_export_tenant_data(self):
        short_term = ShortTermStore(max_entries=100)
        factual = FactualStore()

        short_term.set("t1", "a1", "k1", "v1")
        factual.write("t1", "a1", "fact", "value", "evidence", 0.95)

        gdpr = GDPRManager(short_term=short_term, factual=factual)
        export = gdpr.export_tenant_data("t1")

        assert "short_term" in export
        assert "factual" in export
        assert len(export["factual"]) > 0


class TestMemoryManager:
    def test_create_manager(self):
        mgr = MemoryManager()
        assert mgr is not None

    def test_short_term_via_manager(self):
        mgr = MemoryManager()
        mgr.short_term.set("t1", "a1", "key", "value")
        assert mgr.short_term.get("t1", "a1", "key") == "value"

    def test_factual_via_manager(self):
        mgr = MemoryManager()
        mgr.factual.write("t1", "a1", "key", "v", "e", 0.95)
        assert mgr.factual.get_latest("t1", "a1", "key") is not None

    def test_gdpr_delete_via_manager(self):
        mgr = MemoryManager()
        mgr.short_term.set("t1", "a1", "key", "value")
        mgr.factual.write("t1", "a1", "fact", "v", "e", 0.95)
        result = mgr.gdpr_delete("t1")
        assert result.success
