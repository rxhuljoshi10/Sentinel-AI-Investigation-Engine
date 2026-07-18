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

interface HistoryItem {
  id: string;
  description: string;
  severity: string;
  affected_service: string;
  probable_cause: string;
  confidence: number;
  tools_completed: string[];
  tools_failed: string[];
  created_at: string | null;
}

interface HistoryDetail extends HistoryItem {
  log_content: string;
  evidence: string[];
  immediate_actions: string[];
  investigation_summary: string;
}

const SEVERITY_COLORS: Record<string, string> = {
  critical: "bg-red-500",
  high: "bg-orange-500",
  medium: "bg-yellow-500",
  low: "bg-green-500",
};

const SEVERITY_TEXT: Record<string, string> = {
  critical: "text-red-400",
  high: "text-orange-400",
  medium: "text-yellow-400",
  low: "text-green-400",
};

function SeverityBadge({ severity }: { severity: string }) {
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-bold uppercase ${SEVERITY_COLORS[severity] || "bg-gray-600"}`}>
      {severity || "unknown"}
    </span>
  );
}

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("en-US", {
    month: "short", day: "numeric", year: "numeric", hour: "2-digit", minute: "2-digit"
  });
}

export default function DashboardPage() {
  const router = useRouter();
  const [token, setToken] = useState<string | null>(null);
  const [username, setUsername] = useState("");
  const [description, setDescription] = useState("");
  const [logContent, setLogContent] = useState("");
  const [result, setResult] = useState<InvestigationResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [activeTab, setActiveTab] = useState<"investigate" | "chat" | "history">("investigate");
  const [chatMessage, setChatMessage] = useState("");
  const [chatResponse, setChatResponse] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const [progressLogs, setProgressLogs] = useState<{ node: string; status: string; message: string }[]>([]);
  const logEndRef = useRef<HTMLDivElement | null>(null);

  // History state
  const [historyItems, setHistoryItems] = useState<HistoryItem[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedDetail, setSelectedDetail] = useState<HistoryDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [severityFilter, setSeverityFilter] = useState("all");
  const [serviceFilter, setServiceFilter] = useState("all");
  const [frequencyData, setFrequencyData] = useState<{ date: string; count: number }[]>([]);

  // Evaluation scores state
  const [reportEval, setReportEval] = useState<{ evidence_grounding: number; llm_judge: number; overall: number } | null>(null);
  const [evalRunning, setEvalRunning] = useState(false);

  useEffect(() => {
    const t = localStorage.getItem("token");
    const u = localStorage.getItem("username");
    if (!t) { router.push("/"); return; }
    setToken(t);
    setUsername(u || "");
  }, [router]);

  useEffect(() => {
    if (logEndRef.current) {
      logEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [progressLogs]);

  // Load history when tab becomes active
  useEffect(() => {
    if (activeTab === "history" && token) {
      loadHistory();
      loadFrequency();
    }
  }, [activeTab, token, severityFilter, serviceFilter]);

  async function loadHistory() {
    if (!token) return;
    setHistoryLoading(true);
    try {
      const data = await api.getInvestigations(token, {
        severity: severityFilter,
        service: serviceFilter,
      });
      setHistoryItems(data);
    } catch {
      // silently fail — empty list will show empty state
    } finally {
      setHistoryLoading(false);
    }
  }

  async function loadFrequency() {
    if (!token) return;
    try {
      const data = await api.getInvestigationFrequency(token);
      setFrequencyData(data);
    } catch {
      // chart just won't render
    }
  }

  async function loadDetail(id: string) {
    if (!token) return;
    setSelectedId(id);
    setDetailLoading(true);
    setSelectedDetail(null);
    try {
      const data = await api.getInvestigationById(token, id);
      setSelectedDetail(data);
    } catch {
      setSelectedDetail(null);
    } finally {
      setDetailLoading(false);
    }
  }

  async function handleInvestigate() {
    if (!description.trim() || !token) return;
    setLoading(true);
    setError("");
    setResult(null);
    setProgressLogs([]);

    try {
      await api.runInvestigationStream(
        description, logContent, token,
        (progress) => { setProgressLogs(prev => [...prev, progress]); },
        (data) => { setResult(data); setLoading(false); },
        (err) => { setError(err); setLoading(false); }
      );
    } catch {
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
        setChatResponse(prev => prev + decoder.decode(value, { stream: true }));
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

  async function handleEvaluateReport() {
    if (!token || !result || evalRunning) return;
    setEvalRunning(true);
    setReportEval(null);
    try {
      const scores = await api.evaluateReport(
        token,
        logContent,
        result.final_report
      );
      setReportEval(scores);
    } catch {
      // silently fail
    } finally {
      setEvalRunning(false);
    }
  }

  // Chart helpers
  const maxCount = Math.max(...frequencyData.map(d => d.count), 1);
  const recentFrequency = frequencyData.slice(-14);

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      {/* Header */}
      <header className="border-b border-gray-800 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center text-sm font-bold">S</div>
          <span className="font-semibold text-lg">Sentinel AI</span>
        </div>
        <div className="flex items-center gap-4">
          <span className="text-gray-400 text-sm">{username}</span>
          <button onClick={handleLogout} className="text-gray-400 hover:text-white text-sm transition-colors">
            Sign out
          </button>
        </div>
      </header>

      <div className="max-w-6xl mx-auto px-6 py-8">
        {/* Tabs */}
        <div className="flex gap-2 mb-6">
          {(["investigate", "history", "chat"] as const).map(tab => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                activeTab === tab ? "bg-blue-600 text-white" : "bg-gray-800 text-gray-400 hover:text-white"
              }`}
            >
              {tab === "investigate" ? "🔍 Investigate" : tab === "history" ? "📋 History" : "💬 Chat"}
            </button>
          ))}
        </div>

        {/* ─── Investigate Tab ─────────────────────────────────────────── */}
        {activeTab === "investigate" && (
          <div className="space-y-6">
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 space-y-4">
              <h2 className="font-semibold text-lg">New Investigation</h2>
              <div>
                <label className="text-sm text-gray-400">Incident Description</label>
                <textarea
                  value={description}
                  onChange={e => setDescription(e.target.value)}
                  rows={2}
                  className="w-full mt-1 px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white resize-none focus:outline-none focus:border-blue-500"
                  placeholder="Payment service throwing 500 errors since 3am..."
                />
              </div>
              <div>
                <label className="text-sm text-gray-400">Log Content (optional)</label>
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

            {loading && (
              <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 space-y-4">
                <div className="flex items-center gap-3 border-b border-gray-800 pb-3">
                  <div className="w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
                  <span className="text-sm font-semibold text-gray-300 uppercase tracking-wider">Sentinel Agent Execution Pipeline</span>
                </div>
                <div className="font-mono text-xs space-y-1.5 max-h-60 overflow-y-auto bg-black p-4 rounded-lg border border-gray-800">
                  {progressLogs.length === 0 ? (
                    <div className="text-gray-600 animate-pulse">Initializing pipeline state...</div>
                  ) : progressLogs.map((log, idx) => {
                    const color = log.status === "completed" ? "text-green-400" : log.status === "failed" ? "text-red-400" : "text-blue-400";
                    const icon = log.status === "completed" ? "✔" : log.status === "failed" ? "✘" : "●";
                    return (
                      <div key={idx} className="flex items-start gap-2 leading-relaxed">
                        <span className={`${color} font-bold`}>{icon}</span>
                        <span className="text-gray-500">[{log.node}]</span>
                        <span className="text-gray-300">{log.message}</span>
                      </div>
                    );
                  })}
                  <div ref={logEndRef} />
                </div>
              </div>
            )}

            {result && (
              <div className="space-y-4">
                <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
                  <div className="flex items-start justify-between mb-4">
                    <div>
                      <div className="flex items-center gap-3 mb-1">
                        <SeverityBadge severity={result.final_report.severity} />
                        <span className="text-gray-400 text-sm">{result.final_report.affected_service}</span>
                      </div>
                      <h3 className="text-lg font-semibold">{result.final_report.probable_cause}</h3>
                    </div>
                    <div className="text-right">
                      <div className="text-2xl font-bold text-blue-400">{Math.round(result.final_report.confidence * 100)}%</div>
                      <div className="text-xs text-gray-500">confidence</div>
                    </div>
                  </div>
                  <p className="text-gray-400 text-sm">{result.final_report.investigation_summary}</p>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
                    <h4 className="text-sm font-semibold text-gray-300 mb-3">Key Log Evidence</h4>
                    <ul className="space-y-2">
                      {result.final_report.evidence.map((item, i) => (
                        <li key={i} className="text-sm text-gray-400 flex gap-2">
                          <span className="text-blue-500 mt-0.5">›</span>{item}
                        </li>
                      ))}
                    </ul>
                  </div>
                  <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
                    <h4 className="text-sm font-semibold text-gray-300 mb-3">Immediate Actions</h4>
                    <ul className="space-y-2">
                      {result.final_report.immediate_actions.map((action, i) => (
                        <li key={i} className="text-sm text-gray-400 flex gap-2">
                          <span className="text-green-500 font-bold mt-0.5">{i + 1}.</span>{action}
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>

                <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
                  <h4 className="text-sm font-semibold text-gray-300 mb-3">Investigation Metadata</h4>
                  <div className="grid grid-cols-3 gap-4 text-sm">
                    <div>
                      <div className="text-gray-500">Investigation ID</div>
                      <div className="text-gray-300 font-mono text-xs mt-1">{result.investigation_id.slice(0, 8)}...</div>
                    </div>
                    <div>
                      <div className="text-gray-500">Agents Completed</div>
                      <div className="text-green-400 mt-1">{result.tools_completed.join(", ")}</div>
                    </div>
                    <div>
                      <div className="text-gray-500">Similar Incidents</div>
                      <div className="text-blue-400 mt-1">{result.similar_incidents_found} found</div>
                    </div>
                  </div>
                </div>

                {result.evidence_collected && result.evidence_collected.length > 0 && (
                  <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
                    <h4 className="text-sm font-semibold text-gray-300 mb-3">Pipeline Diagnostic Evidence</h4>
                    <div className="space-y-2 max-h-60 overflow-y-auto pr-1">
                      {result.evidence_collected.map((item, idx) => {
                        let badgeColor = "bg-gray-800 text-gray-400 border border-gray-700";
                        let label = "INFO";
                        let cleanText = item;

                        if (item.startsWith("[GITHUB COMMIT]")) {
                          badgeColor = "bg-purple-950/50 text-purple-400 border border-purple-900/50";
                          label = "GIT";
                          cleanText = item.replace("[GITHUB COMMIT]", "").trim();
                        } else if (item.startsWith("[SIMULATED COMMIT]")) {
                          badgeColor = "bg-indigo-950/50 text-indigo-400 border border-indigo-900/50";
                          label = "MOCK GIT";
                          cleanText = item.replace("[SIMULATED COMMIT]", "").trim();
                        } else if (item.startsWith("[CURRENT LOG]")) {
                          badgeColor = "bg-emerald-950/50 text-emerald-400 border border-emerald-900/50";
                          label = "LOG";
                          cleanText = item.replace("[CURRENT LOG]", "").trim();
                        } else if (item.startsWith("[PAST INCIDENT]")) {
                          badgeColor = "bg-cyan-950/50 text-cyan-400 border border-cyan-900/50";
                          label = "RAG MATCH";
                          cleanText = item.replace("[PAST INCIDENT]", "").trim();
                        } else if (item.startsWith("[MEMORY]")) {
                          badgeColor = "bg-amber-950/50 text-amber-400 border border-amber-900/50";
                          label = "MEMORY";
                          cleanText = item.replace("[MEMORY]", "").trim();
                        }

                        return (
                          <div key={idx} className="flex items-start gap-2.5 text-xs py-1.5 border-b border-gray-800/40 last:border-0">
                            <span className={`px-2 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wider flex-shrink-0 ${badgeColor}`}>
                              {label}
                            </span>
                            <span className="text-gray-300 leading-normal">{cleanText}</span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}


                {/* Evaluate Report button + inline scores */}
                <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <h4 className="text-sm font-semibold text-gray-300">Report Quality</h4>
                      <p className="text-xs text-gray-600 mt-0.5">Score this report against your actual log input</p>
                    </div>
                    <button
                      onClick={handleEvaluateReport}
                      disabled={evalRunning || !logContent.trim()}
                      className="text-xs px-4 py-1.5 rounded-lg bg-gray-800 hover:bg-gray-700 disabled:opacity-40 text-gray-300 transition-colors font-medium border border-gray-700"
                    >
                      {evalRunning ? "Evaluating…" : "Evaluate Report"}
                    </button>
                  </div>

                  {!logContent.trim() && (
                    <p className="text-xs text-gray-600 italic mt-3">Provide log content above to enable evaluation.</p>
                  )}

                  {reportEval && (
                    <div className="mt-4 space-y-2.5">
                      {([
                        { key: "evidence_grounding", label: "Evidence grounding", hint: "Did evidence come from your logs?" },
                        { key: "llm_judge", label: "LLM-as-judge", hint: "Accuracy · completeness · actionability" },
                      ] as const).map(({ key, label, hint }) => {
                        const score = reportEval[key];
                        const pct = Math.round(score * 100);
                        const barColor = pct >= 80 ? "bg-green-500" : pct >= 65 ? "bg-yellow-500" : "bg-red-500";
                        return (
                          <div key={key}>
                            <div className="flex items-center justify-between mb-1">
                              <div>
                                <span className="text-xs text-gray-300">{label}</span>
                                <span className="text-xs text-gray-600 ml-2">{hint}</span>
                              </div>
                              <span className="text-xs font-mono font-semibold text-white">{score.toFixed(2)}</span>
                            </div>
                            <div className="bg-gray-800 rounded-full h-1.5 overflow-hidden">
                              <div
                                className={`h-full rounded-full transition-all duration-700 ${barColor}`}
                                style={{ width: `${pct}%` }}
                              />
                            </div>
                          </div>
                        );
                      })}
                      <div className="flex items-center justify-between pt-2 border-t border-gray-800">
                        <span className="text-xs font-semibold text-gray-300">Overall</span>
                        <span className={`text-sm font-bold ${
                          reportEval.overall >= 0.8 ? "text-green-400" :
                          reportEval.overall >= 0.65 ? "text-yellow-400" : "text-red-400"
                        }`}>
                          {reportEval.overall.toFixed(3)}
                        </span>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        )}

        {/* ─── History Tab ─────────────────────────────────────────────── */}
        {activeTab === "history" && (
          <div className="space-y-6">
            {/* Frequency Chart */}
            {frequencyData.length > 0 && (
              <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
                <h3 className="text-sm font-semibold text-gray-300 mb-4">Incident Frequency — Last 14 Days</h3>
                <div className="flex items-end gap-1 h-24">
                  {recentFrequency.map((d) => (
                    <div key={d.date} className="flex-1 flex flex-col items-center gap-1 group">
                      <div className="relative w-full flex justify-center">
                        {d.count > 0 && (
                          <span className="absolute -top-5 text-xs text-gray-500 opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap">
                            {d.count}
                          </span>
                        )}
                        <div
                          className="w-full rounded-t bg-blue-600 group-hover:bg-blue-400 transition-colors min-h-[2px]"
                          style={{ height: `${Math.max((d.count / maxCount) * 80, d.count > 0 ? 4 : 2)}px` }}
                        />
                      </div>
                      <span className="text-xs text-gray-600 rotate-0" style={{ fontSize: "9px" }}>
                        {d.date.slice(5)}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Filters */}
            <div className="flex gap-3 items-center">
              <span className="text-sm text-gray-400">Filter by:</span>
              <select
                value={severityFilter}
                onChange={e => setSeverityFilter(e.target.value)}
                className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-1.5 text-sm text-white focus:outline-none focus:border-blue-500"
              >
                <option value="all">All severities</option>
                <option value="critical">Critical</option>
                <option value="high">High</option>
                <option value="medium">Medium</option>
                <option value="low">Low</option>
              </select>
              <select
                value={serviceFilter}
                onChange={e => setServiceFilter(e.target.value)}
                className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-1.5 text-sm text-white focus:outline-none focus:border-blue-500"
              >
                <option value="all">All services</option>
                <option value="payment-service">payment-service</option>
                <option value="order-service">order-service</option>
                <option value="auth-service">auth-service</option>
              </select>
              <span className="text-xs text-gray-600 ml-auto">
                {historyItems.length} record{historyItems.length !== 1 ? "s" : ""}
              </span>
            </div>

            {/* Split Layout: List + Detail */}
            <div className="grid grid-cols-5 gap-4 min-h-[480px]">
              {/* Left: Investigation List */}
              <div className="col-span-2 space-y-2 overflow-y-auto max-h-[540px] pr-1">
                {historyLoading ? (
                  <div className="text-gray-500 text-sm text-center py-12 animate-pulse">Loading investigations...</div>
                ) : historyItems.length === 0 ? (
                  <div className="text-gray-600 text-sm text-center py-12">
                    <div className="text-3xl mb-2">🗃️</div>
                    No investigations found.<br />
                    <span className="text-gray-700">Run your first investigation to see it here.</span>
                  </div>
                ) : historyItems.map(item => (
                  <button
                    key={item.id}
                    onClick={() => loadDetail(item.id)}
                    className={`w-full text-left rounded-xl border p-3 transition-all ${
                      selectedId === item.id
                        ? "border-blue-500 bg-blue-950"
                        : "border-gray-800 bg-gray-900 hover:border-gray-600"
                    }`}
                  >
                    <div className="flex items-center gap-2 mb-1">
                      <SeverityBadge severity={item.severity} />
                      <span className="text-xs text-gray-400 truncate">{item.affected_service}</span>
                    </div>
                    <div className="text-sm text-gray-200 truncate">{item.description}</div>
                    <div className="text-xs text-gray-600 mt-1">{formatDate(item.created_at)}</div>
                  </button>
                ))}
              </div>

              {/* Right: Detail Panel */}
              <div className="col-span-3 bg-gray-900 border border-gray-800 rounded-xl p-5 overflow-y-auto max-h-[540px]">
                {!selectedId ? (
                  <div className="flex flex-col items-center justify-center h-full text-gray-600 gap-2">
                    <div className="text-4xl">👈</div>
                    <p className="text-sm">Select an investigation to view its full report</p>
                  </div>
                ) : detailLoading ? (
                  <div className="flex items-center justify-center h-full text-gray-500 text-sm animate-pulse">
                    Loading report...
                  </div>
                ) : !selectedDetail ? (
                  <div className="text-red-400 text-sm p-4">Failed to load investigation detail.</div>
                ) : (
                  <div className="space-y-5">
                    {/* Header */}
                    <div className="flex items-start justify-between">
                      <div>
                        <div className="flex items-center gap-2 mb-1">
                          <SeverityBadge severity={selectedDetail.severity} />
                          <span className={`text-sm font-medium ${SEVERITY_TEXT[selectedDetail.severity] || "text-gray-400"}`}>
                            {selectedDetail.affected_service}
                          </span>
                        </div>
                        <h3 className="text-base font-semibold text-white leading-snug">
                          {selectedDetail.probable_cause}
                        </h3>
                        <p className="text-xs text-gray-500 mt-1">{formatDate(selectedDetail.created_at)}</p>
                      </div>
                      <div className="text-right flex-shrink-0 ml-4">
                        <div className="text-xl font-bold text-blue-400">
                          {Math.round((selectedDetail.confidence || 0) * 100)}%
                        </div>
                        <div className="text-xs text-gray-500">confidence</div>
                      </div>
                    </div>

                    {/* Summary */}
                    {selectedDetail.investigation_summary && (
                      <p className="text-sm text-gray-400 leading-relaxed border-l-2 border-gray-700 pl-3">
                        {selectedDetail.investigation_summary}
                      </p>
                    )}

                    {/* Evidence */}
                    {selectedDetail.evidence?.length > 0 && (
                      <div>
                        <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Key Log Evidence</h4>
                        <ul className="space-y-1.5">
                          {selectedDetail.evidence.map((item, i) => (
                            <li key={i} className="text-sm text-gray-300 flex gap-2">
                              <span className="text-blue-500 flex-shrink-0">›</span>{item}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {/* Actions */}
                    {selectedDetail.immediate_actions?.length > 0 && (
                      <div>
                        <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Immediate Actions</h4>
                        <ul className="space-y-1.5">
                          {selectedDetail.immediate_actions.map((action, i) => (
                            <li key={i} className="text-sm text-gray-300 flex gap-2">
                              <span className="text-green-500 font-bold flex-shrink-0">{i + 1}.</span>{action}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {/* Metadata */}
                    <div className="grid grid-cols-2 gap-3 pt-2 border-t border-gray-800 text-xs">
                      <div>
                        <div className="text-gray-500 mb-1">Agents Completed</div>
                        <div className="text-green-400">{(selectedDetail.tools_completed || []).join(", ") || "—"}</div>
                      </div>
                      <div>
                        <div className="text-gray-500 mb-1">Agents Failed</div>
                        <div className="text-red-400">{(selectedDetail.tools_failed || []).join(", ") || "none"}</div>
                      </div>
                      <div className="col-span-2">
                        <div className="text-gray-500 mb-1">Investigation ID</div>
                        <div className="text-gray-400 font-mono">{selectedDetail.id}</div>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* ─── Chat Tab ────────────────────────────────────────────────── */}
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