import type { ReactNode } from "react";

/** Each navigation remounts the template, replaying a short rise-and-fade that never blocks input. */
export default function PageTransition({ children }: { children: ReactNode }) {
  return <div className="page-in">{children}</div>;
}
