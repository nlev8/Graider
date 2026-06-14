import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import SlideTemplatePicker from '../components/planner-tools/SlideTemplatePicker';

describe('SlideTemplatePicker', () => {
  it('renders the five Phase-1A templates by name', () => {
    render(<SlideTemplatePicker value="minimal" onChange={() => {}} />);
    for (const name of ['Editorial Bold', 'Vibrant Gradient', 'Cinematic Dark', 'Playful Organic', 'Minimal / Swiss']) {
      expect(screen.getByText(name)).toBeTruthy();
    }
  });

  it('calls onChange with the template key when clicked', () => {
    const onChange = vi.fn();
    render(<SlideTemplatePicker value="minimal" onChange={onChange} />);
    fireEvent.click(screen.getByText('Cinematic Dark'));
    expect(onChange).toHaveBeenCalledWith('cinematic');
  });
});
