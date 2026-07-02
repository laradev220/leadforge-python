"use client";

import Link from "next/link";
import { useEffect } from "react";
import { AlertOctagon, ArrowLeft, RefreshCw } from "lucide-react";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Surface to your error tracker of choice.
    console.error("[LeadForge] Unhandled error:", error);
  }, [error]);

  return (
    <div className="min-h-screen flex items-center justify-center px-6">
      <div className="max-w-md w-full text-center">
        <div className="inline-flex h-14 w-14 items-center justify-center bg-ember/10 text-ember mb-6">
          <AlertOctagon size={22} />
        </div>
        <p className="status text-ink-mute mb-3">
          <span className="status-dot bg-ember" /> unhandled error
        </p>
        <h1 className="display text-display-lg text-balance mb-4">
          Something cracked.
        </h1>
        <p className="text-ink-mute text-sm mb-8 max-w-sm mx-auto">
          {error.message || "An unexpected error stopped this view from rendering."}
          {error.digest && (
            <span className="block mt-2 font-mono text-xs text-ink-ghost">
              ref · {error.digest}
            </span>
          )}
        </p>
        <div className="flex items-center justify-center gap-3">
          <button onClick={() => reset()} className="btn-solid">
            <RefreshCw size={14} /> Try again
          </button>
          <Link href="/dashboard" className="btn-outline">
            <ArrowLeft size={14} /> Dashboard
          </Link>
        </div>
      </div>
    </div>
  );
}
