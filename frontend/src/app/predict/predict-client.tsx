"use client";

import { useRouter } from "next/navigation";
import { useTransition } from "react";

import { PlayerSearch } from "@/components/data/player-search";
import { cn } from "@/lib/utils";

export function PredictPicker({ label = "Player" }: { label?: string }) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  return (
    <div aria-busy={pending} className={cn("max-w-xl transition-opacity", pending && "opacity-70")}>
      <PlayerSearch
        label={label}
        onSelect={(player) =>
          startTransition(() => router.push(`/predict?player=${player.id}`, { scroll: false }))
        }
      />
    </div>
  );
}
