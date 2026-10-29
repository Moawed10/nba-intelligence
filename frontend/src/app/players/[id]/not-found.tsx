import Link from "next/link";

import { PageHeader } from "@/components/data/page-header";
import { StateView } from "@/components/data/state-view";

export default function PlayerNotFound() {
  return (
    <>
      <PageHeader title="Player not found" />
      <StateView
        kind="empty"
        title="We couldn't find that player"
        message="The link may be mistyped, or the player isn't in our records."
        action={
          <Link
            href="/players"
            className="inline-flex min-h-10 items-center rounded-lg px-3 text-subhead font-medium text-primary hover:underline"
          >
            Search players
          </Link>
        }
      />
    </>
  );
}
