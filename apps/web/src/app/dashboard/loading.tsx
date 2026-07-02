export default function DashboardLoading() {
  return (
    <div className="space-y-12 animate-fade-in">
      {/* Header */}
      <div className="space-y-4">
        <div className="h-3 w-24 bg-paper-mute animate-pulse" />
        <div className="h-12 w-72 bg-paper-mute animate-pulse" />
      </div>

      {/* Stat strip */}
      <div className="grid grid-cols-1 md:grid-cols-3 border-t border-line">
        {[0, 1, 2].map((i) => (
          <div
            key={i}
            className={`py-8 ${i > 0 ? "md:border-l border-line md:pl-8" : ""}`}
          >
            <div className="h-2.5 w-20 bg-paper-mute animate-pulse mb-3" />
            <div className="h-12 w-24 bg-paper-mute animate-pulse" />
          </div>
        ))}
      </div>

      {/* Card blocks */}
      <div className="grid md:grid-cols-2 gap-12">
        <div className="space-y-4">
          <div className="h-6 w-40 bg-paper-mute animate-pulse" />
          <div className="h-3 w-full bg-paper-mute/60 animate-pulse" />
          <div className="h-3 w-3/4 bg-paper-mute/60 animate-pulse" />
          <div className="h-10 w-36 bg-ink animate-pulse mt-6" />
        </div>
        <div className="space-y-4">
          <div className="h-6 w-40 bg-paper-mute animate-pulse" />
          <div className="space-y-2">
            {[0, 1, 2, 3].map((i) => (
              <div
                key={i}
                className="h-10 w-full bg-paper-mute/40 animate-pulse"
                style={{ animationDelay: `${i * 80}ms` }}
              />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
