import { describe, expect, it } from 'vitest';
import type { ElectiveProgress } from '../api';
import { describeElectiveRemaining, summarizeElectiveRequirements } from './electiveProgress';

const progress = (overrides: Partial<ElectiveProgress>): ElectiveProgress => ({
  program: 'Economics',
  program_type: 'minor',
  credits_required: 9,
  courses_required: null,
  credits_counted: 3,
  remaining: 6,
  unit: 'credits',
  rule_text: 'Any other ECO courses.',
  courses: [],
  ...overrides,
});

describe('summarizeElectiveRequirements', () => {
  it('uses the backend counts and lists majors before minors', () => {
    const summaries = summarizeElectiveRequirements(
      [
        progress({ courses: [{ code: 'ECO 3011', credits: 3, completed: false }, { code: 'ECO 3000', credits: 3, completed: true }] }),
        progress({ program: 'Business Administration', program_type: 'major', remaining: 0, credits_counted: 9 }),
      ],
      [
        {
          id: 'ba-1',
          program: 'Business Administration',
          program_type: 'major',
          label: 'Non-BUS allowed electives',
          allowed_courses: ['EUR 3003', 'jmc  2020'],
        },
      ]
    );

    expect(summaries.map((s) => s.label)).toEqual(['Major: Business Administration', 'Minor: Economics']);
    const [business, economics] = summaries;
    expect(business.isComplete).toBe(true);
    expect(business.allowedCourses).toEqual(['EUR 3003', 'JMC 2020']);
    expect(business.tagPrefixes).toEqual(['bus', 'eur', 'jmc']);
    expect(business.displayTag).toBe('BUS Major Elective');
    expect(economics.counted).toBe(3);
    expect(economics.remaining).toBe(6);
    expect(economics.courses.map((c) => c.code)).toEqual(['ECO 3000', 'ECO 3011']);
    expect(economics.displayTag).toBe('ECO Minor Elective');
  });

  it('counts courses for course-based requirements', () => {
    const [summary] = summarizeElectiveRequirements(
      [progress({ unit: 'courses', credits_required: null, courses_required: 2, remaining: 1 })],
      []
    );
    expect(summary.required).toBe(2);
    expect(summary.counted).toBe(1);
  });
});

describe('describeElectiveRemaining', () => {
  it('reads naturally', () => {
    expect(describeElectiveRemaining({ remaining: 6, unit: 'credits' })).toBe('6 credits left');
    expect(describeElectiveRemaining({ remaining: 1, unit: 'courses' })).toBe('1 course left');
    expect(describeElectiveRemaining({ remaining: 0, unit: 'credits' })).toBe('Completed');
  });
});
