import { describe, expect, it } from "vitest";
import data from "../../seo/programs.json";
import {
  SITE,
  buildPages,
  esc,
  notFoundPage,
  plannerLink,
  programPage,
  requirementSummary,
  sitemap,
} from "../../scripts/seo-pages.mjs";

const pages = buildPages(data);
const csMajor = data.programs.find((p) => p.kind === "major" && p.name === "Computer Science")!;

describe("static requirement pages", () => {
  it("builds one page per program plus the two indexes and general education", () => {
    expect(pages).toHaveLength(data.programs.length + 3);
    expect(new Set(pages.map((p) => p.path)).size).toBe(pages.length);
    expect(pages.map((p) => p.path)).toContain("/majors/computer-science");
    expect(pages.map((p) => p.path)).toContain("/minors/computer-science");
  });

  it("gives every page a unique title, a description, one h1 and a self canonical", () => {
    const titles = new Set<string>();
    for (const { path, html } of pages) {
      const title = html.match(/<title>(.*?)<\/title>/)?.[1] ?? "";
      expect(title.length).toBeGreaterThan(20);
      titles.add(title);
      expect(html).toMatch(/<meta name="description" content="[^"]{60,}"/);
      expect(html.match(/<h1[ >]/g)).toHaveLength(1);
      expect(html).toContain(`<link rel="canonical" href="${SITE}${path}" />`);
    }
    expect(titles.size).toBe(pages.length);
  });

  it("only links to pages that exist", () => {
    const known = new Set(["/", ...pages.map((p) => p.path)]);
    for (const { html } of pages) {
      for (const [, href] of html.matchAll(/<a [^>]*href="(\/[^"#?]*)/g)) {
        expect(known.has(href), href).toBe(true);
      }
    }
  });

  it("lists every required course of a program with its code", () => {
    const html = programPage(csMajor, data);
    expect(csMajor.required.length).toBeGreaterThan(0);
    for (const course of csMajor.required) expect(html).toContain(`>${course.code}<`);
    expect(html).toContain(`href="${plannerLink(csMajor)}"`);
    expect(plannerLink(csMajor)).toBe("/?major=Computer%20Science");
  });

  it("summarises requirements from the data", () => {
    expect(
      requirementSummary({
        required: [{ credits: 3 }, { credits: 4 }],
        choices: [{}],
        electives: [{}],
      }),
    ).toBe("2 required courses (7 credits), 1 course choice and elective requirements");
    expect(requirementSummary({ required: [{ credits: 3 }], choices: [], electives: [] })).toBe(
      "1 required course (3 credits)",
    );
  });

  it("escapes catalog text", () => {
    expect(esc(`C# <Basics> & "more"`)).toBe("C# &lt;Basics&gt; &amp; &quot;more&quot;");
  });

  it("keeps the 404 page out of the index and the sitemap complete", () => {
    expect(notFoundPage()).toContain('<meta name="robots" content="noindex" />');
    const xml = sitemap(pages.map((p) => p.path), { homeDate: "2026-10-11", contentDate: "2026-10-08" });
    expect(xml.match(/<loc>/g)).toHaveLength(pages.length + 1);
    expect(xml).toContain(`<loc>${SITE}/</loc>`);
    expect(xml).toContain(`<loc>${SITE}/majors/computer-science</loc>`);
  });
});
