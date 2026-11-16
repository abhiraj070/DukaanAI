import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "DukaanAI — Decision Intelligence for Indian Kiranas",
  description:
    "Agentic predictive business intelligence and decision platform for Indian retail",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="min-h-full flex flex-col bg-slate-50 text-slate-900">{children}</body>
    </html>
  );
}
