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
        className="inline-flex h-9 min-w-9 pointer-coarse:h-11 pointer-coarse:min-w-11 items-center justify-center gap-2 rounded-full border border-border bg-card/60 px-2.5 text-subhead text-muted-foreground transition-colors hover:border-foreground/20 hover:text-foreground xl:w-56 xl:justify-start xl:px-3"
      >
        <Search aria-hidden className="size-4" />
        <span className="sr-only xl:not-sr-only">Search players</span>
        <kbd
          aria-hidden
          className="ml-auto hidden rounded border border-border px-1.5 font-mono text-[0.6875rem] xl:inline"
        >
          ⌘K
        </kbd>
      </button>
      <DialogContent className="top-[12vh] max-w-xl translate-y-0 gap-3 p-4 sm:p-5" showCloseButton={false}>
        <DialogTitle className="text-headline">Find a player</DialogTitle>
        <DialogDescription className="sr-only">
          Type a name, then choose a player to open their profile.
        </DialogDescription>
        <PlayerSearch
          startOpen
          hideLabel
          listMode="inline"
          label="Search players"
          onSelect={(player) => {
            setOpen(false);
            router.push(`/players/${player.id}`);
          }}
        />
        <p className="text-footnote text-muted-foreground">
          Names match without accents and forgive one typo. Game logs cover 2018-19 onward.
        </p>
      </DialogContent>
    </Dialog>
  );
}
