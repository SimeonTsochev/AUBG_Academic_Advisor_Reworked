// Renders the static, crawlable requirement pages from seo/programs.json (pure functions, no I/O).
// The data comes from the planner's own requirement rules: backend/scripts/build_program_pages_artifact.py.

export const SITE = 'https://aubg-advisor.com';
export const SITE_NAME = 'AUBG Academic Co-Advisor';

const KIND = {
  major: { plural: 'majors', title: 'Majors', param: 'major' },
  minor: { plural: 'minors', title: 'Minors', param: 'minor' },
};

export function esc(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

export const programPath = (program) => `/${KIND[program.kind].plural}/${program.slug}`;

export const plannerLink = (program) =>
  `/?${KIND[program.kind].param}=${encodeURIComponent(program.name)}`;

const plural = (n, word) => `${n} ${word}${n === 1 ? '' : 's'}`;

const sumCredits = (courses) => courses.reduce((total, c) => total + (Number(c.credits) || 0), 0);

/** "7 required courses (21 credits), 1 course choice and elective requirements". */
export function requirementSummary(program) {
  const parts = [];
  if (program.required.length) {
    parts.push(`${plural(program.required.length, 'required course')} (${sumCredits(program.required)} credits)`);
  }
  if (program.choices.length) parts.push(plural(program.choices.length, 'course choice'));
  if (program.electives.length) parts.push('elective requirements');
  if (parts.length <= 1) return parts.join('');
  return `${parts.slice(0, -1).join(', ')} and ${parts[parts.length - 1]}`;
}

const STYLE = `
:root{color-scheme:light;--navy:#1e3a5f;--navy-dark:#0f1e3a;--gold:#c5a572;--gold-text:#7a6136;--bg:#f5f7fa;--card:#fff;--border:#e2e8f0;--text:#1f2937;--muted:#5b6678;--focus:#3b6fb6}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font:16px/1.6 Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
a{color:var(--navy);text-underline-offset:2px}
a:focus-visible{outline:2px solid var(--focus);outline-offset:2px;border-radius:4px}
.wrap{max-width:60rem;margin:0 auto;padding:0 1rem}
.top{background:var(--navy);color:#fff}
.top .wrap{display:flex;flex-wrap:wrap;align-items:center;gap:.5rem 1.25rem;padding-top:.75rem;padding-bottom:.75rem}
.brand{display:inline-flex;align-items:center;gap:.6rem;color:#fff;font-weight:700;text-decoration:none;margin-right:auto}
.brand svg{width:1.75rem;height:1.75rem;flex:none}
.top nav{display:flex;flex-wrap:wrap;gap:.25rem 1rem}
.top nav a{color:#e5edff;text-decoration:none;font-size:.9375rem}
.top nav a:hover,.top nav a[aria-current]{color:#fff;text-decoration:underline}
main{padding:1.5rem 0 3rem}
.crumbs{margin:0 0 1rem;padding:0;list-style:none;display:flex;flex-wrap:wrap;gap:.35rem;font-size:.875rem;color:var(--muted)}
.crumbs li+li::before{content:"/";margin-right:.35rem;color:var(--border)}
h1{margin:0 0 .75rem;font-size:clamp(1.75rem,4.5vw,2.375rem);line-height:1.15;color:var(--navy-dark);text-wrap:balance}
h2{margin:2.25rem 0 .75rem;font-size:1.375rem;line-height:1.25;color:var(--navy-dark)}
h3{margin:1.5rem 0 .5rem;font-size:1.0625rem;color:var(--navy-dark)}
.lede{max-width:44rem;margin:0 0 1.25rem;font-size:1.0625rem;color:var(--muted)}
.btn{display:inline-flex;align-items:center;gap:.5rem;padding:.7rem 1.15rem;border-radius:10px;background:var(--navy);color:#fff;font-weight:600;text-decoration:none}
.btn:hover{background:#2d4d73}
.note{margin:1.5rem 0 0;padding:.85rem 1rem;border:1px solid #f3d48c;border-radius:12px;background:#fff6e5;color:#6b4400;font-size:.9375rem}
.note a{color:inherit}
.rule{margin:0 0 .5rem;font-weight:600;color:var(--gold-text)}
.table{overflow-x:auto;border:1px solid var(--border);border-radius:12px;background:var(--card)}
table{width:100%;border-collapse:collapse;font-size:.9375rem}
th,td{padding:.6rem .8rem;text-align:left;vertical-align:top;border-top:1px solid var(--border)}
thead th{border-top:0;background:#f8fafc;font-size:.8125rem;letter-spacing:.03em;text-transform:uppercase;color:var(--muted)}
td.code{white-space:nowrap;font-weight:600;font-variant-numeric:tabular-nums}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}
td.pre{color:var(--muted);min-width:11rem}
.wording{margin:.25rem 0 1rem;padding:.7rem 1rem;border-left:3px solid var(--gold);border-radius:0 12px 12px 0;background:var(--card)}
.wording>p{margin:0 0 .25rem;font-size:.8125rem;font-weight:600;letter-spacing:.03em;text-transform:uppercase;color:var(--gold-text)}
.catalog{margin:0;padding:0;list-style:none;font-size:.9375rem;color:var(--muted)}
.catalog li{padding:.15rem 0}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(15rem,1fr));gap:.6rem;margin:0;padding:0;list-style:none}
.grid a{display:block;height:100%;padding:.8rem 1rem;border:1px solid var(--border);border-radius:12px;background:var(--card);font-weight:600;text-decoration:none}
.grid a:hover{border-color:var(--gold)}
.grid small{display:block;font-weight:400;color:var(--muted)}
.links{margin:0;padding:0;list-style:none;display:flex;flex-wrap:wrap;gap:.35rem 1rem;font-size:.9375rem}
footer{border-top:1px solid var(--border);padding:1.25rem 0 2rem;font-size:.875rem;color:var(--muted)}
footer p{margin:.25rem 0}
`.trim();

const LOGO =
  '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" aria-hidden="true"><rect width="32" height="32" rx="7" fill="#0f1e3a"/><g transform="translate(4 3.5)" fill="none" stroke="#c5a572" stroke-width="2.25" stroke-linecap="round" stroke-linejoin="round"><path d="M21.42 10.922a1 1 0 0 0-.019-1.838L12.83 5.18a2 2 0 0 0-1.66 0L2.6 9.08a1 1 0 0 0 0 1.832l8.57 3.908a2 2 0 0 0 1.66 0z"/><path d="M22 10v6"/><path d="M6 12.5V16a6 3 0 0 0 12 0v-3.5"/></g></svg>';

const NAV = [
  ['/majors', 'Majors'],
  ['/minors', 'Minors'],
  ['/general-education', 'General education'],
  ['/', 'Degree planner'],
];

function breadcrumbs(crumbs) {
  const items = crumbs
    .map(([href, label], i) =>
      i === crumbs.length - 1
        ? `<li aria-current="page">${esc(label)}</li>`
        : `<li><a href="${esc(href)}">${esc(label)}</a></li>`,
    )
    .join('');
  return `<nav aria-label="Breadcrumb"><ol class="crumbs">${items}</ol></nav>`;
}

function breadcrumbLd(crumbs) {
  return {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: crumbs.map(([href, label], i) => ({
      '@type': 'ListItem',
      position: i + 1,
      name: label,
      item: SITE + href,
    })),
  };
}

// "<" must not close the script element early.
const jsonLd = (data) =>
  `<script type="application/ld+json">${JSON.stringify(data).replace(/</g, '\\u003c')}</script>`;

/** Full HTML document. `path` is the canonical path; pass `noindex` for the 404 page. */
export function layout({ path, title, description, crumbs, body, structured = [], noindex = false }) {
  const url = SITE + path;
  const head = noindex
    ? '<meta name="robots" content="noindex" />'
    : [
        `<link rel="canonical" href="${esc(url)}" />`,
        '<meta property="og:type" content="article" />',
        `<meta property="og:site_name" content="${esc(SITE_NAME)}" />`,
        `<meta property="og:url" content="${esc(url)}" />`,
        `<meta property="og:title" content="${esc(title)}" />`,
        `<meta property="og:description" content="${esc(description)}" />`,
        `<meta property="og:image" content="${SITE}/og-image.png" />`,
        '<meta property="og:image:width" content="1200" />',
        '<meta property="og:image:height" content="630" />',
        '<meta name="twitter:card" content="summary_large_image" />',
        ...(crumbs ? [jsonLd(breadcrumbLd(crumbs))] : []),
        ...structured.map(jsonLd),
      ].join('\n');
  const nav = NAV.map(
    ([href, label]) => `<a href="${href}"${href === path ? ' aria-current="page"' : ''}>${label}</a>`,
  ).join('');

  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>${esc(title)}</title>
<meta name="description" content="${esc(description)}" />
${head}
<meta name="theme-color" content="#1e3a5f" />
<link rel="icon" href="/favicon.ico" sizes="48x48" />
<link rel="icon" href="/favicon.svg" type="image/svg+xml" />
<link rel="apple-touch-icon" href="/apple-touch-icon.png" />
<style>${STYLE}</style>
</head>
<body>
<header class="top"><div class="wrap"><a class="brand" href="/">${LOGO}<span>${esc(SITE_NAME)}</span></a><nav aria-label="Site">${nav}</nav></div></header>
<main><div class="wrap">
${crumbs ? breadcrumbs(crumbs) : ''}
${body}
</div></main>
<footer><div class="wrap">
<p>${esc(SITE_NAME)} is an unofficial student tool and is not affiliated with the American University in Bulgaria.</p>
<p><a href="/majors">AUBG majors</a> · <a href="/minors">AUBG minors</a> · <a href="/general-education">General education</a> · <a href="/">Degree planner</a></p>
</div></footer>
</body>
</html>
`;
}

export function courseTable(courses) {
  if (!courses.length) return '';
  const rows = courses
    .map(
      (c) =>
        `<tr><td class="code">${esc(c.code)}</td><td>${esc(c.title ?? '')}</td><td class="num">${esc(c.credits ?? '')}</td><td class="pre">${esc(c.prereq ?? 'None listed')}</td></tr>`,
    )
    .join('');
  return `<div class="table"><table><thead><tr><th scope="col">Code</th><th scope="col">Course</th><th scope="col" class="num">Credits</th><th scope="col">Prerequisites</th></tr></thead><tbody>${rows}</tbody></table></div>`;
}

function disclaimer(data) {
  return `<p class="note"><strong>Unofficial summary.</strong> These requirements are read from the AUBG Academic Catalog AY ${esc(data.catalog_year)} and are the rules the planner applies. The catalog and your academic advisor are the authority: confirm your plan with your advisor before you register.</p>`;
}

// Only the catalog's own wording states the rule: the parsed numbers can be a minimum or a cap.
function electiveSection(block) {
  const wording = block.catalog_text.length
    ? `<div class="wording"><p>Catalog wording</p><ul class="catalog">${block.catalog_text
        .map((line) => `<li>${esc(line)}</li>`)
        .join('')}</ul></div>`
    : '';
  const courses = block.courses.length
    ? `<p>Courses the planner counts here:</p>${courseTable(block.courses)}`
    : '';
  return `<h3>${esc(block.label)}</h3>${wording}${courses}`;
}

const DIPLOMA = {
  dual: 'A dual-diploma major: graduates receive an American and a Bulgarian diploma.',
  single: 'A single-diploma major (American diploma only): AUBG students also need a dual-diploma major to graduate.',
};

// The elective sub-rules the planner checks, as the catalog words them.
function ruleList(rules) {
  return rules && rules.length ? `<ul class="links">${rules.map((rule) => `<li>${esc(rule)}</li>`).join('')}</ul>` : '';
}

// CS concentrations, the European Studies language: options the student chooses.
function optionSection(options) {
  const heading = options.label === 'Concentration' ? 'Concentrations' : options.label;
  const intro = options.description ? `<p>${esc(options.description)}</p>` : '';
  const choices = options.choices
    .filter((choice) => choice.blocks.length || (choice.rules ?? []).length)
    .map(
      (choice) =>
        `<h3>${esc(choice.name)}</h3>${choice.blocks
          .map(
            (block) =>
              `<p class="rule">${
                block.count >= block.courses.length
                  ? `Take all ${plural(block.courses.length, 'course')}`
                  : `Choose ${plural(block.count, 'course')} from these ${block.courses.length}`
              }</p>${courseTable(block.courses)}`,
          )
          .join('')}${ruleList(choice.rules)}`,
    )
    .join('');
  return `<h2>${esc(heading)}</h2>${intro}${choices}`;
}

export function programPage(program, data) {
  const kind = KIND[program.kind];
  const path = programPath(program);
  const year = data.catalog_year;
  const summary = requirementSummary(program);
  const title = `AUBG ${program.name} ${program.kind} requirements (${year})`;
  const description = `Requirements for the ${program.name} ${program.kind} at the American University in Bulgaria (AUBG), catalog ${year}: ${summary}. See every course with credits and prerequisites.`;
  const crumbs = [['/', 'Home'], [`/${kind.plural}`, kind.title], [path, program.name]];

  const sections = [];
  if (program.required.length) {
    sections.push(
      `<h2>Required courses</h2><p>Every ${esc(program.name)} ${program.kind} takes these ${plural(program.required.length, 'course')} (${sumCredits(program.required)} credits).</p>${courseTable(program.required)}`,
    );
  }
  if (program.choices.length) {
    sections.push(
      `<h2>Course choices</h2>${program.choices
        .map(
          (choice) =>
            `<h3>${esc(choice.label ?? `Choose ${choice.count} of ${choice.courses.length}`)}</h3><p class="rule">Choose ${plural(choice.count, 'course')} from these ${choice.courses.length}</p>${courseTable(choice.courses)}`,
        )
        .join('')}`,
    );
  }
  if (program.electives.length) {
    const rules = program.elective_rules ?? [];
    sections.push(
      `<h2>Electives</h2>${program.electives.map(electiveSection).join('')}${
        rules.length ? `<h3>Rules the planner checks</h3>${ruleList(rules)}` : ''
      }`,
    );
  }
  if (program.options) {
    sections.push(optionSection(program.options));
  }
  if (program.kind === 'major' && program.name === 'Business Administration' && data.business_concentrations.length) {
    sections.push(
      `<h2>Business concentrations</h2><p>Business Administration majors can add a concentration in ${esc(
        data.business_concentrations.join(', '),
      )}. The <a href="${plannerLink(program)}">degree planner</a> tracks the courses each concentration needs.</p>`,
    );
  }

  const counterpart = data.programs.find((p) => p.name === program.name && p.kind !== program.kind);
  const others = data.programs.filter((p) => p.kind === program.kind && p.slug !== program.slug);

  const body = `
<h1>${esc(program.name)} ${program.kind} requirements at AUBG</h1>
<p class="lede">What you need to complete the ${esc(program.name)} ${program.kind} at the American University in Bulgaria, from the AUBG Academic Catalog AY ${esc(year)}: ${esc(summary)}.</p>
${program.diploma && DIPLOMA[program.diploma] ? `<p>${DIPLOMA[program.diploma]}</p>` : ''}
<p><a class="btn" href="${plannerLink(program)}">Plan my ${esc(program.name)} ${program.kind} →</a></p>
${disclaimer(data)}
${sections.join('\n')}
<h2>What every AUBG degree also needs</h2>
<p>A Bachelor of Arts at AUBG takes at least ${esc(data.degree_total_credits)} credit hours, including the <a href="/general-education">general education requirements</a>. The <a href="${plannerLink(program)}">degree planner</a> puts your ${program.kind} courses, general education and free electives into a semester-by-semester plan that respects prerequisites and class standing.</p>
<h2>Related programs</h2>
<ul class="links">
${counterpart ? `<li><a href="${programPath(counterpart)}">${esc(counterpart.name)} ${counterpart.kind}</a></li>` : ''}
${others.map((p) => `<li><a href="${programPath(p)}">${esc(p.name)}</a></li>`).join('\n')}
</ul>`;

  return layout({ path, title, description, crumbs, body });
}

export function indexPage(kindKey, data) {
  const kind = KIND[kindKey];
  const programs = data.programs.filter((p) => p.kind === kindKey);
  const path = `/${kind.plural}`;
  const year = data.catalog_year;
  const missing = data.not_covered.filter((p) => p.kind === kindKey).map((p) => p.name);
  const title = `AUBG ${kind.plural}: course requirements for each ${kindKey} (${year})`;
  const description = `Requirements for ${programs.length} ${kind.plural} at the American University in Bulgaria (AUBG): required courses, electives, credits and prerequisites from the ${year} academic catalog.`;
  const crumbs = [['/', 'Home'], [path, kind.title]];
  const other = kindKey === 'major' ? KIND.minor : KIND.major;

  const body = `
<h1>AUBG ${kind.plural} and their requirements</h1>
<p class="lede">Required courses, electives, credits and prerequisites for ${programs.length} ${kind.plural} at the American University in Bulgaria, from the AUBG Academic Catalog AY ${esc(year)}.</p>
<p><a class="btn" href="/">Build my degree plan →</a></p>
<h2>${kind.title}</h2>
<ul class="grid">
${programs
  .map((p) => `<li><a href="${programPath(p)}">${esc(p.name)}<small>${esc(requirementSummary(p))}</small></a></li>`)
  .join('\n')}
</ul>
${
  missing.length
    ? `<p>Not covered here yet: ${esc(missing.join(', '))}. Use the official AUBG catalog for ${missing.length === 1 ? 'this program' : 'these programs'}.</p>`
    : ''
}
<p>Looking for something else? See the <a href="/${other.plural}">AUBG ${other.plural}</a> or the <a href="/general-education">general education requirements</a>.</p>
${disclaimer(data)}`;

  const structured = [
    {
      '@context': 'https://schema.org',
      '@type': 'ItemList',
      name: `AUBG ${kind.plural}`,
      itemListElement: programs.map((p, i) => ({
        '@type': 'ListItem',
        position: i + 1,
        name: `${p.name} ${p.kind}`,
        url: SITE + programPath(p),
      })),
    },
  ];
  return layout({ path, title, description, crumbs, body, structured });
}

export function genEdPage(data) {
  const path = '/general-education';
  const year = data.catalog_year;
  const totalCourses = data.gen_ed.reduce((total, c) => total + (Number(c.courses_required) || 0), 0);
  const title = `AUBG general education requirements (${year})`;
  const description = `AUBG general education (GenEd) requirements for ${year}: the ${data.gen_ed.length} categories, how many courses each one needs, and every course that counts, with credits and prerequisites.`;
  const crumbs = [['/', 'Home'], [path, 'General education']];

  const body = `
<h1>AUBG general education requirements</h1>
<p class="lede">Every student at the American University in Bulgaria completes the foundation courses and ${totalCourses} general education courses across ${data.gen_ed.length} categories, on top of a major. This is the list from the AUBG Academic Catalog AY ${esc(year)}.</p>
<p><a class="btn" href="/">Build my degree plan →</a></p>
${disclaimer(data)}
<h2>Categories at a glance</h2>
<div class="table"><table><thead><tr><th scope="col">Category</th><th scope="col" class="num">Courses required</th><th scope="col" class="num">Courses that count</th></tr></thead><tbody>
${data.gen_ed
  .map(
    (c) =>
      `<tr><td><a href="#${esc(slug(c.name))}">${esc(c.name)}</a></td><td class="num">${esc(c.courses_required ?? '')}</td><td class="num">${c.courses.length}</td></tr>`,
  )
  .join('\n')}
</tbody></table></div>
<h2>Foundation courses</h2>
<p>Taken in the first year. Placement results can waive some of them.</p>
${courseTable(data.foundation_courses)}
<p>The catalog also requires AUB 1000 Introduction to Liberal Arts Learning in the first year.</p>
${data.gen_ed
  .map(
    (c) =>
      `<h2 id="${esc(slug(c.name))}">${esc(c.name)}</h2>${
        c.courses_required ? `<p class="rule">${plural(c.courses_required, 'course')} required</p>` : ''
      }${courseTable(c.courses)}`,
  )
  .join('\n')}
<h2>Plan it with your major</h2>
<p>Some general education courses also count toward a major or minor. The <a href="/">degree planner</a> picks courses that cover several requirements at once. Browse the <a href="/majors">AUBG majors</a> and <a href="/minors">AUBG minors</a>.</p>`;

  return layout({ path, title, description, crumbs, body });
}

export function notFoundPage() {
  const body = `
<h1>Page not found</h1>
<p class="lede">That address does not exist. Try one of these instead.</p>
<ul class="links"><li><a href="/">Degree planner</a></li><li><a href="/majors">AUBG majors</a></li><li><a href="/minors">AUBG minors</a></li><li><a href="/general-education">General education</a></li></ul>`;
  return layout({
    path: '/404',
    title: `Page not found | ${SITE_NAME}`,
    description: 'This page does not exist.',
    body,
    noindex: true,
  });
}

function slug(name) {
  return name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
}

/** Every generated page as { path, html }. `path` has no trailing slash. */
export function buildPages(data) {
  return [
    { path: '/majors', html: indexPage('major', data) },
    { path: '/minors', html: indexPage('minor', data) },
    { path: '/general-education', html: genEdPage(data) },
    ...data.programs.map((program) => ({ path: programPath(program), html: programPage(program, data) })),
  ];
}

export function sitemap(paths, { homeDate, contentDate }) {
  const entry = (path, date) =>
    `  <url>\n    <loc>${SITE}${path}</loc>\n    <lastmod>${date}</lastmod>\n  </url>`;
  return `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${[entry('/', homeDate), ...paths.map((path) => entry(path, contentDate))].join('\n')}
</urlset>
`;
}
