import type { ReactNode } from 'react';
import { useOutletContext } from 'react-router-dom';

export interface LayoutHeaderConfig {
  content: ReactNode;
  subContent?: ReactNode;
}

export interface LayoutHeaderOutletContext {
  setLayoutHeader: (config: LayoutHeaderConfig | null) => void;
}

export const useLayoutHeader = () => useOutletContext<LayoutHeaderOutletContext>();
