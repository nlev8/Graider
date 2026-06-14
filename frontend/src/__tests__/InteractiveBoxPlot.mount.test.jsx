import { render, screen } from '@testing-library/react';
import { describe, test, expect } from 'vitest';
import InteractiveBoxPlot from '../components/InteractiveBoxPlot.jsx';

describe('InteractiveBoxPlot', () => {
  const defaultData = [[50, 55, 60, 65, 70, 75, 80, 85, 90]];
  const defaultLabels = ['Data Set'];

  test('renders the SVG canvas', () => {
    const { container } = render(
      <InteractiveBoxPlot data={defaultData} labels={defaultLabels} />
    );
    const svg = container.querySelector('svg');
    expect(svg).toBeTruthy();
  });

  test('renders the dataset label inside the SVG', () => {
    const { container } = render(
      <InteractiveBoxPlot data={defaultData} labels={['Test Set']} />
    );
    const svg = container.querySelector('svg');
    expect(svg.textContent).toContain('Test Set');
  });

  test('renders answer input fields for all five-number summary keys', () => {
    render(
      <InteractiveBoxPlot data={defaultData} labels={defaultLabels} />
    );
    // 7 number inputs: min, q1, median, q3, max, range, iqr
    const inputs = screen.getAllByRole('spinbutton');
    expect(inputs).toHaveLength(7);
  });

  test('renders hint text when not readOnly', () => {
    render(
      <InteractiveBoxPlot data={defaultData} labels={defaultLabels} readOnly={false} />
    );
    expect(screen.getByText(/five-number summary/i)).toBeTruthy();
  });

  test('does not render hint when readOnly', () => {
    render(
      <InteractiveBoxPlot data={defaultData} labels={defaultLabels} readOnly={true} />
    );
    expect(screen.queryByText(/five-number summary/i)).toBeNull();
  });

  test('renders legend items in SVG', () => {
    const { container } = render(
      <InteractiveBoxPlot data={defaultData} labels={defaultLabels} />
    );
    const svg = container.querySelector('svg');
    // Legend contains Min, Q1, Med, Q3, Max
    expect(svg.textContent).toContain('Min');
    expect(svg.textContent).toContain('Q1');
    expect(svg.textContent).toContain('Med');
  });

  test('inputs are disabled in readOnly mode', () => {
    render(
      <InteractiveBoxPlot data={defaultData} labels={defaultLabels} readOnly={true} />
    );
    const inputs = screen.getAllByRole('spinbutton');
    inputs.forEach(input => {
      expect(input.disabled).toBe(true);
    });
  });

  test('renders multiple datasets', () => {
    const multiData = [
      [50, 60, 70, 80, 90],
      [40, 55, 65, 75, 85],
    ];
    const { container } = render(
      <InteractiveBoxPlot
        data={multiData}
        labels={['Set A', 'Set B']}
      />
    );
    const svg = container.querySelector('svg');
    expect(svg.textContent).toContain('Set A');
    expect(svg.textContent).toContain('Set B');
  });
});
