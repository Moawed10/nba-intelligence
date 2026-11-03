import Link from "next/link";

import { PageHeader } from "@/components/data/page-header";

export default function TeamNotFound() {
  return (
    <>
      <PageHeader title="Team not found" description="There's no team at this address." />
      <Link href="/players" className="btn btn-primary">
        Browse players
      </Link>
    </>
  );
}
