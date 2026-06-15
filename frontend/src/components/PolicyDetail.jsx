import React, { useState } from "react";
import RuleTree from "./RuleTree.jsx";

export default function PolicyDetail({ detail }) {
  // `treeKey` remounts the tree to apply a global expand/collapse default.
  const [forceOpen, setForceOpen] = useState(null);
  const [treeKey, setTreeKey] = useState(0);
  const apply = (v) => {
    setForceOpen(v);
    setTreeKey((k) => k + 1);
  };

  const structured = detail.structured;
  const tree = structured && !structured.validation_error
    ? structured.structured_json
    : null;

  return (
    <div className="detail">
      <h2>{detail.title}</h2>
      <div className="links">
        <a href={detail.source_page_url} target="_blank" rel="noreferrer">
          Source page ↗
        </a>
        <a href={detail.pdf_url} target="_blank" rel="noreferrer">
          PDF ↗
        </a>
      </div>

      {tree ? (
        <>
          <div className="tree-toolbar">
            <span className="insurance">{tree.insurance_name}</span>
            <div className="legend">
              <span className="op op-AND">AND</span>
              <span className="op op-OR">OR</span>
              <span className="leaf-key">criterion</span>
            </div>
            <div className="tree-actions">
              <button onClick={() => apply(true)}>Expand all</button>
              <button onClick={() => apply(false)}>Collapse all</button>
            </div>
          </div>
          <RuleTree key={treeKey} root={tree.rules} forceOpen={forceOpen} />
        </>
      ) : structured && structured.validation_error ? (
        <div className="error">
          Structured output failed validation:
          <pre>{structured.validation_error}</pre>
        </div>
      ) : (
        <div className="placeholder">
          No structured criteria tree for this policy.
        </div>
      )}
    </div>
  );
}
