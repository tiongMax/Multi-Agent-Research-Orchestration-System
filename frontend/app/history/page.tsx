import Link from "next/link";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type HistoryItem = {
  id: number;
  query: string;
  report: string;
  sub_questions: string[];
  facts: string[];
  created_at: string;
};

async function getHistory(): Promise<HistoryItem[]> {
  try {
    const res = await fetch(`${API}/research/history`, { cache: "no-store" });
    if (!res.ok) return [];
    return res.json();
  } catch {
    return [];
  }
}

export default async function HistoryPage() {
  const items = await getHistory();

  return (
    <div className="max-w-3xl mx-auto w-full px-6 py-10 space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-white">Research History</h1>
        <p className="text-gray-400 text-sm mt-1">{items.length} past sessions</p>
      </div>

      {items.length === 0 ? (
        <div className="text-center py-20 text-gray-500">
          <p>No research sessions yet.</p>
          <Link href="/" className="text-blue-400 hover:underline text-sm mt-2 inline-block">
            Start your first research →
          </Link>
        </div>
      ) : (
        <ul className="space-y-3">
          {items.map((item) => (
            <li key={item.id}>
              <Link
                href={`/history/${item.id}`}
                className="block bg-gray-900 border border-gray-800 rounded-xl px-5 py-4 hover:border-gray-600 transition-colors"
              >
                <p className="text-white font-medium truncate">{item.query}</p>
                <div className="flex gap-4 mt-1 text-xs text-gray-500">
                  <span>{item.facts.length} facts</span>
                  <span>{item.sub_questions.length} sub-questions</span>
                  <span>{new Date(item.created_at).toLocaleString()}</span>
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
