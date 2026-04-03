/**
 * 素材库相关类型定义
 */

export type MaterialCategory =
  | 'business_license'
  | 'legal_person_id'
  | 'qualification_cert'
  | 'award_cert'
  | 'iso_cert'
  | 'contract_sample'
  | 'project_case'
  | 'other';

export type MaterialReviewStatus = 'pending' | 'confirmed' | 'rejected';

export interface MaterialAsset {
  id: string;
  name: string;
  category: MaterialCategory;
  description?: string;
  tags?: string[];
  review_status?: MaterialReviewStatus;
  file_type?: string;
  file_path?: string;
  thumbnail_path?: string;
  preview_path?: string;
  is_expired?: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface MaterialRequirement {
  id: string;
  project_id: string;
  name: string;
  description: string;
  category: MaterialCategory;
  requirement_text: string;
  priority: 'high' | 'medium' | 'low';
  status: 'pending' | 'matched' | 'confirmed';
  matched_material_id?: string;
  confidence?: number;
  created_at: string;
  updated_at: string;
}

export interface ChapterMaterialBinding {
  id: string;
  project_id: string;
  chapter_id: string;
  material_requirement_id?: string | null;
  material_asset_id: string;
  anchor_type?: string;
  anchor_value?: string | null;
  display_mode?: string;
  caption?: string | null;
  sort_index?: number;
  created_at?: string;
}

export interface MaterialMatchCandidate {
  material_id: string;
  material_name: string;
  score: number;
  reason: string;
  matched_fields: string[];
}
