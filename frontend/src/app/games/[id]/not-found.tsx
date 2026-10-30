import Link from "next/link";

import { PageHeader } from "@/components/data/page-header";

export default function GameNotFound() {
  return (
    <>
      <PageHeader title="Game not found" description="There is no game with that id in our schedule." />
      <Link href="/games" className="text-subhead font-medium text-primary hover:underline">
        Browse games by date
      </Link>
    </>
  );
}
