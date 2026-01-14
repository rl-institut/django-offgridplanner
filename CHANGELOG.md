# Changelog

## [Unreleased]
### Added
- Display roads on map ([#138](https://github.com/rl-institut/django-offgridplanner/pull/138)).
- Allow user to duplicate projects ([#191](https://github.com/rl-institut/django-offgridplanner/pull/191))
- Offer example project to users with no projects ([#191](https://github.com/rl-institut/django-offgridplanner/pull/191))
- Enable anonymous login with demo account ([#192](https://github.com/rl-institut/django-offgridplanner/pull/192))

### Fixed
- Fix grid error on recalculation due to label column in nodes

### Changed
- Disable results button if no simulation has been conducted ([#193](https://github.com/rl-institut/django-offgridplanner/pull/193)).

## [v1.0.1] – 2026-01-06
### Added
- Display version in footer
- Add CHANGELOG

## [v1.0.0] – 2026-01-06
### Added
- First official versioned release.

### Notes
- This app replaces the formally existing [offgridplanner](https://github.com/rl-institut/tier_spatial_planning) developed in FastAPI.
- This release marks the start of structured versioning.
- Earlier changes were not formally tracked.
- This Django implementation already contains some new features, such as translation support, sortable projects and minor UX improvements.
