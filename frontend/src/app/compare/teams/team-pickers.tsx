"use client";

import { ArrowLeftRight } from "lucide-react";
import { useRouter } from "next/navigation";
import { useTransition } from "react";

import { hrefWith } from "@/lib/url";
import { cn } from "@/lib/utils";

export interface Slot {
  teamId: number | null;
  season: string | null;
  /** That franchise's seasons, newest first, labelled with the name it had then. */
  seasons: { season: string; label: string }[];
}

interface Franchise {
  id: number;
  label: string;
}

const SELECT = "min-h-10 w-full rounded-lg border border-border bg-card px-3 text-subhead";

/** Two franchise + season pairs held in ?t1=&s1=&t2=&s2= so any comparison can be shared. */
export function TeamPickers({ franchises, slots }: { franchises: Franchise[]; slots: [Slot, Slot] }) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();

  function go(next: [Partial<Slot>, Partial<Slot>]) {
    const [a, b] = next;
    startTransition(() =>
      router.push(
        hrefWith("/compare/teams", {}, { t1: a.teamId, s1: a.season, t2: b.teamId, s2: b.season }),
        { scroll: false },
      ),
    );
  }

  function update(index: 0 | 1, change: Partial<Slot>) {
    const next: [Partial<Slot>, Partial<Slot>] = [{ ...slots[0] }, { ...slots[1] }];
    next[index] = { ...next[index], ...change };
    go(next);
  }

  return (
    <div
      aria-busy={pending}
      className={cn(
        "grid items-end gap-3 transition-opacity md:grid-cols-[1fr_auto_1fr]",
        pending && "opacity-70",
      )}
    >
      {([0, 1] as const).map((index) => {
        const slot = slots[index];
        const label = `Team ${index + 1}`;
        return (
          <fieldset
            key={index}
            className={cn(
              "grid gap-2 rounded-xl border border-border bg-card p-3 sm:grid-cols-2 sm:p-4",
              index === 1 && "md:order-3",
            )}
          >
            <legend className="kicker px-1">{label}</legend>
            <label className="grid gap-1 text-footnote text-muted-foreground">
              Franchise
              <select
                className={SELECT}
                value={slot.teamId ?? ""}
                onChange={(e) => update(index, { teamId: Number(e.target.value) || null, season: null })}
              >
                <option value="">Choose a franchise</option>
                {franchises.map((f) => (
                  <option key={f.id} value={f.id}>
                    {f.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="grid gap-1 text-footnote text-muted-foreground">
              Season
              <select
                className={SELECT}
                value={slot.season ?? ""}
                disabled={!slot.seasons.length}
                onChange={(e) => update(index, { season: e.target.value })}
              >
                {slot.seasons.map((s) => (
                  <option key={s.season} value={s.season}>
                    {s.label}
                  </option>
                ))}
              </select>
            </label>
          </fieldset>
        );
      })}
      <div className="flex justify-center md:order-2 md:pb-4">
        <button
          type="button"
          aria-label="Swap teams"
          disabled={!slots[0].teamId || !slots[1].teamId}
          onClick={() => go([slots[1], slots[0]])}
          className="inline-flex size-9 items-center justify-center rounded-full border border-border text-muted-foreground transition-colors hover:border-foreground/25 hover:text-foreground disabled:pointer-events-none disabled:opacity-40 pointer-coarse:size-11"
        >
          <ArrowLeftRight aria-hidden className="size-4" />
        </button>
      </div>
    </div>
  );
}
