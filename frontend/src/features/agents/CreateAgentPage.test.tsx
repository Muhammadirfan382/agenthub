import { screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { renderApp } from '@/test/renderApp';

async function openForm() {
  const utils = renderApp('/agents/create');
  await screen.findByRole('heading', { level: 1, name: 'Create agent' });
  return utils;
}

const submitButton = () => screen.getByRole('button', { name: 'Create agent' });

describe('create agent form', () => {
  it('reports required fields when submitted empty', async () => {
    const { user } = await openForm();

    await user.click(submitButton());

    expect(await screen.findByRole('alert')).toHaveTextContent(/Please fix \d+ problems/);
    expect(screen.getByText('Name must be at least 3 characters.')).toBeInTheDocument();
    expect(screen.getByText('Description must be at least 20 characters.')).toBeInTheDocument();
    expect(screen.getByText('Choose a category.')).toBeInTheDocument();
    expect(screen.getByText('Add at least one tag.')).toBeInTheDocument();
    expect(screen.getByLabelText(/^Agent name/)).toHaveAttribute('aria-invalid', 'true');
  });

  it('rejects invalid values and field lengths', async () => {
    const { user } = await openForm();

    await user.type(screen.getByLabelText(/^Agent name/), 'Bad<name>');
    const version = screen.getByLabelText(/^Version/);
    await user.clear(version);
    await user.type(version, 'v1');
    const temperature = screen.getByLabelText(/^Temperature/);
    await user.clear(temperature);
    await user.type(temperature, '5');
    await user.click(submitButton());

    expect(await screen.findByText('Use letters, numbers, spaces, dots, dashes or underscores.')).toBeInTheDocument();
    expect(screen.getByText('Use semantic versioning, for example 1.0.0.')).toBeInTheDocument();
    expect(screen.getByText('Temperature must be between 0 and 2.')).toBeInTheDocument();
  });

  it('rejects an invalid configuration: a tool without its capability', async () => {
    const { user } = await openForm();

    await user.click(screen.getByRole('checkbox', { name: 'Web search' }));
    await user.click(submitButton());

    expect(await screen.findByText('"Web search" needs Web access, which is denied in Permissions.')).toBeInTheDocument();
  });

  it('creates an agent from valid input and opens its detail page', async () => {
    const { user, router } = await openForm();

    await user.type(screen.getByLabelText(/^Agent name/), 'Release Notes Writer');
    await user.type(screen.getByLabelText(/^Description/), 'Drafts release notes from merged pull requests for review.');
    await user.selectOptions(screen.getByLabelText(/^Category/), 'engineering');
    await user.type(screen.getByLabelText(/^Add tag/), 'release{Enter}');
    await user.click(submitButton());

    // The toast dismisses itself after a few seconds, so assert it first.
    expect(await screen.findByText('Release Notes Writer created')).toBeInTheDocument();
    expect(await screen.findByRole('heading', { level: 1, name: 'Release Notes Writer' })).toBeInTheDocument();
    expect(router.state.location.pathname).toMatch(/^\/agents\/agt_demo_release_notes_writer_\d+$/);
    expect(screen.getByText('Draft')).toBeInTheDocument();
  });
});
