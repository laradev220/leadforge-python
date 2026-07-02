import Link from "next/link";
import { Compass } from "lucide-react";

export default function NotFound() {
  return (
    <div className="min-h-screen flex items-center justify-center px-6">
      <div className="max-w-md w-full text-center">
        <p className="status text-ink-mute mb-3 justify-center">
          <span className="status-dot bg-ink-ghost" /> 404
        </p>
        <h1 className="display text-display-xl text-balance mb-4">
          Off the map.
        </h1>
        <p className="text-ink-mute text-sm mb-8 max-w-sm mx-auto">
          The page you're looking for either moved or never existed. Try
          heading back to the dashboard.
        </p>
        <Link href="/dashboard" className="btn-solid">
          <Compass size={14} /> Go to dashboard
        </Link>
      </div>
    </div>
  );
}
