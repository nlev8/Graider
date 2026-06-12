import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import AutomationBuilder from '../components/AutomationBuilder';

// Content-asserting mount test for AutomationBuilder. Added with the CQ wave-6
// split of AutomationBuilder.jsx into automation-builder/* (mirrors
// SettingsAI.mount.test.jsx from wave 5, for the same reason): a no-crash
// smoke passes even if the split leaves an unimported view component or a
// mis-threaded prop that blanks a whole view at runtime. This test drives the
// shell through all three extracted views (list → edit → run) and asserts
// real content from each actually mounts.

vi.mock('../services/api', () => ({
  listAutomations: vi.fn(async () => ({
    workflows: [{ id: 'wf1', name: 'Sync Gradebook', description: 'Pushes grades nightly', step_count: 3 }],
  })),
  listAutomationTemplates: vi.fn(async () => ({
    templates: [{ id: 'tpl1', name: 'Portal Login', description: 'Logs into the portal', step_count: 2 }],
  })),
  runAutomation: vi.fn(async () => ({ status: 'started' })),
  getAutomationRunStatus: vi.fn(async () => ({ status: 'running', message: 'Working', current_step: 1, total_steps: 3, log: [] })),
  getAutomation: vi.fn(async () => ({})),
  getTemplate: vi.fn(async () => ({})),
  saveAutomation: vi.fn(async () => ({})),
  deleteAutomation: vi.fn(async () => ({})),
  deleteTemplate: vi.fn(async () => ({})),
  stopAutomationRun: vi.fn(async () => ({})),
  startElementPicker: vi.fn(async () => ({})),
  getPickerEvents: vi.fn(async () => ({ events: [], status: 'idle' })),
  stopElementPicker: vi.fn(async () => ({})),
}));

describe('AutomationBuilder mounts with content from every extracted view', () => {
  it('renders the list view with workflows and templates (AutomationListView)', async () => {
    render(<AutomationBuilder addToast={vi.fn()} />);

    // Toolbar — header + New Automation button
    expect(screen.getByText('Automations')).toBeTruthy();
    expect(screen.getByText('New Automation')).toBeTruthy();
    // Workflow card (async — appears after loadList resolves)
    expect(await screen.findByText('Sync Gradebook')).toBeTruthy();
    expect(screen.getByText('Pushes grades nightly')).toBeTruthy();
    expect(screen.getByText('3 steps')).toBeTruthy();
    expect(screen.getByText('Run')).toBeTruthy();
    // Template card
    expect(screen.getByText('Templates')).toBeTruthy();
    expect(screen.getByText('Portal Login')).toBeTruthy();
    expect(screen.getByText('Template - 2 steps')).toBeTruthy();
  });

  it('renders the edit view and step config panel (AutomationEditView)', async () => {
    render(<AutomationBuilder addToast={vi.fn()} />);
    await screen.findByText('Sync Gradebook');

    fireEvent.click(screen.getByText('New Automation'));

    // Editor header — name input, picker controls, Save (no Run: unsaved)
    expect(screen.getByPlaceholderText('Automation name...')).toBeTruthy();
    expect(screen.getByText('Element Picker')).toBeTruthy();
    expect(screen.getByText('Auto-login')).toBeTruthy();
    expect(screen.getByText('Save')).toBeTruthy();
    // Step list panel — count header, add-step dropdown, empty config message
    expect(screen.getByText('Steps (0)')).toBeTruthy();
    expect(screen.getByText('+ Add Step...')).toBeTruthy();
    expect(screen.getByText('Select a step or add a new one to configure it.')).toBeTruthy();

    // Add a step via the dropdown → config panel renders type-specific fields
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'navigate' } });
    expect(screen.getByText('Steps (1)')).toBeTruthy();
    expect(screen.getByText('Step 1: Navigate')).toBeTruthy();
    expect(screen.getByText('Go to a URL')).toBeTruthy();
    expect(screen.getByText('Label')).toBeTruthy();
    expect(screen.getByText('URL')).toBeTruthy();
    expect(screen.getByPlaceholderText('https://example.com')).toBeTruthy();
  });

  it('renders the run view after starting a workflow (AutomationRunView)', async () => {
    render(<AutomationBuilder addToast={vi.fn()} />);
    await screen.findByText('Sync Gradebook');

    fireEvent.click(screen.getByText('Run'));

    // Run header + stop/back controls + empty log placeholder
    expect(await screen.findByText('Running Automation')).toBeTruthy();
    expect(screen.getByText('Stop')).toBeTruthy();
    expect(screen.getByText('Back')).toBeTruthy();
    expect(screen.getByText('Waiting for output...')).toBeTruthy();
  });
});
