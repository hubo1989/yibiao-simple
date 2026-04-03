import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { TextEncoder } from 'util';
import DocumentAnalysis from './DocumentAnalysis';
import { documentApi } from '../services/api';

jest.mock('../contexts/AuthContext', () => ({
  useAuth: () => ({ token: 'test-token' }),
}));

jest.mock('../utils/modelCache', () => ({
  getCurrentModel: () => 'gpt-test-model',
  getCurrentProviderConfigId: () => 'provider-test',
}));

jest.mock('../services/api', () => ({
  documentApi: {
    uploadFile: jest.fn(),
    uploadToProject: jest.fn(),
    analyzeProjectStream: jest.fn(),
  },
}));

jest.mock('@ant-design/pro-components', () => ({
  ProCard: ({ title, children }: { title?: React.ReactNode; children: React.ReactNode }) => (
    <section>
      {title ? <h2>{title}</h2> : null}
      {children}
    </section>
  ),
}));

jest.mock('react-markdown', () => ({
  __esModule: true,
  default: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

jest.mock('antd', () => {
  return {
    Button: ({ children, onClick, disabled }: any) => (
      <button onClick={onClick} disabled={disabled}>
        {children}
      </button>
    ),
    Typography: {
      Text: ({ children }: any) => <span>{children}</span>,
      Title: ({ children }: any) => <h1>{children}</h1>,
    },
    Space: ({ children }: any) => <div>{children}</div>,
    Alert: ({ message: alertMessage }: any) => <div>{alertMessage}</div>,
    Row: ({ children }: any) => <div>{children}</div>,
    Col: ({ children }: any) => <div>{children}</div>,
    Card: ({ children }: any) => <div>{children}</div>,
    message: {
      success: jest.fn(),
      error: jest.fn(),
      info: jest.fn(),
      warning: jest.fn(),
    },
  };
});

const mockedDocumentApi = documentApi as jest.Mocked<typeof documentApi>;

const createStreamResponse = (chunks: string[]): Response => {
  const encoder = new TextEncoder();
  let index = 0;

  return {
    ok: true,
    status: 200,
    body: {
      getReader: () => ({
        read: async () => {
          if (index >= chunks.length) {
            return { done: true, value: undefined };
          }

          const value = encoder.encode(chunks[index]);
          index += 1;
          return { done: false, value };
        },
      }),
    },
  } as Response;
};

const renderDocumentAnalysis = (props?: Partial<React.ComponentProps<typeof DocumentAnalysis>>) => {
  const onFileUpload = jest.fn();
  const onAnalysisComplete = jest.fn();

  const utils = render(
    <DocumentAnalysis
      fileContent="uploaded file content"
      projectOverview=""
      techRequirements=""
      onFileUpload={onFileUpload}
      onAnalysisComplete={onAnalysisComplete}
      projectId="project-123"
      {...props}
    />
  );

  return {
    ...utils,
    onFileUpload,
    onAnalysisComplete,
  };
};

const uploadTenderFile = async (container: HTMLElement, fileName = 'tender.docx') => {
  const fileInput = container.querySelector('input[type="file"]') as HTMLInputElement;
  const file = new File(['demo'], fileName, {
    type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  });

  fireEvent.change(fileInput, { target: { files: [file] } });

  await waitFor(() => {
    expect(mockedDocumentApi.uploadFile).toHaveBeenCalledWith(file);
  });

  return file;
};

describe('DocumentAnalysis', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockedDocumentApi.uploadFile.mockResolvedValue({
      data: {
        success: true,
        message: '上传成功',
        file_content: 'new uploaded content',
      },
    } as any);
    mockedDocumentApi.uploadToProject.mockResolvedValue({ ok: true } as any);
  });

  it('buffers incomplete SSE frames before appending streamed analysis', async () => {
    mockedDocumentApi.analyzeProjectStream
      .mockResolvedValueOnce(
        createStreamResponse([
          'data: {"chunk":"项目',
          '概述"}\n\n',
          'data: [DONE]\n\n',
        ]) as any
      )
      .mockResolvedValueOnce(
        createStreamResponse([
          'data: {"chunk":"技术要求"}\n\n',
          'data: [DONE]\n\n',
        ]) as any
      );

    const { container, onAnalysisComplete } = renderDocumentAnalysis();

    await uploadTenderFile(container);

    fireEvent.click(screen.getByRole('button', { name: /解析标书/i }));

    await waitFor(() => {
      expect(onAnalysisComplete).toHaveBeenCalledWith('项目概述', '技术要求');
    });

    expect(screen.getAllByText('项目概述')).not.toHaveLength(0);
    expect(screen.getByText('技术要求')).toBeInTheDocument();
  });

  it('clears previous analysis state after uploading a new tender file', async () => {
    const { container, onAnalysisComplete } = renderDocumentAnalysis({
      projectOverview: '旧项目概述',
      techRequirements: '旧技术要求',
    });

    expect(screen.getByText('旧项目概述')).toBeInTheDocument();
    expect(screen.getByText('旧技术要求')).toBeInTheDocument();

    await uploadTenderFile(container, 'replacement.docx');

    await waitFor(() => {
      expect(onAnalysisComplete).toHaveBeenCalledWith('', '');
    });

    expect(screen.queryByText('旧项目概述')).not.toBeInTheDocument();
    expect(screen.queryByText('旧技术要求')).not.toBeInTheDocument();
    expect(screen.getByText('项目概述将在这里显示...')).toBeInTheDocument();
    expect(screen.getByText('技术评分要求将在这里显示...')).toBeInTheDocument();
  });
});
