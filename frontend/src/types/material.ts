export type MaterialScope = 'global' | 'enterprise' | 'user';

export type MaterialCategory =
  | 'business_license'
  | 'legal_person_id'
  | 'qualification_cert'
  | 'award_cert'
  | 'iso_cert'
  | 'contract_sample'
  | 'project_case'
  | 'team_photo'
  | 'equipment_photo'
  | 'financial_report'
  | 'bank_credit'
  | 'social_security'
  | 'other';

export type MaterialReviewStatus = 'pending' | 'confirmed' | 'rejected';
export type MaterialRequirementStatus = 'pending' | 'matched' | 'missing' | 'ignored' | 'confirmed';
export type BindingAnchorType = 'section_end' | 'paragraph_after' | 'paragraph_before' | 'appendix_block';
export type BindingDisplayMode = 'image' | 'attachment_note';

export interface MaterialAsset {
  id: string;
  scope: MaterialScope;
  owner_id?: string | null;
  uploaded_by?: string | null;
  category: MaterialCategory;
  name: string;
  description?: string | null;
  file_path: string;
  preview_path?: string | null;
  thumbnail_path?: string | null;
  file_type: string;
  file_ext: string;
  file_size: number;
  page_count?: number | null;
  tags: string[];
  keywords: string[];
  ai_description?: string | null;
  ai_extracted_fields: Record<string, unknown>;
  valid_from?: string | null;
  valid_until?: string | null;
  is_expired: boolean;
  is_disabled: boolean;
  review_status: MaterialReviewStatus;
  usage_count: number;
  last_used_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface MaterialRequirement {
  id: string;
  project_id: string;
  source_document_id?: string | null;
  chapter_hint?: string | null;
  section_hint?: string | null;
  requirement_name: string;
  requirement_text: string;
  category?: string | null;
  tags: string[];
  is_mandatory: boolean;
  status: MaterialRequirementStatus;
  extracted_by: string;
  sort_index: number;
  created_at: string;
  updated_at: string;
}

export interface MaterialMatchCandidate {
  asset_id: string;
  score: number;
  matched_reasons: string[];
  asset?: MaterialAsset | null;
}

export interface ChapterMaterialBinding {
  id: string;
  project_id: string;
  chapter_id: string;
  material_requirement_id?: string | null;
  material_asset_id: string;
  anchor_type: BindingAnchorType;
  anchor_value?: string | null;
  display_mode: BindingDisplayMode;
  caption?: string | null;
  sort_index: number;
  created_by?: string | null;
  created_at: string;
  updated_at: string;
  material_asset?: MaterialAsset | null;
}
