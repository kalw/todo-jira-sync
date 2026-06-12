# Changelog

## [1.1.2](https://github.com/kalw/todo-jira-sync/compare/v1.1.1...v1.1.2) (2026-06-12)


### Bug Fixes

* Inline publish to PyPI workflow steps ([0f6e1d5](https://github.com/kalw/todo-jira-sync/commit/0f6e1d55f2dbfbaf3575419f0d95fee7705d68d5))

## [1.1.1](https://github.com/kalw/todo-jira-sync/compare/v1.1.0...v1.1.1) (2026-05-23)


### Bug Fixes

* readme update ([dbee5c0](https://github.com/kalw/todo-jira-sync/commit/dbee5c0ee10808b81cff39e5c45d99c42d4aee13))

## [1.1.0](https://github.com/kalw/todo-jira-sync/compare/v1.0.7...v1.1.0) (2026-05-23)


### Features

* first commit ([75f8be7](https://github.com/kalw/todo-jira-sync/commit/75f8be782e641c6f0aa832515bf487ea9bfae5ca))
* first draft ([2771d94](https://github.com/kalw/todo-jira-sync/commit/2771d94cfb8378a6a1a0f0dda266ec5e5f4aa1db))


### Bug Fixes

* Add default-branch parameter to release workflow ([b31359e](https://github.com/kalw/todo-jira-sync/commit/b31359e424ad783115948a54a561e95daea63cc1))
* Add id-token permission to release workflow ([4fb7c3e](https://github.com/kalw/todo-jira-sync/commit/4fb7c3e1c474263f604067d0804fb62b48eefa9c))
* Add permissions for release-please in workflow ([ece88c5](https://github.com/kalw/todo-jira-sync/commit/ece88c57fc0d93f16181f010f48a94e0e88d08be))
* ci and tests ([b88d270](https://github.com/kalw/todo-jira-sync/commit/b88d270714337e4912e5d76f664bef61f54bfd25))
* ci and tests ([58819ea](https://github.com/kalw/todo-jira-sync/commit/58819ea5da2f4110177480955d2861079e3d5865))
* **ci:** add actions:write permission for workflow self-dispatch ([d2e5d10](https://github.com/kalw/todo-jira-sync/commit/d2e5d1075f09f880ca5bce8334af37c1c2089af9))
* **ci:** add workflow_dispatch + deployment envs to publish workflows ([de167a0](https://github.com/kalw/todo-jira-sync/commit/de167a09c407aad4d2f913ecf4f4218de1a9d1f8))
* **ci:** auto-release via PR auto-merge and fix PyPI OIDC via reusable workflow ([658b88c](https://github.com/kalw/todo-jira-sync/commit/658b88c62d04a9e654c93beca609592af11a72fd))
* **ci:** bypass release-please release creation with gh release create ([f481eae](https://github.com/kalw/todo-jira-sync/commit/f481eae67c13428911a9d19d90b5fba3f3429086))
* **ci:** clean up release.yaml permissions and invalid inputs ([c75d264](https://github.com/kalw/todo-jira-sync/commit/c75d2643955a250fa575f99c90639030f05e33af))
* **ci:** consolidate publish jobs into release.yaml to bypass GITHUB_TOKEN trigger restriction ([ee8239d](https://github.com/kalw/todo-jira-sync/commit/ee8239d85375cd3b6560faa62948092f63f48a30))
* **ci:** fix release YAML block scalar and remove invalid commitlint input ([de67394](https://github.com/kalw/todo-jira-sync/commit/de673944d4f9a098d9c43441393f85c531edfa33))
* **ci:** remove --target from gh release create to avoid scope error ([c364d97](https://github.com/kalw/todo-jira-sync/commit/c364d97264855699f6d0a7287e3d54ad22630aa0))
* **ci:** rename docker deployment environment from ghcr to docker ([cccc43d](https://github.com/kalw/todo-jira-sync/commit/cccc43dc4c465c406f2cd25578e876b30fe41b87))
* **ci:** self-dispatch release workflow after Release PR merge ([575666e](https://github.com/kalw/todo-jira-sync/commit/575666ef4c3fd35f2ed8107b76475f9b9256b099))
* **ci:** trigger publish workflows on release: published not push: tags ([a5feeab](https://github.com/kalw/todo-jira-sync/commit/a5feeab39769eccd31005e0d16143d99d5e69c93))
* Modify permissions in release.yaml workflow ([420e304](https://github.com/kalw/todo-jira-sync/commit/420e304444d50323f6bcc3dc77f191e27b0ca01d))
* resolve ruff lint errors and add CI autofix ([10a7255](https://github.com/kalw/todo-jira-sync/commit/10a7255b011591aea8c2cce13c57fc5b31ffbb46))

## [1.0.7](https://github.com/kalw/todo-jira-sync/compare/v1.0.6...v1.0.7) (2026-05-23)


### Bug Fixes

* **ci:** add actions:write permission for workflow self-dispatch ([d2e5d10](https://github.com/kalw/todo-jira-sync/commit/d2e5d1075f09f880ca5bce8334af37c1c2089af9))

## [1.0.6](https://github.com/kalw/todo-jira-sync/compare/v1.0.5...v1.0.6) (2026-05-23)


### Bug Fixes

* Add default-branch parameter to release workflow ([b31359e](https://github.com/kalw/todo-jira-sync/commit/b31359e424ad783115948a54a561e95daea63cc1))
* Add id-token permission to release workflow ([4fb7c3e](https://github.com/kalw/todo-jira-sync/commit/4fb7c3e1c474263f604067d0804fb62b48eefa9c))
* Add permissions for release-please in workflow ([ece88c5](https://github.com/kalw/todo-jira-sync/commit/ece88c57fc0d93f16181f010f48a94e0e88d08be))
* **ci:** bypass release-please release creation with gh release create ([f481eae](https://github.com/kalw/todo-jira-sync/commit/f481eae67c13428911a9d19d90b5fba3f3429086))
* **ci:** clean up release.yaml permissions and invalid inputs ([c75d264](https://github.com/kalw/todo-jira-sync/commit/c75d2643955a250fa575f99c90639030f05e33af))
* **ci:** remove --target from gh release create to avoid scope error ([c364d97](https://github.com/kalw/todo-jira-sync/commit/c364d97264855699f6d0a7287e3d54ad22630aa0))
* **ci:** self-dispatch release workflow after Release PR merge ([575666e](https://github.com/kalw/todo-jira-sync/commit/575666ef4c3fd35f2ed8107b76475f9b9256b099))
* Modify permissions in release.yaml workflow ([420e304](https://github.com/kalw/todo-jira-sync/commit/420e304444d50323f6bcc3dc77f191e27b0ca01d))

## [1.0.5](https://github.com/kalw/todo-jira-sync/compare/v1.0.4...v1.0.5) (2026-05-22)


### Bug Fixes

* **ci:** auto-release via PR auto-merge and fix PyPI OIDC via reusable workflow ([658b88c](https://github.com/kalw/todo-jira-sync/commit/658b88c62d04a9e654c93beca609592af11a72fd))

## [1.0.4](https://github.com/kalw/todo-jira-sync/compare/v1.0.3...v1.0.4) (2026-05-21)


### Bug Fixes

* **ci:** consolidate publish jobs into release.yaml to bypass GITHUB_TOKEN trigger restriction ([ee8239d](https://github.com/kalw/todo-jira-sync/commit/ee8239d85375cd3b6560faa62948092f63f48a30))

## [1.0.3](https://github.com/kalw/todo-jira-sync/compare/v1.0.2...v1.0.3) (2026-05-21)


### Bug Fixes

* **ci:** trigger publish workflows on release: published not push: tags ([a5feeab](https://github.com/kalw/todo-jira-sync/commit/a5feeab39769eccd31005e0d16143d99d5e69c93))

## [1.0.2](https://github.com/kalw/todo-jira-sync/compare/v1.0.1...v1.0.2) (2026-05-21)


### Bug Fixes

* **ci:** add workflow_dispatch + deployment envs to publish workflows ([de167a0](https://github.com/kalw/todo-jira-sync/commit/de167a09c407aad4d2f913ecf4f4218de1a9d1f8))
* **ci:** rename docker deployment environment from ghcr to docker ([cccc43d](https://github.com/kalw/todo-jira-sync/commit/cccc43dc4c465c406f2cd25578e876b30fe41b87))

## [1.0.1](https://github.com/kalw/todo-jira-sync/compare/v1.0.0...v1.0.1) (2026-05-21)


### Bug Fixes

* **ci:** fix release YAML block scalar and remove invalid commitlint input ([de67394](https://github.com/kalw/todo-jira-sync/commit/de673944d4f9a098d9c43441393f85c531edfa33))
