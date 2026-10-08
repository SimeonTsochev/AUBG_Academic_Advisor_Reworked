import { ElectiveSuggestion } from '../types';
import { Award, Check, Plus } from 'lucide-react';
import { useMemo, useState } from 'react';

export interface ElectiveRecommendationFilter {
  id: string;
  label: string;
  program: string;
  programType: 'major' | 'minor';
  tagPrefixes: string[];
  displayTag: string;
}

interface ElectiveRecommendationPanelProps {
  electives: ElectiveSuggestion[];
  onAdd?: (code: string) => void;
  existingCodes?: Set<string>;
  requirementFilters?: ElectiveRecommendationFilter[];
}

export function ElectiveRecommendationPanel({
  electives,
  onAdd,
  existingCodes,
  requirementFilters = []
}: ElectiveRecommendationPanelProps) {
  const [selectedRequirement, setSelectedRequirement] = useState<string>('ALL');
  const normalizeText = (value: string) => value.replace(/\s+/g, ' ').trim().toLowerCase();
  const tagMatchesFilter = (tag: string, filter: ElectiveRecommendationFilter) => {
    const normalizedTag = normalizeText(tag);
    const normalizedDisplayTag = normalizeText(filter.displayTag);
    if (normalizedTag === normalizedDisplayTag) return true;
    if (filter.programType === 'minor' && normalizedTag === normalizeText(`Minor - ${filter.program}`)) return true;

    const needle = filter.programType === 'major' ? 'major elective' : 'minor elective';
    if (!normalizedTag.includes(needle) || filter.tagPrefixes.length === 0) return false;
    return filter.tagPrefixes.some((prefix) => normalizedTag.startsWith(`${prefix} `));
  };
  const electiveMatchesFilter = (elective: ElectiveSuggestion, filter: ElectiveRecommendationFilter) =>
    elective.tags.some((tag) => tagMatchesFilter(tag, filter));
  const requirementOptions = useMemo(() => {
    if (requirementFilters.length > 0) {
      return requirementFilters.map((filter) => ({
        id: filter.id,
        label: filter.label,
        filter
      }));
    }

    const requirements = new Set<string>();
    electives.forEach((elective) => {
      elective.tags.forEach((tag) => {
        const normalized = tag.toLowerCase();
        const isSelectedProgramRequirement =
          normalized.includes('major elective') ||
          normalized.includes('minor elective') ||
          normalized.startsWith('minor - ');
        if (isSelectedProgramRequirement) {
          requirements.add(tag);
        }
      });
    });
    return Array.from(requirements)
      .sort((a, b) => a.localeCompare(b))
      .map((tag) => ({
        id: tag,
        label: tag,
        filter: null
      }));
  }, [electives, requirementFilters]);
  const activeRequirement =
    selectedRequirement === 'ALL' || requirementOptions.some((option) => option.id === selectedRequirement)
      ? selectedRequirement
      : 'ALL';
  const activeRequirementOption = requirementOptions.find((option) => option.id === activeRequirement) ?? null;
  const filteredElectives = useMemo(() => {
    if (activeRequirement === 'ALL') return electives;
    if (!activeRequirementOption) return electives;
    return electives.filter((elective) =>
      activeRequirementOption.filter
        ? electiveMatchesFilter(elective, activeRequirementOption.filter)
        : elective.tags.includes(activeRequirementOption.id)
    );
  }, [activeRequirement, activeRequirementOption, electives]);
  const rankByCode = useMemo(() => {
    return new Map(electives.map((elective, index) => [elective.code, index + 1]));
  }, [electives]);
  const requirementCounts = useMemo(() => {
    const counts = new Map<string, number>();
    requirementOptions.forEach((option) => {
      const count = electives.filter((elective) =>
        option.filter ? electiveMatchesFilter(elective, option.filter) : elective.tags.includes(option.id)
      ).length;
      counts.set(option.id, count);
    });
    return counts;
  }, [electives, requirementOptions]);

  return (
    <section className="stack-4" aria-labelledby="recommended-electives-title">
      <header className="flex items-center gap-3">
        <span className="icon-tile" aria-hidden="true">
          <Award />
        </span>
        <div>
          <h2 id="recommended-electives-title" className="section-title">Recommended electives</h2>
          <p className="section-subtitle">Courses that count toward the elective credits your programs still need.</p>
        </div>
      </header>

      {requirementOptions.length > 0 && (
        <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Filter by program">
          <button
            type="button"
            onClick={() => setSelectedRequirement('ALL')}
            className={`chip filter-chip${activeRequirement === 'ALL' ? ' is-active' : ''}`}
            aria-pressed={activeRequirement === 'ALL'}
          >
            All programs
            <span className="filter-chip-count num">{electives.length}</span>
          </button>
          {requirementOptions.map((requirement) => {
            const isActive = activeRequirement === requirement.id;
            return (
              <button
                key={requirement.id}
                type="button"
                onClick={() => setSelectedRequirement(requirement.id)}
                className={`chip filter-chip${isActive ? ' is-active' : ''}`}
                aria-pressed={isActive}
              >
                {requirement.label}
                <span className="filter-chip-count num">{requirementCounts.get(requirement.id) ?? 0}</span>
              </button>
            );
          })}
        </div>
      )}

      <div className="grid-2">
        {filteredElectives.map((elective) => {
          const inPlan = existingCodes?.has(elective.code) ?? false;
          return (
            <article key={elective.code} className="card card-interactive recommendation-card">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="course-code">{elective.code}</span>
                    <span className="muted text-xs num">{elective.credits} cr</span>
                    <span className="badge badge-gold num">#{rankByCode.get(elective.code) ?? 1}</span>
                  </div>
                  <p className="course-name">{elective.name}</p>
                </div>
                {onAdd && (
                  <button
                    type="button"
                    onClick={() => onAdd(elective.code)}
                    disabled={inPlan}
                    className={`btn btn-sm ${inPlan ? 'btn-outline' : 'btn-primary'}`}
                    title={inPlan ? 'Already in plan' : 'Add to plan'}
                  >
                    {inPlan ? <Check aria-hidden="true" /> : <Plus aria-hidden="true" />}
                    <span>{inPlan ? 'In plan' : 'Add'}</span>
                  </button>
                )}
              </div>

              <p className="course-reason">{elective.explanation}</p>

              <div className="flex flex-wrap gap-1">
                <span className="badge badge-navy num">
                  Counts toward {elective.requirementsSatisfied} requirement{elective.requirementsSatisfied === 1 ? '' : 's'}
                </span>
                {elective.tags.map((tag) => {
                  const normalized = tag.toLowerCase();
                  const tone = normalized.includes('writing intensive')
                    ? 'badge-info'
                    : normalized.includes('gen ed')
                      ? 'badge-gold'
                      : 'badge-neutral';
                  return (
                    <span key={tag} className={`badge ${tone}`}>
                      {tag}
                    </span>
                  );
                })}
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}
