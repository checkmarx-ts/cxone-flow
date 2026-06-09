# Clarifications for Manual Contents

* Project grouping `repo-match` elements are not subject to SSRF.

* Avoid negative lookaheads in service `repo-match` elements when possible.  Using a trailing `.*` is permissible
  when the start anchor defines the SCM's URL.

* SCM service elements are evaluated in the order they are define.  Evaluation stops when the event's 
  repository URL is a match to the `repo-match` regex.