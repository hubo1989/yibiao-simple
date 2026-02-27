/**
 * 应用状态管理Hook
 */
import { useState, useCallback, useEffect } from 'react';
import { AppState, ConfigData, OutlineData } from '../types';
import { draftStorage } from '../utils/draftStorage';

const initialState: AppState = {
  currentStep: 0,
  config: {
    model_name: 'gpt-3.5-turbo',
  },
  fileContent: '',
  projectOverview: '',
  techRequirements: '',
  outlineData: null,
  selectedChapter: '',
};

export const useAppState = (projectId?: string) => {
  // 设置项目ID，确保草稿按项目隔离
  useEffect(() => {
    draftStorage.setProjectId(projectId || null);
  }, [projectId]);

  const [state, setState] = useState<AppState>(() => {
    // 初始化时设置项目ID
    if (projectId) {
      draftStorage.setProjectId(projectId);
    }
    const draft = draftStorage.loadDraft();
    return {
      ...initialState,
      ...(draft || {}),
    };
  });

  const updateConfig = useCallback((config: ConfigData) => {
    setState(prev => ({ ...prev, config }));
  }, []);

  const updateStep = useCallback((step: number) => {
    setState(prev => {
      const next = { ...prev, currentStep: step };
      draftStorage.saveDraft({ currentStep: step });
      return next;
    });
  }, []);

  const updateFileContent = useCallback((fileContent: string) => {
    setState(prev => {
      const next = { ...prev, fileContent };
      draftStorage.saveDraft({ fileContent });
      return next;
    });
  }, []);

  const updateAnalysisResults = useCallback((overview: string, requirements: string) => {
    setState(prev => {
      const next = {
        ...prev,
        projectOverview: overview,
        techRequirements: requirements,
      };
      draftStorage.saveDraft({
        projectOverview: overview,
        techRequirements: requirements,
      });
      return next;
    });
  }, []);

  const updateOutline = useCallback((outlineData: OutlineData) => {
    setState(prev => {
      const next = { ...prev, outlineData };
      draftStorage.saveDraft({ outlineData });
      return next;
    });
  }, []);

  const updateSelectedChapter = useCallback((chapterId: string) => {
    setState(prev => {
      const next = { ...prev, selectedChapter: chapterId };
      draftStorage.saveDraft({ selectedChapter: chapterId });
      return next;
    });
  }, []);

  const nextStep = useCallback(() => {
    setState(prev => {
      const nextStepValue = Math.min(prev.currentStep + 1, 2);
      const next = { ...prev, currentStep: nextStepValue };
      draftStorage.saveDraft({ currentStep: nextStepValue });
      return next;
    });
  }, []);

  const prevStep = useCallback(() => {
    setState(prev => {
      const prevStepValue = Math.max(prev.currentStep - 1, 0);
      const next = { ...prev, currentStep: prevStepValue };
      draftStorage.saveDraft({ currentStep: prevStepValue });
      return next;
    });
  }, []);

  return {
    state,
    updateConfig,
    updateStep,
    updateFileContent,
    updateAnalysisResults,
    updateOutline,
    updateSelectedChapter,
    nextStep,
    prevStep,
  };
};