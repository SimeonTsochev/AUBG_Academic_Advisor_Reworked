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
  isRetake?: boolean;
  prereqWarning?: {
    unmet: string[];
  };
}

export interface ManualCreditEntry {
  code: "OTH 0001";
  instance_id: string;
  term: string;
  credits: number;
  credit_type: "GENED" | "MAJOR_ELECTIVE" | "FREE_ELECTIVE";
  gened_category?: string;
  program?: string;
  note?: string;
}

export interface RetakeEntry {
  instance_id: string;
  code: string;
  term: string;
  status: "PLANNED" | "IN_PROGRESS" | "COMPLETED";
  label: "Retake";
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
