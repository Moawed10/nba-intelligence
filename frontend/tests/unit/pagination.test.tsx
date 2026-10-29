import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Pagination } from "@/components/data/pagination";

const href = (page: number) => `/players?page=${page}`;

describe("Pagination", () => {
  it("renders nothing for a single page", () => {
    const { container } = render(<Pagination label="Pages" page={1} pages={1} total={10} href={href} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("links to neighbouring pages and states the position in text", () => {
    render(<Pagination label="Pages" page={2} pages={3} total={60} href={href} />);
    const nav = screen.getByRole("navigation", { name: "Pages" });
    expect(nav).toHaveTextContent("Page 2 of 3 · 60 total");
    expect(screen.getByRole("link", { name: "Previous page" })).toHaveAttribute("href", "/players?page=1");
    expect(screen.getByRole("link", { name: "Next page" })).toHaveAttribute("href", "/players?page=3");
  });

  it("omits links past either end", () => {
    render(<Pagination label="Pages" page={3} pages={3} total={60} href={href} />);
    expect(screen.queryByRole("link", { name: "Next page" })).toBeNull();
    expect(screen.getByRole("link", { name: "Previous page" })).toBeInTheDocument();
  });
});
