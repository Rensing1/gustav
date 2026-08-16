# Contributing to GUSTAV

GUSTAV is a personal learning-platform project developed in public. Contributions from teachers, students, developers, designers, researchers, and self-hosters are welcome. A thoughtful observation from classroom practice can be just as valuable as a code change.

## How you can help

- Describe a pedagogical challenge or a useful classroom workflow.
- Try GUSTAV locally and report a reproducible problem.
- Question pedagogical, technical, or design decisions constructively.
- Improve clarity, accessibility, or documentation.
- Add tests or implement a clearly scoped change.

Use [GitHub Issues](https://github.com/Rensing1/gustav/issues) for bugs, ideas, and pedagogical questions. Please search briefly for an existing issue first. Larger changes should be discussed in an issue before implementation so that the goal, security boundaries, and domain terminology are clear before substantial work begins.

## Privacy and security

GUSTAV is used in an educational context, so contributions must respect particularly strict boundaries:

- Never publish real names, email addresses, identifiers, or other personal data belonging to students, teachers, or schools.
- Do not share credentials, tokens, keys, production domains, or unsanitized logs.
- Use recognizable placeholders such as `student@example.com` and `school.example` in examples.
- Do not publish exploitable details or real data when you suspect a vulnerability. Start with a general inquiry so that an appropriate confidential reporting path can be agreed upon.

## Development principles

Contributions should remain small, understandable, and reviewable. Code changes follow these principles:

1. Describe the expected behavior as a user story and with relevant Given-When-Then scenarios.
2. Write a failing automated test first.
3. For an API change, update the contract in `api/openapi.yml` before implementation.
4. Change the database schema only through a Supabase migration, applying the same security boundaries locally and in production.
5. Implement the smallest understandable solution, then refactor while the tests remain green.
6. Keep business rules independent of web frameworks and use the terms from the [glossary](docs/glossary.md) consistently.

Every new user-facing workflow requires at least one authenticated Playwright test marked with `@feature-acceptance` that covers the real interface, server, and production-like data storage.

## Language and documentation

- Code, technical identifiers, and code comments are written in English.
- User-facing interface text and German project documentation use correct German, including umlauts and ß.
- The English README and this contribution guide deliberately provide an international entry point to the project.
- Comments should explain why something is done rather than merely repeat the visible control flow.

## Verification

For a change without a new user-facing workflow, run at least:

```bash
make verify
```

A user-facing feature additionally requires:

```bash
make verify-feature
```

When Compose, Keycloak, or the proxy has changed, also run `make docker-validate`. The [Make target reference](docs/references/make_targets.md) documents further checks and their prerequisites.

## License

By contributing, you agree that your contribution will be published under the [GNU Affero General Public License v3](LICENCE.md). When adding a dependency or third-party asset, verify its license and update [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) where necessary.
