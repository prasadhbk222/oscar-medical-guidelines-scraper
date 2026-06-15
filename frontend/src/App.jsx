import React, { useEffect, useMemo, useState } from "react";
import { fetchPolicies, fetchPolicy } from "./api.js";
import PolicyDetail from "./components/PolicyDetail.jsx";

export default function App() {
  const [policies, setPolicies] = useState([]);
  const [error, setError] = useState(null);
  const [query, setQuery] = useState("");
  const [structuredOnly, setStructuredOnly] = useState(false);
  const [selectedId, setSelectedId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [loadingDetail, setLoadingDetail] = useState(false);

  useEffect(() => {
    fetchPolicies().then(setPolicies).catch((e) => setError(e.message));
  }, []);

  useEffect(() => {
    if (selectedId == null) return;
    setLoadingDetail(true);
    fetchPolicy(selectedId)
      .then(setDetail)
      .catch((e) => setError(e.message))
      .finally(() => setLoadingDetail(false));
  }, [selectedId]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return policies.filter((p) => {
      if (structuredOnly && !p.has_structured) return false;
      if (q && !p.title.toLowerCase().includes(q)) return false;
      return true;
    });
  }, [policies, query, structuredOnly]);

  const structuredCount = policies.filter((p) => p.has_structured).length;

  return (
    <div className="layout">
      <aside className="sidebar">
        <h1>Oscar Guidelines</h1>
        <div className="meta">
          {policies.length} policies · {structuredCount} structured
        </div>
        <input
          className="search"
          placeholder="Filter by title…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <label className="toggle">
          <input
            type="checkbox"
            checked={structuredOnly}
            onChange={(e) => setStructuredOnly(e.target.checked)}
          />
          Structured only
        </label>
        {error && <div className="error">{error}</div>}
        <ul className="policy-list">
          {filtered.map((p) => (
            <li
              key={p.id}
              className={p.id === selectedId ? "selected" : ""}
              onClick={() => setSelectedId(p.id)}
            >
              <span className="title">{p.title}</span>
              <span className="badges">
                {p.has_structured && <span className="badge tree">tree</span>}
                <a
                  className="badge pdf"
                  href={p.pdf_url}
                  target="_blank"
                  rel="noreferrer"
                  onClick={(e) => e.stopPropagation()}
                >
                  PDF
                </a>
              </span>
            </li>
          ))}
        </ul>
      </aside>
      <main className="content">
        {selectedId == null ? (
          <div className="placeholder">Select a policy to view its criteria tree.</div>
        ) : loadingDetail ? (
          <div className="placeholder">Loading…</div>
        ) : (
          detail && <PolicyDetail detail={detail} />
        )}
      </main>
    </div>
  );
}
