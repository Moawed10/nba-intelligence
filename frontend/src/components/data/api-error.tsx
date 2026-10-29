import { type ApiError, describeError } from "@/lib/api/errors";

import { StateView } from "./state-view";

/** Server-side rendering of an API failure; only plain-language text crosses to the client. */
export function ApiErrorView({ error, className }: { error: ApiError; className?: string }) {
  const { title, message } = describeError(error);
  return <StateView kind="error" title={title} message={message} className={className} />;
}
