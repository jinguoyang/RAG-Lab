const API_URL = process.env.TEST_API_URL || "http://localhost:8000";

interface SeedPayload {
  users?: Array<{ username: string; platform_role?: string }>;
  libraries?: Array<{
    name: string;
    owner?: string;
    members?: Array<{ username: string; role: string }>;
  }>;
  knowledge_bases?: Array<{
    name: string;
    library_name: string;
    owner?: string;
    members?: Array<{ username: string; role: string }>;
  }>;
}

interface SeedResult {
  users: Array<{ username: string; user_id: string }>;
  libraries: Array<{ name: string; library_id: string }>;
  knowledge_bases: Array<{ name: string; kb_id: string }>;
}

export async function seedTestData(payload: SeedPayload): Promise<SeedResult> {
  const response = await fetch(`${API_URL}/api/v1/test/seed`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(
      `Seed API failed: ${response.status} ${await response.text()}`
    );
  }
  return response.json();
}
