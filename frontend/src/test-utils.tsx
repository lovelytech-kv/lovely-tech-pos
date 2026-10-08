import * as rtl from '@testing-library/react';
import React from 'react';

export function render(ui: React.ReactElement, options?: Parameters<typeof rtl.render>[1]) {
  return rtl.render(ui, options);
}

export { screen, fireEvent, cleanup, act, within, getByText, getByRole, getByPlaceholderText, queryByText } from '@testing-library/react';