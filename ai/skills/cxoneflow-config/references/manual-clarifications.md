# Clarifications for Manual Contents

* Project grouping `repo-match` elements are not subject to SSRF.

* Avoid negative lookaheads in service `repo-match` elements when possible.  Using a trailing `.*` is permissible
  when the start anchor defines the SCM's URL.

* SCM service elements are evaluated in the order they are defined.  Evaluation stops when the event's 
  repository URL is a match to the `repo-match` regex.

## The `default-scan-engines` Element

* Examples in the manual may show YAML boolean values for engine configuration elements.  The engine configuration elements
  should be expressed as string values, even for boolean values (e.g. a `true` boolean value should yield a string value
  of "true").

* The configuration options for the engines have some examples in the manual.  The manual contents does not show examples
  of all possible parameters.

* A complete this of parameters is in the `/api/scans` documentation.  The root of the API documentation can be found
  [at this link](https://checkmarx.stoplight.io/docs/checkmarx-one-api-reference-guide).

* The links to the `/api/scans` documentation in the manual may have changed.  The user should be referred to the URL
  listed in the previous bullet if they need details about scan engine configuration parameters.
