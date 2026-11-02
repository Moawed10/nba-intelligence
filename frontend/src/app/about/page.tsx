import type { Metadata } from "next";

import { InfoHint } from "@/components/data/info-hint";
import { PageHeader } from "@/components/data/page-header";

export const metadata: Metadata = { title: "About" };

/** Set only once the repository is public, so the link never leads to a 404. */
const REPOSITORY_URL = process.env.NEXT_PUBLIC_REPOSITORY_URL;

const SECTIONS = [
  {
    title: "Where the data comes from",
    body: [
      "Box scores, schedules, player details and career totals come from the NBA's public statistics service (stats.nba.com) through the open-source nba_api library. Scheduled jobs copy them into this app's own database, so pages never call the NBA directly.",
      "Game-by-game box scores start with the 2018-19 season and cover the regular season, play-in and playoffs. Season-by-season career totals go back to 1946-47, former players included. Team logos and player photos are loaded from the NBA's public image service.",
      "Every stored record keeps where it came from and when it was last updated. Corrections from the source are logged, never silently overwritten.",
    ],
  },
  {
    title: "How predictions are made",
    body: [
      "Player forecasts use only what was known before tip-off: recent form over the last 3, 5 and 10 games, season averages, history against the opponent, rest, home or away, and the opponent's recent defense and pace.",
      "Score predictions look at both teams' last 10 games (points scored and allowed, efficiency, pace), their records, rest and home court. The win chance comes from the predicted margin, calibrated on a past season's results; on a season it never saw it picked the winner 67% of the time.",
      "Several models are trained on past seasons, chosen on a later one, and scored once on a season none of them saw, against a simple average (the last-10-game average). The Models page shows those results and checks every stored prediction against the real box score.",
    ],
  },
  {
    title: "What it can't tell you",
    body: [
      "Forecasts assume the player plays. The source has no injury or lineup feed, so a late scratch or a minutes limit is not anticipated.",
      "Ranges hold the actual result about 4 times in 5 on average, not in every game. Trades, role changes and injuries can make recent history less useful.",
      "Statistics the league did not record yet stay blank rather than zero: steals and blocks before 1973-74, turnovers before 1977-78 and 3-pointers before 1979-80.",
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
            time. It is set using one season the models never saw and checked on another.
          </InfoHint>
        </h2>
        <p className="mt-2 max-w-3xl text-subhead leading-relaxed text-muted-foreground">
          A forecast of “27 · usually 21–34” means the best single estimate is 27, and results between 21 and
          34 are typical for situations like this one. Results outside the range still happen, roughly one
          game in five.
        </p>
      </section>
      <section className="mt-4 rounded-xl bg-card p-5">
        <h2 className="text-title2 font-semibold">Built with</h2>
        <p className="mt-2 max-w-3xl text-subhead leading-relaxed text-muted-foreground">
          Next.js, TypeScript and Tailwind on the front end; FastAPI, PostgreSQL, scikit-learn and XGBoost
          behind it. Not affiliated with or endorsed by the NBA.
        </p>
        {REPOSITORY_URL && (
          <a
            href={REPOSITORY_URL}
            className="mt-3 inline-flex min-h-10 items-center text-subhead font-medium text-primary hover:underline"
          >
            Source code on GitHub
          </a>
        )}
      </section>
    </>
  );
}
