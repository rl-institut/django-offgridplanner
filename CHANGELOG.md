# Changelog

## [Unreleased]
### Fixed
- Do not overwrite poles when saving updated consumer data ([#263](https://github.com/rl-institut/django-offgridplanner/pull/263))
- Display error message when clicking next without consumers ([#266](https://github.com/rl-institut/django-offgridplanner/pull/266))
- Fix coordinates to xy function using degrees instead of radians ([#266](https://github.com/rl-institut/django-offgridplanner/pull/266))
- Fix grid layout image on PDF export ([#267](https://github.com/rl-institut/django-offgridplanner/pull/267))

### Dev
- Add test suite covering optimization, helpers, models, and views ([#266](https://github.com/rl-institut/django-offgridplanner/pull/266))
- Refactor javascript modules and remove dead code ([#267](https://github.com/rl-institut/django-offgridplanner/pull/267))

## [v1.4.0] – 2026-05-26
### Added
- Display uploaded demand data if provided ([#252](https://github.com/rl-institut/django-offgridplanner/pull/252))

### Changed
- Add warning before deleting all consumers with trash bin tool ([#260](https://github.com/rl-institut/django-offgridplanner/pull/260))

### Fixed
- Fix broken example project for new users ([#259](https://github.com/rl-institut/django-offgridplanner/pull/259))
- Fix timezone offset for solar potential timeseries ([#261](https://github.com/rl-institut/django-offgridplanner/pull/251))
- Fix error simulating example project without clicking through steps ([#262](https://github.com/rl-institut/django-offgridplanner/pull/262))
- Fix delete button for multiple consumer selection ([#260](https://github.com/rl-institut/django-offgridplanner/pull/260))

## [v1.3.0] – 2026-05-04
### Added
- Allow the user to choose between different currencies ([#251](https://github.com/rl-institut/django-offgridplanner/pull/251))

### Fixed
- Fix results processing if all consumers are assigned to solar home systems ([#250](https://github.com/rl-institut/django-offgridplanner/pull/250))
- Fix Overpass API returning error on consumer selection ([#255](https://github.com/rl-institut/django-offgridplanner/pull/255))

## [v1.2.0] – 2026-04-08
### Added
- In Consumer Selection, users can now use Shift+Click to select and edit multiple consumers at the same time ([#212](https://github.com/rl-institut/django-offgridplanner/pull/212))

### Changed
- Display info message if imported consumers are not within the selected country ([#219](https://github.com/rl-institut/django-offgridplanner/pull/219))

### Fixed
- Display consumer import error messages to user ([#235](https://github.com/rl-institut/django-offgridplanner/pull/235))

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
