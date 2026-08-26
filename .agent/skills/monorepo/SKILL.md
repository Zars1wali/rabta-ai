---
name: monorepo
description: >
  Discipline for working inside a monorepo: workspace layout, shared-config
  hygiene, build-graph awareness, cross-package refactors, scoped commands,
  versioning strategy, and submodule integration. Load whenever the
  repository contains multiple packages, apps, or libraries under one
  version control root — pnpm/turbo workspaces, Nx, Cargo workspaces,
  Bazel, CMake supermodules, multi-crate Rust, multi-module Python.
  Builds on the `architecture` skill; does not replace it.
---

# Monorepo

> A monorepo is one repository containing many packages. The packages are
> isolated by the rules in the `architecture` skill. The monorepo
> introduces a second set of concerns on top: where things live in the
> tree, what builds together, what versions together, and how a change
> propagates through the graph.

---

## Why This Is Its Own Skill

The architectural principles (package isolation, dependency direction,
public surfaces) are identical in polyrepos and monorepos. But a
monorepo gives the agent more power and more ways to cause harm:

- A rename in one package can break dozens of consumers in the same commit.
- A change to a root config file affects every package.
- A new dependency edge can rebuild half the graph.
- A bumped version in a shared lib can ship to twenty apps at once.

A polyrepo at least forces these concerns through a release boundary.
A monorepo collapses them into a single commit. The agent must treat
that power with the matching discipline.

---

## Workspace Topology

Most monorepos follow one of these layouts. Names vary by ecosystem;
the shape is universal.

```
<repo-root>/
├── apps/            ← deployable artifacts: web apps, services, CLIs, daemons
├── packages/        ← reusable libraries consumed by apps and other packages
├── libs/            ← alias for `packages/` in some ecosystems (Nx, C++)
├── tools/           ← internal CLIs, codemods, generators, dev scripts
├── configs/         ← shared base configs (tsconfig, eslint, biome, prettier)
├── docs/            ← project documentation, ADRs
├── .github/         ← CI workflows, issue templates
├── <root manifest>  ← pnpm-workspace.yaml / Cargo.toml / WORKSPACE.bazel / CMakeLists.txt
└── <lockfile>       ← pnpm-lock.yaml / Cargo.lock / go.sum / etc.
```

Equivalents across ecosystems:

| Ecosystem | Apps | Libraries | Workspace manifest | Lockfile |
|---|---|---|---|---|
| pnpm + turbo | `apps/` | `packages/` | `pnpm-workspace.yaml` | `pnpm-lock.yaml` |
| Nx (Node) | `apps/` | `libs/` | `nx.json` + `pnpm-workspace.yaml` | `pnpm-lock.yaml` |
| Rust | `crates/<bin>` | `crates/<lib>` | root `Cargo.toml` workspace members | `Cargo.lock` |
| Bazel | `<service>/` | `<library>/` | `MODULE.bazel` / `WORKSPACE.bazel` | `MODULE.bazel.lock` |
| CMake | `<app>/` | `libs/<name>/` | root `CMakeLists.txt` with `add_subdirectory` | n/a |
| Python | `services/` | `packages/` | `pyproject.toml` workspace (uv/rye/PDM) | `uv.lock` etc. |
| Go | `cmd/<bin>/` | `internal/<lib>/`, `pkg/<lib>/` | `go.work` | `go.sum` |

The agent must know which one applies. This information lives in the
project's `codebase-map` skill.

---

## Topology Rules

These are non-negotiable in any monorepo:

1. **Apps depend on packages. Packages do not depend on apps.** An app
   is a leaf in the dependency graph. If a package needs something from
   an app, that something belongs in a package.
2. **Apps do not depend on apps.** If two apps share code, that code
   becomes a package.
3. **Packages may depend on packages, in the direction the architecture
   skill prescribes.** Domain depends on ports; infra implements ports;
   shared utilities sit at the bottom. No cycles, ever.
4. **`tools/` does not become a package consumer.** Tools are
   internal-only and may not be runtime dependencies of apps or
   packages. If shared logic emerges, extract it into a package.
5. **Root configs are extended, not forked.** Every package's `tsconfig`
   extends the root base. Every package's lint config extends the root
   base. Forking a config is a structural defect — refuse it.

---

## When to Add a Package

The default move is **not** to add a package. The default move is to
put the code where similar code already lives.

Add a new package when:

- A second consumer needs the same code (the rule of three from the
  `change-discipline` skill applies — but two real consumers can be
  enough for shared types or constants).
- The code has a clear, nameable responsibility distinct from any
  existing package.
- The dependency direction is sound: the new package sits at or below
  the layer of every intended consumer.
- The build-graph cost is justified: adding it does not turn a one-app
  rebuild into a many-app rebuild for trivial changes.

Do not add a package when:

- It would have one consumer and no plausible second one in the near
  term.
- Its responsibility is a thin wrapper around something already in a
  neighbouring package.
- It exists to "look organized" rather than to enforce a boundary.

Premature packaging is harder to undo than premature inlining. A
package, once it exists, accretes consumers, configs, tests, and
release expectations.

---

## Naming and Scoping

Packages have names that are stable, scoped, and predictable.

- **Scope the org or product.** `@rabta-ai/foo`, `@rabta-ai/foo`. Never an
  unscoped name in a monorepo — the registry namespace is shared.
- **Name the responsibility, not the implementation.** `@rabta-ai/auth`,
  not `@rabta-ai/auth-with-passport-and-jwt`. The implementation may
  change; the responsibility should not.
- **Avoid generic suffixes.** `@rabta-ai/utils`, `@rabta-ai/common`,
  `@rabta-ai/shared` become trash drawers. Split by domain.
- **Match the directory name to the package name** (modulo the scope).
  `packages/auth/package.json` declares `@rabta-ai/auth`. No surprises.

In Rust: `crates/auth/Cargo.toml` declares the crate `auth` (or
`org-auth`). Same principle.

In C++ with CMake: `libs/auth/CMakeLists.txt` declares
`add_library(auth ...)` with public headers in `libs/auth/include/auth/`.

---

## Declaring Workspace Dependencies

Every monorepo tool has a way to say "this dependency resolves to
another package in the same workspace, not the public registry."

**pnpm / Yarn workspaces:**
```json
{
  "dependencies": {
    "@rabta-ai/auth": "workspace:*",
    "@prisma/ui": "workspace:*"
  }
}
```

**Cargo:**
```toml
[dependencies]
auth = { path = "../auth" }
# or in a workspace root:
auth = { workspace = true }
```

**Go workspaces:**
```
go.work declares the module replacements; modules import by path.
```

**CMake:**
```cmake
target_link_libraries(my_app PRIVATE auth)  # auth defined in another subdirectory
```

The rule: use the workspace syntax, not a version number or a relative
path that bypasses the resolver. The workspace protocol exists so the
tool knows it is in-tree and can rebuild only what changed.

---

## Shared Configs

Every monorepo accumulates these. They live at the root or in a
dedicated `configs/` package, and every other package extends them.

| Concern | Typical files | Discipline |
|---|---|---|
| TypeScript | `tsconfig.base.json` | Each package's `tsconfig.json` extends it. Local overrides are minimal and justified. |
| Lint | `eslint.config.js`, `biome.json` | One root config. Package-level overrides only for genuine divergence. |
| Format | `.prettierrc`, `.editorconfig` | One root config. No package-level forks. |
| CI | `.github/workflows/*.yml` | Shared workflow templates. Per-package CI is the exception, not the rule. |
| Test | `vitest.workspace.ts`, `jest.config.base.js` | One base, per-package overrides only when needed. |
| Build orchestrator | `turbo.json`, `nx.json` | Pipeline definitions live here; package scripts call into them. |

**Discipline:** if you are about to add a config file in a package
that duplicates 80% of the root, stop. Extend the root instead. Forks
of shared config are how monorepos rot.

---

## Build Graph Awareness

In a monorepo, the agent must think in graphs, not files.

- A change to a leaf package (a deeply-shared utility) affects every
  downstream package.
- A change to an app affects only that app's build artifact.
- Adding a new dependency edge changes what rebuilds on every future
  change.

Before making a change, ask:

```
1. What package am I editing?
2. What packages depend on this one, directly or transitively?
3. Is my change in the public surface (rebuilds consumers) or
   internal (rebuilds only this package)?
4. Will the test suite I run cover the affected graph, or only the
   package I touched?
```

Most build orchestrators (Turbo, Nx, Bazel, Cargo, CMake with proper
target dependencies) compute this automatically. Trust them, but
understand what they are doing.

---

## Scoped Commands

The agent must know how to run a command for one package, for the
affected graph, or for the whole repo. The commands differ per tool;
the categories do not.

**pnpm:**
```bash
pnpm --filter @rabta-ai/auth test            # single package
pnpm --filter ...@rabta-ai/auth test         # @rabta-ai/auth + everything that depends on it
pnpm --filter @rabta-ai/auth... test         # @rabta-ai/auth + everything it depends on
pnpm -r test                            # all packages
```

**Turbo:**
```bash
turbo run test --filter=@rabta-ai/auth       # single package
turbo run test --filter=...@rabta-ai/auth    # downstream
turbo run test --affected               # only packages affected vs base branch
turbo run test                          # all
```

**Nx:**
```bash
nx test auth                            # single project
nx affected -t test                     # affected by current branch
nx run-many -t test                     # all
```

**Cargo:**
```bash
cargo test -p auth                      # single crate
cargo test --workspace                  # all crates
```

**Bazel:**
```bash
bazel test //auth:all                   # single package
bazel test //...                        # all
```

The agent should default to **scoped** commands for fast iteration and
**affected** commands for verifying a change is complete. Whole-repo
commands belong in CI, not in the inner loop.

---

## Cross-Package Refactors

A rename or signature change that crosses package boundaries is a
monorepo-specific operation. The rules:

```
1. Identify every consumer. Use the build graph, not grep alone — a
   re-export can hide a usage.
2. Update the producer and all consumers in the same commit. Never
   leave a half-migrated state on `main`.
3. If the change is large, use a codemod. Hand-edits across many
   files invite typos and inconsistencies.
4. Run the affected test suite, not just the producer's tests.
5. If consumers cannot all be updated atomically (rare in a monorepo —
   common only when external consumers exist), introduce the new API,
   deprecate the old, migrate in a follow-up, remove later.
```

The agent does **not** silently update consumers it did not announce
it would touch. The commit summary lists every consumer changed.

---

## Versioning

A monorepo decides this once, and the agent reads which mode applies:

- **Single-version policy.** One version of React, one version of
  TypeScript, one version of every shared dependency, across the whole
  repo. Enforced by tooling (pnpm `overrides`, Cargo workspace
  dependencies, `peerDependencyRules`). The agent never adds a
  divergent version to a single package without surfacing it.

- **Per-package versions.** Each package versions independently. A
  release tool (Changesets, release-please, semantic-release) tracks
  what changed and bumps versions accordingly. The agent must create a
  changeset (or equivalent) for any change that affects a package's
  public surface.

- **Internal-only, unversioned.** Packages are private,
  `workspace:*`-linked, and never published. Versioning is for the
  apps as deployment artifacts, not for the libraries. The agent does
  not bump versions; CI does, on the app.

The `codebase-map` skill records which mode applies. The agent reads
it before changing anything that might trigger a release.

---

## Git Submodules

Some monorepos pull in external repos as git submodules — typically
when a UI library, a shared schema, or a vendored dependency is owned
elsewhere but consumed in-tree.

When a submodule is present:

```
1. The submodule path is declared in .gitmodules at the repo root.
2. The submodule is checked out at a specific commit, pinned by the
   parent repo. It is not a floating reference.
3. CI clones with `--recurse-submodules` or runs
   `git submodule update --init --recursive` after checkout.
4. The submodule's code is read-only from the parent repo's
   perspective. Changes to it go through the submodule's own
   repository, then the parent bumps the pinned commit.
```

**The agent does not edit files inside a submodule from the parent
repo.** If the submodule needs a change, surface it: the work happens
in the submodule's repo, in a separate commit, then the parent updates
the pin.

**The agent does not commit a submodule pin change without an
explicit human instruction.** A pin bump pulls in every commit between
the old and new pin — that is a release, not a tweak.

If the submodule provides a package consumed via the workspace (e.g.
the submodule contains an `apps/` and `packages/` tree of its own, and
its package is referenced as `workspace:*`), the workspace manifest
must list the submodule's path as a workspace member. The
`codebase-map` records this so the agent does not hallucinate the
linkage.

---

## Anti-Patterns to Refuse

- **The `utils` swamp.** A package named `utils`, `common`, `shared`,
  or `core` that grows without bound. Split by domain or reject the
  addition.
- **App depending on app.** Always indicates code that belongs in a
  package.
- **Cross-package internal imports.** Reaching into another package's
  `src/internal/*`. Reject.
- **Per-package config drift.** Each package with its own subtly
  different `tsconfig`, `eslint`, or `prettier`. Consolidate to a
  single base.
- **Editing inside a submodule from the parent repo.** Work goes in
  the submodule's repo. The parent updates the pin afterwards, on
  human instruction.
- **Floating workspace versions.** A package depending on `^1.2.3` of
  a sibling rather than `workspace:*`. Breaks atomicity guarantees.
- **Unscoped commands.** Running `pnpm test` from root for every tiny
  change. Wastes time; teaches the agent nothing about what is
  actually affected.
- **Silent cross-package edits.** Renaming an export and patching
  consumers without saying so in the summary.

---

## What the Agent Must Do

- Read the `codebase-map` skill before any monorepo change. It records
  the package manager, build orchestrator, versioning mode, workspace
  layout, and submodule list.
- For any new package: justify its responsibility, its layer, its
  consumers, and its dependency direction. Surface the proposal before
  creating it.
- For any change to a shared package: enumerate downstream consumers
  in the task summary and run the affected test suite.
- For any change involving a submodule: do not edit submodule files,
  do not bump the pin, and surface if either is needed.
- For any change that would introduce a divergent dependency version
  in a single-version repo: refuse and surface.

---

## When to Refuse and Pause

Refuse the change, and surface, when:

- A new package would have one consumer and no plausible second one.
- A rename would leave consumers half-migrated.
- A submodule file is being edited from the parent repo.
- A submodule pin would be bumped without explicit human instruction.
- A root config would be forked into a package-level override.
- A change would introduce a circular dependency, an app→app
  dependency, or a package→app dependency.

---

## The Monorepo Mantra

> **"One repo, many packages. Apps are leaves. Configs are extended. The graph rebuilds what changes. Submodules are pinned, not edited."**
