export interface RatingChecklistItem {
  rating_item: string;
  score: string;
  response_targets: string[];
  evidence_suggestions: string[];
  writing_focus: string;
  risk_points: string[];
}

export interface RatingChecklistResponse {
  items: RatingChecklistItem[];
}

export interface ClauseResponseRequest {
  clause_text: string;
  knowledge_context?: string | null;
}

export interface ClauseResponseResult {
  content: string;
}

export interface ChapterEnhancementAction {
  problem: string;
  action: string;
  evidence_needed: string;
  priority: 'high' | 'medium' | 'low';
}

export interface ChapterReverseEnhanceResponse {
  coverage_assessment: string;
  matched_points: string[];
  missing_points: string[];
  enhancement_actions: ChapterEnhancementAction[];
  summary: string;
}
