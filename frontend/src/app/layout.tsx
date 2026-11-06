import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AutoSync Video - Desktop Studio",
  description: "Automated Video & Voiceover Synchronization Engine",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="id" className="dark h-full antialiased">
      <body className="min-h-full flex flex-col bg-slate-950 text-slate-100">{children}</body>
    </html>
  );
}
