import { Heart, MessageCircle, Repeat2 } from "lucide-react";

import type { FanPosts } from "@/lib/api/types";
import { formatRelativeTime } from "@/lib/format";

function Count({ icon: Icon, value, label }: { icon: typeof Heart; value: number; label: string }) {
  return (
    <span className="inline-flex items-center gap-1 tabular-nums">
      <Icon aria-hidden className="size-3.5" />
      {value}
      <span className="sr-only"> {label}</span>
    </span>
  );
}

/** Real public posts with attribution and a link back; the wording says what they are and aren't. */
export function FanPostsSection({ data, teamName }: { data: FanPosts; teamName: string }) {
  if (data.posts.length === 0) {
    return (
      <p className="text-subhead text-muted-foreground">
        No recent {data.source} posts about the {teamName} made the cut this week.
      </p>
    );
  }
  return (
    <div className="space-y-4">
      <ul className="divide-y divide-border">
        {data.posts.map((post) => (
          <li key={post.url} className="py-4 first:pt-0">
            <blockquote className="max-w-[65ch] text-body break-words whitespace-pre-line">
              {post.text}
            </blockquote>
            <p className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-footnote text-muted-foreground">
              <a
                href={post.url}
                target="_blank"
                rel="noopener noreferrer nofollow"
                className="inline-flex min-h-6 items-center font-medium break-all text-foreground hover:text-primary"
              >
                {post.author_name ? `${post.author_name} · ` : ""}@{post.author_handle}
                <span className="sr-only"> (opens this post on {data.source})</span>
              </a>
              <span suppressHydrationWarning>{formatRelativeTime(post.posted_at)}</span>
              <Count icon={Heart} value={post.likes} label="likes" />
              <Count icon={Repeat2} value={post.reposts} label="reposts" />
              <Count icon={MessageCircle} value={post.replies} label="replies" />
            </p>
          </li>
        ))}
      </ul>
      <p className="max-w-[65ch] text-footnote text-muted-foreground">
        Public {data.source} posts from the past week that mention the team, ranked by likes, reposts and
        replies, with newer posts counting more. Filtered automatically, so it isn&apos;t a survey of all
        fans, and the views belong to their authors.
      </p>
    </div>
  );
}
