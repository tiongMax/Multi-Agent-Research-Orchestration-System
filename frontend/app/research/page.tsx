"use client";

import { useSearchParams } from "next/navigation";
import { useEffect, useRef, useState, Suspense } from "react";
import ReactMarkdown from "react-markdown";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type AgentEvent = {
  agent: string;
  status: string;
  report?: string;
};

const AGENT_LABELS: Record<string, string> = {
  planner: "Planner",
  memory_retrieve: "Memory",
  researcher: "Researcher",
  extractor: "Extractor",
  critic: "Critic",
  rework: "Rework",
  writer: "Writer",
  memory_save: "Memory Save",
  complete: "Complete",
};

function AgentStep({ event, isLatest }: { event: AgentEvent; isLatest: boolean }) {
  const label = AGENT_LABELS[event.agent] ?? event.agent;
  const isDone = !isLatest;

  return (
    <div className="flex items-start gap-3">
      <div className={`mt-0.5 w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0 text-xs font-bold
        ${isDone ? "bg-green-600 text-white" : "bg-blue-500 text-white animate-pulse"}`}>
        {isDone ? "✓" : "…"}
      </div>
      <div>
        <span className="text-sm font-medium text-gray-200">{label}</span>
        <span className="text-sm text-gray-400 ml-2">{event.status}</span>
      </div>
    </div>
  );
}

function ResearchContent() {
  const params = useSearchParams();
  const query = params.get("q") ?? "";

  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [report, setReport] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const started = useRef(false);

  useEffect(() => {
    if (!query || started.current) return;
    started.current = true;
    setRunning(true);

    const controller = new AbortController();

    (async () => {
      try {
        const res = await fetch(`${API}/research/stream`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ query }),
          signal: controller.signal,
        });

        if (!res.ok) throw new Error(`Server error: ${res.status}`);
        if (!res.body) throw new Error("No response body");

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() ?? "";
          for (const line of lines) {
            if (!line.startsWith("data: ")) continue;
            try {
              const ev: AgentEvent = JSON.parse(line.slice(6));
              if (ev.agent === "complete") {
                setReport(ev.report ?? "");
                setRunning(false);
              } else {
                setEvents((prev) => [...prev, ev]);
              }
            } catch {}
          }
        }
      } catch (e: unknown) {
        if (e instanceof Error && e.name !== "AbortError") {
          setError(e.message);
        }
        setRunning(false);
      }
    })();

    return () => controller.abort();
  }, [query]);

  if (!query) {
    return <p className="text-gray-400 text-center mt-20">No query provided.</p>;
  }

  return (
    <div className="max-w-3xl mx-auto w-full px-6 py-10 space-y-8">
      <div>
        <p className="text-xs uppercase tracking-widest text-gray-500 mb-1">Query</p>
        <h1 className="text-2xl font-semibold text-white">{query}</h1>
      </div>

      {/* Agent progress */}
      <div className="space-y-3 bg-gray-900 rounded-xl p-5 border border-gray-800">
        <p className="text-xs uppercase tracking-widest text-gray-500 mb-3">Pipeline</p>
        {events.map((ev, i) => (
          <AgentStep key={i} event={ev} isLatest={running && i === events.length - 1} />
        ))}
        {running && events.length === 0 && (
          <p className="text-sm text-gray-500 animate-pulse">Starting pipeline…</p>
        )}
        {error && <p className="text-sm text-red-400">Error: {error}</p>}
      </div>

      {/* Report */}
      {report !== null && (
        <div className="bg-gray-900 rounded-xl p-6 border border-gray-800 prose prose-invert prose-sm max-w-none">
          <p className="text-xs uppercase tracking-widest text-gray-500 mb-4 not-prose">Report</p>
          <ReactMarkdown>{report}</ReactMarkdown>
        </div>
      )}
    </div>
  );
}

export default function ResearchPage() {
  return (
    <Suspense fallback={<p className="text-gray-400 text-center mt-20">Loading…</p>}>
      <ResearchContent />
    </Suspense>
  );
}
