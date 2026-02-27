export interface Course {
  instanceId: string;
  code: string;
  name: string;
  credits: number;
  tags: string[];
  semester: string;
  status: 'completed' | 'in-progress' | 'remaining';
  prerequisites?: string[];
  prereqText?: string | null;
  reason?: string;
  satisfies?: string[];
  electiveNotes?: string[];
  courseType?: 'PROGRAM' | 'GENED' | 'FREE' | 'FOUNDATION' | 'FREE_ELECTIVE';
  sourceReason?: string;
  prereqWarning?: {
    unmet: string[];
  };
}

export interface Major {
  id: string;
  name: string;
}

export interface Minor {
  id: string;
  name: string;
}

export interface Progress {
  category: string;
  completed: number;
  total: number;
}

export interface ChatMessage {
  role: 'assistant' | 'user';
  content: string;
  timestamp: Date;
}

export interface ElectiveSuggestion {
  code: string;
  name: string;
  credits: number;
  requirementsSatisfied: number;
  tags: string[];
  explanation: string;
}

export interface GenEdDiscoveryCourse {
  code: string;
  name: string;
  credits: number;
  tags: string[];
}

export interface MinorSuggestion {
  minorName: string;
  coursesNeeded: number;
  remainingCourses: string[];
  creditImpact: number;
}

export interface ElectivePlaceholder {
  id: string;
  program: string;
  program_type: 'major' | 'minor';
  label: string;
  credits_required?: number | null;
  courses_required?: number | null;
  allowed_courses?: string[];
  rule_text?: string;
  is_total?: boolean;
}
