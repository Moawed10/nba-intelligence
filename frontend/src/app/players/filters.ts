export const POSITIONS = [
  { value: "G", label: "Guards" },
  { value: "F", label: "Forwards" },
  { value: "C", label: "Centers" },
] as const;

export interface DirectoryFilters {
  team?: string;
  position?: string;
  status?: string;
}
