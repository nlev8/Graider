/**
 * Tests for ImportEventsModal.
 */
import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import ImportEventsModal from '../components/ImportEventsModal';

const baseProps = {
  open: true,
  onClose: () => {},
  selectedDoc: '',
  setSelectedDoc: () => {},
  events: [],
  setEvents: () => {},
  checked: {},
  setChecked: () => {},
  parsing: false,
  importing: false,
  supportDocs: [
    { filename: 'syllabus.pdf' },
    { filename: 'notes.docx' },
    { filename: 'image.png' }, // should be filtered out (not pdf/doc)
  ],
  onParse: () => {},
  onImport: () => {},
};

describe('ImportEventsModal', () => {
  it('renders nothing when open is false', () => {
    const { container } = render(<ImportEventsModal {...baseProps} open={false} />);
    expect(container.firstChild).toBeNull();
  });

  it('renders header and the doc dropdown', () => {
    render(<ImportEventsModal {...baseProps} />);
    expect(screen.getByText('Import Events from Document')).toBeDefined();
    expect(screen.getByText('Select a document...')).toBeDefined();
  });

  it('only includes pdf/doc/docx files in the doc dropdown', () => {
    render(<ImportEventsModal {...baseProps} />);
    expect(screen.getByText('syllabus.pdf')).toBeDefined();
    expect(screen.getByText('notes.docx')).toBeDefined();
    expect(screen.queryByText('image.png')).toBeNull();
  });

  it('Parse button is disabled when no doc is selected', () => {
    render(<ImportEventsModal {...baseProps} selectedDoc="" />);
    expect(screen.getByText('Parse Document').disabled).toBe(true);
  });

  it('Parse button is disabled while parsing is true', () => {
    render(<ImportEventsModal {...baseProps} selectedDoc="syllabus.pdf" parsing={true} />);
    expect(screen.getByText('Parsing...').disabled).toBe(true);
  });

  it('Parse button calls onParse when clicked', () => {
    const onParse = vi.fn();
    render(<ImportEventsModal {...baseProps} selectedDoc="syllabus.pdf" onParse={onParse} />);
    fireEvent.click(screen.getByText('Parse Document'));
    expect(onParse).toHaveBeenCalledTimes(1);
  });

  it('shows the AI extraction loader when parsing is true', () => {
    render(<ImportEventsModal {...baseProps} parsing={true} />);
    expect(screen.getByText(/AI is extracting events/)).toBeDefined();
  });

  it('renders parsed events with correct type pills', () => {
    const events = [
      { type: 'holiday', title: 'Spring Break', date: '2026-04-01' },
      { type: 'lesson', title: 'Civil War Intro', date: '2026-04-02' },
    ];
    render(<ImportEventsModal {...baseProps} events={events} checked={{ 0: true, 1: true }} />);
    expect(screen.getByText('Spring Break')).toBeDefined();
    expect(screen.getByText('Civil War Intro')).toBeDefined();
    expect(screen.getByText('2 events found')).toBeDefined();
    expect(screen.getByText('Holiday')).toBeDefined();
    expect(screen.getByText('Lesson')).toBeDefined();
  });

  it('Import button shows the count of checked events and is disabled when none checked', () => {
    const events = [
      { type: 'holiday', title: 'Spring Break', date: '2026-04-01' },
      { type: 'lesson', title: 'Civil War Intro', date: '2026-04-02' },
    ];
    const { rerender } = render(<ImportEventsModal {...baseProps} events={events} checked={{ 0: true, 1: false }} />);
    expect(screen.getByText('Import 1 Events')).toBeDefined();

    rerender(<ImportEventsModal {...baseProps} events={events} checked={{}} />);
    const btn = screen.getByText('Import 0 Events');
    expect(btn.disabled).toBe(true);
  });

  it('Import button calls onImport when clicked', () => {
    const onImport = vi.fn();
    const events = [{ type: 'lesson', title: 'x', date: 'd' }];
    render(<ImportEventsModal {...baseProps} events={events} checked={{ 0: true }} onImport={onImport} />);
    fireEvent.click(screen.getByText('Import 1 Events'));
    expect(onImport).toHaveBeenCalledTimes(1);
  });

  it('Cancel button calls onClose', () => {
    const onClose = vi.fn();
    render(<ImportEventsModal {...baseProps} onClose={onClose} />);
    fireEvent.click(screen.getByText('Cancel'));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('Select All sets all event indices to checked', () => {
    const setChecked = vi.fn();
    const events = [
      { type: 'holiday', title: 'a', date: 'd1' },
      { type: 'lesson', title: 'b', date: 'd2' },
    ];
    render(<ImportEventsModal {...baseProps} events={events} setChecked={setChecked} />);
    fireEvent.click(screen.getByText('Select All'));
    expect(setChecked).toHaveBeenCalledWith({ 0: true, 1: true });
  });

  it('Deselect All clears the checked map', () => {
    const setChecked = vi.fn();
    const events = [{ type: 'holiday', title: 'a', date: 'd' }];
    render(<ImportEventsModal {...baseProps} events={events} setChecked={setChecked} />);
    fireEvent.click(screen.getByText('Deselect All'));
    expect(setChecked).toHaveBeenCalledWith({});
  });
});
