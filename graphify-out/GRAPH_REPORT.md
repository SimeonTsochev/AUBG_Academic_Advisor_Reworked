# Graph Report - AUBG_Academic_Advisor_Reworked-main  (2026-11-09)

## Corpus Check
- 246 files · ~230,863 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 19 file(s) not represented in the graph (top: (none) 6, .css 6, .sha256 2)

## Summary
- 2419 nodes · 6092 edges · 127 communities (91 shown, 36 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 138 edges (avg confidence: 0.88)
- Token cost: 446,922 input · 0 output

## Community Hubs (Navigation)
- Catalog PDF Parser
- Transcript Import Tests
- Engine Course Assignment & Balancing
- Advisor Header & Snapshot Types
- Catalog Cache & Test Isolation
- Excel Course Catalog Index
- Minor Detection & Suggestions
- UI Primitives: Avatar/Breadcrumb
- UI Primitives: Alerts & Dialogs
- UI Primitives: Input/Sheet
- iOS Design Skill Docs
- Backend Response Models
- API Combination Sweep Tests
- App Shell & Snapshot Restore
- Catalog Artifact Builder
- Business Concentrations
- Codebase Design Skill Docs
- Internships & Independent Study
- Plan Generation & Validation
- Setup Screen & Transcript Types
- SEO Page Generator
- Academic Record & Elective Cards
- Plan Overrides & Retakes
- Catalog Correction Tests
- API Routes (main.py)
- Prerequisite Parsing
- Real Catalog Scenario Tests
- Program Rule Tests
- UI Primitives: Checkbox/Dropdown
- Elective Credit Caps
- Program Options Reader
- Shared Snapshot Storage
- Elective Sub-Rules
- Excel Catalog Loader
- Frontend Runtime Dependencies
- Frontend API Client
- Requirement Slot Builder
- Plan Audit & Progress
- Semester Plan View & Availability
- Retake Resolution (frontend)
- UI Primitives: Command/Dialog
- Frontend Package Manifest
- Setup/Advisor Props & Requests
- Program Pages Data
- Private Grades Storage
- GPA & Honors Rules
- Term Eligibility & Rebalancing
- Planner Rules (CLAUDE.md)
- CI Workflow
- Browser MCP Agent Skill
- Academic Record Tests
- Frontend Dev Tooling
- Plan Warnings & Program Links
- UI Primitives: Context Menu
- TypeScript Config
- Graduation Check Tests
- UI Primitives: Carousel/Button
- Elective Recommendations
- Plan PDF Export
- Program Option Tests
- Transcript OCR (frontend)
- UI Primitives: Form
- Elective Progress Tests
- Architecture & Deployment Docs
- Requirement Coverage Tests
- Catalog Policy Concepts (docs)
- UI Primitives: Chart
- UI Primitives: Drawer
- UI Primitives: Select
- iOS Design Manifest
- UI Taste Manifest
- Backend Dependencies & Sources
- UI Primitives: Navigation Menu
- UI Primitives: Pagination
- Program Info Models
- Privacy, Sharing & Public Pages
- Degree Total Top-Up
- Repo Docs & Checks
- Minor Proximity Tests
- QA Plan & Test Gotchas
- Architecture Skill Agent Config
- Course Catalog Endpoint Tests
- Instance ID Override Tests
- Toast Notifications
- UI Primitives: Collapsible
- NPM Scripts
- Social Preview Image
- iOS Design Agent Config
- UI Taste Agent Config
- Figma Origin & Attributions
- UI Primitives: Accordion
- Codebase Design Agent Config
- Domain Modeling Agent Config
- Grilling Agent Config
- Browser MCP Config
- UI Primitives: Aspect Ratio
- SEO Page Types
- Frontend Vercel Config
- Root Package Manifest
- Root Vercel Config
- program_snapshots_create()
- cmdk
- input-otp
- pdfjs-dist
- @radix-ui/react-alert-dialog
- @radix-ui/react-avatar
- @radix-ui/react-checkbox
- @radix-ui/react-context-menu
- @radix-ui/react-hover-card
- @radix-ui/react-label
- @radix-ui/react-navigation-menu
- @radix-ui/react-popover
- @radix-ui/react-radio-group
- @radix-ui/react-scroll-area
- @radix-ui/react-switch
- @radix-ui/react-toggle
- react-day-picker
- react-dom
- react-hook-form
- react-resizable-panels
- recharts
- tailwindcss@*
- SITE
- SITE_NAME
- S6 Responsiveness and robustness

## God Nodes (most connected - your core abstractions)
1. `cn()` - 223 edges
2. `generate_plan()` - 123 edges
3. `IsolatedTestCase` - 85 edges
4. `react` - 61 edges
5. `_normalize_course_code()` - 55 edges
6. `compute_minor_proximity_smart_details()` - 55 edges
7. `MainAdvisorScreen()` - 49 edges
8. `getCatalogCache()` - 41 edges
9. `_course_credits()` - 41 edges
10. `normalize_course_code()` - 37 edges

## Surprising Connections (you probably didn't know these)
- `supabase==2.28.0` --conceptually_related_to--> `Shared /p/<token> snapshot links (Supabase, debounced autosave)`  [INFERRED]
  backend/requirements.txt → CLAUDE.md
- `Black-box student-persona QA agent (anti-detect-browser MCP)` --semantically_similar_to--> `Real-catalog scenario tests (every major at several stages)`  [INFERRED] [semantically similar]
  qa/ux-scenarios.md → CLAUDE.md
- `What counts as an issue (wrong numbers, plan logic, edits that don't stick, privacy)` --semantically_similar_to--> `validate_plan audits the final plan ('Plan needs attention')`  [INFERRED] [semantically similar]
  qa/ux-scenarios.md → README.md
- `Browser MCP Agent skill (.claude)` --semantically_similar_to--> `Browser MCP Agent skill (.agents)`  [INFERRED] [semantically similar]
  .claude/skills/browser-mcp-agent/SKILL.md → .agents/skills/browser-mcp-agent/SKILL.md
- `pdfplumber==0.11.4` --conceptually_related_to--> `Catalog sources: AY-2026-27-2nd-ed.pdf and course_catalog 110926.xls`  [INFERRED]
  backend/requirements.txt → CLAUDE.md

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Catalog data and its hand-edited correction layer** — claude_catalog_data_pipeline, claude_catalog_sources, claude_policy_overrides, claude_course_renumbering, claude_course_groups, claude_program_options, claude_elective_rules, claude_placement_waivers, claude_grade_and_sequence_rules, claude_catalog_dict_shape [EXTRACTED 1.00]
- **generate_plan pipeline stages** — claude_plan_generation_flow, claude_requirement_slots, claude_term_scheduling, claude_plan_overrides, claude_relieve_overloaded_terms, claude_plan_state_audit, claude_graduation_rules, claude_academic_record [EXTRACTED 1.00]
- **Public crawler-facing surface (homepage SEO, llms.txt, robots.txt, program pages)** — frontend_index_open_graph_meta, frontend_index_json_ld_webapplication, frontend_index_crawler_copy, frontend_public_llms, frontend_public_robots, claude_seo_program_pages [INFERRED 0.85]
- **Codebase-design architecture vocabulary (module, interface, implementation, depth, seam, adapter, leverage, locality)** — _agents_skills_codebase_design_skill_module, _agents_skills_codebase_design_skill_interface, _agents_skills_codebase_design_skill_implementation, _agents_skills_codebase_design_skill_depth, _agents_skills_codebase_design_skill_seam, _agents_skills_codebase_design_skill_adapter, _agents_skills_codebase_design_skill_leverage, _agents_skills_codebase_design_skill_locality [EXTRACTED 1.00]
- **Dependency categories for deepening** — _agents_skills_codebase_design_deepening_in_process_dependency, _agents_skills_codebase_design_deepening_local_substitutable_dependency, _agents_skills_codebase_design_deepening_ports_and_adapters, _agents_skills_codebase_design_deepening_true_external_mock [EXTRACTED 1.00]
- **Architecture review workflow (scan, report, grill, record domain model)** — _agents_skills_improve_codebase_architecture_skill_improve_codebase_architecture, _agents_skills_improve_codebase_architecture_html_report_html_report, _agents_skills_codebase_design_skill_codebase_design, _agents_skills_grilling_skill_grilling, _agents_skills_domain_modeling_skill_domain_modeling [EXTRACTED 1.00]
- **ui-taste playbooks selected by the router** — _agents_skills_ui_taste_skill_playbook_router, _agents_skills_ui_taste_reference_new_work, _agents_skills_ui_taste_reference_operate, _agents_skills_ui_taste_reference_polish, _agents_skills_ui_taste_reference_distill, _agents_skills_ui_taste_reference_audit, _agents_skills_ui_taste_reference_ios, _agents_skills_ui_taste_reference_overdrive, _agents_skills_ui_taste_reference_craft [EXTRACTED 1.00]
- **Guidance adapted from Impeccable (new-work, craft, Overdrive)** — _agents_skills_ui_taste_modifications_impeccable, _agents_skills_ui_taste_reference_new_work, _agents_skills_ui_taste_reference_craft, _agents_skills_ui_taste_reference_overdrive, _agents_skills_ios_design_reference_craft, _agents_skills_ios_design_reference_overdrive [EXTRACTED 1.00]
- **Render, batch-fix and re-inspect verification loop** — _agents_skills_ui_taste_reference_craft_close_the_loop, _agents_skills_ios_design_reference_craft_close_the_loop, _agents_skills_ios_design_skill_affected_states_check, _agents_skills_ui_taste_reference_overdrive_resilient_enhancement, _agents_skills_ui_taste_reference_overdrive_four_final_questions [INFERRED 0.85]

## Communities (127 total, 36 thin omitted)

### Community 0 - "Catalog PDF Parser"
Cohesion: 0.05
Nodes (59): _clean_title(), _collect_prereq_codes_from_blocks(), _dedupe_codes(), _dedupe_display_letters(), detect_course_table_pages(), extract_catalog_year(), _extract_codes_in_order(), extract_course_table_from_pdf() (+51 more)

### Community 1 - "Transcript Import Tests"
Cohesion: 0.06
Nodes (54): _build_pdf_bytes(), _lines(), _pdf_without_fonts(), PdfTextLayerTests, PortalTranscriptLayoutTests, _stub_page(), TranscriptImportTests, TranscriptMergeTests (+46 more)

### Community 2 - "Engine Course Assignment & Balancing"
Cohesion: 0.05
Nodes (68): _assign_course_to_slots(), balance_term_credits(), add_free_elective(), term_credit_bounds(), _build_course_output(), _build_direct_reason_map(), _canonicalize_gened_labels(), _catalog_courses() (+60 more)

### Community 3 - "Advisor Header & Snapshot Types"
Cohesion: 0.05
Nodes (55): PlanCourse, PlanOverrideAdd, PlanOverrides, ProgramSnapshotSwappedElective, AdvisorHeader(), AdvisorHeaderProps, ShareToken, ShareTokenButton() (+47 more)

### Community 4 - "Catalog Cache & Test Isolation"
Cohesion: 0.09
Nodes (10): CatalogCache, getCatalogCache(), mark_catalog_read_only(), load_course_catalog_from_data(), IsolatedTestCase, load_real_excel_index(), CorsTests, PdfExportEndpointTests (+2 more)

### Community 5 - "Excel Course Catalog Index"
Cohesion: 0.09
Nodes (44): _apply_catalog_payload(), _area_tag_rows(), _availability_indices(), build_course_catalog_data(), _build_course_record(), _build_search_blob(), _clean_cell(), _clean_header() (+36 more)

### Community 6 - "Minor Detection & Suggestions"
Cohesion: 0.07
Nodes (22): _compute_minor_alerts(), compute_minor_proximity_smart_details(), compute_minor_suggestions(), _elective_block_is_cap(), _elective_block_is_level_constraint(), _infer_allowed_prefixes_for_minor_electives(), _is_creative_writing_minor(), _is_cs_minor() (+14 more)

### Community 7 - "UI Primitives: Avatar/Breadcrumb"
Cohesion: 0.07
Nodes (43): Avatar(), AvatarFallback(), AvatarImage(), BreadcrumbEllipsis(), BreadcrumbItem(), BreadcrumbLink(), BreadcrumbList(), BreadcrumbPage() (+35 more)

### Community 8 - "UI Primitives: Alerts & Dialogs"
Cohesion: 0.06
Nodes (31): Alert(), AlertDescription(), AlertTitle(), alertVariants, AlertDialogAction(), AlertDialogCancel(), AlertDialogContent, AlertDialogDescription (+23 more)

### Community 9 - "UI Primitives: Input/Sheet"
Cohesion: 0.06
Nodes (43): Input(), Separator(), Sheet(), SheetContent(), SheetDescription(), SheetFooter(), SheetHeader(), SheetOverlay() (+35 more)

### Community 10 - "iOS Design Skill Docs"
Cohesion: 0.06
Nodes (29): ios-design Modifications Notice, Impeccable by Paul Bakaus (Apache-2.0, v4.4.0), Uizze Craft Checks (ios-design), Uizze Overdrive (ios-design), Overdrive Four Final Questions, Uizze Reference Policy (ios-design), ios-design Skill (iPhone UI/UX), Apple Human Interface Guidelines (+21 more)

### Community 11 - "Backend Response Models"
Cohesion: 0.07
Nodes (40): AcademicRecord, CourseRequirement, DualDiplomaCheck, ElectivePlaceholder, ElectiveProgress, ElectiveProgressCourse, ElectiveRecommendation, ElectiveRuleStatus (+32 more)

### Community 12 - "API Combination Sweep Tests"
Cohesion: 0.06
Nodes (15): _ApiCase, ProgramCombinationSweepTests, RandomEditWalkTests, PlanApiTests, _choice_group_catalog(), MinorChoiceGroupProximityTests, build_filler_catalog(), build_random_catalog() (+7 more)

### Community 13 - "App Shell & Snapshot Restore"
Cohesion: 0.07
Nodes (34): getProgramSnapshot(), AcademicSetupScreen, App(), restoreFromToken(), importAdvisorScreen(), importSetupScreen(), MainAdvisorScreen, ManualCreditCandidate (+26 more)

### Community 14 - "Catalog Artifact Builder"
Cohesion: 0.11
Nodes (26): apply_policy_overrides(), _apply_program_policy(), build_excel_catalog_artifact(), build_pdf_requirements_artifact(), ensure_policy_overrides_file(), expand_course_groups(), normalize_mismatch_snapshot(), normalize_policy_overrides() (+18 more)

### Community 15 - "Business Concentrations"
Cohesion: 0.15
Nodes (40): active_business_concentration(), _audit_remaining_score(), available_business_concentrations(), build_business_concentration_audit(), business_concentration_messages(), _business_required_courses(), _candidate_codes_for_rule(), _catalog_course_codes() (+32 more)

### Community 16 - "Codebase Design Skill Docs"
Cohesion: 0.06
Nodes (29): Deepening (cluster of shallow modules), In-process dependency category, Local-substitutable dependency category, Remote but owned (Ports & Adapters), True external dependency (Mock), Sub-agent design constraints (minimize, flexibility, common caller, ports & adapters), John Ousterhout (A Philosophy of Software Design), Adapter (+21 more)

### Community 17 - "Internships & Independent Study"
Cohesion: 0.08
Nodes (14): _eligibility_errors(), independent_study_check(), internship_check(), is_independent_study(), is_internship(), _enforces_academic_policies(), program_sequence_rules(), _projected_degree_credits() (+6 more)

### Community 18 - "Plan Generation & Validation"
Cohesion: 0.09
Nodes (20): _collect_elective_placeholders(), _compute_prereq_warnings(), _foundation_timing_warnings(), _gen_ed_status(), generate_plan(), _make_warning(), _unmet_prereq_labels(), validate_plan() (+12 more)

### Community 19 - "Setup Screen & Transcript Types"
Cohesion: 0.10
Nodes (34): PlacementWaiver, ProgramInfo, ProgramOptions, SearchCoursesContext, TranscriptImportCourse, TranscriptImportMatchCandidate, TranscriptImportResponse, TranscriptUnreadLine (+26 more)

### Community 20 - "SEO Page Generator"
Cohesion: 0.12
Nodes (33): data, outDir, pages, root, breadcrumbLd(), breadcrumbs(), buildPages(), courseTable() (+25 more)

### Community 21 - "Academic Record & Elective Cards"
Cohesion: 0.11
Nodes (33): AcademicRecord, ElectiveProgress, ElectiveRuleStatus, GeneratePlanResponse, MinorSuggestion, AcademicRecordCard(), AcademicRecordCardProps, GradeSelect() (+25 more)

### Community 22 - "Plan Overrides & Retakes"
Cohesion: 0.09
Nodes (30): _annotate_unlocks(), _apply_latest_attempt_credit_rule(), _apply_plan_overrides(), add_filler(), available_bounds(), before_start(), drop_course(), ensure_course_obj() (+22 more)

### Community 23 - "Catalog Correction Tests"
Cohesion: 0.09
Nodes (5): _min_credits_for_course(), CatalogCorrectionTests, build_sample_catalog(), plan_course(), PlanValidationTests

### Community 24 - "API Routes (main.py)"
Cohesion: 0.15
Nodes (26): _cached_plan(), _catalog_courses_for_response(), catalog_integrity(), courses_get(), courses_list(), courses_search(), _ensure_catalog(), _excel_only_code_set() (+18 more)

### Community 25 - "Prerequisite Parsing"
Cohesion: 0.10
Nodes (31): normalize_course_code(), _choice_count_hint_from_text(), _course_coreqs(), _course_prereq_expr(), _course_prereqs(), _dedupe_course_codes(), _extract_or_prereq_groups(), _extract_required_from_program_choice_blocks() (+23 more)

### Community 26 - "Real Catalog Scenario Tests"
Cohesion: 0.12
Nodes (8): _completed_after(), _min_credits_stated_in_catalog(), _plan(), _real_courses(), RealCatalogScenarioTests, _required_options(), Scenario, _term_of()

### Community 28 - "UI Primitives: Checkbox/Dropdown"
Cohesion: 0.06
Nodes (18): Checkbox(), DropdownMenuCheckboxItem(), DropdownMenuContent(), DropdownMenuItem(), DropdownMenuLabel(), DropdownMenuRadioItem(), DropdownMenuSeparator(), DropdownMenuShortcut() (+10 more)

### Community 29 - "Elective Credit Caps"
Cohesion: 0.13
Nodes (18): _counted_credits_with_caps(), _elective_block_rule_text(), _expand_wildcard_allowed_courses(), _expand_wildcard_matches(), _parse_number(), compute_elective_progress(), counts(), course_credits() (+10 more)

### Community 30 - "Program Options Reader"
Cohesion: 0.13
Nodes (17): _choice(), chosen_choices(), offered_placement_waivers(), OptionBlock, OptionChoice, options_offered(), placement_tests(), PlacementWaiver (+9 more)

### Community 31 - "Shared Snapshot Storage"
Cohesion: 0.13
Nodes (17): _check_snapshot_db(), _ensure_snapshot_storage_available(), program_snapshots_get(), _startup_init_snapshot_db(), _startup_preload_catalog_cache(), _cleanup_expired_snapshot(), _coerce_int(), create_snapshot() (+9 more)

### Community 32 - "Elective Sub-Rules"
Cohesion: 0.11
Nodes (8): is_upper_level_creative_writing(), _course_number(), _codes(), CourseSet, ElectiveRule, pattern_regex(), pool_matcher(), _prefixes()

### Community 33 - "Excel Catalog Loader"
Cohesion: 0.21
Nodes (15): _clean_cell(), _clean_header(), _decode_excel_escapes(), _empty_catalog(), get_case_studies_gened_courses(), get_selected_program_elective_tags(), is_program_elective_tag(), load_excel_catalog() (+7 more)

### Community 34 - "Frontend Runtime Dependencies"
Cohesion: 0.09
Nodes (23): dependencies, class-variance-authority@^0.7.1, clsx@*, embla-carousel-react@^8.6.0, lucide-react@^0.487.0, @radix-ui/react-dropdown-menu@^2.1.6, @radix-ui/react-menubar@^1.1.6, @radix-ui/react-progress@^1.1.2 (+15 more)

### Community 35 - "Frontend API Client"
Cohesion: 0.14
Nodes (22): API_BASE, BusinessCourseClassification, CourseRequirement, createProgramSnapshot(), CreateProgramSnapshotResponse, downloadPlanPdf(), generatePlan(), getCourse() (+14 more)

### Community 36 - "Requirement Slot Builder"
Cohesion: 0.12
Nodes (14): build_requirement_slots(), merge_program_choice_requirements(), _choice_group_deficits(), dfs(), _coerce_minor_choice_group(), _coerce_positive_int(), _extract_minor_required_structure(), add_choice_group() (+6 more)

### Community 37 - "Plan Audit & Progress"
Cohesion: 0.15
Nodes (9): _apply_manual_credit_progress(), _category_credit_progress(), _completed_credit_total(), audit_plan(), _category_progress(), _elective_progress(), _placement_elective_credits(), PlanAudit (+1 more)

### Community 38 - "Semester Plan View & Availability"
Cohesion: 0.13
Nodes (18): CourseCatalogRecord, searchCourses(), GroupedCourses, HIDDEN_TAGS, SemesterPlanView(), SemesterPlanViewProps, TAG_BADGES, TERM_STATUS_BADGE (+10 more)

### Community 39 - "Retake Resolution (frontend)"
Cohesion: 0.19
Nodes (17): normalizeCompletedCourseTerms(), ActiveAttemptResolution, attemptId(), CourseAttemptLike, describeFailedAttempt(), FailedAttempt, normalizeCode(), normalizeFailedCourses() (+9 more)

### Community 40 - "UI Primitives: Command/Dialog"
Cohesion: 0.16
Nodes (16): Command(), CommandDialog(), CommandGroup(), CommandInput(), CommandItem(), CommandList(), CommandSeparator(), CommandShortcut() (+8 more)

### Community 41 - "Frontend Package Manifest"
Cohesion: 0.10
Nodes (19): @radix-ui/react-accordion@^1.2.3, @radix-ui/react-dialog@^1.1.6, @radix-ui/react-select@^2.1.6, @radix-ui/react-slider@^1.2.3, @radix-ui/react-tabs@^1.1.3, @radix-ui/react-toggle-group@^1.1.2, @vercel/analytics@^2.0.1, @vercel/speed-insights@^2.0.0 (+11 more)

### Community 42 - "Setup/Advisor Props & Requests"
Cohesion: 0.17
Nodes (17): GeneratePlanRequest, ProgramOptionSelection, ProgramSnapshotPayload, UploadCatalogResponse, AcademicSelection, AcademicSetupScreenProps, SetupPrefill, MainAdvisorScreenProps (+9 more)

### Community 43 - "Program Pages Data"
Cohesion: 0.21
Nodes (10): readable_label(), build_program_pages_payload(), _business_concentrations(), catalog_text_lines(), _course(), _courses(), _options(), _program() (+2 more)

### Community 44 - "Private Grades Storage"
Cohesion: 0.19
Nodes (14): GradeEntry, usePrivateGrades(), GradeRecord, gradesFromTranscript(), GradeStorage, loadGrades(), normalizeGrades(), readAll() (+6 more)

### Community 45 - "GPA & Honors Rules"
Cohesion: 0.18
Nodes (10): academic_record(), program_courses(), _gpa(), _grade_rule_errors(), honors_outlook(), latest_grades(), _load_errors(), _program_courses() (+2 more)

### Community 46 - "Term Eligibility & Rebalancing"
Cohesion: 0.28
Nodes (16): _completed_gened_categories(), _course_gened_categories(), _eligible_for_term(), _rebalance_term_mix(), attempt_diversity_swap(), attempt_swap(), available_bounds(), completed_before() (+8 more)

### Community 47 - "Planner Rules (CLAUDE.md)"
Cohesion: 0.14
Nodes (14): Academic record (GPA, Dean's/President's List, Latin honors, load limits 17/19/22), Elective sub-rules (at_least / at_most / at_least_in_one_group over CourseSets), enforce_academic_policies flag, Graduation rules (3 WICs, 60 AUBG credits, 3 retakes, double-counting limits, internships, independent studies), MAX_PLAN_TERMS = 12 (never silently truncated), generate_plan flow (slots -> select -> schedule -> balance -> overrides -> validate -> audit), PlanState + audit_plan (graduation checks, elective progress, GPA record), Hard-coded program special cases (CS, Creative Writing, Fine Arts, Economics minors, Textual Analysis) (+6 more)

### Community 48 - "CI Workflow"
Cohesion: 0.11
Nodes (17): runs-on, steps, jobs, check, name, on, pull_request, push (+9 more)

### Community 49 - "Browser MCP Agent Skill"
Cohesion: 0.13
Nodes (11): anti-detect-browser npm package (MCP server), antibrow PyPI package, Browser MCP Agent skill (.agents), Browsing tool set (launch_browser, navigate, get_content, screenshot, click, fill, close_browser), Kernel-enforced concurrency limit (close_browser required), Persistent browser profile, Recipe tools (list_recipes, run_recipe, fanout_recipe), Temporary (throwaway) profile option (+3 more)

### Community 51 - "Frontend Dev Tooling"
Cohesion: 0.13
Nodes (14): devDependencies, @types/node@^20.10.0, @types/react@^18.3.31, @types/react-dom@^18.3.7, typescript@^5.9.3, vite@^6.4.1, @vitejs/plugin-react@^4.7.0, vitest@^3.2.7 (+6 more)

### Community 52 - "Plan Warnings & Program Links"
Cohesion: 0.19
Nodes (12): PlanWarning, describeEditWarning(), describeEditWarnings(), offeredIn(), text(), matchPrograms(), NO_PROGRAM_LINK, ProgramLink (+4 more)

### Community 53 - "UI Primitives: Context Menu"
Cohesion: 0.12
Nodes (9): ContextMenuCheckboxItem(), ContextMenuContent(), ContextMenuItem(), ContextMenuLabel(), ContextMenuRadioItem(), ContextMenuSeparator(), ContextMenuShortcut(), ContextMenuSubContent() (+1 more)

### Community 54 - "TypeScript Config"
Cohesion: 0.12
Nodes (15): compilerOptions, esModuleInterop, isolatedModules, jsx, lib, module, moduleResolution, noEmit (+7 more)

### Community 55 - "Graduation Check Tests"
Cohesion: 0.22
Nodes (3): residency_check(), GraduationCheckTests, below_minimum()

### Community 56 - "UI Primitives: Carousel/Button"
Cohesion: 0.19
Nodes (14): Button(), Carousel(), CarouselApi, CarouselContent(), CarouselContext, CarouselContextProps, CarouselItem(), CarouselNext() (+6 more)

### Community 57 - "Elective Recommendations"
Cohesion: 0.23
Nodes (3): get_recommended_electives(), ExcelCatalogTests, _write_xlsx()

### Community 58 - "Plan PDF Export"
Cohesion: 0.20
Nodes (5): _course_label_for_pdf(), _manual_credit_label(), plan_to_pdf_bytes(), _term_sort_key(), PdfRetakeExportTests

### Community 60 - "Transcript OCR (frontend)"
Cohesion: 0.22
Nodes (10): tesseract.js@^6.0.1, TranscriptImportLineInput, extractTranscriptLinesFromImage(), extractTranscriptLinesFromPdf(), normalizeOcrLine(), OcrLine, OcrPage, ocrRenderScale() (+2 more)

### Community 61 - "UI Primitives: Form"
Cohesion: 0.21
Nodes (11): FormControl(), FormDescription(), FormFieldContext, FormFieldContextValue, FormItem(), FormItemContext, FormItemContextValue, FormLabel() (+3 more)

### Community 63 - "Architecture & Deployment Docs"
Cohesion: 0.17
Nodes (9): fastapi==0.115.5, API routes (/catalog/load-default, /plan/generate, /transcript/import, /program-snapshots, ...), CORS policy (localhost, *.vercel.app, CORS_ORIGINS, CORS_ALLOW_ALL), Frontend screen flow (welcome -> setup -> advisor, SetupPrefill), Vercel deployment (frontend aubg-advisor.com, backend *.vercel.app, two vercel.json copies), frontend/index.html (app shell + homepage SEO), Boot loader ('Preparing your plan'), JSON-LD WebApplication schema (+1 more)

### Community 65 - "Catalog Policy Concepts (docs)"
Cohesion: 0.20
Nodes (8): Catalog dict shape (courses, course_meta, majors/minors, gen_ed, degree_total_credits), course_groups ({"group": name} expansion), course_renumbering (old code -> current code), grade_rules and sequence_rules (SequenceRule), Placement waivers (COS 1020, INF 1030, MLC; MAT 1000 / ENG 1000 auto-waiver), Program options (concentrations, language focus; block roles elective/required/collateral), Class standing by earned credits (27/57/87), S1 First visit and setup

### Community 66 - "UI Primitives: Chart"
Cohesion: 0.27
Nodes (10): ChartConfig, ChartContainer(), ChartContext, ChartContextProps, ChartLegendContent(), ChartStyle(), ChartTooltipContent(), getPayloadConfigFromPayload() (+2 more)

### Community 67 - "UI Primitives: Drawer"
Cohesion: 0.22
Nodes (7): DrawerContent(), DrawerDescription(), DrawerFooter(), DrawerHeader(), DrawerOverlay(), DrawerPortal(), DrawerTitle()

### Community 68 - "UI Primitives: Select"
Cohesion: 0.22
Nodes (7): SelectContent(), SelectItem(), SelectLabel(), SelectScrollDownButton(), SelectScrollUpButton(), SelectSeparator(), SelectTrigger()

### Community 69 - "iOS Design Manifest"
Cohesion: 0.20
Nodes (9): designAuthority, designStack, commit, license, version, evidenceMode, included, name (+1 more)

### Community 70 - "UI Taste Manifest"
Cohesion: 0.20
Nodes (9): designAuthority, designStack, commit, license, version, evidenceMode, included, name (+1 more)

### Community 71 - "Backend Dependencies & Sources"
Cohesion: 0.22
Nodes (8): backend/requirements.txt (runtime deps), pdfplumber==0.11.4, pydantic==2.11.7, rapidfuzz==3.14.3, reportlab==4.2.5, supabase==2.28.0, xlrd==2.0.1 / openpyxl==3.1.5 (Excel readers), Catalog sources: AY-2026-27-2nd-ed.pdf and course_catalog 110926.xls

### Community 72 - "UI Primitives: Navigation Menu"
Cohesion: 0.24
Nodes (9): NavigationMenu(), NavigationMenuContent(), NavigationMenuIndicator(), NavigationMenuItem(), NavigationMenuLink(), NavigationMenuList(), NavigationMenuTrigger(), navigationMenuTriggerStyle (+1 more)

### Community 73 - "UI Primitives: Pagination"
Cohesion: 0.28
Nodes (7): Pagination(), PaginationContent(), PaginationEllipsis(), PaginationLink(), PaginationLinkProps, PaginationNext(), PaginationPrevious()

### Community 74 - "Program Info Models"
Cohesion: 0.25
Nodes (4): _program_info(), PlacementWaiverInfo, ProgramInfo, ProgramOptionsInfo

### Community 75 - "Privacy, Sharing & Public Pages"
Cohesion: 0.39
Nodes (6): Public requirement pages (SEO: programs.json -> static HTML, sitemap), Shared /p/<token> snapshot links (Supabase, debounced autosave), frontend/public/llms.txt (LLM-facing site summary), Unofficial tool disclaimer (confirm with advisor), frontend/public/robots.txt (Disallow /p/, sitemap), S5 Side panels and outputs (PDF, shared link)

### Community 76 - "Degree Total Top-Up"
Cohesion: 0.38
Nodes (6): _free_elective_code_generator(), next_code(), _next_term_label(), _top_up_to_degree_total(), add_placeholder(), occupied_credits()

### Community 77 - "Repo Docs & Checks"
Cohesion: 0.43
Nodes (7): backend/requirements-dev.txt (pytest, pytest-cov, pytest-randomly, ruff), pytest-randomly (shuffled test order), CLAUDE.md (repo guide), AUBG Academic Advisor, scripts/check.py (CI + pre-push: lint, tests, typecheck, build), IsolatedTestCase (excel_index empty/real), README.md (project overview)

### Community 79 - "QA Plan & Test Gotchas"
Cohesion: 0.29
Nodes (6): Start-term clamp (_current_start_term uses date.today()), Real-catalog scenario tests (every major at several stages), qa/ux-scenarios.md (browser QA test plan), Findings log format (qa/runs/<date>/findings.md), What counts as an issue (wrong numbers, plan logic, edits that don't stick, privacy), validate_plan audits the final plan ('Plan needs attention')

### Community 80 - "Architecture Skill Agent Config"
Cohesion: 0.33
Nodes (5): interface, display_name, short_description, policy, allow_implicit_invocation

### Community 83 - "Toast Notifications"
Cohesion: 0.33
Nodes (4): next-themes@^0.4.6, sonner@^2.0.3, next-themes, sonner

### Community 85 - "NPM Scripts"
Cohesion: 0.33
Nodes (6): scripts, build, dev, preview, test, typecheck

### Community 86 - "Social Preview Image"
Cohesion: 0.47
Nodes (6): aubg-advisor.com, Free degree planner for AUBG students, Graduation Cap App Icon, AUBG Academic Co-Advisor (product name), Open Graph Social Preview Card (og-image.png), Semester-by-semester degree plan for majors and minors

### Community 87 - "iOS Design Agent Config"
Cohesion: 0.40
Nodes (4): interface, default_prompt, display_name, short_description

### Community 88 - "UI Taste Agent Config"
Cohesion: 0.40
Nodes (4): interface, default_prompt, display_name, short_description

### Community 89 - "Figma Origin & Attributions"
Cohesion: 0.40
Nodes (4): frontend/README.md (Figma 'Academic Advising App Design' bundle), Figma design origin (Academic Advising App Design), shadcn/ui (MIT), Unsplash photos

### Community 90 - "UI Primitives: Accordion"
Cohesion: 0.40
Nodes (3): AccordionContent(), AccordionItem(), AccordionTrigger()

### Community 91 - "Codebase Design Agent Config"
Cohesion: 0.50
Nodes (3): interface, display_name, short_description

### Community 92 - "Domain Modeling Agent Config"
Cohesion: 0.50
Nodes (3): interface, display_name, short_description

### Community 93 - "Grilling Agent Config"
Cohesion: 0.50
Nodes (3): interface, display_name, short_description

### Community 94 - "Browser MCP Config"
Cohesion: 0.50
Nodes (3): ANTI_DETECT_BROWSER_KEY, anti-detect-browser, anti-detect-browser

### Community 96 - "SEO Page Types"
Cohesion: 0.50
Nodes (3): PageCourse, PageData, PageProgram

### Community 97 - "Frontend Vercel Config"
Cohesion: 0.50
Nodes (3): headers, rewrites, trailingSlash

### Community 98 - "Root Package Manifest"
Cohesion: 0.67
Nodes (3): dependencies, @vercel/analytics@^2.0.1, @vercel/analytics

### Community 99 - "Root Vercel Config"
Cohesion: 0.50
Nodes (3): headers, rewrites, trailingSlash

### Community 100 - "program_snapshots_create()"
Cohesion: 0.67
Nodes (3): program_snapshots_create(), CreateSnapshotRequest, CreateSnapshotResponse

## Knowledge Gaps
- **42 isolated node(s):** `anti-detect-browser`, `ANTI_DETECT_BROWSER_KEY`, `SITE`, `SITE_NAME`, `course_renumbering (old code -> current code)` (+37 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 506 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **36 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `generate_plan()` connect `Plan Generation & Validation` to `Catalog PDF Parser`, `Engine Course Assignment & Balancing`, `Catalog Cache & Test Isolation`, `Minor Detection & Suggestions`, `API Combination Sweep Tests`, `Business Concentrations`, `Internships & Independent Study`, `Plan Overrides & Retakes`, `Catalog Correction Tests`, `API Routes (main.py)`, `Real Catalog Scenario Tests`, `Program Rule Tests`, `Program Options Reader`, `Excel Catalog Loader`, `Requirement Slot Builder`, `Plan Audit & Progress`, `Term Eligibility & Rebalancing`, `Academic Record Tests`, `Graduation Check Tests`, `Elective Recommendations`, `Program Option Tests`, `Elective Progress Tests`, `Requirement Coverage Tests`, `Degree Total Top-Up`, `Instance ID Override Tests`?**
  _High betweenness centrality (0.062) - this node is a cross-community bridge._
- **Are the 2 inferred relationships involving `generate_plan()` (e.g. with `_normalize_course_code()` and `PlanState`) actually correct?**
  _`generate_plan()` has 2 INFERRED edges - model-reasoned connections that need verification._
- **What connects `anti-detect-browser`, `ANTI_DETECT_BROWSER_KEY`, `SITE` to the rest of the system?**
  _42 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Catalog PDF Parser` be split into smaller, more focused modules?**
  _Cohesion score 0.05172413793103448 - nodes in this community are weakly interconnected._
- **Why does `IsolatedTestCase` connect `Catalog Cache & Test Isolation` to `Catalog PDF Parser`, `Transcript Import Tests`, `Excel Course Catalog Index`, `Minor Detection & Suggestions`, `API Combination Sweep Tests`, `Business Concentrations`, `Plan Generation & Validation`, `Catalog Correction Tests`, `Real Catalog Scenario Tests`, `Program Rule Tests`, `Requirement Slot Builder`, `Academic Record Tests`, `Graduation Check Tests`, `Elective Recommendations`, `Plan PDF Export`, `Program Option Tests`, `Elective Progress Tests`, `Requirement Coverage Tests`, `Minor Proximity Tests`, `Course Catalog Endpoint Tests`, `Instance ID Override Tests`?**
  _High betweenness centrality (0.061) - this node is a cross-community bridge._
- **Are the 36 inferred relationships involving `_normalize_course_code()` (e.g. with `_apply_latest_attempt_credit_rule()` and `_apply_plan_overrides()`) actually correct?**
  _`_normalize_course_code()` has 36 INFERRED edges - model-reasoned connections that need verification._
- **Should `Transcript Import Tests` be split into smaller, more focused modules?**
  _Cohesion score 0.06138975966562173 - nodes in this community are weakly interconnected._