# CxOne Flow

If you are familiar with [CxFlow](https://github.com/checkmarx-ltd/cx-flow) for Checkmarx SAST, you will be familiar with the role of CxOneFlow.  

For those that have not used CxFlow with Checkmarx SAST, CxOneFlow is a scan orchestrator that executes multiple source code analysis scans.  It is driven by web hook events coming from a source control system.

## CxOneFlow vs CxFlow

CxOneFlow is not intended to ever reach feature parity with CxFlow.  Many CxFlow features will not apply to Checkmarx One scanning.  CxOneFlow currently orchestrates scans via webhook events for push and pull-requests involving protected branches.  CxOneFlow
itself does not create results in feedback applications.

# Quickstart and Documentation

Please refer to the [Releases](https://github.com/checkmarx-ts/cxone-flow/releases) where you will find the following downloadable artifacts:

* An AI skill that will answer questions about how CxOneFlow works and assist in configuration.
* A complete PDF manual that covers all topics in a human-readable, structured format.

Using AI to guide setup and configuration will be the most rapid method of starting a working CxOneFlow server.

# Feature Summary

* Supported SCMs
    * BitBucket Data Center[^1] and Cloud.
    * Azure DevOps Enterprise Self-Hosted and Cloud.
      * New extended token lengths supported.
      * Service Principal authentication supported with Entra.
    * GitHub Enterprise Self-Hosted and Cloud.
      * GitHub app authentication supported.
    * GitLab Self-Hosted and Cloud.
* Scans are invoked by Push events when code is pushed to protected branches.
  * A SARIF log of the completed scan can be optionally pushed to an HTTPS or AQMP endpoint. See [cxone-sarif](https://github.com/checkmarx-ts/cxone-sarif).
* Scans are invoked on Pull-Requests that target a protected branch.
* Scan results for Pull-Request scans are summarized in a pull-request comment.
* Pull-Request state is reflected in scan tags as the pull request is under review.
* Pull-Request merges can be blocked[^2] in these scenarios:
  * Waiting for scan to complete (via "required checks").
  * Break-build Checkmarx One policy violations.
* Scans are tagged with the Git commit hash.
* Pre-scan execution of SCA Resolver and/or shell script.

[^1]: Atlassian has announced EOL for BitBucket Data Center.  Further development of features for BitBucket
    Data Center is no longer possible.  New releases are no longer tested against BitBucket Data Center.
[^2]: Not currently supported for GitLab.
