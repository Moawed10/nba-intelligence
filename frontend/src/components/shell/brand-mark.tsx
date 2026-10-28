/** A ball-seam glyph in the accent color; decorative, so hidden from assistive tech. */
export function BrandMark() {
  return (
    <svg aria-hidden viewBox="0 0 24 24" className="size-6 text-primary" fill="none">
      <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="2" />
      <path
        d="M2 12h20M12 2v20M5 5c3 3 3 11 0 14M19 5c-3 3-3 11 0 14"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
    </svg>
  );
}
