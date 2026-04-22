import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";
import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Research Orchestrator",
  description: "Multi-agent AI research pipeline",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable} h-full`}>
      <body className="min-h-full flex flex-col bg-gray-950 text-gray-100 antialiased">
        <header className="border-b border-gray-800 px-6 py-4 flex items-center gap-8">
          <Link href="/" className="text-lg font-semibold tracking-tight text-white">
            Research Orchestrator
          </Link>
          <nav className="flex gap-6 text-sm text-gray-400">
            <Link href="/" className="hover:text-white transition-colors">New Research</Link>
            <Link href="/history" className="hover:text-white transition-colors">History</Link>
          </nav>
        </header>
        <main className="flex-1 flex flex-col">{children}</main>
      </body>
    </html>
  );
}
