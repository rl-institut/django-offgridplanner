# Changelog

## [Unreleased]
### Added
- In Consumer Selection, Users can use shift+click to select multiple consumers at the same time and change type, detail, load and shs-options for all of them at the same time([#212](https://github.com/rl-institut/django-offgridplanner/pull/212))

## [v1.1.7] – 2026-03-25
### Changed
- User now receives an info message if consumers are not within the selected country([#219](https://github.com/rl-institut/django-offgridplanner/pull/219))

## [v1.1.6] – 2026-03-23
### Fixed
- Fix blocked tiles on OpenStreetMap views ([#232](https://github.com/rl-institut/django-offgridplanner/pull/232))
- Fix error on demand export with empty demand tier share ([#233](https://github.com/rl-institut/django-offgridplanner/pull/233))
- Fix error on grid results processing for large communities ([#231](https://github.com/rl-institut/django-offgridplanner/pull/231))

## [v1.1.5] – 2026-03-19
### Fixed
- Export demand with currently selected share values instead of previously saved values ([#229](https://github.com/rl-institut/django-offgridplanner/pull/229)) ([#230](https://github.com/rl-institut/django-offgridplanner/pull/230))

## [v1.1.4] – 2026-03-17
### Changed
- Display message to users about backend migration ([#221](https://github.com/rl-institut/django-offgridplanner/pull/221))
- Update navbar logo ([#221](https://github.com/rl-institut/django-offgridplanner/pull/221))

### Fixed
- Fix delete project modal layout ([#221](https://github.com/rl-institut/django-offgridplanner/pull/221))
- Fix login page bugs ([#221](https://github.com/rl-institut/django-offgridplanner/pull/221))

## [v1.1.3] – 2026-03-16
### Changed
- Remove landing page (send directly to login) ([#223](https://github.com/rl-institut/django-offgridplanner/pull/223))

### Fixed
- Fix dynamic plot updates on demand estimation, shares reset and calibration option issues ([#195](https://github.com/rl-institut/django-offgridplanner/pull/195))
- Fix upload custom demand option being enabled by default ([#222](https://github.com/rl-institut/django-offgridplanner/pull/222))

## [v1.1.2] – 2026-03-03
### Added
- Automatically log out users after 1 hour of idle time ([#216](https://github.com/rl-institut/django-offgridplanner/pull/216))

### Changed
- If results for the simulation already exist for the project, calculation is skipped ([#215](https://github.com/rl-institut/django-offgridplanner/pull/215))

### Fixed
- Fix recalculate button on results page ([#215](https://github.com/rl-institut/django-offgridplanner/pull/215))

## [v1.1.1] – 2026-02-25
### Changed
- Do not display options fields on first steps ([#210](https://github.com/rl-institut/django-offgridplanner/pull/210))
- Add captcha for demo users instead of IP rate limit ([#203](https://github.com/rl-institut/django-offgridplanner/pull/203))
- Do not fetch roads data on map to avoid overloading the OpenStreetMap API ([#206](https://github.com/rl-institut/django-offgridplanner/pull/206))

### Fixed
- Fix uploaded demand being used instead of computed demand if provided ([#210](https://github.com/rl-institut/django-offgridplanner/pull/210))
- Fix percentage fields scaling on project import / duplication ([#205](https://github.com/rl-institut/django-offgridplanner/pull/205))
- Display error message if OpenStreetMap building data loading fails ([#206](https://github.com/rl-institut/django-offgridplanner/pull/206))

## [v1.1.0] – 2026-02-02
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
