import Link from "next/link";

import { StateView } from "./state-view";

/** Shown where a screen's data API does not exist yet. Never stands in for real data. */
export function NotConnected({ shows, title }: { shows: string; title?: string }) {
  return (
    <StateView
      kind="unavailable"
      title={title ?? "Live data isn't connected to this screen yet"}
      message={`When it is, this screen will show ${shows}. Nothing here is sample or placeholder data.`}
      action={
        <Link
          href="/about"
          className="inline-flex min-h-10 items-center rounded-lg px-3 text-subhead font-medium text-primary hover:underline"
        >
          How the data works
        </Link>
      }
    />
  );
}
