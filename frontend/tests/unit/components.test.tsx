import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { ChartFrame } from "@/components/data/chart-frame";
import { DataTable } from "@/components/data/data-table";
import { IntervalBar } from "@/components/data/interval-bar";
import { SegmentedControl } from "@/components/data/segmented-control";
import { StateView } from "@/components/data/state-view";
import { StatTile } from "@/components/data/stat-tile";
import { ApiError } from "@/lib/api/errors";

function Controlled() {
  const [value, setValue] = useState<"a" | "b" | "c">("a");
  return (
    <SegmentedControl
      label="Stat"
      value={value}
      onChange={setValue}
      segments={[
        { value: "a", label: "Points" },
        { value: "b", label: "Rebounds" },
        { value: "c", label: "Assists" },
      ]}
    />
  );
}

describe("SegmentedControl", () => {
  it("is one tab stop and moves selection with arrow keys", async () => {
    const user = userEvent.setup();
    render(<Controlled />);
    const group = screen.getByRole("radiogroup", { name: "Stat" });
    const radios = within(group).getAllByRole("radio");
    expect(radios.map((r) => r.tabIndex)).toEqual([0, -1, -1]);

    await user.tab();
    expect(radios[0]).toHaveFocus();
    await user.keyboard("{ArrowRight}");
    expect(screen.getByRole("radio", { name: "Rebounds" })).toHaveAttribute("aria-checked", "true");
    expect(screen.getByRole("radio", { name: "Rebounds" })).toHaveFocus();
    await user.keyboard("{ArrowLeft}{ArrowLeft}");
    expect(screen.getByRole("radio", { name: "Assists" })).toHaveAttribute("aria-checked", "true");
    await user.keyboard("{Home}");
    expect(screen.getByRole("radio", { name: "Points" })).toHaveAttribute("aria-checked", "true");
  });
});

describe("DataTable", () => {
  const rows = [
    { id: "1", name: "Game A", pts: 20 },
    { id: "2", name: "Game B", pts: 31 },
    { id: "3", name: "Game C", pts: null },
  ];
  it("renders a captioned table and sorts with aria-sort", async () => {
    const user = userEvent.setup();
    render(
      <DataTable
        caption="Synthetic game log"
        rows={rows}
        rowKey={(r) => r.id}
        columns={[
          { key: "name", header: "Game", cell: (r) => r.name },
          {
            key: "pts",
            header: "PTS",
            description: "Points",
            numeric: true,
            cell: (r) => r.pts ?? "—",
            sortValue: (r) => r.pts,
          },
        ]}
      />,
    );
    expect(screen.getByRole("table", { name: "Synthetic game log" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Synthetic game log" })).toHaveAttribute("tabindex", "0");
    await user.click(screen.getByRole("button", { name: /PTS/ }));
    expect(screen.getByRole("columnheader", { name: /PTS/ })).toHaveAttribute("aria-sort", "descending");
    const firstCells = screen.getAllByRole("rowheader").map((c) => c.textContent);
    expect(firstCells).toEqual(["Game B", "Game A", "Game C"]);
    await user.click(screen.getByRole("button", { name: /PTS/ }));
    expect(screen.getAllByRole("rowheader").map((c) => c.textContent)).toEqual([
      "Game A",
      "Game B",
      "Game C",
    ]);
  });
});

describe("ChartFrame", () => {
  it("states its finding in text and offers an equivalent table", async () => {
    const user = userEvent.setup();
    render(
      <ChartFrame
        title="Points by game"
        unit="Points per game"
        summary="Synthetic summary sentence."
        chart={<svg data-testid="chart" />}
        table={<table aria-label="Points table" />}
      />,
    );
    expect(screen.getByRole("heading", { name: "Points by game" })).toBeInTheDocument();
    expect(screen.getByRole("figure", { name: "Points by game" })).toHaveAccessibleDescription(
      "Synthetic summary sentence.",
    );
    await user.click(screen.getByRole("radio", { name: "Table" }));
    expect(screen.getByRole("table", { name: "Points table" })).toBeInTheDocument();
    expect(screen.queryByTestId("chart")).not.toBeInTheDocument();
  });
});

describe("StateView", () => {
  it("announces errors and offers retry", async () => {
    const user = userEvent.setup();
    const onRetry = vi.fn();
    render(<StateView kind="error" error={new ApiError(503, "x", "x")} onRetry={onRetry} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Something went wrong on our side");
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(onRetry).toHaveBeenCalledOnce();
  });

  it("uses a polite status role for empty states", () => {
    render(<StateView kind="empty" title="No games" message="Pick another date." />);
    expect(screen.getByRole("status")).toHaveTextContent("No games");
  });
});

describe("StatTile", () => {
  it("shows a dash, not zero, for missing values", () => {
    render(
      <dl>
        <StatTile label="Points" value={null} />
      </dl>,
    );
    expect(screen.getByText("—")).toBeInTheDocument();
    expect(screen.getByText("Not available")).toHaveClass("sr-only");
  });

  it("describes deltas in words, not only color", () => {
    render(
      <dl>
        <StatTile label="Points" value={25} delta={{ value: -1.96, versus: "season" }} />
      </dl>,
    );
    expect(screen.getByText(/−2\.0 vs season/)).toBeInTheDocument();
  });
});

describe("IntervalBar", () => {
  it("states the prediction and range for assistive tech", () => {
    render(<IntervalBar label="Points" point={27.4} lower={21} upper={34} level={0.8} max={50} />);
    expect(
      screen.getByRole("img", {
        name: "Points: predicted 27.4, likely range 21.0 to 34.0 (80% interval)",
      }),
    ).toBeInTheDocument();
  });
});
