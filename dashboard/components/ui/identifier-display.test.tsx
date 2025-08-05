import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { IdentifierDisplay, IdentifierItem } from './identifier-display';

// Mock the toast utility
jest.mock('sonner', () => ({
  toast: {
    success: jest.fn(),
    error: jest.fn()
  }
}));

// Mock clipboard API
const mockClipboard = {
  writeText: jest.fn()
};
Object.assign(navigator, {
  clipboard: mockClipboard
});

describe('IdentifierDisplay', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockClipboard.writeText.mockResolvedValue(undefined);
  });

  describe('single identifier display', () => {
    it('should display a single identifier without expand button', () => {
      const identifiers: IdentifierItem[] = [
        { name: 'Form ID', value: 'FORM-123' }
      ];

      render(<IdentifierDisplay identifiers={identifiers} />);
      
      expect(screen.getByText('Form ID:')).toBeInTheDocument();
      expect(screen.getByText('FORM-123')).toBeInTheDocument();
      expect(screen.queryByLabelText(/expand|collapse/i)).not.toBeInTheDocument();
    });

    it('should truncate long values', () => {
      const identifiers: IdentifierItem[] = [
        { name: 'Long ID', value: 'VERY-LONG-IDENTIFIER-THAT-EXCEEDS-25-CHARACTERS' }
      ];

      render(<IdentifierDisplay identifiers={identifiers} />);
      
      expect(screen.getByText('VERY-LONG-IDENTIFIER-THAT...')).toBeInTheDocument();
    });

    it('should display clickable URL when provided', () => {
      const identifiers: IdentifierItem[] = [
        { name: 'Report ID', value: 'RPT-789', url: '/reports/789' }
      ];

      render(<IdentifierDisplay identifiers={identifiers} />);
      
      const link = screen.getByRole('link', { name: 'RPT-789' });
      expect(link).toHaveAttribute('href', '/reports/789');
      expect(link).toHaveAttribute('target', '_blank');
      expect(link).toHaveAttribute('rel', 'noopener noreferrer');
    });
  });

  describe('multiple identifiers display', () => {
    const multipleIdentifiers: IdentifierItem[] = [
      { name: 'Form ID', value: 'FORM-123' },
      { name: 'Session ID', value: 'SESS-456' },
      { name: 'Report ID', value: 'RPT-789', url: '/reports/789' }
    ];

    it('should show first identifier and expand button', () => {
      render(<IdentifierDisplay identifiers={multipleIdentifiers} />);
      
      // Should show first identifier
      expect(screen.getByText('Form ID:')).toBeInTheDocument();
      expect(screen.getByText('FORM-123')).toBeInTheDocument();
      
      // Should show expand button
      expect(screen.getByLabelText('Expand identifiers')).toBeInTheDocument();
      
      // Should not show other identifiers initially
      expect(screen.queryByText('Session ID:')).not.toBeInTheDocument();
      expect(screen.queryByText('Report ID:')).not.toBeInTheDocument();
    });

    it('should expand to show all identifiers when clicked', () => {
      render(<IdentifierDisplay identifiers={multipleIdentifiers} />);
      
      // Click expand button
      fireEvent.click(screen.getByLabelText('Expand identifiers'));
      
      // Should show all identifiers
      expect(screen.getByText('Form ID:')).toBeInTheDocument();
      expect(screen.getByText('FORM-123')).toBeInTheDocument();
      expect(screen.getByText('Session ID:')).toBeInTheDocument();
      expect(screen.getByText('SESS-456')).toBeInTheDocument();
      expect(screen.getByText('Report ID:')).toBeInTheDocument();
      expect(screen.getByRole('link', { name: 'RPT-789' })).toBeInTheDocument();
      
      // Should show collapse button
      expect(screen.getByLabelText('Collapse identifiers')).toBeInTheDocument();
    });

    it('should collapse when clicking collapse button', () => {
      render(<IdentifierDisplay identifiers={multipleIdentifiers} />);
      
      // Expand first
      fireEvent.click(screen.getByLabelText('Expand identifiers'));
      expect(screen.getByText('Session ID:')).toBeInTheDocument();
      
      // Then collapse
      fireEvent.click(screen.getByLabelText('Collapse identifiers'));
      expect(screen.queryByText('Session ID:')).not.toBeInTheDocument();
      expect(screen.getByLabelText('Expand identifiers')).toBeInTheDocument();
    });
  });

  describe('copy functionality', () => {
    it('should copy identifier value to clipboard', async () => {
      const identifiers: IdentifierItem[] = [
        { name: 'Form ID', value: 'FORM-123' }
      ];

      render(<IdentifierDisplay identifiers={identifiers} />);
      
      const copyButton = screen.getByTitle('Copy Form ID');
      fireEvent.click(copyButton);
      
      expect(mockClipboard.writeText).toHaveBeenCalledWith('FORM-123');
    });

    it('should show success toast after successful copy', async () => {
      const { toast } = require('sonner');
      const identifiers: IdentifierItem[] = [
        { name: 'Session ID', value: 'SESS-456' }
      ];

      render(<IdentifierDisplay identifiers={identifiers} />);
      
      const copyButton = screen.getByTitle('Copy Session ID');
      fireEvent.click(copyButton);
      
      await waitFor(() => {
        expect(toast.success).toHaveBeenCalledWith('Copied Session ID to clipboard');
      });
    });

    it('should handle clipboard errors gracefully', async () => {
      const { toast } = require('sonner');
      mockClipboard.writeText.mockRejectedValue(new Error('Clipboard error'));
      
      const identifiers: IdentifierItem[] = [
        { name: 'Error ID', value: 'ERR-123' }
      ];

      render(<IdentifierDisplay identifiers={identifiers} />);
      
      const copyButton = screen.getByTitle('Copy Error ID');
      fireEvent.click(copyButton);
      
      await waitFor(() => {
        expect(toast.error).toHaveBeenCalledWith('Failed to copy to clipboard');
      });
    });
  });

  describe('external ID fallback', () => {
    it('should display external ID when no identifiers provided', () => {
      render(<IdentifierDisplay externalId="EXT-789" />);
      
      expect(screen.getByText('EXT-789')).toBeInTheDocument();
    });

    it('should prefer identifiers over external ID', () => {
      const identifiers: IdentifierItem[] = [
        { name: 'Priority ID', value: 'PRI-123' }
      ];

      render(<IdentifierDisplay identifiers={identifiers} externalId="EXT-789" />);
      
      expect(screen.getByText('Priority ID:')).toBeInTheDocument();
      expect(screen.getByText('PRI-123')).toBeInTheDocument();
      expect(screen.queryByText('EXT-789')).not.toBeInTheDocument();
    });

    it('should copy external ID to clipboard', async () => {
      render(<IdentifierDisplay externalId="EXT-456" />);
      
      const copyButton = screen.getByTitle('Copy External ID');
      fireEvent.click(copyButton);
      
      expect(mockClipboard.writeText).toHaveBeenCalledWith('EXT-456');
    });
  });

  describe('compact mode', () => {
    it('should not show copy buttons in compact mode', () => {
      const identifiers: IdentifierItem[] = [
        { name: 'Form ID', value: 'FORM-123' }
      ];

      render(<IdentifierDisplay identifiers={identifiers} displayMode="compact" />);
      
      // In compact mode, only the value is shown, not the label
      expect(screen.getByText('FORM-123')).toBeInTheDocument();
      expect(screen.queryByTitle('Copy Form ID')).not.toBeInTheDocument();
    });

    it('should not show copy button for external ID in compact mode', () => {
      render(<IdentifierDisplay externalId="EXT-123" displayMode="compact" />);
      
      expect(screen.getByText('EXT-123')).toBeInTheDocument();
      expect(screen.queryByTitle('Copy External ID')).not.toBeInTheDocument();
    });
  });

  describe('skeleton mode', () => {
    it('should show loading skeleton', () => {
      const { container } = render(<IdentifierDisplay skeletonMode={true} />);
      
      // Should have exactly 2 skeleton elements with animate-pulse (icon and text)
      const skeletons = container.querySelectorAll('.animate-pulse');
      expect(skeletons).toHaveLength(2);
      
      // Check that both skeleton elements are present
      expect(skeletons[0]).toBeInTheDocument();
      expect(skeletons[1]).toBeInTheDocument();
    });
  });

  describe('edge cases', () => {
    it('should return null when no identifiers or external ID provided', () => {
      const { container } = render(<IdentifierDisplay />);
      
      expect(container.firstChild).toBeNull();
    });

    it('should handle empty identifiers array', () => {
      render(<IdentifierDisplay identifiers={[]} externalId="EXT-123" />);
      
      expect(screen.getByText('EXT-123')).toBeInTheDocument();
    });

    it('should handle JSON string identifiers (legacy support)', () => {
      const legacyIdentifiers = JSON.stringify([
        { name: 'Legacy ID', id: 'LEG-123' },
        { name: 'Old ID', id: 'OLD-456', url: '/old/456' }
      ]);

      render(<IdentifierDisplay identifiers={legacyIdentifiers} />);
      
      expect(screen.getByText('Legacy ID:')).toBeInTheDocument();
      expect(screen.getByText('LEG-123')).toBeInTheDocument();
      expect(screen.getByLabelText('Expand identifiers')).toBeInTheDocument();
    });

    it('should handle malformed JSON string gracefully', () => {
      const malformedJson = '{ invalid json ';

      // Suppress console.error for this test
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation(() => {});

      render(<IdentifierDisplay identifiers={malformedJson} externalId="EXT-FALLBACK" />);
      
      expect(screen.getByText('EXT-FALLBACK')).toBeInTheDocument();
      
      // Restore console.error
      consoleSpy.mockRestore();
    });
  });
});