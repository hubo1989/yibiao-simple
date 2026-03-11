import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import ConfigPanel from './ConfigPanel';
import { configApi } from '../services/api';

jest.mock('../services/api', () => ({
  configApi: {
    getModels: jest.fn(),
  },
}));

const mockedConfigApi = configApi as jest.Mocked<typeof configApi>;

describe('ConfigPanel', () => {
  beforeEach(() => {
    localStorage.clear();
    jest.clearAllMocks();
  });

  it('switches provider and refreshes model options', async () => {
    mockedConfigApi.getModels.mockResolvedValue({
      data: {
        success: true,
        message: '获取成功',
        default_provider_config_id: 'provider-zhipu',
        providers: [
          {
            config_id: 'provider-zhipu',
            provider: '智谱',
            models: ['glm-4.5', 'glm-4-air'],
            default_model: 'glm-4.5',
            is_default: true,
          },
          {
            config_id: 'provider-openai',
            provider: 'OpenAI',
            models: ['gpt-4.1', 'gpt-4o'],
            default_model: 'gpt-4.1',
            is_default: false,
          },
        ],
      },
    } as any);

    render(<ConfigPanel />);

    fireEvent.click(screen.getByRole('button', { name: '重新获取模型列表' }));

    await waitFor(() => {
      expect(screen.getByLabelText('当前 Provider')).toBeInTheDocument();
    });

    const providerSelect = screen.getByLabelText('当前 Provider') as HTMLSelectElement;
    const modelSelect = screen.getByLabelText('当前默认模型') as HTMLSelectElement;

    expect(providerSelect.value).toBe('provider-zhipu');
    expect(modelSelect.value).toBe('glm-4.5');

    fireEvent.change(providerSelect, { target: { value: 'provider-openai' } });

    await waitFor(() => {
      expect(modelSelect.value).toBe('gpt-4.1');
    });

    const cache = JSON.parse(localStorage.getItem('yibiao:model_cache') || '{}');
    expect(cache.currentProviderId).toBe('provider-openai');
    expect(cache.currentModel).toBe('gpt-4.1');
  });

  it('falls back to a default provider when backend only returns legacy models', async () => {
    mockedConfigApi.getModels.mockResolvedValue({
      data: {
        success: true,
        message: '获取到 16 个模型',
        models: ['gpt-5', 'gpt-5-mini'],
        providers: [],
      },
    } as any);

    render(<ConfigPanel />);

    fireEvent.click(screen.getByRole('button', { name: '重新获取模型列表' }));

    await waitFor(() => {
      expect(screen.getByLabelText('当前 Provider')).toBeInTheDocument();
    });

    const providerSelect = screen.getByLabelText('当前 Provider') as HTMLSelectElement;
    const modelSelect = screen.getByLabelText('当前默认模型') as HTMLSelectElement;

    expect(providerSelect.value).toBe('');
    expect(providerSelect.options[0].text).toContain('默认配置');
    expect(modelSelect.value).toBe('gpt-5');
    expect(screen.getByText('获取到 1 个 Provider')).toBeInTheDocument();
  });
});
