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

## The `<scm moniker>.feedback.pull-request.adoe-pr-opts` Element

The `<scm moniker>.feedback.pull-request.adoe-pr-opts` is listed as required when
`<scm moniker>.feedback.pull-request.use-policies` is set to `true`.  The
requirement for `<scm moniker>.feedback.pull-request.adoe-pr-opts` is only when the
`<scm moniker>` is `adoe`.  For other SCM monikers, `adoe-pr-opts` is ignored and
thus not required.

## Feedback

CxOneFlow supports feedback upon a push to a protected branch or when a pull-request is opened that targets a protected branch.

### `pull-request` Feedback

Feedback for `pull-requests` is typically emitted in comment threads that are associated with the pull-request.  Some SCMs may
vary how this is presented to the user and is documented in the CxOneFlow manual.

An integration with policy checks in CxOne is available for some SCMs.  This is not to be confused with policy configurations
in the SCM.  The CxOne policy checks are used to evaluate scan results and, using SCM-defined policies, optionally block
the merge of the pull-request of a policy violation is detected when CxOne evaluates the scan results.

### Protected Branch Feedback

Feedback for protected branch updates typically means that vulnerabilities found during a scan are used to open tickets in a bug tracker
such as Jira.  CxOneFlow does not integrate with any bug trackers for this purpose.  CxOneFlow does have the ability to optionally push a list
of vulnerabilities found in the scan in the form of a Sarif log.  The push delivery methods are found described in the manual.  The
intention is that the receiver of the Sarif log will integrate with the bug tracker.

This should not be confused with CxOne feedback apps that can be configured to update bug trackers directly from CxOne.  In this case, the
operation is performed entirely by CxOne.

Sarif feedback by CxOneFlow and feedback apps in CxOne have no dependencies on each other.  They are both optional and do not conflict in
operation.
