import type { components } from "./schema";

/** Response models generated from backend/openapi.json (`npm run api:types`). */
type Schemas = components["schemas"];

export type PlayerSearchResult = Schemas["PlayerSearchResult"];
export type PlayerSummary = Schemas["PlayerSummary"];
export type PlayerProfile = Schemas["PlayerProfile"];
export type PlayerSeasonStats = Schemas["PlayerSeasonStats"];
export type PlayerGameLine = Schemas["PlayerGameLine"];
export type PlayerTrends = Schemas["PlayerTrends"];
export type Team = Schemas["Team"];
export type TeamDetail = Schemas["TeamDetail"];
export type TeamSeasonStats = Schemas["TeamSeasonStats"];
export type GameSummary = Schemas["GameSummary"];
export type GameDetail = Schemas["GameDetail"];
export type BoxScore = Schemas["BoxScore"];
export type DataStatus = Schemas["DataStatus"];
export type Meta = Schemas["Meta"];
export type PlayerPage = Schemas["Page_DirectoryPlayer_"];
export type PlayerGameLinePage = Schemas["Page_PlayerGameLine_"];
export type GamePage = Schemas["Page_GameSummary_"];
export type Split = Schemas["Split"];
export type SeasonLine = Schemas["SeasonLine"];
export type TrendPoint = Schemas["TrendPoint"];
export type DirectoryPlayer = Schemas["DirectoryPlayer"];
export type SeasonAverages = Schemas["SeasonAverages"];
export type Leaders = Schemas["Leaders"];
export type Leader = Schemas["Leader"];
export type Standouts = Schemas["Standouts"];
export type Performance = Schemas["Performance"];
export type Overview = Schemas["Overview"];
export type ModelReleaseSummary = Schemas["ModelReleaseSummary"];
export type ModelReleaseDetail = Schemas["ModelReleaseDetail"];
export type ModelSnapshot = Schemas["ModelSnapshot"];
export type TargetMetrics = Schemas["TargetMetrics"];
export type AlgorithmMetrics = Schemas["AlgorithmMetrics"];
export type TeamRef = Schemas["TeamRef"];
export type DatasetStatus = Schemas["DatasetStatus"];
