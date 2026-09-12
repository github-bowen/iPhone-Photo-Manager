export async function api(endpoint, options = {}) {
  const res = await fetch(endpoint, options);
  if (!res.ok) {
    throw new Error("API error: " + res.status);
  }
  return res.json();
}
