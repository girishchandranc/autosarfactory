# ChangeLog
All notable changes to this project will be documented in this file.

## [0.1.0]() - 2021-01-05
First release of the AutosarModeller. Please refer README for more information.

## [0.1.1]() - 2021-01-11
Provision to get the objects which refer a particular object.

## [0.2.0]() - 2021-01-16
### Added
New UI to visualize the Autosar model.
### Changed
- New API `get_children()` to get child elements of a particular autosar element
- New API `get_property_values()` to get values of all attributes of anautosar element.

## [0.2.1]() - 2021-01-24
Support for processing the integer attributes configured as hex, binary or octal values in arxml file.

## [0.2.2]() - 2021-01-28
- Small UI improvement - posibility to select search type
- Implemented multiple type searches (by short name, by Autosar type and by regular expression on name)
- Added menu bar - implemented theme selection at runtime

## [0.2.3]() - 2021-02-04
- Small UI improvement - possibility to copy `name` and `path` of a node from the autosar explorer to clipboard.

## [0.3.0]() - 2023-05-19
- Fixed issue with elements not being added to set when the element has no short name(eg: DATA-TYPE-MAP)
- Added splittable support
- Now, `autosarfactory` can read list of folders and can deep search for the arxml files.

## [0.3.1]() - 2023-07-11
- Check if the parent node can have children before getting or adding children

## [0.4.0]() - 2023-11-17
- ARXML elements are now added respecting the sequence order specified by Autosar schema.
- Introduced new API `get_all_instances` to get all the instances of a particular node based on the given class type.
- New feature to export AR-Package or PackageableElement(ApplicationSwComponentType, ISignal etc) to a file.

## [0.4.1]() - 2024-02-28
- Added a function to get the referenced value as string. This will be useful when you want to get the path of an referenced node which doesn't exist in the model.

## [0.5.0]() - 2024-05-24
- Support for AUTOSAR R23-11
- Added type hint for the method arguments and return types. This will assist users to efficiently write scripts(provided an editor with content assistance is used).

## [0.5.1]() - 2024-12-09
- Fixed issues with reading contents of CompuMethod
- Fixed issues with type hint for the setter method accepting enumeration types
- Minor UI updates
