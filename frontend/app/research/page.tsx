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
  kind?: string;
};

const SSE_ERROR_MESSAGES: Record<string, string> = {
  rate_limit: "The AI service is temporarily rate-limited. Please wait a minute and try again.",
  timeout: "The research took too long to complete. Please try again.",
  unknown: "Research failed unexpectedly. Please try again.",
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

function StopIcon() {
  return (
    <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 24 24">
      <rect x="4" y="4" width="16" height="16" rx="2" />
    </svg>
  );
}

function RetryIcon() {
  return (
    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
    </svg>
  );
}

function StepItem({
  step,
  isActive,
  isLast,
  isStopped,
}: {
  step: Step;
  isActive: boolean;
  isLast: boolean;
  isStopped: boolean;
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
              : isStopped
              ? "bg-amber-950 border border-amber-800 text-amber-400"
              : isActive
              ? "bg-blue-500 text-white"
              : "bg-gray-800 border border-gray-700 text-gray-500"
            }`}
        >
          {step.done ? (
            <CheckIcon />
          ) : isStopped ? (
            <StopIcon />
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
      <div className={`pb-6 min-w-0 transition-opacity duration-300 ${!isActive && !step.done && !isStopped ? "opacity-35" : ""}`}>
        <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
          <span
            className={`text-sm font-semibold ${
              step.done ? "text-gray-200" : isStopped ? "text-amber-400" : isActive ? "text-white" : "text-gray-500"
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
          {isStopped && (
            <span className="text-xs text-amber-600">Stopped</span>
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
  const [stopped, setStopped] = useState(false);
  const [runCount, setRunCount] = useState(0);

  const controllerRef = useRef<AbortController | null>(null);
  const stoppedByUserRef = useRef(false);
  // Prevents double-invoke on initial mount (React StrictMode)
  const initialStarted = useRef(false);

  useEffect(() => {
    if (!query) return;
    if (runCount === 0 && initialStarted.current) return;
    initialStarted.current = true;

    stoppedByUserRef.current = false;
    setSteps([]);
    setReport(null);
    setError(null);
    setStopped(false);
    setRunning(true);

    const controller = new AbortController();
    controllerRef.current = controller;

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
              } else if (ev.agent === "error") {
                const msg = SSE_ERROR_MESSAGES[ev.kind ?? "unknown"] ?? SSE_ERROR_MESSAGES.unknown;
                setError(msg);
                setStopped(true);
                setRunning(false);
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
        if (e instanceof Error && e.name === "AbortError") {
          if (stoppedByUserRef.current) setStopped(true);
          // else: cleanup abort on unmount/re-run — ignore
        } else {
          setError(e instanceof Error ? e.message : "Something went wrong.");
        }
        setRunning(false);
      }
    })();

    return () => controller.abort();
  }, [query, runCount]);

  function handleStop() {
    stoppedByUserRef.current = true;
    controllerRef.current?.abort();
  }

  function handleRetry() {
    setRunCount((c) => c + 1);
  }

  if (!query) {
    return <p className="text-gray-400 text-center mt-20">No query provided.</p>;
  }

  const doneCount = steps.filter((s) => s.done).length;
  const totalCount = steps.length;
  const activeIdx = running ? steps.length - 1 : -1;
  const stoppedIdx = (stopped || error !== null) && !running ? steps.length - 1 : -1;
  const showRetry = (stopped || error !== null) && !running;

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
            {!running && stopped && <span className="w-2 h-2 rounded-full bg-amber-500 flex-shrink-0" />}
            {!running && error !== null && <span className="w-2 h-2 rounded-full bg-red-500 flex-shrink-0" />}
            <span className="text-sm font-medium text-gray-200">
              {running
                ? "Researching your question…"
                : report !== null
                ? "Research complete"
                : stopped
                ? "Research stopped"
                : error
                ? "Something went wrong"
                : "Starting…"}
            </span>
          </div>

          <div className="flex items-center gap-3">
            {totalCount > 0 && (
              <span className="text-xs text-gray-500 tabular-nums">
                {doneCount} / {totalCount} steps
              </span>
            )}
            {running && (
              <button
                onClick={handleStop}
                className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg bg-gray-800 hover:bg-red-950 border border-gray-700 hover:border-red-800 text-gray-400 hover:text-red-400 transition-colors"
              >
                <StopIcon />
                Stop
              </button>
            )}
            {showRetry && (
              <button
                onClick={handleRetry}
                className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg bg-gray-800 hover:bg-gray-700 border border-gray-700 text-gray-300 transition-colors"
              >
                <RetryIcon />
                Try again
              </button>
            )}
          </div>
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
              isStopped={i === stoppedIdx}
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
