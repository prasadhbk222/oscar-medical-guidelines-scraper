export async function fetchPolicies() {
  const r = await fetch("/api/policies");
  if (!r.ok) throw new Error(`GET /api/policies -> ${r.status}`);
  return r.json();
}

export async function fetchPolicy(id) {
  const r = await fetch(`/api/policies/${id}`);
  if (!r.ok) throw new Error(`GET /api/policies/${id} -> ${r.status}`);
  return r.json();
}
