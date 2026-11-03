"use client";

import { Search } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { PlayerSearch } from "@/components/data/player-search";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";

function typingIn(target: EventTarget | null): boolean {
  return (
    target instanceof HTMLElement &&
    (target.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName))
  );
}

/** Global player search: the top-bar button, ⌘K / Ctrl+K, or "/" outside text fields. */
export function CommandSearch() {
  const router = useRouter();
  const [open, setOpen] = useState(false);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      const shortcut = (event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k";
      if (shortcut || (event.key === "/" && !typingIn(event.target))) {
        event.preventDefault();
        setOpen(true);
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-keyshortcuts="Meta+K Control+K /"
        className="inline-flex size-10 items-center justify-center gap-2 rounded-full text-muted-foreground transition-colors duration-150 hover:bg-muted hover:text-foreground pointer-coarse:size-11 lg:h-10 lg:w-full lg:max-w-md lg:justify-start lg:bg-muted lg:px-4 lg:hover:bg-thumb"
      >
        <Search aria-hidden className="size-4" />
        <span className="sr-only lg:not-sr-only lg:whitespace-nowrap">Search players and teams</span>
        <kbd
          aria-hidden
          className="ml-auto hidden rounded bg-background px-1.5 font-mono text-[0.75rem] lg:inline"
        >
          ⌘K
        </kbd>
      </button>
      <DialogContent className="top-[12vh] max-w-xl translate-y-0 gap-3 p-4 sm:p-5" showCloseButton={false}>
        <DialogTitle className="text-headline">Find a player or team</DialogTitle>
        <DialogDescription className="sr-only">
          Type a name, then choose a player or team to open their page.
        </DialogDescription>
        <PlayerSearch
          startOpen
          hideLabel
          listMode="inline"
          label="Search players and teams"
          onSelect={(player) => {
            setOpen(false);
            router.push(`/players/${player.id}`);
          }}
          onSelectTeam={(team) => {
            setOpen(false);
            router.push(`/teams/${team.id}`);
          }}
        />
        <p className="text-footnote text-muted-foreground">
          Names match without accents and forgive one typo. Game logs cover 2018-19 onward.
        </p>
      </DialogContent>
    </Dialog>
  );
}
