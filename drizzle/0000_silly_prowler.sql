CREATE TYPE "public"."device_category" AS ENUM('mouse', 'keyboard', 'headset', 'monitor', 'mousepad', 'controller');--> statement-breakpoint
CREATE TYPE "public"."event_type" AS ENUM('championship', 'split', 'playoffs', 'pro_league', 'challenger_circuit', 'open_qualifier', 'community');--> statement-breakpoint
CREATE TYPE "public"."news_category" AS ENUM('roster_change', 'tournament_result', 'scrim_update', 'other');--> statement-breakpoint
CREATE TYPE "public"."region" AS ENUM('NA', 'EMEA', 'APAC_N', 'APAC_S', 'GLOBAL');--> statement-breakpoint
CREATE TYPE "public"."stage_type" AS ENUM('group', 'bracket', 'round_robin', 'match_point');--> statement-breakpoint
CREATE TYPE "public"."tournament_status" AS ENUM('upcoming', 'ongoing', 'completed');--> statement-breakpoint
CREATE TABLE "devices" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"player_id" uuid NOT NULL,
	"category" "device_category" NOT NULL,
	"brand" varchar(100) NOT NULL,
	"model" varchar(200) NOT NULL,
	"amazon_url_ja" varchar(500),
	"amazon_url_en" varchar(500),
	"updated_at" timestamp DEFAULT now() NOT NULL,
	"created_at" timestamp DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "match_results" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"stage_id" uuid NOT NULL,
	"match_number" integer NOT NULL,
	"team_id" uuid NOT NULL,
	"placement" integer NOT NULL,
	"kills" integer DEFAULT 0 NOT NULL,
	"points" integer DEFAULT 0 NOT NULL,
	"created_at" timestamp DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "news_posts" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"slug" varchar(200) NOT NULL,
	"title_en" varchar(300) NOT NULL,
	"title_ja" varchar(300) NOT NULL,
	"body_en" text NOT NULL,
	"body_ja" text NOT NULL,
	"category" "news_category" DEFAULT 'other' NOT NULL,
	"related_tournament_id" uuid,
	"related_team_id" uuid,
	"posted_to_x" boolean DEFAULT false NOT NULL,
	"posted_to_discord" boolean DEFAULT false NOT NULL,
	"published_at" timestamp DEFAULT now() NOT NULL,
	"created_at" timestamp DEFAULT now() NOT NULL,
	CONSTRAINT "news_posts_slug_unique" UNIQUE("slug")
);
--> statement-breakpoint
CREATE TABLE "players" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"slug" varchar(100) NOT NULL,
	"ign" varchar(100) NOT NULL,
	"real_name" varchar(100),
	"real_name_ja" varchar(100),
	"nationality" varchar(2),
	"region" "region",
	"role" varchar(50),
	"profile_image_url" varchar(500),
	"twitter_url" varchar(300),
	"twitch_url" varchar(300),
	"youtube_url" varchar(300),
	"liquipedia_url" varchar(500),
	"is_active" boolean DEFAULT true NOT NULL,
	"bio_en" text,
	"bio_ja" text,
	"created_at" timestamp DEFAULT now() NOT NULL,
	"updated_at" timestamp DEFAULT now() NOT NULL,
	CONSTRAINT "players_slug_unique" UNIQUE("slug")
);
--> statement-breakpoint
CREATE TABLE "scrim_entries" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"scrim_date" date NOT NULL,
	"scrim_name" varchar(200) NOT NULL,
	"team_id" uuid,
	"team_name_raw" varchar(200) NOT NULL,
	"source" varchar(50) DEFAULT 'fight_nt' NOT NULL,
	"created_at" timestamp DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "team_rosters" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"team_id" uuid NOT NULL,
	"player_id" uuid NOT NULL,
	"role" varchar(50),
	"joined_at" date NOT NULL,
	"left_at" date,
	"is_substitute" boolean DEFAULT false NOT NULL,
	"source_url" varchar(500),
	"created_at" timestamp DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "teams" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"slug" varchar(100) NOT NULL,
	"name" varchar(200) NOT NULL,
	"name_ja" varchar(200),
	"short_name" varchar(20),
	"region" "region",
	"logo_url" varchar(500),
	"website_url" varchar(300),
	"twitter_url" varchar(300),
	"liquipedia_url" varchar(500),
	"is_active" boolean DEFAULT true NOT NULL,
	"founded_date" date,
	"bio_en" text,
	"bio_ja" text,
	"created_at" timestamp DEFAULT now() NOT NULL,
	"updated_at" timestamp DEFAULT now() NOT NULL,
	CONSTRAINT "teams_slug_unique" UNIQUE("slug")
);
--> statement-breakpoint
CREATE TABLE "tournament_results" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tournament_id" uuid NOT NULL,
	"stage_id" uuid,
	"team_id" uuid NOT NULL,
	"placement" integer NOT NULL,
	"total_points" integer,
	"total_kills" integer,
	"games_played" integer,
	"prize_usd" integer,
	"created_at" timestamp DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "tournament_stages" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tournament_id" uuid NOT NULL,
	"name" varchar(200) NOT NULL,
	"stage_type" "stage_type",
	"stage_order" integer DEFAULT 0 NOT NULL,
	"battlefy_stage_id" varchar(100),
	"created_at" timestamp DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "tournaments" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"slug" varchar(200) NOT NULL,
	"name" varchar(300) NOT NULL,
	"name_ja" varchar(300),
	"series" varchar(100),
	"event_type" "event_type",
	"region" "region",
	"start_date" date,
	"end_date" date,
	"prize_pool_usd" integer,
	"is_lan" boolean DEFAULT false NOT NULL,
	"location" varchar(200),
	"battlefy_id" varchar(100),
	"liquipedia_url" varchar(500),
	"status" "tournament_status" DEFAULT 'upcoming' NOT NULL,
	"created_at" timestamp DEFAULT now() NOT NULL,
	"updated_at" timestamp DEFAULT now() NOT NULL,
	CONSTRAINT "tournaments_slug_unique" UNIQUE("slug")
);
--> statement-breakpoint
ALTER TABLE "devices" ADD CONSTRAINT "devices_player_id_players_id_fk" FOREIGN KEY ("player_id") REFERENCES "public"."players"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "match_results" ADD CONSTRAINT "match_results_stage_id_tournament_stages_id_fk" FOREIGN KEY ("stage_id") REFERENCES "public"."tournament_stages"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "match_results" ADD CONSTRAINT "match_results_team_id_teams_id_fk" FOREIGN KEY ("team_id") REFERENCES "public"."teams"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "news_posts" ADD CONSTRAINT "news_posts_related_tournament_id_tournaments_id_fk" FOREIGN KEY ("related_tournament_id") REFERENCES "public"."tournaments"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "news_posts" ADD CONSTRAINT "news_posts_related_team_id_teams_id_fk" FOREIGN KEY ("related_team_id") REFERENCES "public"."teams"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "scrim_entries" ADD CONSTRAINT "scrim_entries_team_id_teams_id_fk" FOREIGN KEY ("team_id") REFERENCES "public"."teams"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "team_rosters" ADD CONSTRAINT "team_rosters_team_id_teams_id_fk" FOREIGN KEY ("team_id") REFERENCES "public"."teams"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "team_rosters" ADD CONSTRAINT "team_rosters_player_id_players_id_fk" FOREIGN KEY ("player_id") REFERENCES "public"."players"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "tournament_results" ADD CONSTRAINT "tournament_results_tournament_id_tournaments_id_fk" FOREIGN KEY ("tournament_id") REFERENCES "public"."tournaments"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "tournament_results" ADD CONSTRAINT "tournament_results_stage_id_tournament_stages_id_fk" FOREIGN KEY ("stage_id") REFERENCES "public"."tournament_stages"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "tournament_results" ADD CONSTRAINT "tournament_results_team_id_teams_id_fk" FOREIGN KEY ("team_id") REFERENCES "public"."teams"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "tournament_stages" ADD CONSTRAINT "tournament_stages_tournament_id_tournaments_id_fk" FOREIGN KEY ("tournament_id") REFERENCES "public"."tournaments"("id") ON DELETE no action ON UPDATE no action;