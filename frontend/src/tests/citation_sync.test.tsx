/**
 * The hero interaction contract: clicking citation chip [n] locates the
 * CORRECT timeline signal — scrolled to and highlighted — not just "a" signal.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import VendorDetail from '@/pages/VendorDetail';
import { useUiStore } from '@/lib/store';

const HIGHLIGHT = 'bg-tint-blue-panel';
const scrollTo = vi.fn();

beforeEach(() => {
  cleanup();
  // jsdom has no scrolling; the assertion is that the timeline box is asked to scroll
  Element.prototype.scrollTo = scrollTo as unknown as Element['scrollTo'];
  scrollTo.mockClear();
  useUiStore.setState({ activeSignal: 0 });
});

function renderVendorDetail() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={['/vendor/aldermere']}>
        <Routes>
          <Route path="/vendor/:id" element={<VendorDetail />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

/** The timeline entry element wrapping a signal title. */
const entryOf = (title: string) => screen.getByText(title).closest('.border-line-row') as HTMLElement;

describe('citation chip ↔ timeline sync', () => {
  it('clicking chip [7] scrolls to and highlights the CCJ signal — and only it', async () => {
    renderVendorDetail();
    await screen.findByText('County court judgment vs subsidiary');

    fireEvent.click(screen.getAllByRole('button', { name: '[7]' })[0]);

    const target = entryOf('County court judgment vs subsidiary');
    expect(target.className).toContain(HIGHLIGHT);
    // the wrong signals are NOT highlighted
    expect(entryOf('Engineering postings down 63% q/q').className).not.toContain(HIGHLIGHT);
    expect(entryOf('CFO departure announced').className).not.toContain(HIGHLIGHT);
    // the timeline container was asked to scroll the entry into view
    expect(scrollTo).toHaveBeenCalled();
  });

  it('clicking chip [3] moves the highlight to the job-postings signal', async () => {
    renderVendorDetail();
    await screen.findByText('Engineering postings down 63% q/q');

    fireEvent.click(screen.getAllByRole('button', { name: '[3]' })[0]);

    expect(entryOf('Engineering postings down 63% q/q').className).toContain(HIGHLIGHT);
    expect(entryOf('County court judgment vs subsidiary').className).not.toContain(HIGHLIGHT);
  });

  it('clicking a timeline entry activates the matching narrative chip (bidirectional)', async () => {
    renderVendorDetail();
    await screen.findByText('CFO departure announced');

    fireEvent.click(entryOf('CFO departure announced'));

    const chip2 = screen.getAllByRole('button', { name: '[2]' })[0];
    expect(chip2.className).toContain('bg-tint-blue-active');
  });
});
