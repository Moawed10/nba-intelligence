import type { Metadata } from "next";

import { InfoHint } from "@/components/data/info-hint";
import { PageHeader } from "@/components/data/page-header";

export const metadata: Metadata = { title: "About" };

const SECTIONS = [
  {
    title: "Data",
    body: [
      "Box scores, schedules and player details come from the NBA's public statistics service through the open-source nba_api library. They are copied into this app's own database by scheduled jobs, so pages never call the NBA directly.",
      "Coverage starts with the 2018-19 season and includes regular season, play-in and playoff games. Every stored record keeps where it came from and when it was last updated, and corrections from the source are logged rather than silently overwritten.",
    ],
  },
  {
    title: "How predictions are made",
    body: [
      "Each prediction uses only information available before tip-off: recent form over the last 3, 5 and 10 games, season averages, rest, home or away, and the opponent's recent defense and pace.",
      "Several models are trained on past seasons and compared with a simple baseline (the player's last-10-game average) on a later season none of them saw. A model is used only where it beats that baseline.",
    ],
  },
  {
    title: "Limitations",
    body: [
      "Predictions assume the player plays. The data source has no injury or lineup feed, so a late scratch is not anticipated.",
      "Ranges cover the actual result about 80% of the time on average, not for every individual game. Role changes, trades and injuries can make a player's recent history less predictive.",
      "Player photos are not shown, because NBA headshots are NBA property.",
    ],
  },
];

export default function AboutPage() {
  return (
    <>
      <PageHeader
        title="About"
        description="Where the numbers come from, how predictions are made, and what they can't tell you."
      />
      <div className="grid gap-4 md:grid-cols-3">
        {SECTIONS.map((section) => (
          <section key={section.title} className="rounded-xl bg-card p-5">
            <h2 className="text-title2 font-semibold">{section.title}</h2>
            <div className="mt-3 space-y-3 text-subhead leading-relaxed text-muted-foreground">
              {section.body.map((p) => (
                <p key={p.slice(0, 32)}>{p}</p>
              ))}
            </div>
          </section>
        ))}
      </div>
      <section className="mt-4 rounded-xl bg-card p-5">
        <h2 className="text-title2 font-semibold">
          Reading a prediction range{" "}
          <InfoHint term="80% range">
            A range built so that, across many past games, the actual result fell inside it about 80% of the
            time. It is calibrated on a held-out season and checked on another.
          </InfoHint>
        </h2>
        <p className="mt-2 max-w-3xl text-subhead leading-relaxed text-muted-foreground">
          A forecast of “27 · likely 21–34” means the model&apos;s best single estimate is 27, and results
          between 21 and 34 are typical for situations like this one. Outcomes outside the range still happen,
          roughly one game in five.
        </p>
      </section>
    </>
  );
}
