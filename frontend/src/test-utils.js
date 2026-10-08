import * as rtl from '@testing-library/react';
export function render(ui, options) {
    return rtl.render(ui, options);
}
export { screen, fireEvent, cleanup, act, within, getByText, getByRole, getByPlaceholderText, queryByText } from '@testing-library/react';
