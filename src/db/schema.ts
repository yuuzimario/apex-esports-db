import {
  pgTable,
  uuid,
  varchar,
  text,
  boolean,
  integer,
  date,
  timestamp,
  pgEnum,
} from "drizzle-orm/pg-core";

// Enums
export const regionEnum = pgEnum("region", [
  "NA",
  "EMEA",
  "APAC_N",
  "APAC_S",
  "GLOBAL",
]);

export const tournamentStatusEnum = pgEnum("tournament_status", [
  "upcoming",
  "ongoing",
  "completed",
]);

export const eventTypeEnum = pgEnum("event_type", [
  "championship",
  "split",
  "playoffs",
  "pro_league",
  "challenger_circuit",
  "open_qualifier",
  "community",
]);

export const deviceCategoryEnum = pgEnum("device_category", [
  "mouse",
  "keyboard",
  "headset",
  "monitor",
  "mousepad",
  "controller",
]);

export const newsCategoryEnum = pgEnum("news_category", [
  "roster_change",
  "tournament_result",
  "scrim_update",
  "other",
]);

export const stageTypeEnum = pgEnum("stage_type", [
  "group",
  "bracket",
  "round_robin",
  "match_point",
]);

// テーブル定義
export const players = pgTable("players", {
  id: uuid("id").primaryKey().defaultRandom(),
  slug: varchar("slug", { length: 100 }).unique().notNull(),
  ign: varchar("ign", { length: 100 }).notNull(),
  realName: varchar("real_name", { length: 100 }),
  realNameJa: varchar("real_name_ja", { length: 100 }),
  nationality: varchar("nationality", { length: 2 }),
  region: regionEnum("region"),
  role: varchar("role", { length: 50 }),
  profileImageUrl: varchar("profile_image_url", { length: 500 }),
  twitterUrl: varchar("twitter_url", { length: 300 }),
  twitchUrl: varchar("twitch_url", { length: 300 }),
  youtubeUrl: varchar("youtube_url", { length: 300 }),
  liquipediaUrl: varchar("liquipedia_url", { length: 500 }),
  isActive: boolean("is_active").default(true).notNull(),
  bioEn: text("bio_en"),
  bioJa: text("bio_ja"),
  createdAt: timestamp("created_at").defaultNow().notNull(),
  updatedAt: timestamp("updated_at").defaultNow().notNull(),
});

export const teams = pgTable("teams", {
  id: uuid("id").primaryKey().defaultRandom(),
  slug: varchar("slug", { length: 100 }).unique().notNull(),
  name: varchar("name", { length: 200 }).notNull(),
  nameJa: varchar("name_ja", { length: 200 }),
  shortName: varchar("short_name", { length: 20 }),
  region: regionEnum("region"),
  logoUrl: varchar("logo_url", { length: 500 }),
  websiteUrl: varchar("website_url", { length: 300 }),
  twitterUrl: varchar("twitter_url", { length: 300 }),
  liquipediaUrl: varchar("liquipedia_url", { length: 500 }),
  isActive: boolean("is_active").default(true).notNull(),
  foundedDate: date("founded_date"),
  bioEn: text("bio_en"),
  bioJa: text("bio_ja"),
  createdAt: timestamp("created_at").defaultNow().notNull(),
  updatedAt: timestamp("updated_at").defaultNow().notNull(),
});

export const teamRosters = pgTable("team_rosters", {
  id: uuid("id").primaryKey().defaultRandom(),
  teamId: uuid("team_id")
    .references(() => teams.id)
    .notNull(),
  playerId: uuid("player_id")
    .references(() => players.id)
    .notNull(),
  role: varchar("role", { length: 50 }),
  joinedAt: date("joined_at").notNull(),
  leftAt: date("left_at"),
  isSubstitute: boolean("is_substitute").default(false).notNull(),
  sourceUrl: varchar("source_url", { length: 500 }),
  createdAt: timestamp("created_at").defaultNow().notNull(),
});

export const tournaments = pgTable("tournaments", {
  id: uuid("id").primaryKey().defaultRandom(),
  slug: varchar("slug", { length: 200 }).unique().notNull(),
  name: varchar("name", { length: 300 }).notNull(),
  nameJa: varchar("name_ja", { length: 300 }),
  series: varchar("series", { length: 100 }),
  eventType: eventTypeEnum("event_type"),
  region: regionEnum("region"),
  startDate: date("start_date"),
  endDate: date("end_date"),
  prizePoolUsd: integer("prize_pool_usd"),
  isLan: boolean("is_lan").default(false).notNull(),
  location: varchar("location", { length: 200 }),
  battlefyId: varchar("battlefy_id", { length: 100 }),
  liquipediaUrl: varchar("liquipedia_url", { length: 500 }),
  status: tournamentStatusEnum("status").default("upcoming").notNull(),
  createdAt: timestamp("created_at").defaultNow().notNull(),
  updatedAt: timestamp("updated_at").defaultNow().notNull(),
});

export const tournamentStages = pgTable("tournament_stages", {
  id: uuid("id").primaryKey().defaultRandom(),
  tournamentId: uuid("tournament_id")
    .references(() => tournaments.id)
    .notNull(),
  name: varchar("name", { length: 200 }).notNull(),
  stageType: stageTypeEnum("stage_type"),
  stageOrder: integer("stage_order").default(0).notNull(),
  battlefyStageId: varchar("battlefy_stage_id", { length: 100 }),
  createdAt: timestamp("created_at").defaultNow().notNull(),
});

export const tournamentResults = pgTable("tournament_results", {
  id: uuid("id").primaryKey().defaultRandom(),
  tournamentId: uuid("tournament_id")
    .references(() => tournaments.id)
    .notNull(),
  stageId: uuid("stage_id").references(() => tournamentStages.id),
  teamId: uuid("team_id")
    .references(() => teams.id)
    .notNull(),
  placement: integer("placement").notNull(),
  totalPoints: integer("total_points"),
  totalKills: integer("total_kills"),
  gamesPlayed: integer("games_played"),
  prizeUsd: integer("prize_usd"),
  createdAt: timestamp("created_at").defaultNow().notNull(),
});

export const matchResults = pgTable("match_results", {
  id: uuid("id").primaryKey().defaultRandom(),
  stageId: uuid("stage_id")
    .references(() => tournamentStages.id)
    .notNull(),
  matchNumber: integer("match_number").notNull(),
  teamId: uuid("team_id")
    .references(() => teams.id)
    .notNull(),
  placement: integer("placement").notNull(),
  kills: integer("kills").default(0).notNull(),
  points: integer("points").default(0).notNull(),
  createdAt: timestamp("created_at").defaultNow().notNull(),
});

export const devices = pgTable("devices", {
  id: uuid("id").primaryKey().defaultRandom(),
  playerId: uuid("player_id")
    .references(() => players.id)
    .notNull(),
  category: deviceCategoryEnum("category").notNull(),
  brand: varchar("brand", { length: 100 }).notNull(),
  model: varchar("model", { length: 200 }).notNull(),
  amazonUrlJa: varchar("amazon_url_ja", { length: 500 }),
  amazonUrlEn: varchar("amazon_url_en", { length: 500 }),
  updatedAt: timestamp("updated_at").defaultNow().notNull(),
  createdAt: timestamp("created_at").defaultNow().notNull(),
});

export const scrimEntries = pgTable("scrim_entries", {
  id: uuid("id").primaryKey().defaultRandom(),
  scrimDate: date("scrim_date").notNull(),
  scrimName: varchar("scrim_name", { length: 200 }).notNull(),
  teamId: uuid("team_id").references(() => teams.id),
  teamNameRaw: varchar("team_name_raw", { length: 200 }).notNull(),
  source: varchar("source", { length: 50 }).default("fight_nt").notNull(),
  createdAt: timestamp("created_at").defaultNow().notNull(),
});

export const newsPosts = pgTable("news_posts", {
  id: uuid("id").primaryKey().defaultRandom(),
  slug: varchar("slug", { length: 200 }).unique().notNull(),
  titleEn: varchar("title_en", { length: 300 }).notNull(),
  titleJa: varchar("title_ja", { length: 300 }).notNull(),
  bodyEn: text("body_en").notNull(),
  bodyJa: text("body_ja").notNull(),
  category: newsCategoryEnum("category").default("other").notNull(),
  relatedTournamentId: uuid("related_tournament_id").references(
    () => tournaments.id
  ),
  relatedTeamId: uuid("related_team_id").references(() => teams.id),
  postedToX: boolean("posted_to_x").default(false).notNull(),
  postedToDiscord: boolean("posted_to_discord").default(false).notNull(),
  publishedAt: timestamp("published_at").defaultNow().notNull(),
  createdAt: timestamp("created_at").defaultNow().notNull(),
});
