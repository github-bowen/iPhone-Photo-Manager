export async function api(endpoint) {
  const res = await fetch(endpoint);
  if (!res.ok) {
    throw new Error("API error: " + res.status);
  }
  return res.json();
}
