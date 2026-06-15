import React, { useState } from "react";

function RuleNode({ node, depth, forceOpen }) {
  const isBranch = Array.isArray(node.rules) && node.rules.length > 0;
  // Collapse deep branches by default so large trees stay readable.
  const [open, setOpen] = useState(forceOpen == null ? depth < 2 : forceOpen);

  return (
    <li className="node">
      <div className={`node-row ${isBranch ? "branch" : "leaf"}`}>
        {isBranch ? (
          <button className="toggle-btn" onClick={() => setOpen((o) => !o)}>
            {open ? "▾" : "▸"}
          </button>
        ) : (
          <span className="toggle-spacer" />
        )}
        <span className="rule-id">{node.rule_id}</span>
        {isBranch && (
          <span className={`op op-${node.operator}`}>{node.operator}</span>
        )}
        <span className="rule-text">{node.rule_text}</span>
      </div>
      {isBranch && open && (
        <ul className="children">
          {node.rules.map((child, i) => (
            <RuleNode
              key={child.rule_id || i}
              node={child}
              depth={depth + 1}
              forceOpen={forceOpen}
            />
          ))}
        </ul>
      )}
    </li>
  );
}

export default function RuleTree({ root, forceOpen }) {
  return (
    <ul className="rule-tree">
      <RuleNode node={root} depth={0} forceOpen={forceOpen} />
    </ul>
  );
}
