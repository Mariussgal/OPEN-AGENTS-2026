"use client";

import Image from "next/image";
import { useRouter } from "next/navigation";
import { Terminal } from "lucide-react";

export default function NotFound() {
    const router = useRouter();

    return (
        <div className="min-h-screen bg-[#0a0a0a] text-zinc-100 font-sans flex items-center justify-center relative selection:bg-white/20">
            {/* Subtle modern background blur */}
            <div className="absolute top-0 left-1/2 -translate-x-1/2 w-full max-w-3xl h-[400px] bg-white opacity-[0.02] rounded-[100%] blur-[100px] pointer-events-none" />

            <div className="text-center relative z-10">
                <div className="text-8xl font-bold text-zinc-800 mb-6 tracking-tight">404</div>
                <div className="text-lg font-medium text-red-400 mb-2">Page not found.</div>

                <div className="border border-white/5 bg-zinc-900/40 p-5 rounded-2xl inline-block text-left mb-10">
                    <div className="flex items-center gap-2">
                        <span className="font-mono text-sm text-[#0DFC67]">$</span>
                        <span className="font-mono text-sm text-zinc-400">Onchor-ai --help</span>
                        <span className="w-2 h-4 bg-[#0DFC67] animate-blink inline-block ml-1" />
                    </div>
                </div>

                <div className="flex items-center justify-center gap-6">
                    <button
                        onClick={() => router.push("/")}
                        className="text-sm text-zinc-500 hover:text-zinc-300 transition-colors font-medium"
                    >
                        ← Home
                    </button>
                    <button
                        onClick={() => router.push("/history")}
                        className="text-sm text-[#0DFC67] hover:opacity-80 transition-opacity font-medium"
                    >
                        Audit History →
                    </button>
                </div>
            </div>
        </div>
    );
}