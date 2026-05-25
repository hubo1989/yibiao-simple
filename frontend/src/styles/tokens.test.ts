import fs from 'fs';
import path from 'path';

const tokensCss = fs.readFileSync(path.resolve(__dirname, './tokens.css'), 'utf8');

describe('tokens.css theme contract', () => {
  it('uses the new blue primary palette', () => {
    expect(tokensCss).toContain('--accent: #09A4FA;');
    expect(tokensCss).toContain('--accent-light: #0ea5e9;');
    expect(tokensCss).toContain('--accent-dark: #0284c7;');
    expect(tokensCss).toContain('--accent-grad: linear-gradient(135deg, #09A4FA 0%, #0ea5e9 100%);');
  });

  it('defines both dark and light theme scopes', () => {
    expect(tokensCss).toContain('[data-theme="dark"]');
    expect(tokensCss).toContain('[data-theme="light"]');
  });

  it('provides a readable light theme surface and text palette', () => {
    expect(tokensCss).toContain('--bg-primary: #ffffff;');
    expect(tokensCss).toContain('--bg-surface: #f8fafc;');
    expect(tokensCss).toContain('--text-primary: #1f2937;');
    expect(tokensCss).toContain('--text-secondary: #4b5563;');
  });
});
