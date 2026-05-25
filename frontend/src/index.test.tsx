import React from 'react';

jest.mock('react-dom/client', () => {
  const mockRender = jest.fn();
  const mockCreateRoot = jest.fn(() => ({
    render: mockRender,
  }));

  return {
    __esModule: true,
    default: {
      createRoot: mockCreateRoot,
    },
    createRoot: mockCreateRoot,
    __mockRender: mockRender,
  };
});

jest.mock('./App', () => ({
  __esModule: true,
  default: function MockApp() {
    return <div data-testid="mock-app">Mock App</div>;
  },
}));

describe('index bootstrap', () => {
  beforeEach(() => {
    document.body.innerHTML = '<div id="root"></div>';
  });

  it('wraps App with ThemeProvider before rendering', () => {
    const reactDomClient = require('react-dom/client');
    const { ThemeProvider } = require('./contexts/ThemeContext');

    require('./index');

    expect(reactDomClient.createRoot).toHaveBeenCalledTimes(1);
    expect(reactDomClient.__mockRender).toHaveBeenCalledTimes(1);

    const rootElement = reactDomClient.__mockRender.mock.calls[0][0] as React.ReactElement<{
      children?: React.ReactNode;
    }>;
    expect(rootElement.type).toBe(React.StrictMode);

    const strictChildren = React.Children.toArray(rootElement.props.children);
    expect(strictChildren).toHaveLength(1);

    const themeProviderElement = strictChildren[0] as React.ReactElement<{
      children?: React.ReactNode;
    }>;
    expect(themeProviderElement.type).toBe(ThemeProvider);

    const providerChildren = React.Children.toArray(themeProviderElement.props.children);
    expect(providerChildren).toHaveLength(1);
    expect((providerChildren[0] as React.ReactElement).type).toBe(require('./App').default);
  });
});
