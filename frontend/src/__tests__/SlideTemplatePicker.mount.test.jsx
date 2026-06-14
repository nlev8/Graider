import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import SlideTemplatePicker from '../components/planner-tools/SlideTemplatePicker';

describe('SlideTemplatePicker', () => {
  it('renders all four templates and marks the selected one', () => {
    render(<SlideTemplatePicker value="academic" onChange={() => {}} />);
    expect(screen.getByText('Editorial')).toBeTruthy();
    expect(screen.getByText('Bold')).toBeTruthy();
    expect(screen.getByText('Academic')).toBeTruthy();
    expect(screen.getByText('Playful')).toBeTruthy();
  });

  it('calls onChange with the template key when clicked', () => {
    const onChange = vi.fn();
    render(<SlideTemplatePicker value="academic" onChange={onChange} />);
    fireEvent.click(screen.getByText('Bold'));
    expect(onChange).toHaveBeenCalledWith('bold');
  });
});
