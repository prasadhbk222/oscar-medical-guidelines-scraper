from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, model_validator


class RuleNode(BaseModel):
    """Recursive criteria node matching oscar.json.

    Leaf  = rule_id + rule_text.
    Branch = rule_id + rule_text + operator + rules[].
    """

    model_config = ConfigDict(extra="forbid")

    rule_id: str
    rule_text: str
    operator: Optional[Literal["AND", "OR"]] = None
    rules: Optional[list["RuleNode"]] = None

    @model_validator(mode="after")
    def _check_branch_consistency(self) -> "RuleNode":
        has_children = bool(self.rules)
        if has_children and self.operator is None:
            raise ValueError(
                f"node {self.rule_id!r} has child rules but no operator"
            )
        if self.operator is not None and not has_children:
            raise ValueError(
                f"node {self.rule_id!r} has an operator but no child rules"
            )
        return self


class StructuredPolicySchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    insurance_name: Literal["Oscar Health"] = "Oscar Health"
    rules: RuleNode


RuleNode.model_rebuild()
