# Changelog

All notable changes to this project will be documented in this file.

---
## [v1.510] - df63d71
### Fixed
- Wait for cloud download to finish to retrieve hoster files on TorBox

## [v1.5.0] - 39e6993
### Added
- Feat: Allow to select file ranges as well as individual files
- Feat: Add file selection when downloading from mega folders
### Fixed
- Fix: Send mega folder to TorBox instead of file by file
- Fix: Downloads with multiple files on TorBox was only downloading the first file
- Fix: Improve findig if hoster is supported on real debrid

## [v1.4.0] - c3cc6d3
### Added
- Check if hosters are supported
- Don't show option that can't be used if certain API Keys are not set

## [v1.3.0] - 0eb8ee7
### Added
- Fetch MEGA files from folders using MEGA API directly (no longer depends on Premiumize)
### Fixed
- Retry logic for waiting on NZB files added to TorBox

## [v1.2.0] - e18ad99
### Added
- Support for container files: `.nzb` and `.torrent`
### Fixed
- Proper handling of MEGA single file links inside folders

## [v1.1.0] - 8969182
### Added
- Initial support for **TorBox**

## [v1.0.1] - 8acadfe
### Fixed
- Terminal color rendering during debrid option selection

## [v1.0.0] - 959d6d2
### Initial Release
- Universal downloader supporting Real-Debrid, AllDebrid, Premiumize, MEGA, and direct links.
