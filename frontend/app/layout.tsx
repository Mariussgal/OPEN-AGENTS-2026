import type { Metadata } from "next";
import { GeistSans } from "geist/font/sans";
import { GeistMono } from "geist/font/mono";
import { TooltipProvider } from "@/components/ui/tooltip";
import "./globals.css";

export const metadata: Metadata = {
  title: "Onchor.ai — Solidity Security Copilot",
  description:
    "AI-powered Solidity audits with persistent memory. Finds vulnerabilities your tools miss — powered by pattern recognition across thousands of past audits.",
  keywords: ["solidity", "security", "audit", "smart contracts", "defi", "vulnerability"],
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <body
        className={`${GeistSans.variable} ${GeistMono.variable} antialiased bg-background text-foreground min-h-screen`}
        suppressHydrationWarning
      >
        <TooltipProvider delay={0}    >
          {children}
        </TooltipProvider>
      </body>
    </html>
  );
}