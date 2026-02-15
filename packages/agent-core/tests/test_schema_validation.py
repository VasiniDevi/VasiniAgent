import pytest
from pathlib import Path
from vasini.schema import validate_pack


EXAMPLES_DIR = Path(__file__).parent.parent.parent.parent / "examples" / "packs"


class TestPackSchemaValidation:
    def test_valid_pack_passes(self):
        pack_dir = EXAMPLES_DIR / "senior-python-dev"
        result = validate_pack(pack_dir)
        assert result.valid is True, f"Errors: {result.errors}"
        assert result.errors == []

    def test_missing_schema_version_fails(self, tmp_path):
        pack_file = tmp_path / "profession-pack.yaml"
        pack_file.write_text("pack_id: test\nversion: '1.0.0'\nrisk_level: low\nauthor:\n  name: test\nrole:\n  file: './ROLE.yaml'\n")
        result = validate_pack(tmp_path)
        assert result.valid is False
        assert any("schema_version" in e for e in result.errors)

    def test_missing_pack_id_fails(self, tmp_path):
        pack_file = tmp_path / "profession-pack.yaml"
        pack_file.write_text("schema_version: '1.0'\nversion: '1.0.0'\nrisk_level: low\nauthor:\n  name: test\nrole:\n  file: './ROLE.yaml'\n")
        result = validate_pack(tmp_path)
        assert result.valid is False
        assert any("pack_id" in e for e in result.errors)

    def test_invalid_risk_level_fails(self, tmp_path):
        pack_file = tmp_path / "profession-pack.yaml"
        pack_file.write_text(
            "schema_version: '1.0'\npack_id: test\nversion: '1.0.0'\n"
            "risk_level: extreme\nauthor:\n  name: test\nrole:\n  file: './ROLE.yaml'\n"
        )
        result = validate_pack(tmp_path)
        assert result.valid is False
        assert any("risk_level" in e for e in result.errors)

    def test_missing_profession_pack_file_fails(self, tmp_path):
        result = validate_pack(tmp_path)
        assert result.valid is False
        assert any("profession-pack.yaml" in e for e in result.errors)
