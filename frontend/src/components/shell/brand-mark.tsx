/** A ball-seam glyph in the accent color; decorative, so hidden from assistive tech. */
export function BrandMark() {
  return (
    <svg aria-hidden viewBox="0 0 24 24" className="size-6 text-primary" fill="none">
      <circle cx="12" cy="12" r="10.25" stroke="currentColor" strokeWidth="1.5" />
      <path
        d="M1.75 12h20.5M12 1.75v20.5M5 4.75c3.2 3.4 3.2 11.1 0 14.5M19 4.75c-3.2 3.4-3.2 11.1 0 14.5"
        stroke="currentColor"
        strokeWidth="1.25"
        strokeLinecap="round"
      />
    </svg>
  );
}
