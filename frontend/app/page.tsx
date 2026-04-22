"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

const EXAMPLES = [
  "What is retrieval-augmented generation?",
  "How do transformer models work?",
  "What are the benefits of vector databases?",
];

export default function Home() {
  const router = useRouter();
  const [query, setQuery] = useState("");

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const q = query.trim();
    if (!q) return;
    router.push(`/research?q=${encodeURIComponent(q)}`);
  }

  return (
    <div className="flex-1 flex flex-col items-center justify-center px-6 py-24 gap-10">
      <div className="text-center space-y-3">
        <h1 className="text-4xl font-bold tracking-tight text-white">
          Multi-Agent Research
        </h1>
        <p className="text-gray-400 text-lg max-w-lg">
          Ask any question. A pipeline of AI agents will search the web, extract
          facts, critique quality, and write you a report.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="w-full max-w-2xl flex gap-3">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="What are the trade-offs between LangGraph and AutoGen?"
          className="flex-1 rounded-lg bg-gray-900 border border-gray-700 px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        />
        <button
          type="submit"
          disabled={!query.trim()}
          className="px-6 py-3 rounded-lg bg-blue-600 text-white font-medium hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          Research
        </button>
      </form>

      <div className="flex gap-3 flex-wrap justify-center">
        {EXAMPLES.map((example) => (
          <button
            key={example}
            onClick={() => setQuery(example)}
            className="text-sm px-4 py-2 rounded-full border border-gray-700 text-gray-400 hover:text-white hover:border-gray-500 transition-colors"
          >
            {example}
          </button>
        ))}
      </div>
    </div>
  );
}
