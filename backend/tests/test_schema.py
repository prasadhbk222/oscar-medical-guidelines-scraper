import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.app.schemas import RuleNode, StructuredPolicySchema

ROOT = Path(__file__).resolve().parents[2]


def test_canonical_oscar_json_validates():
    data = json.loads((ROOT / "oscar.json").read_text())
    model = StructuredPolicySchema.model_validate(data)
    assert model.insurance_name == "Oscar Health"
    assert model.rules.operator == "AND"
    assert model.rules.rules[1].rules[1].rule_id == "1.2.2"  # nested branch present


def test_leaf_node_valid():
    node = RuleNode.model_validate({"rule_id": "1", "rule_text": "x"})
    assert node.operator is None and node.rules is None


def test_branch_requires_operator():
    with pytest.raises(ValidationError, match="operator"):
        RuleNode.model_validate(
            {"rule_id": "1", "rule_text": "x", "rules": [{"rule_id": "1.1", "rule_text": "y"}]}
        )


def test_operator_requires_children():
    with pytest.raises(ValidationError, match="child rules"):
        RuleNode.model_validate({"rule_id": "1", "rule_text": "x", "operator": "AND"})


def test_extra_fields_rejected():
    with pytest.raises(ValidationError):
        RuleNode.model_validate({"rule_id": "1", "rule_text": "x", "junk": 1})


def test_bad_operator_value_rejected():
    with pytest.raises(ValidationError):
        RuleNode.model_validate(
            {"rule_id": "1", "rule_text": "x", "operator": "XOR",
             "rules": [{"rule_id": "1.1", "rule_text": "y"}]}
        )


def test_wrong_insurance_name_rejected():
    with pytest.raises(ValidationError):
        StructuredPolicySchema.model_validate(
            {"title": "t", "insurance_name": "Aetna",
             "rules": {"rule_id": "1", "rule_text": "x"}}
        )
