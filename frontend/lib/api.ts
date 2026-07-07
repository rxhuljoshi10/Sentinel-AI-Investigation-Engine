const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export const api = {
  async login(username: string, password: string) {
    const res = await fetch(`${API_BASE}/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password })
    });
    if (!res.ok) throw new Error("Login failed");
    return res.json();
  },

  async runInvestigation(
    description: string,
    logContent: string,
    token: string
  ) {
    const res = await fetch(`${API_BASE}/api/investigation/run`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${token}`
      },
      body: JSON.stringify({
        incident_description: description,
        log_content: logContent
      })
    });
    if (!res.ok) throw new Error("Investigation failed");
    return res.json();
  },

  async streamChat(message: string, token: string): Promise<ReadableStream> {
    const res = await fetch(`${API_BASE}/api/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${token}`
      },
      body: JSON.stringify({ message })
    });
    if (!res.ok) throw new Error("Chat failed");
    return res.body!;
  }
};