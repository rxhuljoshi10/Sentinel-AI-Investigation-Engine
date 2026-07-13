"use client";
import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";

interface InvestigationResult {
  investigation_id: string;
  final_report: {
    severity: string;
    affected_service: string;
    probable_cause: string;
    evidence: string[];
    immediate_actions: string[];
    confidence: number;
    investigation_summary: string;
  };
  evidence_collected: string[];
  tools_completed: string[];
  tools_failed: string[];
  similar_incidents_found: number;
}

const SEVERITY_COLORS = {
  critical: "bg-red-500",
  high: "bg-orange-500",
  medium: "bg-yellow-500",
  low: "bg-green-500"
};

export default function DashboardPage() {
  const router = useRouter();
  const [token, setToken] = useState<string | null>(null);
  const [username, setUsername] = useState("");
  const [description, setDescription] = useState("");
  const [logContent, setLogContent] = useState("");
  const [result, setResult] = useState<InvestigationResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [activeTab, setActiveTab] = useState<"investigate" | "chat">("investigate");
  const [chatMessage, setChatMessage] = useState("");
  const [chatResponse, setChatResponse] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const [progressLogs, setProgressLogs] = useState<{ node: string; status: string; message: string }[]>([]);
  const logEndRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const t = localStorage.getItem("token");
    const u = localStorage.getItem("username");
    if (!t) {
      router.push("/");
      return;
    }
    setToken(t);
    setUsername(u || "");
  }, [router]);

  useEffect(() => {
    if (logEndRef.current) {
      logEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [progressLogs]);

  async function handleInvestigate() {
    if (!description.trim() || !token) return;
    setLoading(true);
    setError("");
    setResult(null);
    setProgressLogs([]);

    try {
      await api.runInvestigationStream(
        description,
        logContent,
        token,
        (progress) => {
          setProgressLogs(prev => [...prev, progress]);
        },
        (data) => {
          setResult(data);
          setLoading(false);
        },
        (err) => {
          setError(err);
          setLoading(false);
        }
      );
    } catch (e) {
      setError("Investigation failed. Check backend logs.");
      setLoading(false);
    }
  }

  async function handleChat() {
    if (!chatMessage.trim() || !token) return;
    setChatLoading(true);
    setChatResponse("");

    try {
      const stream = await api.streamChat(chatMessage, token);
      const reader = stream.getReader();
      const decoder = new TextDecoder();

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value, { stream: true });
        setChatResponse(prev => prev + chunk);
      }
    } catch {
      setChatResponse("Chat failed.");
    } finally {
      setChatLoading(false);
    }
  }

  function handleLogout() {
    localStorage.clear();
    router.push("/");
  }

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      {/* Header */}
      <header className="border-b border-gray-800 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center text-sm font-bold">
            S
          </div>
          <span className="font-semibold text-lg">Sentinel AI</span>
        </div>
        <div className="flex items-center gap-4">
          <span className="text-gray-400 text-sm">{username}</span>
          <button
            onClick={handleLogout}
            className="text-gray-400 hover:text-white text-sm transition-colors"
          >
            Sign out
          </button>
        </div>
      </header>

      <div className="max-w-5xl mx-auto px-6 py-8">
        {/* Tabs */}
        <div className="flex gap-2 mb-8">
          {(["investigate", "chat"] as const).map(tab => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`px-4 py-2 rounded-lg text-sm font-medium capitalize transition-colors ${
                activeTab === tab
                  ? "bg-blue-600 text-white"
                  : "bg-gray-800 text-gray-400 hover:text-white"
              }`}
            >
              {tab === "investigate" ? "🔍 Investigate" : "💬 Chat"}
            </button>
          ))}
        </div>

        {/* Investigate Tab */}
        {activeTab === "investigate" && (
          <div className="space-y-6">
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 space-y-4">
              <h2 className="font-semibold text-lg">New Investigation</h2>

              <div>
                <label className="text-sm text-gray-400">
                  Incident Description
                </label>
                <textarea
                  value={description}
                  onChange={e => setDescription(e.target.value)}
                  rows={2}
                  className="w-full mt-1 px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white resize-none focus:outline-none focus:border-blue-500"
                  placeholder="Payment service throwing 500 errors since 3am..."
                />
              </div>

              <div>
                <label className="text-sm text-gray-400">
                  Log Content (optional)
                </label>
                <textarea
                  value={logContent}
                  onChange={e => setLogContent(e.target.value)}
                  rows={5}
                  className="w-full mt-1 px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white font-mono text-sm resize-none focus:outline-none focus:border-blue-500"
                  placeholder="Paste log content here..."
                />
              </div>

              <button
                onClick={handleInvestigate}
                disabled={loading || !description.trim()}
                className="px-6 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 disabled:text-gray-500 rounded-lg font-medium transition-colors"
              >
                {loading ? "Investigating..." : "Run Investigation"}
              </button>

              {error && <p className="text-red-400 text-sm">{error}</p>}
            </div>

            {/* Loading / Progress State */}
            {loading && (
              <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 space-y-4">
                <div className="flex items-center gap-3 border-b border-gray-800 pb-3">
                  <div className="w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
                  <span className="text-sm font-semibold text-gray-300 uppercase tracking-wider">
                    Sentinel Agent Execution Pipeline
                  </span>
                </div>
                
                <div className="font-mono text-xs space-y-1.5 max-h-60 overflow-y-auto bg-black p-4 rounded-lg border border-gray-800 select-text">
                  {progressLogs.length === 0 ? (
                    <div className="text-gray-600 animate-pulse">Initializing pipeline state...</div>
                  ) : (
                    progressLogs.map((log, idx) => {
                      const color = log.status === "completed" ? "text-green-400" : log.status === "failed" ? "text-red-400" : "text-blue-400";
                      const icon = log.status === "completed" ? "✔" : log.status === "failed" ? "✘" : "●";
                      return (
                        <div key={idx} className="flex items-start gap-2 leading-relaxed">
                          <span className={`${color} font-bold`}>{icon}</span>
                          <span className="text-gray-500">[{log.node}]</span>
                          <span className="text-gray-300">{log.message}</span>
                        </div>
                      );
                    })
                  )}
                  <div ref={logEndRef} />
                </div>
              </div>
            )}

            {/* Result */}
            {result && (
              <div className="space-y-4">
                {/* Report Header */}
                <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
                  <div className="flex items-start justify-between mb-4">
                    <div>
                      <div className="flex items-center gap-3 mb-1">
                        <span className={`px-2 py-0.5 rounded text-xs font-bold uppercase ${
                          SEVERITY_COLORS[result.final_report.severity as keyof typeof SEVERITY_COLORS] || "bg-gray-500"
                        }`}>
                          {result.final_report.severity}
                        </span>
                        <span className="text-gray-400 text-sm">
                          {result.final_report.affected_service}
                        </span>
                      </div>
                      <h3 className="text-lg font-semibold">
                        {result.final_report.probable_cause}
                      </h3>
                    </div>
                    <div className="text-right">
                      <div className="text-2xl font-bold text-blue-400">
                        {Math.round(result.final_report.confidence * 100)}%
                      </div>
                      <div className="text-xs text-gray-500">confidence</div>
                    </div>
                  </div>

                  <p className="text-gray-400 text-sm">
                    {result.final_report.investigation_summary}
                  </p>
                </div>

                {/* Evidence + Actions */}
                <div className="grid grid-cols-2 gap-4">
                  <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
                    <h4 className="text-sm font-semibold text-gray-300 mb-3">
                      Evidence
                    </h4>
                    <ul className="space-y-2">
                      {result.final_report.evidence.map((item, i) => (
                        <li key={i} className="text-sm text-gray-400 flex gap-2">
                          <span className="text-blue-500 mt-0.5">›</span>
                          {item}
                        </li>
                      ))}
                    </ul>
                  </div>

                  <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
                    <h4 className="text-sm font-semibold text-gray-300 mb-3">
                      Immediate Actions
                    </h4>
                    <ul className="space-y-2">
                      {result.final_report.immediate_actions.map((action, i) => (
                        <li key={i} className="text-sm text-gray-400 flex gap-2">
                          <span className="text-green-500 font-bold mt-0.5">
                            {i + 1}.
                          </span>
                          {action}
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>

                {/* Agent Summary */}
                <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
                  <h4 className="text-sm font-semibold text-gray-300 mb-3">
                    Investigation Metadata
                  </h4>
                  <div className="grid grid-cols-3 gap-4 text-sm">
                    <div>
                      <div className="text-gray-500">Investigation ID</div>
                      <div className="text-gray-300 font-mono text-xs mt-1">
                        {result.investigation_id.slice(0, 8)}...
                      </div>
                    </div>
                    <div>
                      <div className="text-gray-500">Agents Completed</div>
                      <div className="text-green-400 mt-1">
                        {result.tools_completed.join(", ")}
                      </div>
                    </div>
                    <div>
                      <div className="text-gray-500">Similar Incidents</div>
                      <div className="text-blue-400 mt-1">
                        {result.similar_incidents_found} found
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Chat Tab */}
        {activeTab === "chat" && (
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 space-y-4">
            <h2 className="font-semibold text-lg">Chat with Sentinel</h2>

            <div>
              <textarea
                value={chatMessage}
                onChange={e => setChatMessage(e.target.value)}
                rows={3}
                className="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white resize-none focus:outline-none focus:border-blue-500"
                placeholder="Ask anything about incidents..."
              />
            </div>

            <button
              onClick={handleChat}
              disabled={chatLoading || !chatMessage.trim()}
              className="px-6 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 disabled:text-gray-500 rounded-lg font-medium transition-colors"
            >
              {chatLoading ? "Thinking..." : "Send"}
            </button>

            {chatResponse && (
              <div className="bg-gray-800 rounded-lg p-4 text-gray-300 text-sm whitespace-pre-wrap font-mono">
                {chatResponse}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}