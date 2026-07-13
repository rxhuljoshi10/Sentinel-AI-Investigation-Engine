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
  },

  async runInvestigationStream(
    description: string,
    logContent: string,
    token: string,
    onProgress: (data: { node: string; status: string; message: string }) => void,
    onResult: (data: any) => void,
    onError: (err: string) => void
  ) {
    try {
      const res = await fetch(`${API_BASE}/api/investigation/run-stream`, {
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

      if (!res.ok) throw new Error("Failed to start investigation stream");

      const reader = res.body?.getReader();
      if (!reader) throw new Error("Stream reader not available");

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        // Save the last line if it's incomplete
        buffer = lines.pop() || "";

        let currentEvent = "";

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed) continue;

          if (trimmed.startsWith("event:")) {
            currentEvent = trimmed.replace("event:", "").trim();
          } else if (trimmed.startsWith("data:")) {
            const dataStr = trimmed.replace("data:", "").trim();
            try {
              const parsed = JSON.parse(dataStr);
              if (currentEvent === "progress") {
                onProgress(parsed);
              } else if (currentEvent === "result") {
                onResult(parsed);
              } else if (currentEvent === "error") {
                onError(parsed.error);
              }
            } catch (e) {
              console.error("Failed to parse SSE data chunk", dataStr, e);
            }
          }
        }
      }
    } catch (e: any) {
      onError(e.message || "Connection error");
    }
  }
};