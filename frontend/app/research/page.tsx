"use client";

import { useSearchParams } from "next/navigation";
import { useEffect, useRef, useState, Suspense } from "react";
import ReactMarkdown from "react-markdown";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type AgentEvent = {
  agent: string;
  status: string;
  report?: string;
  details?: string[];
};

type Step = {
  agent: string;
  status: string;
  details?: string[];
  done: boolean;
};

const AGENT_DETAIL_LABEL: Record<string, string> = {
  planner: "Topics to explore",
  extractor: "Key findings",
};

const AGENT_META: Record<string, { label: string; description: string }> = {
  planner: {
    label: "Planning",
    description: "Breaking your question into focused research areas",
  },
  memory_retrieve: {
    label: "Checking knowledge base",
    description: "Looking for relevant information from past research",
  },
  researcher: {
    label: "Searching the web",
    description: "Gathering sources across all research areas",
  },
  extractor: {
    label: "Analyzing sources",
    description: "Extracting the most relevant facts and insights",
  },
  critic: {
    label: "Reviewing research",
    description: "Checking that the research is thorough and accurate",
  },
  rework: {
    label: "Deepening research",
    description: "Going deeper to find more comprehensive information",
  },
  writer: {
    label: "Writing report",
    description: "Putting everything together into a clear report",
  },
  memory_save: {
    label: "Wrapping up",
    description: "Saving this research for future reference",
  },
};

function toUserStatus(agent: string, raw: string): string {
  const num = raw.match(/\d+/);
  const n = num ? parseInt(num[0]) : null;

  if (agent === "planner" && n !== null)
    return `Identified ${n} research ${n === 1 ? "angle" : "angles"}`;
  if (agent === "memory_retrieve")
    return raw.includes("No memory") ? "No prior research found" : "Found relevant prior research";
  if (agent === "researcher" && n !== null)
    return `Gathered ${n} ${n === 1 ? "source" : "sources"}`;
  if (agent === "extractor" && n !== null)
    return `Found ${n} key ${n === 1 ? "insight" : "insights"}`;
  if (agent === "critic")
    return raw.includes("GOOD") ? "Research looks comprehensive" : "Needs more depth";
  if (agent === "rework" && n !== null)
    return `Deepening search, pass ${n}`;
  if (agent === "writer") return "Assembling your report";
  if (agent === "memory_save") return "Done";
  return "";
}

function CheckIcon() {
  return (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
    </svg>
  );
}

function StepItem({
  step,
  isActive,
  isLast,
}: {
  step: Step;
  isActive: boolean;
  isLast: boolean;
}) {
  const meta = AGENT_META[step.agent];
  if (!meta) return null;

  return (
    <div className="flex items-start gap-4">
      {/* Icon + connector line */}
      <div className="flex flex-col items-center flex-shrink-0">
        <div
          className={`w-8 h-8 rounded-full flex items-center justify-center transition-colors duration-300
            ${step.done
              ? "bg-emerald-600 text-white"
              : isActive
              ? "bg-blue-500 text-white"
              : "bg-gray-800 border border-gray-700 text-gray-500"
            }`}
        >
          {step.done ? (
            <CheckIcon />
          ) : isActive ? (
            <span className="block w-2.5 h-2.5 rounded-full bg-white animate-ping" />
          ) : (
            <span className="block w-2 h-2 rounded-full bg-gray-600" />
          )}
        </div>
        {!isLast && (
          <div
            className={`w-0.5 min-h-[24px] mt-1 mb-1 transition-colors duration-500
              ${step.done ? "bg-emerald-800" : "bg-gray-800"}`}
          />
        )}
      </div>

      {/* Text */}
      <div className={`pb-6 min-w-0 transition-opacity duration-300 ${!isActive && !step.done ? "opacity-35" : ""}`}>
        <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
          <span
            className={`text-sm font-semibold ${
              step.done ? "text-gray-200" : isActive ? "text-white" : "text-gray-500"
            }`}
          >
            {meta.label}
          </span>
          {step.done && step.status && (
            <span className="text-xs text-emerald-400">{step.status}</span>
          )}
          {isActive && (
            <span className="text-xs text-blue-400 animate-pulse">In progress…</span>
          )}
        </div>
        <p className={`text-xs mt-0.5 leading-relaxed ${isActive ? "text-gray-300" : "text-gray-500"}`}>
          {meta.description}
        </p>
        {step.done && step.details && step.details.length > 0 && (
          <div className="mt-2">
            <p className="text-xs text-gray-500 mb-1">{AGENT_DETAIL_LABEL[step.agent]}</p>
            <ul className="space-y-1">
              {step.details.map((item, i) => (
                <li key={i} className="flex items-start gap-1.5 text-xs text-gray-400">
                  <span className="mt-1 w-1 h-1 rounded-full bg-gray-600 flex-shrink-0" />
                  {item}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}

function ResearchContent() {
  const params = useSearchParams();
  const query = params.get("q") ?? "";

  const [steps, setSteps] = useState<Step[]>([]);
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

        if (!res.ok) throw new Error("The research service is currently unavailable. Please try again.");
        if (!res.body) throw new Error("No response received from the server.");

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
                setSteps((prev) =>
                  prev.map((s, i) => (i === prev.length - 1 ? { ...s, done: true } : s))
                );
              } else if (AGENT_META[ev.agent]) {
                setSteps((prev) => {
                  const allDone = prev.map((s) => ({ ...s, done: true }));
                  return [
                    ...allDone,
                    {
                      agent: ev.agent,
                      status: toUserStatus(ev.agent, ev.status),
                      details: ev.details,
                      done: false,
                    },
                  ];
                });
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

  const doneCount = steps.filter((s) => s.done).length;
  const totalCount = steps.length;
  const activeIdx = running ? steps.length - 1 : -1;

  return (
    <div className="max-w-3xl mx-auto w-full px-6 py-10 space-y-8">
      {/* Query header */}
      <div>
        <p className="text-xs uppercase tracking-widest text-gray-500 mb-1">Research query</p>
        <h1 className="text-2xl font-semibold text-white">{query}</h1>
      </div>

      {/* Progress card */}
      <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-hidden">
        {/* Card header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-800">
          <div className="flex items-center gap-2.5">
            {running && <span className="w-2 h-2 rounded-full bg-blue-400 animate-pulse flex-shrink-0" />}
            {!running && report !== null && <span className="w-2 h-2 rounded-full bg-emerald-400 flex-shrink-0" />}
            {!running && report === null && !error && <span className="w-2 h-2 rounded-full bg-gray-600 flex-shrink-0" />}
            <span className="text-sm font-medium text-gray-200">
              {running
                ? "Researching your question…"
                : report !== null
                ? "Research complete"
                : error
                ? "Research stopped"
                : "Starting…"}
            </span>
          </div>
          {totalCount > 0 && (
            <span className="text-xs text-gray-500 tabular-nums">
              {doneCount} / {totalCount} steps
            </span>
          )}
        </div>

        {/* Steps */}
        <div className="px-5 pt-5">
          {steps.length === 0 && running && (
            <div className="flex items-center gap-4 pb-6">
              <div className="w-8 h-8 rounded-full bg-blue-500 flex items-center justify-center flex-shrink-0">
                <span className="block w-2.5 h-2.5 rounded-full bg-white animate-ping" />
              </div>
              <span className="text-sm text-gray-400 animate-pulse">Starting research…</span>
            </div>
          )}

          {steps.map((step, i) => (
            <StepItem
              key={`${step.agent}-${i}`}
              step={step}
              isActive={i === activeIdx}
              isLast={i === steps.length - 1}
            />
          ))}

          {error && (
            <div className="flex items-start gap-4 pb-6">
              <div className="w-8 h-8 rounded-full bg-red-950 border border-red-800 flex items-center justify-center flex-shrink-0 text-red-400 font-bold">
                !
              </div>
              <div>
                <p className="text-sm font-semibold text-red-400">Something went wrong</p>
                <p className="text-xs text-gray-500 mt-0.5">{error}</p>
              </div>
            </div>
          )}
        </div>
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
