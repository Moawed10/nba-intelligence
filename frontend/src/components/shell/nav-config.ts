import {
  ArrowLeftRight,
  CalendarDays,
  ChartLine,
  House,
  Info,
  type LucideIcon,
  Target,
  Users,
} from "lucide-react";

export interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
}

export const PRIMARY_NAV: NavItem[] = [
  { href: "/", label: "Overview", icon: House },
  { href: "/players", label: "Players", icon: Users },
  { href: "/predict", label: "Predictions", icon: Target },
  { href: "/compare", label: "Compare", icon: ArrowLeftRight },
  { href: "/models", label: "Models", icon: ChartLine },
];

export const SECONDARY_NAV: NavItem[] = [
  { href: "/games", label: "Games", icon: CalendarDays },
  { href: "/about", label: "About", icon: Info },
];

export function isActive(pathname: string | null, href: string): boolean {
  if (pathname == null) return false;
  return href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(`${href}/`);
}
