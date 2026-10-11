// Types for seo-pages.mjs, so the vitest suite in src/seo type-checks.
export interface PageCourse {
  code: string;
  title: string | null;
  credits: number | null;
  prereq: string | null;
}

export interface PageProgram {
  kind: string;
  name: string;
  slug: string;
  required: PageCourse[];
  choices: { label: string | null; count: number; courses: PageCourse[] }[];
  electives: {
    label: string;
    credits_required: number | null;
    courses_required: number | null;
    courses: PageCourse[];
    catalog_text: string[];
  }[];
}

export interface PageData {
  catalog_year: string;
  catalog_date: string;
  degree_total_credits: number;
  programs: PageProgram[];
  not_covered: { kind: string; name: string }[];
  business_concentrations: string[];
  foundation_courses: PageCourse[];
  gen_ed: { name: string; courses_required: number | null; courses: PageCourse[] }[];
}

export const SITE: string;
export const SITE_NAME: string;
export function esc(value: unknown): string;
export function programPath(program: Pick<PageProgram, "kind" | "slug">): string;
export function plannerLink(program: Pick<PageProgram, "kind" | "name">): string;
export function requirementSummary(program: {
  required: { credits?: number | null }[];
  choices: unknown[];
  electives: unknown[];
}): string;
export function courseTable(courses: PageCourse[]): string;
export function programPage(program: PageProgram, data: PageData): string;
export function indexPage(kind: "major" | "minor", data: PageData): string;
export function genEdPage(data: PageData): string;
export function notFoundPage(): string;
export function buildPages(data: PageData): { path: string; html: string }[];
export function sitemap(paths: string[], dates: { homeDate: string; contentDate: string }): string;
