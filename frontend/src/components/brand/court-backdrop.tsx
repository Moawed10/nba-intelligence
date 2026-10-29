import { cn } from "@/lib/utils";

/** Faint half-court lines (three-point arc, lane, free-throw circle) behind hero sections. */
export function CourtBackdrop({ className, color }: { className?: string; color?: string | null }) {
  const stroke = color ?? "var(--foreground)";
  return (
    <svg
      aria-hidden
      viewBox="0 0 500 470"
      preserveAspectRatio="xMaxYMid slice"
      className={cn("pointer-events-none absolute inset-0 h-full w-full", className)}
    >
      <g fill="none" stroke={stroke} strokeWidth="2" opacity="0.09">
        <path d="M30 0 V140 A220 220 0 0 0 470 140 V0" />
        <rect x="170" y="0" width="160" height="190" />
        <circle cx="250" cy="190" r="60" />
        <path d="M210 40 A40 40 0 0 0 290 40" />
        <line x1="220" y1="40" x2="280" y2="40" />
        <circle cx="250" cy="55" r="7.5" />
        <path d="M0 470 H500" />
        <path d="M190 470 A60 60 0 0 1 310 470" />
      </g>
    </svg>
  );
}
