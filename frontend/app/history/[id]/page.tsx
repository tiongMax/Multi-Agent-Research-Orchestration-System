import Link from "next/link";
import { notFound } from "next/navigation";
import ReactMarkdown from "react-markdown";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type HistoryItem = {
  id: number;
  query: string;
  report: string;
  sub_questions: string[];
  facts: string[];
  created_at: string;
};

async function getItem(id: string): Promise<HistoryItem | null> {
  try {
    const res = await fetch(`${API}/research/history`, { cache: "no-store" });
    if (!res.ok) return null;
    const items: HistoryItem[] = await res.json();
    return items.find((i) => String(i.id) === id) ?? null;
  } catch {
    return null;
  }
}

export default async function ReportPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const item = await getItem(id);
  if (!item) notFound();

  return (
    <div className="max-w-3xl mx-auto w-full px-6 py-10 space-y-8">
      <div className="flex items-start justify-between gap-4">
        <div>
          <Link href="/history" className="text-xs text-gray-500 hover:text-gray-300 transition-colors">
            ← History
          </Link>
          <h1 className="text-2xl font-semibold text-white mt-2">{item.query}</h1>
          <p className="text-sm text-gray-500 mt-1">{new Date(item.created_at).toLocaleString()}</p>
        </div>
      </div>

      {/* Sub-questions */}
      <div className="bg-gray-900 rounded-xl p-5 border border-gray-800 space-y-2">
        <p className="text-xs uppercase tracking-widest text-gray-500">Sub-questions</p>
        <ol className="list-decimal list-inside space-y-1">
          {item.sub_questions.map((q, i) => (
            <li key={i} className="text-sm text-gray-300">{q}</li>
          ))}
        </ol>
      </div>

      {/* Facts */}
      <div className="bg-gray-900 rounded-xl p-5 border border-gray-800 space-y-2">
        <p className="text-xs uppercase tracking-widest text-gray-500">
          Extracted Facts ({item.facts.length})
        </p>
        <ul className="space-y-1">
          {item.facts.map((f, i) => (
            <li key={i} className="text-sm text-gray-300 flex gap-2">
              <span className="text-gray-600 flex-shrink-0">—</span>
              <span>{f}</span>
            </li>
          ))}
        </ul>
      </div>

      {/* Report */}
      <div className="bg-gray-900 rounded-xl p-6 border border-gray-800 prose prose-invert prose-sm max-w-none">
        <p className="text-xs uppercase tracking-widest text-gray-500 mb-4 not-prose">Report</p>
        <ReactMarkdown>{item.report}</ReactMarkdown>
      </div>
    </div>
  );
}
